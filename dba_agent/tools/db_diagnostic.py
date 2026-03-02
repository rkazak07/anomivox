"""
DB Diagnostic Tools — Veritabanı Diagnostik Araçları
════════════════════════════════════════════════════
DatabaseAdapter üzerinden çalışan read-only diagnostik araçlar.
"""

import logging
from typing import Any, Dict, Optional

from dba_agent.db import get_adapter
from dba_agent.tools.registry import ToolDef, get_tool_registry

logger = logging.getLogger("dba_agent.tools.db_diagnostic")


# ─────────────────────────────────────────────
# Tool Fonksiyonları
# ─────────────────────────────────────────────

def get_health(db_name: Optional[str] = None) -> Dict[str, Any]:
    """Veritabanı genel sağlık durumu."""
    adapter = get_adapter(db_name)
    with adapter:
        health = adapter.get_health()
        return {
            "db_type": health.db_type,
            "version": health.version,
            "uptime_hours": round(health.uptime_sec / 3600, 1),
            "connections": f"{health.active_connections}/{health.max_connections}",
            "connection_usage_pct": round(health.connection_usage_pct, 1),
            "database_size_mb": round(health.database_size_mb, 1),
            "cache_hit_ratio": f"{health.cache_hit_ratio:.1%}",
            "long_running_queries": health.long_running_queries,
            "blocked_locks": health.blocked_locks,
            "health_score": health.health_score,
        }


def get_active_connections(db_name: Optional[str] = None) -> Dict[str, Any]:
    """Aktif veritabanı bağlantıları."""
    adapter = get_adapter(db_name)
    with adapter:
        conns = adapter.get_active_connections()
        # State bazlı gruplama
        by_state: Dict[str, int] = {}
        for c in conns:
            by_state[c.state] = by_state.get(c.state, 0) + 1
        
        return {
            "total": len(conns),
            "by_state": by_state,
            "connections": [
                {
                    "pid": c.pid,
                    "user": c.user,
                    "state": c.state,
                    "duration_sec": round(c.duration_sec, 1),
                    "query": c.query[:200] if c.query else "",
                    "client": c.client_addr,
                }
                for c in conns[:20]  # İlk 20
            ],
        }


