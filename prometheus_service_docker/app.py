import json
import os
import threading
import logging
import requests

import uvicorn
from fastapi import FastAPI, Request
from datetime import datetime

from prometheus_abnormal_metric import obtain_exceptions_in_times
from get_slow_queries import obtain_slow_queries


app = FastAPI()
logger = logging.getLogger("alert_app")
logging.basicConfig(level=logging.INFO)

# ── DBA Agent entegrasyonu ──────────────────────────
DBA_AGENT_URL = os.environ.get("DBA_AGENT_URL", "http://dba-agent:8100")
DBA_AGENT_NOTIFY_ENABLED = os.environ.get("DBA_AGENT_NOTIFY_ENABLED", "true").lower() == "true"

# Telegram Bot API — alert bildirimleri doğrudan
# Env'den veya configs/telegram_alert_config.py'den okunur.
# UI'dan kaydedilen ayarlar config dosyasına yazılır.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = os.environ.get("TELEGRAM_CHAT_IDS", "")  # virgülle ayrılmış chat_id'ler
TELEGRAM_ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")  # Ana admin chat_id


def _load_telegram_config():
    """configs/telegram_alert_config.py'den token ve chat_id oku (fallback)"""
    global TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, TELEGRAM_CHAT_IDS
    import re as _re
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "telegram_alert_config.py")
    if not os.path.exists(config_path):
        return
    try:
        with open(config_path, "r") as f:
            content = f.read()
        def _extract(key, default=""):
            m = _re.search(rf'^{key}\s*=\s*["\']([^"\']*)["\']', content, _re.MULTILINE)
            return m.group(1) if m else default
        cfg_token = _extract("TELEGRAM_BOT_TOKEN")
        cfg_admin = _extract("TELEGRAM_ADMIN_CHAT_ID")
        cfg_extra = _extract("TELEGRAM_EXTRA_CHAT_IDS")
        # Config'den gelen değerler env'den gelenleri override eder (UI'dan kaydedilmiş)
        if cfg_token:
            TELEGRAM_BOT_TOKEN = cfg_token
        if cfg_admin:
            TELEGRAM_ADMIN_CHAT_ID = cfg_admin
        if cfg_extra:
            TELEGRAM_CHAT_IDS = cfg_extra
        logger.info(f"Telegram config loaded: token={'set' if TELEGRAM_BOT_TOKEN else 'empty'}, admin_chat_id={TELEGRAM_ADMIN_CHAT_ID or 'empty'}")
    except Exception as e:
        logger.warning(f"Telegram config load error: {e}")


# İlk yüklemede config'ten oku
_load_telegram_config()

# Prometheus
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")

# ── Multi-DB konfigürasyonu ────────────────────────────────
# DB_TYPE: postgresql | mysql | oracle | mssql | mariadb
DB_TYPE = os.environ.get("DB_TYPE", "postgresql").lower()
DB_HOST = os.environ.get("DB_HOST", os.environ.get("PG_HOST", "postgres_db"))
DB_PORT = os.environ.get("DB_PORT", os.environ.get("PG_PORT", "5432"))
DB_USER = os.environ.get("DB_USER", os.environ.get("PG_USER", "test"))
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("PG_PASSWORD", "Test123_456"))
DB_NAME = os.environ.get("DB_NAME", os.environ.get("PG_DB", "anomivox"))
# Oracle için ek
DB_SERVICE_NAME = os.environ.get("DB_SERVICE_NAME", "")


# ═══════════════════════════════════════════════════════════
# Multi-DB Diagnostik Sorgular
# ═══════════════════════════════════════════════════════════

