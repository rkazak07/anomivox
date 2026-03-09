"""
DB Action Tools — Veritabanı Yazma/Yönetim Araçları
═══════════════════════════════════════════════════
Veritabanı üzerinde aktif müdahale araçları:
  - Session/Query öldürme (pg_terminate_backend, KILL, ALTER SYSTEM KILL SESSION)
  - VACUUM / VACUUM FULL / OPTIMIZE TABLE / SHRINK SPACE / ALTER INDEX REBUILD
  - REINDEX / ALTER INDEX REBUILD / DBMS_STATS
  - ANALYZE / UPDATE STATISTICS / DBMS_STATS.GATHER_TABLE_STATS
  - Config parametre değiştirme (ALTER SYSTEM SET / SET GLOBAL / sp_configure)
  - Config yeniden yükleme (pg_reload_conf / FLUSH / RECONFIGURE)

Desteklenen DB'ler: PostgreSQL, MySQL/MariaDB, Oracle, MSSQL

Risk Seviyeleri:
  SAFE     — ANALYZE / UPDATE STATISTICS / DBMS_STATS
  LOW      — pg_cancel_backend, VACUUM (normal), OPTIMIZE TABLE
  MEDIUM   — pg_terminate_backend, REINDEX, KILL, ALTER INDEX REBUILD
  HIGH     — VACUUM FULL, ALTER SYSTEM SET, SHRINK SPACE CASCADE

Tüm riskli operasyonlar Telegram onay sistemi ile korunur.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from dba_agent.config import get_config
from dba_agent.db.adapter import RiskLevel
from dba_agent.db.factory import get_adapter
from dba_agent.tools.registry import ToolDef, get_tool_registry

logger = logging.getLogger("dba_agent.tools.db_action_tools")


# ─────────────────────────────────────────────
# Güvenlik Helpers
# ─────────────────────────────────────────────

def _check_sql_forbidden(sql: str) -> Optional[str]:
    """
    SQL'i forbidden patterns'a karşı kontrol et.

    Returns:
        None = güvenli, str = engelleme sebebi
    """
    config = get_config()
    for pattern in config.security.forbidden_sql_patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            return f"FORBIDDEN: SQL pattern '{pattern}' güvenlik politikası gereği engellenmiştir."
    return None


def _audit_action(target: str, sql: str, risk: str, result: str, **kwargs) -> None:
    """Audit log yaz."""
    try:
        from dba_agent.security.audit import AuditLogger
        audit = AuditLogger()
        audit.log_sql(
            target=target,
            sql=sql,
            risk=risk,
            result=result,
            **kwargs,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────
# PostgreSQL Specific Actions
# ─────────────────────────────────────────────

def cancel_query(pid: int, db_name: str = None) -> Dict[str, Any]:
    """
    Çalışan sorguyu iptal et (pg_cancel_backend).
    Sorguyu nazikçe durdurur, bağlantıyı kapatmaz.

    Risk: LOW

    Args:
        pid: Backend process ID
        db_name: Veritabanı adı (None = varsayılan)

    Returns:
        {"pid": int, "cancelled": bool, "message": str}
    """
    with get_adapter(db_name) as adapter:
        db_type = adapter.target.db_type.lower()

        if db_type in ("postgresql", "postgres"):
            check = adapter.execute_query(
                "SELECT pid, usename, state, query FROM pg_stat_activity WHERE pid = %s",
                (pid,),
            )
            if not check.rows:
                return {
                    "pid": pid,
                    "cancelled": False,
                    "message": f"PID {pid} bulunamadı veya zaten sonlanmış.",
                }
            query_info = {
                "user": str(check.rows[0][1]),
                "state": str(check.rows[0][2]),
                "query": str(check.rows[0][3])[:200],
            }
            sql = f"SELECT pg_cancel_backend({pid})"

        elif db_type in ("mysql", "mariadb"):
            check = adapter.execute_query(
                "SELECT ID, USER, COMMAND, INFO FROM information_schema.PROCESSLIST WHERE ID = %s",
                (pid,),
            )
            if not check.rows:
                return {
                    "pid": pid,
                    "cancelled": False,
                    "message": f"Thread ID {pid} bulunamadı veya zaten sonlanmış.",
                }
            query_info = {
                "user": str(check.rows[0][1]),
                "state": str(check.rows[0][2]),
                "query": str(check.rows[0][3] or "")[:200],
            }
            sql = f"KILL QUERY {pid}"

        elif db_type == "oracle":
            check = adapter.execute_query(
                f"SELECT sid, username, status, sql_id FROM v$session WHERE sid = {pid}"
            )
            if not check.rows:
                return {"pid": pid, "cancelled": False, "message": f"SID {pid} bulunamadı."}
            query_info = {
                "user": str(check.rows[0][1] or ""),
                "state": str(check.rows[0][2] or ""),
                "query": str(check.rows[0][3] or ""),
            }
            sql = f"ALTER SYSTEM CANCEL SQL '{check.rows[0][3]}'"

        elif db_type in ("mssql", "sqlserver"):
            check = adapter.execute_query(
                f"SELECT session_id, login_name, status FROM sys.dm_exec_sessions WHERE session_id = {pid}"
            )
            if not check.rows:
                return {"pid": pid, "cancelled": False, "message": f"Session {pid} bulunamadı."}
            query_info = {
                "user": str(check.rows[0][1] or ""),
                "state": str(check.rows[0][2] or ""),
            }
            sql = f"KILL {pid}"

        else:
            return {
                "pid": pid,
                "cancelled": False,
                "message": f"Desteklenmeyen DB tipi: {db_type}",
            }

        result = adapter.execute_action(sql, RiskLevel.LOW)

        _audit_action(
            target=adapter.display_name,
            sql=sql,
            risk="low",
            result="success" if result.success else "failed",
        )

        return {
            "pid": pid,
            "cancelled": result.success,
            "db_type": db_type,
            "message": result.message,
            "query_info": query_info,
            "execution_time_ms": result.execution_time_ms,
        }


def kill_session(pid: int, db_name: str = None) -> Dict[str, Any]:
    """
    Oturumu sonlandır (pg_terminate_backend / KILL).
    Bağlantıyı tamamen kapatır.

    Risk: MEDIUM

    Args:
        pid: Backend process ID (PostgreSQL) veya Thread ID (MySQL)
        db_name: Veritabanı adı

    Returns:
        {"pid": int, "killed": bool, "message": str}
    """
    with get_adapter(db_name) as adapter:
        db_type = adapter.target.db_type.lower()

        if db_type in ("postgresql", "postgres"):
            # Önce PID bilgisini al
            check = adapter.execute_query(
                "SELECT pid, usename, state, query FROM pg_stat_activity WHERE pid = %s",
                (pid,),
            )
            query_info = {}
            if check.rows:
                query_info = {
                    "user": str(check.rows[0][1]),
                    "state": str(check.rows[0][2]),
                    "query": str(check.rows[0][3])[:200],
                }

            sql = f"SELECT pg_terminate_backend({pid})"
            result = adapter.execute_action(sql, RiskLevel.MEDIUM)

        elif db_type in ("mysql", "mariadb"):
            check = adapter.execute_query(
                "SELECT ID, USER, HOST, DB, COMMAND FROM information_schema.PROCESSLIST WHERE ID = %s",
                (pid,),
            )
            query_info = {}
            if check.rows:
                query_info = {
                    "user": str(check.rows[0][1]),
                    "host": str(check.rows[0][2]),
                    "db": str(check.rows[0][3]),
                    "command": str(check.rows[0][4]),
                }

            sql = f"KILL {pid}"
            result = adapter.execute_action(sql, RiskLevel.MEDIUM)

        elif db_type == "oracle":
            check = adapter.execute_query(
                f"SELECT sid, serial#, username, status FROM v$session WHERE sid = {pid}"
            )
            query_info = {}
            if check.rows:
                query_info = {
                    "user": str(check.rows[0][2] or ""),
                    "state": str(check.rows[0][3] or ""),
                }
                serial = int(check.rows[0][1])
                sql = f"ALTER SYSTEM KILL SESSION '{pid},{serial}' IMMEDIATE"
            else:
                return {"pid": pid, "killed": False, "message": f"SID {pid} bulunamadı."}

            result = adapter.execute_action(sql, RiskLevel.MEDIUM)

        elif db_type in ("mssql", "sqlserver"):
            check = adapter.execute_query(
                f"SELECT session_id, login_name, status, host_name FROM sys.dm_exec_sessions WHERE session_id = {pid}"
            )
            query_info = {}
            if check.rows:
                query_info = {
                    "user": str(check.rows[0][1] or ""),
                    "state": str(check.rows[0][2] or ""),
                    "host": str(check.rows[0][3] or ""),
                }

            sql = f"KILL {pid}"
            result = adapter.execute_action(sql, RiskLevel.MEDIUM)

        else:
            return {
                "pid": pid,
                "killed": False,
                "message": f"Desteklenmeyen DB tipi: {db_type}",
            }

        _audit_action(
            target=adapter.display_name,
            sql=sql,
            risk="medium",
            result="success" if result.success else "failed",
        )

        return {
            "pid": pid,
            "killed": result.success,
            "db_type": db_type,
            "message": result.message,
            "query_info": query_info,
            "execution_time_ms": result.execution_time_ms,
        }


def vacuum_table(
    table_name: str,
    analyze: bool = True,
    db_name: str = None,
) -> Dict[str, Any]:
    """
    Tablo üzerinde VACUUM çalıştır (normal mod).
    Dead tuple'ları temizler, tablo boyutunu küçültmez.

    Risk: LOW

    Args:
        table_name: Tablo adı (schema.tablo veya sadece tablo)
        analyze: VACUUM ANALYZE olarak çalıştır (istatistikleri güncelle)
        db_name: Veritabanı adı

    Returns:
        {"table": str, "vacuumed": bool, "message": str, "before": Dict, "after": Dict}
    """
    with get_adapter(db_name) as adapter:
        # Önceki durumu al
        schema, tbl = _parse_table_name(table_name)
        before = _get_table_snapshot(adapter, schema, tbl)

        db_type = adapter.target.db_type.lower()
        if db_type in ("mysql", "mariadb"):
            # MySQL/MariaDB: OPTIMIZE TABLE (dead rows temizle + istatistik güncelle)
            sql = f"OPTIMIZE TABLE {table_name}"
        elif db_type == "oracle":
            # Oracle: ALTER TABLE ... SHRINK SPACE veya istatistik güncelle
            if analyze:
                sql = f"BEGIN DBMS_STATS.GATHER_TABLE_STATS(ownname => USER, tabname => '{tbl.upper()}'); END;"
            else:
                sql = f"ALTER TABLE {table_name} ENABLE ROW MOVEMENT"
        elif db_type in ("mssql", "sqlserver"):
            # MSSQL: sp_clean_db_free_space + UPDATE STATISTICS
            if analyze:
                sql = f"UPDATE STATISTICS {table_name}"
            else:
                sql = f"ALTER INDEX ALL ON {table_name} REORGANIZE"
        else:
            analyze_str = " ANALYZE" if analyze else ""
            sql = f"VACUUM{analyze_str} {table_name}"

        # VACUUM autocommit gerektirir
        result = adapter.execute_action(sql, RiskLevel.LOW)

        # Sonraki durum
        after = _get_table_snapshot(adapter, schema, tbl) if result.success else None

        _audit_action(
            target=adapter.display_name,
            sql=sql,
            risk="low",
            result="success" if result.success else "failed",
            execution_time_ms=result.execution_time_ms,
        )

        return {
            "table": table_name,
            "vacuumed": result.success,
            "analyze": analyze,
            "message": result.message,
            "execution_time_ms": result.execution_time_ms,
            "before": before,
            "after": after,
        }


def vacuum_full_table(
    table_name: str,
    db_name: str = None,
) -> Dict[str, Any]:
    """
    Tablo üzerinde VACUUM FULL çalıştır.
    ⚠️ Tablo kilitler, boyutu küçültür.
    Yoğun saatlerde KULLANMAYIN.

    Risk: HIGH

    Args:
        table_name: Tablo adı
        db_name: Veritabanı adı

    Returns:
        {"table": str, "vacuumed": bool, "message": str, "before": Dict, "after": Dict}
    """
    with get_adapter(db_name) as adapter:
        schema, tbl = _parse_table_name(table_name)
        before = _get_table_snapshot(adapter, schema, tbl)

        db_type = adapter.target.db_type.lower()
        if db_type in ("mysql", "mariadb"):
            # MySQL'de VACUUM FULL yok — OPTIMIZE TABLE en yakın eşdeğer
            sql = f"OPTIMIZE TABLE {table_name}"
        elif db_type == "oracle":
            # Oracle: ALTER TABLE ... SHRINK SPACE COMPACT + CASCADE (index dahil)
            sql = f"ALTER TABLE {table_name} SHRINK SPACE CASCADE"
        elif db_type in ("mssql", "sqlserver"):
            # MSSQL: DBCC CLEANTABLE + index rebuild
            sql = f"ALTER INDEX ALL ON {table_name} REBUILD"
        else:
            sql = f"VACUUM FULL ANALYZE {table_name}"
        result = adapter.execute_action(sql, RiskLevel.HIGH)

        after = _get_table_snapshot(adapter, schema, tbl) if result.success else None

        _audit_action(
            target=adapter.display_name,
            sql=sql,
            risk="high",
            result="success" if result.success else "failed",
            execution_time_ms=result.execution_time_ms,
        )

        return {
            "table": table_name,
            "vacuumed": result.success,
            "full": True,
            "message": result.message,
            "execution_time_ms": result.execution_time_ms,
            "before": before,
            "after": after,
        }


def reindex_table(
    table_name: str,
    db_name: str = None,
) -> Dict[str, Any]:
    """
    Tablo index'lerini yeniden oluştur (REINDEX TABLE).
    Bozuk/şişmiş index'leri düzeltir.

    Risk: MEDIUM

    Args:
        table_name: Tablo adı
        db_name: Veritabanı adı

    Returns:
        {"table": str, "reindexed": bool, "message": str}
    """
    with get_adapter(db_name) as adapter:
        db_type = adapter.target.db_type.lower()
        schema, tbl = _parse_table_name(table_name)

        if db_type in ("postgresql", "postgres"):
            sql = f"REINDEX TABLE {table_name}"
        elif db_type in ("mysql", "mariadb"):
            # MySQL: ALTER TABLE ... FORCE veya OPTIMIZE TABLE
            sql = f"OPTIMIZE TABLE {table_name}"
        elif db_type == "oracle":
            # Oracle: ALTER INDEX ... REBUILD (tüm indexler için)
            sql = f"BEGIN FOR idx IN (SELECT index_name FROM user_indexes WHERE table_name = '{tbl.upper()}') LOOP EXECUTE IMMEDIATE 'ALTER INDEX ' || idx.index_name || ' REBUILD'; END LOOP; END;"
        elif db_type in ("mssql", "sqlserver"):
            # MSSQL: ALTER INDEX ALL ... REBUILD
            sql = f"ALTER INDEX ALL ON {table_name} REBUILD"
        else:
            return {
                "table": table_name,
                "reindexed": False,
                "message": f"Desteklenmeyen DB tipi: {db_type}",
            }

        result = adapter.execute_action(sql, RiskLevel.MEDIUM)

        _audit_action(
            target=adapter.display_name,
            sql=sql,
            risk="medium",
            result="success" if result.success else "failed",
            execution_time_ms=result.execution_time_ms,
        )

        return {
            "table": table_name,
            "db_type": db_type,
            "reindexed": result.success,
            "message": result.message,
            "execution_time_ms": result.execution_time_ms,
        }


def analyze_table(
    table_name: str,
    db_name: str = None,
) -> Dict[str, Any]:
    """
    Tablo istatistiklerini güncelle (ANALYZE).
    Sorgu planlayıcı daha iyi kararlar alır.

    Risk: SAFE

    Args:
        table_name: Tablo adı
        db_name: Veritabanı adı

    Returns:
        {"table": str, "analyzed": bool, "message": str}
    """
    with get_adapter(db_name) as adapter:
        db_type = adapter.target.db_type.lower()

        schema, tbl = _parse_table_name(table_name)

        if db_type in ("postgresql", "postgres"):
            sql = f"ANALYZE {table_name}"
        elif db_type in ("mysql", "mariadb"):
            sql = f"ANALYZE TABLE {table_name}"
        elif db_type == "oracle":
            # Oracle: DBMS_STATS.GATHER_TABLE_STATS
            sql = f"BEGIN DBMS_STATS.GATHER_TABLE_STATS(ownname => USER, tabname => '{tbl.upper()}'); END;"
        elif db_type in ("mssql", "sqlserver"):
            # MSSQL: UPDATE STATISTICS
            sql = f"UPDATE STATISTICS {table_name}"
        else:
            return {
                "table": table_name,
                "analyzed": False,
                "message": f"Desteklenmeyen DB tipi: {db_type}",
            }

        result = adapter.execute_action(sql, RiskLevel.SAFE)

        _audit_action(
            target=adapter.display_name,
            sql=sql,
            risk="safe",
            result="success" if result.success else "failed",
            execution_time_ms=result.execution_time_ms,
        )

        return {
            "table": table_name,
            "db_type": db_type,
            "analyzed": result.success,
            "message": result.message,
            "execution_time_ms": result.execution_time_ms,
        }


def set_db_config(
    param_name: str,
    param_value: str,
    db_name: str = None,
) -> Dict[str, Any]:
    """
    Veritabanı konfigürasyon parametresi değiştir.
    PostgreSQL: ALTER SYSTEM SET
    MySQL: SET GLOBAL

    Risk: HIGH

    Args:
        param_name: Parametre adı (work_mem, shared_buffers, vb.)
        param_value: Yeni değer
        db_name: Veritabanı adı

    Returns:
        {"param": str, "old_value": str, "new_value": str, "applied": bool}
    """
    # Güvenlik: Bazı parametreleri engelle
    dangerous_params = [
        "data_directory", "config_file", "hba_file",
        "ident_file", "ssl_cert_file", "ssl_key_file",
    ]
    if param_name.lower() in dangerous_params:
        return {
            "param": param_name,
            "applied": False,
            "message": f"FORBIDDEN: '{param_name}' parametresi güvenlik nedeniyle değiştirilemez.",
        }

    with get_adapter(db_name) as adapter:
        db_type = adapter.target.db_type.lower()

        # Mevcut değeri al
        if db_type in ("postgresql", "postgres"):
            old_r = adapter.execute_query(
                "SELECT setting, unit FROM pg_settings WHERE name = %s",
                (param_name,),
            )
            old_value = str(old_r.rows[0][0]) if old_r.rows else "?"
            old_unit = str(old_r.rows[0][1] or "") if old_r.rows else ""

            sql = f"ALTER SYSTEM SET {param_name} = '{param_value}'"

        elif db_type in ("mysql", "mariadb"):
            old_r = adapter.execute_query(
                f"SHOW VARIABLES LIKE '{param_name}'"
            )
            old_value = str(old_r.rows[0][1]) if old_r.rows else "?"
            old_unit = ""

            sql = f"SET GLOBAL {param_name} = '{param_value}'"

        elif db_type == "oracle":
            old_r = adapter.execute_query(
                f"SELECT value FROM v$parameter WHERE name = '{param_name.lower()}'"
            )
            old_value = str(old_r.rows[0][0]) if old_r.rows else "?"
            old_unit = ""

            sql = f"ALTER SYSTEM SET {param_name} = '{param_value}' SCOPE=BOTH"

        elif db_type in ("mssql", "sqlserver"):
            old_r = adapter.execute_query(
                f"SELECT CAST(value_in_use AS NVARCHAR(200)) FROM sys.configurations WHERE name = '{param_name}'"
            )
            old_value = str(old_r.rows[0][0]) if old_r.rows else "?"
            old_unit = ""

            sql = f"EXEC sp_configure '{param_name}', {param_value}; RECONFIGURE"

        else:
            return {
                "param": param_name,
                "applied": False,
                "message": f"Desteklenmeyen DB tipi: {db_type}",
            }

        # Forbidden SQL check
        forbidden = _check_sql_forbidden(sql)
        if forbidden:
            return {
                "param": param_name,
                "applied": False,
                "message": forbidden,
            }

        result = adapter.execute_action(sql, RiskLevel.HIGH)

        _audit_action(
            target=adapter.display_name,
            sql=sql,
            risk="high",
            result="success" if result.success else "failed",
            execution_time_ms=result.execution_time_ms,
        )

        return {
            "param": param_name,
            "db_type": db_type,
            "old_value": f"{old_value}{old_unit}",
            "new_value": param_value,
            "applied": result.success,
            "message": result.message,
            "note": (
                "PostgreSQL: pg_reload_conf() veya restart gerekebilir."
                if db_type in ("postgresql", "postgres")
                else "Oracle: SCOPE=BOTH — hemen aktif + spfile."
                if db_type == "oracle"
                else "MSSQL: RECONFIGURE ile hemen aktif."
                if db_type in ("mssql", "sqlserver")
                else "MySQL: Hemen aktif (SET GLOBAL)."
            ),
            "execution_time_ms": result.execution_time_ms,
        }


def reload_db_config(db_name: str = None) -> Dict[str, Any]:
    """
    Veritabanı konfigürasyonunu yeniden yükle.
    PostgreSQL: SELECT pg_reload_conf()
    MySQL: FLUSH PRIVILEGES

    Risk: MEDIUM

    Args:
        db_name: Veritabanı adı

    Returns:
        {"reloaded": bool, "message": str}
    """
    with get_adapter(db_name) as adapter:
        db_type = adapter.target.db_type.lower()

        if db_type in ("postgresql", "postgres"):
            sql = "SELECT pg_reload_conf()"
        elif db_type in ("mysql", "mariadb"):
            sql = "FLUSH PRIVILEGES"
        elif db_type == "oracle":
            # Oracle: ALTER SYSTEM — spfile parametreleri restart gerektirir
            sql = "ALTER SYSTEM FLUSH SHARED_POOL"
        elif db_type in ("mssql", "sqlserver"):
            # MSSQL: RECONFIGURE
            sql = "RECONFIGURE"
        else:
            return {
                "reloaded": False,
                "message": f"Desteklenmeyen DB tipi: {db_type}",
            }

        result = adapter.execute_action(sql, RiskLevel.MEDIUM)

        _audit_action(
            target=adapter.display_name,
            sql=sql,
            risk="medium",
            result="success" if result.success else "failed",
        )

        return {
            "db_type": db_type,
            "reloaded": result.success,
            "message": result.message,
            "execution_time_ms": result.execution_time_ms,
        }


def kill_long_running_queries(
    threshold_sec: float = 300,
    db_name: str = None,
) -> Dict[str, Any]:
    """
    Belirtilen süreden uzun çalışan TÜM sorguları öldür.
    ⚠️ Dikkatli kullanın!

    Risk: HIGH

    Args:
        threshold_sec: Süre eşiği (saniye, varsayılan 300s = 5dk)
        db_name: Veritabanı adı

    Returns:
        {"killed_count": int, "killed_pids": List[int], "message": str}
    """
    with get_adapter(db_name) as adapter:
        db_type = adapter.target.db_type.lower()

        if db_type in ("postgresql", "postgres"):
            # Uzun çalışan sorguları bul
            r = adapter.execute_query("""
                SELECT pid, usename, 
                       EXTRACT(EPOCH FROM (now() - query_start))::int as duration,
                       query
                FROM pg_stat_activity
                WHERE state = 'active'
                  AND pid != pg_backend_pid()
                  AND now() - query_start > interval '%s seconds'
                ORDER BY duration DESC
            """ % int(threshold_sec))

            killed = []
            failed = []
            for row in r.rows:
                pid = int(row[0])
                result = adapter.execute_action(
                    f"SELECT pg_terminate_backend({pid})",
                    RiskLevel.MEDIUM,
                )
                if result.success:
                    killed.append({
                        "pid": pid,
                        "user": str(row[1]),
                        "duration_sec": int(row[2]),
                        "query": str(row[3])[:100],
                    })
                else:
                    failed.append(pid)

        elif db_type in ("mysql", "mariadb"):
            r = adapter.execute_query("""
                SELECT ID, USER, TIME, INFO
                FROM information_schema.PROCESSLIST
                WHERE COMMAND != 'Sleep'
                  AND TIME > %s
                ORDER BY TIME DESC
            """, (int(threshold_sec),))

            killed = []
            failed = []
            for row in r.rows:
                pid = int(row[0])
                result = adapter.execute_action(f"KILL {pid}", RiskLevel.MEDIUM)
                if result.success:
                    killed.append({
                        "pid": pid,
                        "user": str(row[1]),
                        "duration_sec": int(row[2]),
                        "query": str(row[3] or "")[:100],
                    })
                else:
                    failed.append(pid)

        elif db_type == "oracle":
            r = adapter.execute_query(f"""
                SELECT s.sid, s.serial#, s.username, s.last_call_et,
                       q.sql_text
                FROM v$session s
                LEFT JOIN v$sqlarea q ON s.sql_id = q.sql_id
                WHERE s.type = 'USER' AND s.status = 'ACTIVE'
                  AND s.last_call_et > {int(threshold_sec)}
                ORDER BY s.last_call_et DESC
            """)

            killed = []
            failed = []
            for row in r.rows:
                sid = int(row[0])
                serial = int(row[1])
                result = adapter.execute_action(
                    f"ALTER SYSTEM KILL SESSION '{sid},{serial}' IMMEDIATE",
                    RiskLevel.MEDIUM,
                )
                if result.success:
                    killed.append({
                        "pid": sid,
                        "user": str(row[2] or ""),
                        "duration_sec": int(row[3]),
                        "query": str(row[4] or "")[:100],
                    })
                else:
                    failed.append(sid)

        elif db_type in ("mssql", "sqlserver"):
            r = adapter.execute_query(f"""
                SELECT r.session_id, s.login_name,
                       r.total_elapsed_time / 1000 AS duration_sec,
                       ISNULL(t.text, '')
                FROM sys.dm_exec_requests r
                JOIN sys.dm_exec_sessions s ON r.session_id = s.session_id
                OUTER APPLY sys.dm_exec_sql_text(r.sql_handle) t
                WHERE r.total_elapsed_time > {int(threshold_sec * 1000)}
                  AND r.session_id > 50
                ORDER BY r.total_elapsed_time DESC
            """)

            killed = []
            failed = []
            for row in r.rows:
                pid = int(row[0])
                result = adapter.execute_action(f"KILL {pid}", RiskLevel.MEDIUM)
                if result.success:
                    killed.append({
                        "pid": pid,
                        "user": str(row[1] or ""),
                        "duration_sec": int(row[2] or 0),
                        "query": str(row[3] or "")[:100],
                    })
                else:
                    failed.append(pid)

        else:
            return {
                "killed_count": 0,
                "message": f"Desteklenmeyen DB tipi: {db_type}",
            }

        _audit_action(
            target=adapter.display_name,
            sql=f"kill_long_running threshold={threshold_sec}s",
            risk="high",
            result=f"killed={len(killed)}, failed={len(failed)}",
        )

        return {
            "db_type": db_type,
            "threshold_sec": threshold_sec,
            "killed_count": len(killed),
            "killed": killed,
            "failed_pids": failed,
            "message": f"{len(killed)} sorgu sonlandırıldı"
                       + (f", {len(failed)} başarısız" if failed else ""),
        }


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _parse_table_name(table_name: str):
    """schema.table_name → (schema, table_name)"""
    if "." in table_name:
        parts = table_name.split(".", 1)
        return parts[0], parts[1]
    return "public", table_name


def _get_table_snapshot(adapter, schema: str, table_name: str) -> Dict[str, Any]:
    """Tablo anlık durumu — PostgreSQL ve MySQL destekli."""
    db_type = adapter.target.db_type.lower()
    try:
        if db_type in ("postgresql", "postgres"):
            r = adapter.execute_query("""
                SELECT n_live_tup, n_dead_tup,
                       pg_total_relation_size(relid) as total_size,
                       last_vacuum, last_autovacuum, last_analyze
                FROM pg_stat_user_tables
                WHERE schemaname = %s AND relname = %s
            """, (schema, table_name))
            if r.rows:
                return {
                    "live_rows": int(r.rows[0][0] or 0),
                    "dead_rows": int(r.rows[0][1] or 0),
                    "total_size_bytes": int(r.rows[0][2] or 0),
                    "total_size_mb": round(int(r.rows[0][2] or 0) / (1024 * 1024), 2),
                    "last_vacuum": str(r.rows[0][3]) if r.rows[0][3] else None,
                    "last_autovacuum": str(r.rows[0][4]) if r.rows[0][4] else None,
                    "last_analyze": str(r.rows[0][5]) if r.rows[0][5] else None,
                }
        elif db_type in ("mysql", "mariadb"):
            r = adapter.execute_query("""
                SELECT TABLE_ROWS,
                       DATA_LENGTH + INDEX_LENGTH AS total_size
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """, (schema, table_name))
            if r.rows:
                return {
                    "live_rows": int(r.rows[0][0] or 0),
                    "dead_rows": 0,
                    "total_size_bytes": int(r.rows[0][1] or 0),
                    "total_size_mb": round(int(r.rows[0][1] or 0) / (1024 * 1024), 2),
                }
        elif db_type == "oracle":
            owner = schema.upper() if schema != "public" else adapter.target.user.upper()
            r = adapter.execute_query(f"""
                SELECT t.num_rows, NVL(s.bytes, 0)
                FROM dba_tables t
                LEFT JOIN dba_segments s ON s.segment_name = t.table_name
                    AND s.owner = t.owner AND s.segment_type = 'TABLE'
                WHERE t.owner = '{owner}' AND t.table_name = '{table_name.upper()}'
            """)
            if r.rows:
                return {
                    "live_rows": int(r.rows[0][0] or 0),
                    "dead_rows": 0,
                    "total_size_bytes": int(r.rows[0][1] or 0),
                    "total_size_mb": round(int(r.rows[0][1] or 0) / (1024 * 1024), 2),
                }
        elif db_type in ("mssql", "sqlserver"):
            schema_name = schema if schema != "public" else "dbo"
            r = adapter.execute_query(f"""
                SELECT p.rows, SUM(a.total_pages) * 8 * 1024 AS total_bytes
                FROM sys.tables t
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0, 1)
                JOIN sys.allocation_units a ON p.partition_id = a.container_id
                WHERE s.name = '{schema_name}' AND t.name = '{table_name}'
                GROUP BY p.rows
            """)
            if r.rows:
                return {
                    "live_rows": int(r.rows[0][0] or 0),
                    "dead_rows": 0,
                    "total_size_bytes": int(r.rows[0][1] or 0),
                    "total_size_mb": round(int(r.rows[0][1] or 0) / (1024 * 1024), 2),
                }
    except Exception as e:
        logger.debug(f"Table snapshot hatası: {e}")

    return {}


# ─────────────────────────────────────────────
# Tool Registration
# ─────────────────────────────────────────────

def register_db_action_tools() -> None:
    """DB aksiyon araçlarını registry'ye kaydet."""
    registry = get_tool_registry()

    tools = [
        ToolDef(
            name="cancel_query",
            description="Çalışan sorguyu iptal et (pg_cancel_backend) — bağlantı açık kalır",
            category="db_action",
            func=cancel_query,
            args_schema={
                "pid": "int — Backend PID",
                "db_name": "str|None — Veritabanı adı",
            },
            risk_level="low",
            requires_db=True,
        ),
        ToolDef(
            name="kill_session",
            description="Oturumu tamamen sonlandır (pg_terminate_backend / KILL)",
            category="db_action",
            func=kill_session,
            args_schema={
                "pid": "int — Backend/Thread PID",
                "db_name": "str|None — Veritabanı adı",
            },
            risk_level="medium",
            requires_db=True,
        ),
        ToolDef(
            name="vacuum_table",
            description="VACUUM (ANALYZE) — dead tuple temizle, istatistik güncelle",
            category="db_action",
            func=vacuum_table,
            args_schema={
                "table_name": "str — Tablo adı (schema.tablo veya tablo)",
                "analyze": "bool — ANALYZE ekle (varsayılan: True)",
                "db_name": "str|None — Veritabanı adı",
            },
            risk_level="low",
            requires_db=True,
        ),
        ToolDef(
            name="vacuum_full_table",
            description="VACUUM FULL — tablo boyutunu küçült ⚠️ TABLO KİLİTLER",
            category="db_action",
            func=vacuum_full_table,
            args_schema={
                "table_name": "str — Tablo adı",
                "db_name": "str|None — Veritabanı adı",
            },
            risk_level="high",
            requires_db=True,
        ),
        ToolDef(
            name="reindex_table",
            description="REINDEX TABLE — bozuk/şişmiş index'leri yeniden oluştur",
            category="db_action",
            func=reindex_table,
            args_schema={
                "table_name": "str — Tablo adı",
                "db_name": "str|None — Veritabanı adı",
            },
            risk_level="medium",
            requires_db=True,
        ),
        ToolDef(
            name="analyze_table",
            description="ANALYZE — tablo istatistiklerini güncelle (planlayıcı iyileştirme)",
            category="db_action",
            func=analyze_table,
            args_schema={
                "table_name": "str — Tablo adı",
                "db_name": "str|None — Veritabanı adı",
            },
            risk_level="safe",
            requires_db=True,
        ),
        ToolDef(
            name="set_db_config",
            description="DB parametre değiştir (ALTER SYSTEM SET / SET GLOBAL) ⚠️ ONAY GEREKTİRİR",
            category="db_action",
            func=set_db_config,
            args_schema={
                "param_name": "str — Parametre adı (work_mem, shared_buffers...)",
                "param_value": "str — Yeni değer",
                "db_name": "str|None — Veritabanı adı",
            },
            risk_level="high",
            requires_db=True,
        ),
        ToolDef(
            name="reload_db_config",
            description="DB config yeniden yükle (pg_reload_conf / FLUSH PRIVILEGES)",
            category="db_action",
            func=reload_db_config,
            args_schema={
                "db_name": "str|None — Veritabanı adı",
            },
            risk_level="medium",
            requires_db=True,
        ),
        ToolDef(
            name="kill_long_running_queries",
            description="Belirtilen süreden uzun TÜM sorguları öldür ⚠️ DİKKATLİ KULLANIN",
            category="db_action",
            func=kill_long_running_queries,
            args_schema={
                "threshold_sec": "float — Süre eşiği saniye (varsayılan: 300)",
                "db_name": "str|None — Veritabanı adı",
            },
            risk_level="high",
            requires_db=True,
        ),
    ]

    for tool in tools:
        registry.register(tool)

    logger.info(f"DB action tools registered: {len(tools)} araç")