def get_long_running_queries(
    threshold_sec: float = 1.0,
    db_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Uzun süren sorgular."""
    adapter = get_adapter(db_name)
    with adapter:
        queries = adapter.get_long_running_queries(threshold_sec)
        return {
            "count": len(queries),
            "threshold_sec": threshold_sec,
            "queries": [
                {
                    "pid": q.pid,
                    "user": q.user,
                    "duration_sec": round(q.duration_sec, 1),
                    "state": q.state,
                    "query": q.query[:300],
                }
                for q in queries[:10]
            ],
        }


def get_blocked_locks(db_name: Optional[str] = None) -> Dict[str, Any]:
    """Engellenmiş kilitler."""
    adapter = get_adapter(db_name)
    with adapter:
        locks = adapter.get_blocked_locks()
        return {
            "count": len(locks),
            "locks": [
                {
                    "pid": l.pid,
                    "lock_type": l.lock_type,
                    "table": l.table,
                    "mode": l.mode,
                    "granted": l.granted,
                    "waiting_pid": l.waiting_pid,
                    "duration_sec": round(l.duration_sec, 1),
                    "query": l.query[:200],
                }
                for l in locks[:10]
            ],
        }


def get_slow_queries(
    limit: int = 10,
    db_name: Optional[str] = None,
) -> Dict[str, Any]:
    """En yavaş sorgular (pg_stat_statements / performance_schema)."""
    adapter = get_adapter(db_name)
    with adapter:
        queries = adapter.get_slow_queries(limit)
        return {
            "count": len(queries),
            "queries": [
                {
                    "query": q.query[:300],
                    "calls": q.calls,
                    "mean_time_ms": round(q.mean_time_ms, 1),
                    "total_time_ms": round(q.total_time_ms, 1),
                    "rows": q.rows,
                    "hit_ratio": f"{q.hit_ratio:.1%}",
                }
                for q in queries
            ],
        }


def get_table_stats(
    schema: str = "public",
    db_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Tablo istatistikleri."""
    adapter = get_adapter(db_name)
    with adapter:
        tables = adapter.get_table_stats(schema)
        return {
            "count": len(tables),
            "tables": [
                {
                    "table": f"{t.schema}.{t.table_name}",
                    "rows": t.row_count,
                    "size_mb": round(t.total_size_mb, 1),
                    "dead_rows": t.dead_rows,
                    "needs_vacuum": t.needs_vacuum,
                    "last_vacuum": str(t.last_vacuum) if t.last_vacuum else "never",
                    "seq_scan": t.seq_scan,
                    "idx_scan": t.idx_scan,
                }
                for t in tables[:30]
            ],
        }


def get_index_stats(
    schema: str = "public",
    db_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Index istatistikleri."""
    adapter = get_adapter(db_name)
    with adapter:
        indexes = adapter.get_index_stats(schema)
        unused = [i for i in indexes if i.is_unused]
        return {
            "total": len(indexes),
            "unused_count": len(unused),
            "indexes": [
                {
                    "table": f"{i.schema}.{i.table_name}",
                    "index": i.index_name,
                    "size_mb": round(i.index_size_mb, 1),
                    "scans": i.index_scans,
                    "is_unused": i.is_unused,
                    "columns": i.columns,
                }
                for i in indexes[:30]
            ],
            "unused_indexes": [
                {
                    "index": i.index_name,
                    "table": f"{i.schema}.{i.table_name}",
                    "size_mb": round(i.index_size_mb, 1),
                }
                for i in unused
            ],
        }


def explain_query(
    sql: str,
    db_name: Optional[str] = None,
) -> Dict[str, Any]:
    """SQL sorgusu için EXPLAIN ANALYZE."""
    adapter = get_adapter(db_name)
    with adapter:
        result = adapter.explain_query(sql)
        return {
            "query": sql[:300],
            "explain": result,
        }


def execute_diagnostic_query(
    sql: str,
    db_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Özel diagnostik sorgusu çalıştır (read-only)."""
    # Güvenlik: Sadece SELECT/SHOW/EXPLAIN izinli
    sql_upper = sql.strip().upper()
    if not any(sql_upper.startswith(p) for p in ("SELECT", "SHOW", "EXPLAIN", "WITH")):
        return {"success": False, "error": "Sadece SELECT/SHOW/EXPLAIN/WITH sorguları çalıştırılabilir"}
    
    adapter = get_adapter(db_name)
    with adapter:
        result = adapter.execute_query(sql, timeout=10)
        if not result.success:
            return {"success": False, "error": result.error}
        return {
            "success": True,
            "columns": result.columns,
            "rows": result.as_dicts[:50],  # Max 50 satır
            "row_count": result.row_count,
            "execution_time_ms": round(result.execution_time_ms, 1),
        }


# ─────────────────────────────────────────────
# Tüm DB Diagnostic Tool'ları Kaydet
# ─────────────────────────────────────────────

def register_db_diagnostic_tools() -> None:
    """Tüm DB diagnostic araçlarını registry'ye ekle."""
    registry = get_tool_registry()

    tools = [
        ToolDef(
            name="get_health",
            description="Veritabanı genel sağlık durumu (version, connections, cache, locks, score)",
            category="db_diagnostic",
            func=get_health,
            args_schema={"db_name": "str (opsiyonel)"},
            risk_level="safe",
            requires_db=True,
        ),
        ToolDef(
            name="get_active_connections",
            description="Aktif veritabanı bağlantıları, state bazlı gruplama",
            category="db_diagnostic",
            func=get_active_connections,
            args_schema={"db_name": "str (opsiyonel)"},
            risk_level="safe",
            requires_db=True,
        ),
        ToolDef(
            name="get_long_running_queries",
            description="Belirtilen eşik süresinden uzun çalışan sorgular",
            category="db_diagnostic",
            func=get_long_running_queries,
            args_schema={"threshold_sec": "float (varsayılan: 1.0)", "db_name": "str (opsiyonel)"},
            risk_level="safe",
            requires_db=True,
        ),
        ToolDef(
            name="get_blocked_locks",
            description="Engellenmiş kilitler — lock contention tespiti",
            category="db_diagnostic",
            func=get_blocked_locks,
            args_schema={"db_name": "str (opsiyonel)"},
            risk_level="safe",
            requires_db=True,
        ),
        ToolDef(
            name="get_slow_queries",
            description="En yavaş sorgular (pg_stat_statements / performance_schema)",
            category="db_diagnostic",
            func=get_slow_queries,
            args_schema={"limit": "int (varsayılan: 10)", "db_name": "str (opsiyonel)"},
            risk_level="safe",
            requires_db=True,
        ),
        ToolDef(
            name="get_table_stats",
            description="Tablo istatistikleri (satır sayısı, boyut, dead rows, vacuum durumu)",
            category="db_diagnostic",
            func=get_table_stats,
            args_schema={"schema": "str (varsayılan: public)", "db_name": "str (opsiyonel)"},
            risk_level="safe",
            requires_db=True,
        ),
        ToolDef(
            name="get_index_stats",
            description="Index istatistikleri ve kullanılmayan index tespiti",
            category="db_diagnostic",
            func=get_index_stats,
            args_schema={"schema": "str (varsayılan: public)", "db_name": "str (opsiyonel)"},
            risk_level="safe",
            requires_db=True,
        ),
        ToolDef(
            name="explain_query",
            description="SQL sorgusu için EXPLAIN ANALYZE çalıştır",
            category="db_diagnostic",
            func=explain_query,
            args_schema={"sql": "str (SQL sorgusu)", "db_name": "str (opsiyonel)"},
            risk_level="safe",
            requires_db=True,
        ),
        ToolDef(
            name="execute_diagnostic_query",
            description="Özel diagnostik SQL sorgusu çalıştır (sadece SELECT/SHOW/EXPLAIN)",
            category="db_diagnostic",
            func=execute_diagnostic_query,
            args_schema={"sql": "str (read-only SQL)", "db_name": "str (opsiyonel)"},
            risk_level="safe",
            requires_db=True,
        ),
    ]

    for tool in tools:
        registry.register(tool)
    
    logger.info(f"DB diagnostic tools registered: {len(tools)} tools")