def _get_db_connection():
    """Veritabanı tipine göre bağlantı oluştur"""
    if DB_TYPE in ("postgresql", "postgres"):
        import psycopg2
        return psycopg2.connect(
            host=DB_HOST, port=int(DB_PORT),
            user=DB_USER, password=DB_PASSWORD,
            dbname=DB_NAME, connect_timeout=5,
        )
    elif DB_TYPE in ("mysql", "mariadb"):
        import mysql.connector
        return mysql.connector.connect(
            host=DB_HOST, port=int(DB_PORT),
            user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME, connect_timeout=5,
        )
    elif DB_TYPE == "oracle":
        import oracledb
        dsn = f"{DB_HOST}:{DB_PORT}/{DB_SERVICE_NAME}" if DB_SERVICE_NAME else f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
        return oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=dsn)
    elif DB_TYPE == "mssql":
        import pymssql
        return pymssql.connect(
            server=DB_HOST, port=int(DB_PORT),
            user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME, login_timeout=5,
        )
    else:
        raise ValueError(f"Desteklenmeyen DB tipi: {DB_TYPE}")


def _db_label() -> str:
    """DB tipi için okunabilir etiket"""
    labels = {
        "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
        "mysql": "MySQL", "mariadb": "MariaDB",
        "oracle": "Oracle", "mssql": "SQL Server",
    }
    return labels.get(DB_TYPE, DB_TYPE.upper())


def get_db_diagnostics() -> dict:
    """Veritabanı tipine göre anlık diagnostik bilgileri al"""
    diag = {"db_type": DB_TYPE, "db_label": _db_label()}
    try:
        conn = _get_db_connection()
        cur = conn.cursor()

        if DB_TYPE in ("postgresql", "postgres"):
            _diag_postgresql(cur, diag)
        elif DB_TYPE in ("mysql", "mariadb"):
            _diag_mysql(cur, diag)
        elif DB_TYPE == "oracle":
            _diag_oracle(cur, diag)
        elif DB_TYPE == "mssql":
            _diag_mssql(cur, diag)

        cur.close()
        conn.close()
    except Exception as e:
        diag["error"] = str(e)[:300]
    return diag


# ── PostgreSQL ──────────────────────────────────────────────
def _diag_postgresql(cur, diag):
    cur.execute("""
        SELECT state, count(*)
        FROM pg_stat_activity WHERE datname = current_database()
        GROUP BY state
    """)
    diag["connections"] = {row[0] or "null": row[1] for row in cur.fetchall()}

    cur.execute("""
        SELECT pid, now() - query_start AS duration,
               left(query, 120) AS query, state, wait_event_type
        FROM pg_stat_activity
        WHERE state != 'idle'
          AND query NOT ILIKE '%%pg_stat_activity%%'
          AND now() - query_start > interval '1 second'
        ORDER BY duration DESC LIMIT 5
    """)
    diag["long_queries"] = [
        {"pid": r[0], "duration": str(r[1]), "query": r[2], "state": r[3], "wait": r[4]}
        for r in cur.fetchall()
    ]

    cur.execute("SELECT count(*) FROM pg_locks WHERE NOT granted")
    diag["blocked_locks"] = cur.fetchone()[0]

    try:
        cur.execute("""
            SELECT left(query, 150), calls,
                   round(mean_exec_time::numeric, 2),
                   round(total_exec_time::numeric, 0)
            FROM pg_stat_statements
            WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
            ORDER BY mean_exec_time DESC LIMIT 5
        """)
        diag["top_slow_queries"] = [
            {"query": r[0], "calls": r[1], "avg_ms": float(r[2]), "total_ms": float(r[3])}
            for r in cur.fetchall()
        ]
    except Exception:
        diag["top_slow_queries"] = []

    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
    diag["db_size"] = cur.fetchone()[0]

    cur.execute("""
        SELECT relname, n_live_tup, n_dead_tup,
               last_vacuum, last_autovacuum, last_analyze
        FROM pg_stat_user_tables
        ORDER BY n_dead_tup DESC LIMIT 5
    """)
    diag["table_stats"] = [
        {"table": r[0], "live": r[1], "dead": r[2],
         "last_vacuum": str(r[3]) if r[3] else None,
         "last_autovacuum": str(r[4]) if r[4] else None}
        for r in cur.fetchall()
    ]


