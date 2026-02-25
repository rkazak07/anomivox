"""
Anomivox ClawBot — DB Skills Engine
Veritabanı sorgulama, analiz ve otonom müdahale becerileri.

Her skill fonksiyonu doğrudan PostgreSQL'e bağlanarak
gerçek zamanlı veri döndürür.
"""

import os
import sys
import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(
    format="%(asctime)s [ClawBot] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("anomivox.clawbot.skills")


# ── DB Bağlantısı ──────────────────────────────────────────

def _get_db_config(db_id: str = None):
    """Multi-DB: ID ile veya default bağlantı ayarlarını al."""
    try:
        from configs.clawbot_config import get_db_connection_by_id
        conn = get_db_connection_by_id(db_id)
        if conn:
            return {
                "host": conn["host"],
                "port": conn.get("port", 5432),
                "user": conn["user"],
                "password": conn["password"],
                "dbname": conn["dbname"],
            }
    except ImportError:
        pass

    # Fallback: eski tek-DB config
    try:
        from configs.clawbot_config import (
            CLAWBOT_PG_HOST, CLAWBOT_PG_PORT,
            CLAWBOT_PG_USER, CLAWBOT_PG_PASSWORD, CLAWBOT_PG_DB,
        )
        return {
            "host": CLAWBOT_PG_HOST,
            "port": CLAWBOT_PG_PORT,
            "user": CLAWBOT_PG_USER,
            "password": CLAWBOT_PG_PASSWORD,
            "dbname": CLAWBOT_PG_DB,
        }
    except ImportError:
        try:
            from configs.diagnose_config import POSTGRESQL_CONFIG
            return POSTGRESQL_CONFIG
        except ImportError:
            logger.error("DB config bulunamadı!")
            return None


def _get_conn(db_id: str = None):
    """PostgreSQL bağlantısı oluştur (multi-DB desteği)."""
    cfg = _get_db_config(db_id)
    if not cfg:
        raise ConnectionError("PostgreSQL config bulunamadı")
    return psycopg2.connect(
        host=cfg["host"],
        port=cfg.get("port", 5432),
        user=cfg["user"],
        password=cfg["password"],
        dbname=cfg["dbname"],
        connect_timeout=10,
    )


def _format_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SKILL 1 — Genel Durum (Overview)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def skill_db_overview(db_id: str = None) -> dict:
    """
    Veritabanı genel özeti:
    - Versiyon, uptime, bağlantı sayısı, boyut, DB listesi
    """
    conn = _get_conn(db_id)
    cur = conn.cursor()
    result = {}

    try:
        # Versiyon
        cur.execute("SELECT version();")
        result["version"] = cur.fetchone()[0].split(",")[0]

        # Uptime
        cur.execute("SELECT current_timestamp - pg_postmaster_start_time();")
        uptime = cur.fetchone()[0]
        result["uptime"] = str(uptime).split(".")[0]

        # Bağlantılar
        cur.execute("SELECT count(*) FROM pg_stat_activity;")
        active = cur.fetchone()[0]
        cur.execute("SHOW max_connections;")
        max_conn = int(cur.fetchone()[0])
        result["connections"] = {"active": active, "max": max_conn, "usage_pct": round(active / max_conn * 100, 1)}

        # Tüm DB'ler
        cur.execute("""
            SELECT datname, pg_database_size(datname)
            FROM pg_database
            WHERE datistemplate = false
            ORDER BY pg_database_size(datname) DESC;
        """)
        dbs = []
        total_size = 0
        for name, size in cur.fetchall():
            dbs.append({"name": name, "size": _format_bytes(size), "size_bytes": size})
            total_size += size
        result["databases"] = dbs
        result["total_size"] = _format_bytes(total_size)
        result["database_count"] = len(dbs)

        # Şu anki DB boyutu
        cfg = _get_db_config(db_id)
        cur.execute(f"SELECT pg_size_pretty(pg_database_size('{cfg['dbname']}'));") 
        result["current_db_size"] = cur.fetchone()[0]

    finally:
        cur.close()
        conn.close()

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SKILL 2 — Sağlık Raporu (Health)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def skill_health_check(db_id: str = None) -> dict:
    """
    Kapsamlı sağlık raporu:
    - Cache hit ratio, commit ratio, dead tuples, index usage,
    - Bağlantı durumları, long-running queries, replikasyon
    """
    conn = _get_conn(db_id)
    cur = conn.cursor()
    report = {"status": "healthy", "issues": [], "metrics": {}}

    try:
        # 1. Cache Hit Ratio
        cur.execute("""
            SELECT round(
                sum(blks_hit) * 100.0 / NULLIF(sum(blks_hit) + sum(blks_read), 0), 2
            ) FROM pg_stat_database;
        """)
        cache_hit = float(cur.fetchone()[0] or 0)
        report["metrics"]["cache_hit_ratio"] = cache_hit
        if cache_hit < 85:
            report["issues"].append({"severity": "critical", "msg": f"Cache hit ratio çok düşük: %{cache_hit}"})
            report["status"] = "critical"
        elif cache_hit < 95:
            report["issues"].append({"severity": "warning", "msg": f"Cache hit ratio düşük: %{cache_hit}"})
            if report["status"] == "healthy":
                report["status"] = "warning"

        # 2. Commit Ratio
        cur.execute("""
            SELECT round(
                sum(xact_commit) * 100.0 / NULLIF(sum(xact_commit) + sum(xact_rollback), 0), 2
            ) FROM pg_stat_database;
        """)
        commit_ratio = float(cur.fetchone()[0] or 0)
        report["metrics"]["commit_ratio"] = commit_ratio
        if commit_ratio < 90:
            report["issues"].append({"severity": "warning", "msg": f"Commit ratio düşük: %{commit_ratio}"})
            if report["status"] == "healthy":
                report["status"] = "warning"

        # 3. Bağlantı kullanımı
        cur.execute("SELECT count(*) FROM pg_stat_activity;")
        active = cur.fetchone()[0]
        cur.execute("SHOW max_connections;")
        max_c = int(cur.fetchone()[0])
        usage = round(active / max_c * 100, 1)
        report["metrics"]["connection_usage_pct"] = usage
        if usage > 80:
            report["issues"].append({"severity": "critical", "msg": f"Bağlantı dolmak üzere: {active}/{max_c} (%{usage})"})
            report["status"] = "critical"

        # 4. Dead Tuples
        cur.execute("""
            SELECT schemaname || '.' || relname, n_dead_tup, n_live_tup,
                   round(n_dead_tup * 100.0 / NULLIF(n_live_tup + n_dead_tup, 0), 1)
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 1000
            ORDER BY n_dead_tup DESC LIMIT 5;
        """)
        dead_tables = []
        for tbl, dead, live, pct in cur.fetchall():
            dead_tables.append({"table": tbl, "dead_tuples": dead, "live_tuples": live, "dead_pct": float(pct or 0)})
            if dead > 10000:
                report["issues"].append({"severity": "warning", "msg": f"{tbl}: {dead:,} dead tuple — VACUUM önerilir"})
                if report["status"] == "healthy":
                    report["status"] = "warning"
        report["metrics"]["dead_tuple_tables"] = dead_tables

        # 5. Long-running queries (>30s)
        cur.execute("""
            SELECT count(*) FROM pg_stat_activity
            WHERE state = 'active'
            AND query NOT ILIKE '%pg_stat%'
            AND now() - query_start > interval '30 seconds';
        """)
        long_running = cur.fetchone()[0]
        report["metrics"]["long_running_queries"] = long_running
        if long_running > 0:
            report["issues"].append({"severity": "warning", "msg": f"30s+ çalışan {long_running} sorgu var"})
            if report["status"] == "healthy":
                report["status"] = "warning"

        # 6. Lock bekleyen sorgular
        cur.execute("SELECT count(*) FROM pg_locks WHERE NOT granted;")
        waiting_locks = cur.fetchone()[0]
        report["metrics"]["waiting_locks"] = waiting_locks
        if waiting_locks > 0:
            report["issues"].append({"severity": "warning", "msg": f"{waiting_locks} sorgu kilit bekliyor"})
            if report["status"] == "healthy":
                report["status"] = "warning"

        # 7. Bağlantı durumları
        cur.execute("""
            SELECT state, count(*)
            FROM pg_stat_activity
            GROUP BY state ORDER BY count(*) DESC;
        """)
        conn_states = {}
        for state, cnt in cur.fetchall():
            conn_states[state or "null"] = cnt
        report["metrics"]["connection_states"] = conn_states

    finally:
        cur.close()
        conn.close()

    return report


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SKILL 3 — Yavaş Sorgular
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def skill_slow_queries(threshold_ms: float = 1000, limit: int = 10, db_id: str = None) -> dict:
    """
    pg_stat_statements'tan yavaş sorguları getir.
    threshold_ms: Bu ms'den yavaş olanları filtreler
    """
    conn = _get_conn(db_id)
    cur = conn.cursor()
    result = {"queries": [], "extension_available": True}

    try:
        cur.execute("""
            SELECT query, calls,
                   round(mean_exec_time::numeric, 2) as avg_ms,
                   round(total_exec_time::numeric, 2) as total_ms,
                   rows
            FROM pg_stat_statements
            WHERE query NOT LIKE '%pg_stat%'
            AND mean_exec_time > %s
            ORDER BY mean_exec_time DESC
            LIMIT %s;
        """, (threshold_ms, limit))

        for query, calls, avg_ms, total_ms, row_count in cur.fetchall():
            result["queries"].append({
                "query": query[:300],
                "calls": calls,
                "avg_ms": float(avg_ms),
                "total_ms": float(total_ms),
                "rows": row_count,
            })

    except Exception as e:
        if "pg_stat_statements" in str(e):
            result["extension_available"] = False
            result["error"] = "pg_stat_statements eklentisi yüklü değil"
        else:
            raise
    finally:
        cur.close()
        conn.close()

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SKILL 4 — Aktif Sorgular
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def skill_active_queries(db_id: str = None) -> dict:
    """Şu an çalışan aktif sorguları listele."""
    conn = _get_conn(db_id)
    cur = conn.cursor()
    result = {"queries": []}

    try:
        cur.execute("""
            SELECT pid, usename, datname,
                   extract(epoch from now() - query_start)::numeric as duration_sec,
                   state, left(query, 200) as query
            FROM pg_stat_activity
            WHERE state = 'active'
            AND pid != pg_backend_pid()
            AND query NOT ILIKE '%pg_stat%'
            ORDER BY query_start ASC
            LIMIT 20;
        """)

        for pid, user, db, dur, state, query in cur.fetchall():
            result["queries"].append({
                "pid": pid,
                "user": user,
                "database": db,
                "duration": _format_duration(float(dur or 0)),
                "duration_sec": float(dur or 0),
                "query": query,
            })

    finally:
        cur.close()
        conn.close()

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SKILL 5 — Kilitler
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def skill_locks(db_id: str = None) -> dict:
    """Kilit bekleyen sorguları göster."""
    conn = _get_conn(db_id)
    cur = conn.cursor()
    result = {"locks": []}

    try:
        cur.execute("""
            SELECT blocked.pid AS blocked_pid,
                   blocked.usename AS blocked_user,
                   left(blocked_activity.query, 150) AS blocked_query,
                   blocking.pid AS blocking_pid,
                   blocking.usename AS blocking_user,
                   left(blocking_activity.query, 150) AS blocking_query,
                   extract(epoch from now() - blocked_activity.query_start)::numeric as wait_sec
            FROM pg_catalog.pg_locks AS blocked
            JOIN pg_catalog.pg_stat_activity AS blocked_activity ON blocked.pid = blocked_activity.pid
            JOIN pg_catalog.pg_locks AS blocking
                ON blocked.locktype = blocking.locktype
                AND blocked.database IS NOT DISTINCT FROM blocking.database
                AND blocked.relation IS NOT DISTINCT FROM blocking.relation
                AND blocked.page IS NOT DISTINCT FROM blocking.page
                AND blocked.tuple IS NOT DISTINCT FROM blocking.tuple
                AND blocked.virtualxid IS NOT DISTINCT FROM blocking.virtualxid
                AND blocked.transactionid IS NOT DISTINCT FROM blocking.transactionid
                AND blocked.classid IS NOT DISTINCT FROM blocking.classid
                AND blocked.objid IS NOT DISTINCT FROM blocking.objid
                AND blocked.objsubid IS NOT DISTINCT FROM blocking.objsubid
                AND blocked.pid != blocking.pid
            JOIN pg_catalog.pg_stat_activity AS blocking_activity ON blocking.pid = blocking_activity.pid
            WHERE NOT blocked.granted
            LIMIT 10;
        """)

        for bpid, buser, bquery, kpid, kuser, kquery, wait in cur.fetchall():
            result["locks"].append({
                "blocked_pid": bpid,
                "blocked_user": buser,
                "blocked_query": bquery,
                "blocking_pid": kpid,
                "blocking_user": kuser,
                "blocking_query": kquery,
                "wait_duration": _format_duration(float(wait or 0)),
            })

    finally:
        cur.close()
        conn.close()

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SKILL 6 — Tablo İstatistikleri
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def skill_table_stats(limit: int = 15, db_id: str = None) -> dict:
    """En büyük tabloların boyut, satır, dead tuple, son VACUUM bilgisi."""
    conn = _get_conn(db_id)
    cur = conn.cursor()
    result = {"tables": []}

    try:
        cur.execute("""
            SELECT schemaname || '.' || relname as table_name,
                   pg_total_relation_size(relid) as total_bytes,
                   pg_size_pretty(pg_total_relation_size(relid)) as total_size,
                   n_live_tup, n_dead_tup,
                   last_vacuum, last_autovacuum,
                   seq_scan, idx_scan,
                   round(idx_scan * 100.0 / NULLIF(seq_scan + idx_scan, 0), 1) as idx_pct
            FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(relid) DESC
            LIMIT %s;
        """, (limit,))

        for tbl, total_bytes, total_size, live, dead, vac, auto_vac, seq, idx, idx_pct in cur.fetchall():
            result["tables"].append({
                "name": tbl,
                "size": total_size,
                "size_bytes": total_bytes,
                "live_rows": live,
                "dead_rows": dead,
                "last_vacuum": str(vac or auto_vac or "never")[:16],
                "seq_scan": seq,
                "idx_scan": idx,
                "index_usage_pct": float(idx_pct) if idx_pct else 0,
            })

    finally:
        cur.close()
        conn.close()

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SKILL 7 — Index Önerisi
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def skill_index_recommendations(db_id: str = None) -> dict:
    """
    Sequential scan ağırlıklı tabloları analiz ederek
    index önerisi üret.
    """
    conn = _get_conn(db_id)
    cur = conn.cursor()
    result = {"recommendations": [], "analysis": {}}

    try:
        # Sequential scan ağırlıklı tablolar
        cur.execute("""
            SELECT schemaname || '.' || relname as table_name,
                   seq_scan, idx_scan,
                   seq_tup_read, idx_tup_fetch,
                   n_live_tup,
                   pg_size_pretty(pg_total_relation_size(relid))
            FROM pg_stat_user_tables
            WHERE seq_scan > 100
            AND n_live_tup > 1000
            AND (idx_scan IS NULL OR seq_scan > idx_scan * 2)
            ORDER BY seq_tup_read DESC
            LIMIT 10;
        """)

        seq_heavy = cur.fetchall()
        result["analysis"]["seq_heavy_tables"] = len(seq_heavy)

        for tbl, seq, idx, seq_read, idx_fetch, live, size in seq_heavy:
            idx_ratio = round(idx / (seq + idx) * 100, 1) if (seq + idx) > 0 else 0

            rec = {
                "table": tbl,
                "seq_scan": seq,
                "idx_scan": idx or 0,
                "index_usage_pct": idx_ratio,
                "rows": live,
                "size": size,
                "severity": "high" if idx_ratio < 30 else ("medium" if idx_ratio < 60 else "low"),
                "suggestion": "",
            }

            if idx_ratio < 30:
                rec["suggestion"] = f"⚠️ {tbl} tablosu %{idx_ratio} index kullanıyor. WHERE/JOIN sütunlarına composite index ekleyin."
            elif idx_ratio < 60:
                rec["suggestion"] = f"💡 {tbl} tablosunda index kullanımı geliştirilebilir (%{idx_ratio})."

            result["recommendations"].append(rec)

        # Kullanılmayan indexler
        cur.execute("""
            SELECT schemaname || '.' || relname as table_name,
                   indexrelname as index_name,
                   pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                   idx_scan
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0
            AND schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY pg_relation_size(indexrelid) DESC
            LIMIT 5;
        """)

        unused = []
        for tbl, idx_name, size, scans in cur.fetchall():
            unused.append({
                "table": tbl,
                "index": idx_name,
                "size": size,
                "scans": scans,
            })
        result["analysis"]["unused_indexes"] = unused

    finally:
        cur.close()
        conn.close()

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SKILL 8 — Otonom Müdahale (DevOps Actions)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def skill_vacuum_table(table_name: str, db_id: str = None) -> dict:
    """Belirtilen tabloda VACUUM ANALYZE çalıştır."""
    conn = _get_conn(db_id)
    conn.autocommit = True
    cur = conn.cursor()
    result = {"success": False}

    try:
        # Önce tabloyu doğrula
        cur.execute("""
            SELECT schemaname || '.' || relname, n_dead_tup
            FROM pg_stat_user_tables
            WHERE schemaname || '.' || relname = %s
            OR relname = %s;
        """, (table_name, table_name))
        row = cur.fetchone()
        if not row:
            result["error"] = f"Tablo bulunamadı: {table_name}"
            return result

        actual_name = row[0]
        dead_before = row[1]

        cur.execute(f"VACUUM ANALYZE {actual_name};")

        # Sonucu doğrula
        cur.execute("""
            SELECT n_dead_tup FROM pg_stat_user_tables
            WHERE schemaname || '.' || relname = %s;
        """, (actual_name,))
        dead_after = cur.fetchone()[0]

        result["success"] = True
        result["table"] = actual_name
        result["dead_before"] = dead_before
        result["dead_after"] = dead_after
        result["cleaned"] = dead_before - dead_after

    except Exception as e:
        result["error"] = str(e)[:300]
    finally:
        cur.close()
        conn.close()

    return result


def skill_reindex_table(table_name: str, db_id: str = None) -> dict:
    """Belirtilen tabloyu reindex et."""
    conn = _get_conn(db_id)
    conn.autocommit = True
    cur = conn.cursor()
    result = {"success": False}

    try:
        cur.execute("""
            SELECT schemaname || '.' || relname
            FROM pg_stat_user_tables
            WHERE schemaname || '.' || relname = %s
            OR relname = %s;
        """, (table_name, table_name))
        row = cur.fetchone()
        if not row:
            result["error"] = f"Tablo bulunamadı: {table_name}"
            return result

        actual_name = row[0]
        cur.execute(f"REINDEX TABLE {actual_name};")
        result["success"] = True
        result["table"] = actual_name

    except Exception as e:
        result["error"] = str(e)[:300]
    finally:
        cur.close()
        conn.close()

    return result


def skill_kill_query(pid: int, force: bool = False, db_id: str = None) -> dict:
    """
    Belirtilen PID'li sorguyu durdur.
    force=False → pg_cancel_backend (nazik)
    force=True → pg_terminate_backend (zorla)
    """
    conn = _get_conn(db_id)
    cur = conn.cursor()
    result = {"success": False}

    try:
        # Önce PID'nin var olduğunu doğrula
        cur.execute("SELECT usename, left(query, 200), state FROM pg_stat_activity WHERE pid = %s;", (pid,))
        row = cur.fetchone()
        if not row:
            result["error"] = f"PID {pid} bulunamadı veya zaten kapanmış"
            return result

        result["target"] = {"user": row[0], "query": row[1], "state": row[2]}

        if force:
            cur.execute("SELECT pg_terminate_backend(%s);", (pid,))
        else:
            cur.execute("SELECT pg_cancel_backend(%s);", (pid,))

        success = cur.fetchone()[0]
        result["success"] = success
        result["action"] = "terminate" if force else "cancel"

    except Exception as e:
        result["error"] = str(e)[:300]
    finally:
        cur.close()
        conn.close()

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SKILL 9 — Veritabanı Performans Özeti
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def skill_performance_summary(db_id: str = None) -> dict:
    """
    Kapsamlı performans özeti — tüm metrikleri tek çağrıda döndürür.
    Kullanıcı "veritabanı neden yavaş?" gibi genel sorularında kullanılır.
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "overview": {},
        "health": {},
        "slow_queries": [],
        "active_queries": [],
        "locks": [],
        "index_issues": [],
        "actions_suggested": [],
    }

    try:
        # Overview
        overview = skill_db_overview(db_id=db_id)
        result["overview"] = overview

        # Health
        health = skill_health_check(db_id=db_id)
        result["health"] = health

        # Yavaş sorgular (top 5)
        slow = skill_slow_queries(threshold_ms=500, limit=5, db_id=db_id)
        result["slow_queries"] = slow.get("queries", [])

        # Aktif sorgular
        active = skill_active_queries(db_id=db_id)
        result["active_queries"] = active.get("queries", [])

        # Kilitler
        locks = skill_locks(db_id=db_id)
        result["locks"] = locks.get("locks", [])

        # Index önerileri
        idx = skill_index_recommendations(db_id=db_id)
        result["index_issues"] = idx.get("recommendations", [])

        # Otomatik aksiyon önerileri oluştur
        if health["status"] != "healthy":
            for issue in health.get("issues", []):
                if "VACUUM" in issue["msg"]:
                    # Tabloyu parse et
                    parts = issue["msg"].split(":")
                    if len(parts) > 0:
                        tbl = parts[0].split()[-1] if parts[0] else ""
                        result["actions_suggested"].append({
                            "action": "vacuum",
                            "table": tbl,
                            "reason": issue["msg"],
                        })

                if "kilit" in issue["msg"]:
                    result["actions_suggested"].append({
                        "action": "investigate_locks",
                        "reason": issue["msg"],
                    })

        for sq in result["slow_queries"][:3]:
            if sq["avg_ms"] > 5000:
                result["actions_suggested"].append({
                    "action": "optimize_query",
                    "query": sq["query"][:100],
                    "avg_ms": sq["avg_ms"],
                    "reason": f"Ortalama {sq['avg_ms']}ms — çok yavaş",
                })

        for idx_rec in result["index_issues"][:3]:
            if idx_rec.get("severity") == "high":
                result["actions_suggested"].append({
                    "action": "create_index",
                    "table": idx_rec["table"],
                    "reason": idx_rec.get("suggestion", ""),
                })

    except Exception as e:
        result["error"] = str(e)[:500]

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SKILL REGISTRY — Tüm becerilerin kayıt defteri
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SKILL_REGISTRY = {
    "db_overview": {
        "fn": skill_db_overview,
        "description": "Veritabanı genel durumu — versiyon, uptime, boyut, bağlantılar",
        "keywords": ["durum", "status", "genel", "özet", "bilgi", "boyut", "size", "kaç db", "database",
                      "overview", "info", "summary", "bağlantı", "connection", "uptime"],
        "params": {},
    },
    "health_check": {
        "fn": skill_health_check,
        "description": "Kapsamlı sağlık raporu — cache, commit ratio, dead tuples, long queries",
        "keywords": ["sağlık", "health", "kontrol", "check", "sorun", "problem", "issue",
                      "cache", "dead tuple", "rapor", "report"],
        "params": {},
    },
    "slow_queries": {
        "fn": skill_slow_queries,
        "description": "En yavaş sorguları listele",
        "keywords": ["yavaş", "slow", "sorgu", "query", "performans", "performance", "neden yavaş",
                      "why slow", "hız", "speed", "gecikme", "latency", "pg_stat_statements"],
        "params": {"threshold_ms": 1000, "limit": 10},
    },
    "active_queries": {
        "fn": skill_active_queries,
        "description": "Şu an çalışan aktif sorguları göster",
        "keywords": ["aktif", "active", "çalışan", "running", "şu an", "current",
                      "now", "pid"],
        "params": {},
    },
    "locks": {
        "fn": skill_locks,
        "description": "Kilit bekleyen sorguları göster",
        "keywords": ["kilit", "lock", "bekleme", "wait", "deadlock", "blocked",
                      "blocking", "kilitlenme"],
        "params": {},
    },
    "table_stats": {
        "fn": skill_table_stats,
        "description": "Tablo boyutları, satır sayıları ve VACUUM durumu",
        "keywords": ["tablo", "table", "boyut", "satır", "row", "istatistik", "stat",
                      "vacuum", "büyük", "large"],
        "params": {"limit": 15},
    },
    "index_recommendations": {
        "fn": skill_index_recommendations,
        "description": "Index analizi ve önerileri",
        "keywords": ["index", "indeks", "öneri", "recommendation", "seq scan", "sequential",
                      "optimize", "optimizasyon", "kullanılmayan", "unused"],
        "params": {},
    },
    "performance_summary": {
        "fn": skill_performance_summary,
        "description": "Komple performans özeti — sağlık + yavaş sorgu + index + aksiyon önerisi",
        "keywords": ["performans", "performance", "neden yavaş", "why slow", "yavaşlık",
                      "genel analiz", "full analysis", "komple", "kapsamlı", "comprehensive",
                      "ne oluyor", "what's happening", "problem ne"],
        "params": {},
    },
}

# Aksiyon becerileri (kullanıcı onayı gerektirir)
ACTION_SKILLS = {
    "vacuum": {
        "fn": skill_vacuum_table,
        "description": "Belirtilen tabloda VACUUM ANALYZE çalıştır",
        "requires_param": "table_name",
    },
    "reindex": {
        "fn": skill_reindex_table,
        "description": "Belirtilen tabloda REINDEX çalıştır",
        "requires_param": "table_name",
    },
    "kill_query": {
        "fn": skill_kill_query,
        "description": "Belirtilen PID'li sorguyu durdur",
        "requires_param": "pid",
    },
}