# ── MySQL / MariaDB ────────────────────────────────────────
def _diag_mysql(cur, diag):
    cur.execute("SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE DB = %s", (DB_NAME,))
    total = cur.fetchone()[0]
    cur.execute("SELECT COMMAND, COUNT(*) FROM information_schema.PROCESSLIST WHERE DB = %s GROUP BY COMMAND", (DB_NAME,))
    diag["connections"] = {row[0]: row[1] for row in cur.fetchall()}
    diag["connections"]["total"] = total

    cur.execute("""
        SELECT ID, TIME_MS / 1000.0 AS duration_sec,
               LEFT(INFO, 120) AS query, COMMAND, STATE
        FROM information_schema.PROCESSLIST
        WHERE DB = %s AND COMMAND != 'Sleep' AND TIME > 1
        ORDER BY TIME DESC LIMIT 5
    """, (DB_NAME,))
    diag["long_queries"] = [
        {"pid": r[0], "duration": f"{r[1]:.1f}s", "query": r[2], "state": r[4]}
        for r in cur.fetchall()
    ]

    cur.execute("""
        SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS
    """)
    diag["blocked_locks"] = cur.fetchone()[0]

    try:
        cur.execute("""
            SELECT LEFT(DIGEST_TEXT, 150), COUNT_STAR AS calls,
                   ROUND(AVG_TIMER_WAIT / 1000000000, 2) AS avg_ms,
                   ROUND(SUM_TIMER_WAIT / 1000000000, 0) AS total_ms
            FROM performance_schema.events_statements_summary_by_digest
            WHERE SCHEMA_NAME = %s
            ORDER BY AVG_TIMER_WAIT DESC LIMIT 5
        """, (DB_NAME,))
        diag["top_slow_queries"] = [
            {"query": r[0], "calls": r[1], "avg_ms": float(r[2]), "total_ms": float(r[3])}
            for r in cur.fetchall()
        ]
    except Exception:
        diag["top_slow_queries"] = []

    cur.execute("""
        SELECT ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 1)
        FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s
    """, (DB_NAME,))
    size = cur.fetchone()[0]
    diag["db_size"] = f"{size} MB" if size else "?"

    cur.execute("""
        SELECT TABLE_NAME, TABLE_ROWS,
               ROUND(DATA_LENGTH / 1024 / 1024, 1) AS data_mb,
               ROUND(DATA_FREE / 1024 / 1024, 1) AS fragmented_mb
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY DATA_FREE DESC LIMIT 5
    """, (DB_NAME,))
    diag["table_stats"] = [
        {"table": r[0], "rows": r[1], "data_mb": float(r[2]) if r[2] else 0,
         "fragmented_mb": float(r[3]) if r[3] else 0}
        for r in cur.fetchall()
    ]


# ── Oracle ──────────────────────────────────────────────────
def _diag_oracle(cur, diag):
    cur.execute("""
        SELECT status, COUNT(*) FROM v$session
        WHERE type = 'USER' GROUP BY status
    """)
    diag["connections"] = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute("""
        SELECT sid, ROUND(last_call_et) AS duration_sec,
               SUBSTR(sql_text, 1, 120) AS query, status, event
        FROM v$session s LEFT JOIN v$sql q ON s.sql_id = q.sql_id
        WHERE s.type = 'USER' AND s.status = 'ACTIVE'
          AND s.last_call_et > 1
        ORDER BY last_call_et DESC FETCH FIRST 5 ROWS ONLY
    """)
    diag["long_queries"] = [
        {"sid": r[0], "duration": f"{r[1]}s", "query": r[2], "state": r[3], "wait": r[4]}
        for r in cur.fetchall()
    ]

    cur.execute("SELECT COUNT(*) FROM v$lock WHERE request > 0")
    diag["blocked_locks"] = cur.fetchone()[0]

    try:
        cur.execute("""
            SELECT SUBSTR(sql_text, 1, 150), executions,
                   ROUND(elapsed_time / NULLIF(executions, 0) / 1000, 2) AS avg_ms,
                   ROUND(elapsed_time / 1000, 0) AS total_ms
            FROM v$sql
            WHERE parsing_schema_name NOT IN ('SYS','SYSTEM')
            ORDER BY elapsed_time / NULLIF(executions, 0) DESC
            FETCH FIRST 5 ROWS ONLY
        """)
        diag["top_slow_queries"] = [
            {"query": r[0], "calls": r[1], "avg_ms": float(r[2]) if r[2] else 0,
             "total_ms": float(r[3]) if r[3] else 0}
            for r in cur.fetchall()
        ]
    except Exception:
        diag["top_slow_queries"] = []

    cur.execute("""
        SELECT ROUND(SUM(bytes) / 1024 / 1024, 1)
        FROM dba_segments WHERE owner NOT IN ('SYS','SYSTEM')
    """)
    size = cur.fetchone()[0]
    diag["db_size"] = f"{size} MB" if size else "?"

    cur.execute("""
        SELECT table_name, num_rows,
               ROUND(blocks * 8 / 1024, 1) AS size_mb,
               last_analyzed
        FROM all_tables
        WHERE owner NOT IN ('SYS','SYSTEM')
        ORDER BY num_rows DESC NULLS LAST
        FETCH FIRST 5 ROWS ONLY
    """)
    diag["table_stats"] = [
        {"table": r[0], "rows": r[1], "size_mb": float(r[2]) if r[2] else 0,
         "last_analyzed": str(r[3]) if r[3] else None}
        for r in cur.fetchall()
    ]


# ── SQL Server ──────────────────────────────────────────────
def _diag_mssql(cur, diag):
    cur.execute("""
        SELECT status, COUNT(*) FROM sys.dm_exec_sessions
        WHERE database_id = DB_ID() GROUP BY status
    """)
    diag["connections"] = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute("""
        SELECT TOP 5 r.session_id,
               DATEDIFF(SECOND, r.start_time, GETDATE()) AS duration_sec,
               LEFT(t.text, 120) AS query, r.status, r.wait_type
        FROM sys.dm_exec_requests r
        CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
        WHERE r.database_id = DB_ID()
          AND DATEDIFF(SECOND, r.start_time, GETDATE()) > 1
        ORDER BY r.start_time ASC
    """)
    diag["long_queries"] = [
        {"pid": r[0], "duration": f"{r[1]}s", "query": r[2], "state": r[3], "wait": r[4]}
        for r in cur.fetchall()
    ]

    cur.execute("SELECT COUNT(*) FROM sys.dm_os_waiting_tasks WHERE blocking_session_id IS NOT NULL")
    diag["blocked_locks"] = cur.fetchone()[0]

    try:
        cur.execute("""
            SELECT TOP 5 LEFT(qt.text, 150),
                   qs.execution_count,
                   ROUND(qs.total_elapsed_time / NULLIF(qs.execution_count, 0) / 1000.0, 2),
                   ROUND(qs.total_elapsed_time / 1000.0, 0)
            FROM sys.dm_exec_query_stats qs
            CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
            ORDER BY qs.total_elapsed_time / NULLIF(qs.execution_count, 0) DESC
        """)
        diag["top_slow_queries"] = [
            {"query": r[0], "calls": r[1], "avg_ms": float(r[2]) if r[2] else 0,
             "total_ms": float(r[3]) if r[3] else 0}
            for r in cur.fetchall()
        ]
    except Exception:
        diag["top_slow_queries"] = []

    cur.execute("SELECT ROUND(SUM(size) * 8.0 / 1024, 1) FROM sys.database_files")
    size = cur.fetchone()[0]
    diag["db_size"] = f"{size} MB" if size else "?"

    cur.execute("""
        SELECT TOP 5 t.name,
               SUM(p.rows) AS rows,
               ROUND(SUM(a.total_pages) * 8.0 / 1024, 1) AS size_mb
        FROM sys.tables t
        JOIN sys.indexes i ON t.object_id = i.object_id
        JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
        JOIN sys.allocation_units a ON p.partition_id = a.container_id
        GROUP BY t.name ORDER BY SUM(p.rows) DESC
    """)
    diag["table_stats"] = [
        {"table": r[0], "rows": r[1], "size_mb": float(r[2]) if r[2] else 0}
        for r in cur.fetchall()
    ]


# ═══════════════════════════════════════════════════════════
# Alert Formatlama & AI Agent Bildirim
# ═══════════════════════════════════════════════════════════

def notify_dba_agent(message: str):
    """
    Alert bildirimini Telegram'a gönder.

    Strateji:
      1. TELEGRAM_BOT_TOKEN + TELEGRAM_ADMIN_CHAT_ID varsa → doğrudan Telegram Bot API
      2. Yoksa DBA Agent API'ye alert gönder (fallback)

    Kullanıcı Telegram'dan yanıt verdiğinde DBA Agent otomatik olarak
    teşhis başlatır.
    """
    if not DBA_AGENT_NOTIFY_ENABLED:
        return

    # Her çağrıda config'i yeniden oku (UI'dan değiştirilebilir)
    _load_telegram_config()

    sent = False

    # ── 1. Doğrudan Telegram Bot API ──
    if TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_ID:
        try:
            chat_ids = [TELEGRAM_ADMIN_CHAT_ID]
            if TELEGRAM_CHAT_IDS:
                chat_ids += [c.strip() for c in TELEGRAM_CHAT_IDS.split(",") if c.strip()]
            chat_ids = list(set(chat_ids))  # deduplicate

            for chat_id in chat_ids:
                resp = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    logger.info(f"Telegram alert sent to chat_id={chat_id}")
                    sent = True
                else:
                    logger.warning(f"Telegram send failed chat_id={chat_id}: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Telegram Bot API error: {e}")

    # ── 2. Fallback: DBA Agent API ──
    if not sent:
        try:
            resp = requests.post(
                f"{DBA_AGENT_URL}/api/agent/alert",
                json={"message": message, "source": "prometheus"},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            logger.info(f"DBA Agent notify response: {resp.status_code}")
        except Exception as e:
            logger.error(f"DBA Agent notify failed: {e}")


def query_prometheus_instant(query: str) -> dict:
    """Prometheus'tan anlık metrik sorgula"""
    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=10,
        )
        return resp.json() if resp.status_code == 200 else {}
    except Exception:
        return {}


def format_alert_message(args: dict, diagnostics: dict = None) -> str:
    """Alert bilgisini okunabilir formata çevir — tüm DB tipleri"""
    alerts = args.get("alerts", [])
    status = args.get("status", "unknown")
    status_emoji = "🔴" if status == "firing" else "🟢"
    db_label = diagnostics.get("db_label", _db_label()) if diagnostics else _db_label()

    lines = [f"{status_emoji} **{db_label} Alert — {status.upper()}**", ""]

    for alert in alerts:
        labels = alert.get("labels", {})
        ann = alert.get("annotations", {})
        severity = labels.get("severity", "?")
        sev_icon = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(severity, "❓")

        lines.append(f"{sev_icon} **{labels.get('alertname', 'Unknown')}** [{severity}]")
        if ann.get("summary"):
            lines.append(f"  📋 {ann['summary']}")
        if ann.get("description"):
            lines.append(f"  📝 {ann['description']}")
        lines.append(f"  ⏰ Başlangıç: {alert.get('startsAt', '?')[:19]}")
        if alert.get("endsAt") and status == "resolved":
            lines.append(f"  ✅ Çözüm: {alert['endsAt'][:19]}")
        lines.append("")

    # Diagnostik bilgiler
    if diagnostics and not diagnostics.get("error"):
        lines.append(f"📊 **Anlık {db_label} Durumu:**")

        conn = diagnostics.get("connections", {})
        conn_parts = [f"{k}={v}" for k, v in conn.items()]
        lines.append(f"  🔗 Bağlantılar: {', '.join(conn_parts)}")
        lines.append(f"  🔒 Bekleyen lock: {diagnostics.get('blocked_locks', 0)}")
        lines.append(f"  💾 DB boyut: {diagnostics.get('db_size', '?')}")

        long_q = diagnostics.get("long_queries", [])
        if long_q:
            lines.append(f"\n  🐌 **Uzun Süren Sorgular ({len(long_q)}):**")
            for q in long_q[:3]:
                pid_key = "pid" if "pid" in q else "sid"
                lines.append(f"    {pid_key.upper()} {q.get(pid_key, '?')} ({q.get('duration','?')}) — {(q.get('query','') or '')[:80]}")

        slow = diagnostics.get("top_slow_queries", [])
        if slow:
            lines.append(f"\n  🔥 **En Yavaş Sorgular (avg):**")
            for q in slow[:3]:
                lines.append(f"    [{q.get('avg_ms',0)}ms, {q.get('calls',0)} çağrı] {(q.get('query','') or '')[:80]}")

        tables = diagnostics.get("table_stats", [])
        if tables:
            lines.append(f"\n  📋 **Tablo Durumu:**")
            for t in tables[:3]:
                if DB_TYPE in ("postgresql", "postgres"):
                    dead = t.get("dead", 0)
                    if dead and dead > 0:
                        lines.append(f"    {t['table']}: dead_rows={dead}, vacuum={t.get('last_autovacuum','hiç')}")
                elif DB_TYPE in ("mysql", "mariadb"):
                    frag = t.get("fragmented_mb", 0)
                    if frag and frag > 0:
                        lines.append(f"    {t['table']}: rows={t.get('rows','?')}, fragmented={frag}MB")
                else:
                    lines.append(f"    {t['table']}: rows={t.get('rows','?')}")
    elif diagnostics and diagnostics.get("error"):
        lines.append(f"⚠️ DB diagnostik hatası: {diagnostics['error'][:100]}")

    lines.append("")
    lines.append("💬 Ne yapmamı istersin? Örnekler:")
    lines.append("• `slow query analiz` — Yavaş sorguları detaylı analiz et")
    lines.append("• `db durum` — Genel veritabanı durumunu göster")
    lines.append("• `bağlantılar` — Aktif bağlantı detayları")

    if DB_TYPE in ("postgresql", "postgres"):
        lines.append("• `vacuum <tablo>` — Tabloyu vacuum yap")
        lines.append("• `kill <pid>` — Sorguyu sonlandır (pg_terminate_backend)")
        lines.append("• `reindex <tablo>` — Index yeniden oluştur")
    elif DB_TYPE in ("mysql", "mariadb"):
        lines.append("• `optimize <tablo>` — Tabloyu optimize et")
        lines.append("• `kill <id>` — Sorguyu sonlandır (KILL QUERY)")
        lines.append("• `analyze <tablo>` — Tablo istatistiklerini güncelle")
    elif DB_TYPE == "oracle":
        lines.append("• `kill <sid,serial>` — Session sonlandır")
        lines.append("• `gather stats <tablo>` — İstatistik topla")
        lines.append("• `tablespace durum` — Tablespace kullanımı")
    elif DB_TYPE == "mssql":
        lines.append("• `kill <spid>` — Session sonlandır")
        lines.append("• `rebuild index <tablo>` — Index rebuild")
        lines.append("• `update stats <tablo>` — İstatistik güncelle")

    return "\n".join(lines)


@app.get('/test')
async def test():
    return {
        "code": 0,
        "msg": "success",
        "data": "prometheus service is running"
    }


@app.post('/test_alert')
async def test_alert():
    """
    Manuel test — Telegram'a örnek alert gönder.
    Kullanım: curl -X POST http://localhost:8023/test_alert
    """
    try:
        diagnostics = get_db_diagnostics()
        test_args = {
            "status": "firing",
            "alerts": [{
                "labels": {"alertname": "TestAlert", "severity": "warning"},
                "annotations": {
                    "summary": "Bu bir test alertidir",
                    "description": "Anomivox alert sistemi doğru çalışıyor mu kontrol ediliyor."
                },
                "startsAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }]
        }
        message = format_alert_message(test_args, diagnostics)
        notify_dba_agent(message)
        return {"code": 0, "msg": "success", "data": "test alert sent",
                "diagnostics": diagnostics, "chat_id": TELEGRAM_ADMIN_CHAT_ID}
    except Exception as e:
        return {"code": 1, "msg": str(e)}


@app.post('/alert')
async def alert(request: Request):
    """
    AlertManager webhook — hem firing hem resolved durumları işle
    """
    args = await request.json()
    try:
        with open("alert_history.txt", "a") as f:
            f.write(json.dumps(args) + "\n")
    except Exception as e:
        logger.warning(f"alert_history.txt yazma hatası: {e}")

    try:
        status = args.get("status", "unknown")

        # Her alert'te Telegram'a bildirim gönder
        if DBA_AGENT_NOTIFY_ENABLED:
            thread_notify = threading.Thread(
                target=_send_alert_notification, args=(args,), daemon=True
            )
            thread_notify.start()

        # Resolved durumda diagnostik dosya oluştur (mevcut davranış)
        if status == "resolved":
            thread = threading.Thread(target=gen_diagnostic_file, args=(args,))
            thread.start()

    except Exception as e:
        logging.error(e)

    return {
        "code": 0,
        "msg": "success",
        "data": ""
    }


def _send_alert_notification(args):
    """Alert bildirimi — DB diagnostik bilgileriyle birlikte"""
    try:
        diagnostics = get_db_diagnostics()
        message = format_alert_message(args, diagnostics)
        notify_dba_agent(message)
    except Exception as e:
        logger.error(f"Alert notification error: {e}")


def _parse_alert_time(raw_time: str) -> datetime:
    """
    AlertManager zaman damgasını datetime'a çevir.
    Nanosecond (9 hane) ve microsecond (6 hane) formatlarını destekler.
    """
    if not raw_time or not raw_time.endswith("Z") or "." not in raw_time:
        raise ValueError(f"Beklenmeyen zaman formatı: {raw_time!r}")
    dot_pos = raw_time.index(".")
    frac = raw_time[dot_pos + 1:-1][:6]  # maks 6 hane (microsecond)
    normalized = raw_time[:dot_pos + 1] + frac + "Z"
    return datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%S.%fZ")


def gen_diagnostic_file(args):
    alerts = args.get("alerts", [])

    if not alerts:
        logger.warning("gen_diagnostic_file: boş alert listesi, atlandı.")
        return

    try:
        alert_time = _parse_alert_time(alerts[0].get("startsAt", ""))
    except (ValueError, TypeError) as e:
        logger.error(f"gen_diagnostic_file: alert_time parse hatası: {e}")
        return

    start_seconds = alert_time.timestamp() - 60 * 5
    end_seconds = alert_time.timestamp() + 60

    try:
        exceptions = obtain_exceptions_in_times(start_seconds, end_seconds)
    except Exception as e:
        logger.error(f"gen_diagnostic_file: obtain_exceptions_in_times hatası: {e}")
        exceptions = {}

    try:
        slow_queries = obtain_slow_queries(start_seconds, end_seconds)
    except Exception as e:
        logger.error(f"gen_diagnostic_file: obtain_slow_queries hatası: {e}")
        slow_queries = []

    diagnostic_file_data = {
        "start_time": start_seconds,
        "end_time": end_seconds,
        "start_timestamp": datetime.fromtimestamp(start_seconds).strftime("%Y-%m-%d %H:%M:%S"),
        "end_timestamp": datetime.fromtimestamp(end_seconds).strftime("%Y-%m-%d %H:%M:%S"),
        "alerts": [alerts],
        "workload": [],
        "slow_queries": slow_queries,
        "exceptions": exceptions
    }

    path = './gen_diagnostic_files'
    try:
        os.makedirs(path, exist_ok=True)
        filename = 'alert_time_' + datetime.fromtimestamp(start_seconds).strftime("%Y-%m-%d-%H-%M-%S") + '.json'
        with open(os.path.join(path, filename), 'w') as f:
            json.dump(diagnostic_file_data, f)
        logger.info(f"Tanı dosyası oluşturuldu: {filename}")
    except Exception as e:
        logger.error(f"gen_diagnostic_file: dosya yazma hatası: {e}")


if __name__ == "__main__":
    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=8023
    )
