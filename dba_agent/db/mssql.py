"""
Microsoft SQL Server Adapter
═════════════════════════════
MSSQL diagnostik sorguları ve aksiyon yürütme.
Driver: pymssql (FreeTDS tabanlı — ODBC driver gerektirmez)
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from dba_agent.config import DatabaseTarget
from dba_agent.db.adapter import (
    ActionResult,
    ConnectionInfo,
    DatabaseAdapter,
    DatabaseHealth,
    IndexStats,
    LockInfo,
    QueryResult,
    RiskLevel,
    SlowQueryInfo,
    TableStats,
)

logger = logging.getLogger("dba_agent.db.mssql")


class MSSQLAdapter(DatabaseAdapter):
    """Microsoft SQL Server adapter'ı (pymssql)."""

    def __init__(self, target: DatabaseTarget):
        super().__init__(target)
        self._connection = None

    # ── Bağlantı Yönetimi ────────────────────

    def connect(self) -> None:
        import pymssql
        self._connection = pymssql.connect(
            server=self.target.host,
            port=self.target.port,
            user=self.target.user,
            password=self.target.password,
            database=self.target.database,
            login_timeout=5,
            timeout=10,
            autocommit=True,
        )
        logger.info(f"Connected to MSSQL: {self.display_name}")

    def disconnect(self) -> None:
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            logger.info(f"Disconnected from MSSQL: {self.display_name}")
        self._connection = None

    def is_connected(self) -> bool:
        if self._connection is None:
            return False
        try:
            cur = self._connection.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            return True
        except Exception:
            return False

    # ── Diagnostik Sorgular ──────────────────

    def execute_query(self, sql: str, params: Optional[tuple] = None,
                      timeout: int = 10) -> QueryResult:
        self.ensure_connected()
        start = time.time()
        try:
            cur = self._connection.cursor()
            cur.execute(sql, params or ())
            elapsed_ms = (time.time() - start) * 1000

            if cur.description:
                columns = [desc[0].lower() for desc in cur.description]
                rows = cur.fetchall()
                return QueryResult(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    execution_time_ms=elapsed_ms,
                )
            return QueryResult(
                row_count=cur.rowcount if cur.rowcount >= 0 else 0,
                execution_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            return QueryResult(
                error=str(e)[:300],
                success=False,
                execution_time_ms=elapsed_ms,
            )

    def get_health(self) -> DatabaseHealth:
        self.ensure_connected()
        health = DatabaseHealth(
            db_type="mssql",
            host=self.target.host,
            database=self.target.database,
        )

        # Version
        try:
            r = self.execute_query("SELECT @@VERSION")
            if r.rows:
                health.version = str(r.rows[0][0])[:120]
        except Exception:
            pass

        # Uptime
        try:
            r = self.execute_query("""
                SELECT DATEDIFF(SECOND, login_time, GETDATE())
                FROM sys.dm_exec_sessions WHERE session_id = 1
            """)
            if r.rows:
                health.uptime_sec = int(r.rows[0][0] or 0)
        except Exception:
            pass

        # Connections
        try:
            r = self.execute_query("""
                SELECT COUNT(*) FROM sys.dm_exec_sessions
                WHERE is_user_process = 1
            """)
            if r.rows:
                health.active_connections = int(r.rows[0][0])
        except Exception:
            pass

        try:
            r = self.execute_query(
                "SELECT CAST(value_in_use AS INT) FROM sys.configurations "
                "WHERE name = 'user connections'"
            )
            if r.rows:
                val = int(r.rows[0][0] or 0)
                health.max_connections = val if val > 0 else 32767
        except Exception:
            health.max_connections = 32767

        # Database size
        try:
            r = self.execute_query("""
                SELECT SUM(size) * 8.0 / 1024 FROM sys.database_files
            """)
            if r.rows and r.rows[0][0]:
                health.database_size_mb = float(r.rows[0][0])
        except Exception:
            pass

        # Buffer cache hit ratio
        try:
            r = self.execute_query("""
                SELECT
                    CAST(a.cntr_value AS FLOAT) / CAST(b.cntr_value AS FLOAT) AS hit_ratio
                FROM sys.dm_os_performance_counters a
                JOIN sys.dm_os_performance_counters b
                    ON a.object_name = b.object_name
                WHERE a.counter_name = 'Buffer cache hit ratio'
                  AND b.counter_name = 'Buffer cache hit ratio base'
                  AND b.cntr_value > 0
            """)
            if r.rows and r.rows[0][0]:
                health.cache_hit_ratio = float(r.rows[0][0])
        except Exception:
            pass

        # Long running queries
        try:
            r = self.execute_query("""
                SELECT COUNT(*) FROM sys.dm_exec_requests
                WHERE total_elapsed_time > 5000
                  AND session_id > 50
            """)
            if r.rows:
                health.long_running_queries = int(r.rows[0][0])
        except Exception:
            pass

        # Blocked sessions
        try:
            r = self.execute_query("""
                SELECT COUNT(*) FROM sys.dm_exec_requests
                WHERE blocking_session_id > 0
            """)
            if r.rows:
                health.blocked_locks = int(r.rows[0][0])
        except Exception:
            pass

        return health

    def get_active_connections(self) -> List[ConnectionInfo]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT s.session_id, s.login_name, s.host_name, s.status,
                   ISNULL(t.text, ''),
                   DATEDIFF(SECOND, s.last_request_start_time, GETDATE()),
                   s.host_name, s.program_name
            FROM sys.dm_exec_sessions s
            LEFT JOIN sys.dm_exec_requests r ON s.session_id = r.session_id
            OUTER APPLY sys.dm_exec_sql_text(r.sql_handle) t
            WHERE s.is_user_process = 1
            ORDER BY s.last_request_start_time DESC
        """)
        conns = []
        for row in r.rows:
            conns.append(ConnectionInfo(
                pid=int(row[0]),
                user=str(row[1] or ""),
                database=str(row[2] or ""),
                state=str(row[3] or ""),
                query=str(row[4] or "")[:500],
                duration_sec=float(row[5] or 0),
                client_addr=str(row[6] or ""),
                application_name=str(row[7] or ""),
            ))
        return conns

    def get_long_running_queries(self, threshold_sec: float = 1.0) -> List[ConnectionInfo]:
        self.ensure_connected()
        threshold_ms = int(threshold_sec * 1000)
        r = self.execute_query(f"""
            SELECT r.session_id, s.login_name, DB_NAME(r.database_id),
                   r.status, ISNULL(t.text, ''),
                   r.total_elapsed_time / 1000.0,
                   s.host_name, s.program_name
            FROM sys.dm_exec_requests r
            JOIN sys.dm_exec_sessions s ON r.session_id = s.session_id
            OUTER APPLY sys.dm_exec_sql_text(r.sql_handle) t
            WHERE r.total_elapsed_time > {threshold_ms}
              AND r.session_id > 50
            ORDER BY r.total_elapsed_time DESC
        """)
        conns = []
        for row in r.rows:
            conns.append(ConnectionInfo(
                pid=int(row[0]),
                user=str(row[1] or ""),
                database=str(row[2] or ""),
                state=str(row[3] or ""),
                query=str(row[4] or "")[:500],
                duration_sec=float(row[5] or 0),
                client_addr=str(row[6] or ""),
                application_name=str(row[7] or ""),
            ))
        return conns

    def get_blocked_locks(self) -> List[LockInfo]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT r.session_id, r.blocking_session_id,
                   r.wait_type, OBJECT_NAME(r.object_id),
                   r.wait_time / 1000.0,
                   ISNULL(t.text, '')
            FROM sys.dm_exec_requests r
            OUTER APPLY sys.dm_exec_sql_text(r.sql_handle) t
            WHERE r.blocking_session_id > 0
        """)
        locks = []
        for row in r.rows:
            locks.append(LockInfo(
                pid=int(row[1]),  # blocking session
                lock_type=str(row[2] or ""),
                table=str(row[3] or ""),
                mode=str(row[2] or ""),
                granted=False,
                waiting_pid=int(row[0]),
                duration_sec=float(row[4] or 0),
                query=str(row[5] or "")[:500],
            ))
        return locks

    def get_slow_queries(self, limit: int = 20) -> List[SlowQueryInfo]:
        self.ensure_connected()
        r = self.execute_query(f"""
            SELECT TOP {limit}
                ISNULL(t.text, ''),
                qs.execution_count,
                qs.total_elapsed_time / 1000.0,
                CASE WHEN qs.execution_count > 0
                     THEN qs.total_elapsed_time / qs.execution_count / 1000.0
                     ELSE 0 END,
                qs.total_rows,
                qs.total_logical_reads,
                qs.total_physical_reads
            FROM sys.dm_exec_query_stats qs
            CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t
            WHERE qs.execution_count > 0
            ORDER BY qs.total_elapsed_time DESC
        """)
        queries = []
        for row in r.rows:
            queries.append(SlowQueryInfo(
                query=str(row[0] or "")[:500],
                calls=int(row[1] or 0),
                total_time_ms=float(row[2] or 0),
                mean_time_ms=float(row[3] or 0),
                rows=int(row[4] or 0),
                shared_blks_hit=int(row[5] or 0),   # logical_reads
                shared_blks_read=int(row[6] or 0),   # physical_reads
            ))
        return queries

    def get_table_stats(self, schema: str = "public") -> List[TableStats]:
        self.ensure_connected()
        schema_name = schema if schema != "public" else "dbo"
        r = self.execute_query(f"""
            SELECT s.name AS schema_name, t.name AS table_name,
                   p.rows,
                   SUM(a.total_pages) * 8 * 1024 AS total_bytes,
                   SUM(CASE WHEN i.type_desc = 'NONCLUSTERED' THEN a.used_pages * 8 * 1024 ELSE 0 END) AS index_bytes,
                   STATS_DATE(t.object_id, 1) AS last_stats_update
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0, 1)
            JOIN sys.allocation_units a ON p.partition_id = a.container_id
            LEFT JOIN sys.indexes i ON t.object_id = i.object_id
            WHERE s.name = '{schema_name}'
            GROUP BY s.name, t.name, p.rows, t.object_id
            ORDER BY SUM(a.total_pages) DESC
        """)
        tables = []
        for row in r.rows:
            tables.append(TableStats(
                schema=str(row[0] or ""),
                table_name=str(row[1] or ""),
                row_count=int(row[2] or 0),
                total_size_bytes=int(row[3] or 0),
                index_size_bytes=int(row[4] or 0),
                last_analyze=row[5] if isinstance(row[5], datetime) else None,
            ))
        return tables

    def get_index_stats(self, schema: str = "public") -> List[IndexStats]:
        self.ensure_connected()
        schema_name = schema if schema != "public" else "dbo"
        r = self.execute_query(f"""
            SELECT s.name AS schema_name, t.name AS table_name,
                   i.name AS index_name,
                   SUM(a.used_pages) * 8 * 1024 AS index_bytes,
                   ISNULL(us.user_seeks + us.user_scans + us.user_lookups, 0) AS scans,
                   i.is_unique, i.is_primary_key,
                   STUFF((
                       SELECT ', ' + c.name
                       FROM sys.index_columns ic
                       JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                       WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id
                       ORDER BY ic.key_ordinal
                       FOR XML PATH('')
                   ), 1, 2, '') AS columns
            FROM sys.indexes i
            JOIN sys.tables t ON i.object_id = t.object_id
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            LEFT JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
            LEFT JOIN sys.allocation_units a ON p.partition_id = a.container_id
            LEFT JOIN sys.dm_db_index_usage_stats us ON i.object_id = us.object_id
                AND i.index_id = us.index_id AND us.database_id = DB_ID()
            WHERE s.name = '{schema_name}' AND i.name IS NOT NULL
            GROUP BY s.name, t.name, i.name, i.is_unique, i.is_primary_key,
                     us.user_seeks, us.user_scans, us.user_lookups,
                     i.object_id, i.index_id
            ORDER BY SUM(a.used_pages) DESC
        """)
        indexes = []
        for row in r.rows:
            indexes.append(IndexStats(
                schema=str(row[0] or ""),
                table_name=str(row[1] or ""),
                index_name=str(row[2] or ""),
                index_size_bytes=int(row[3] or 0),
                index_scans=int(row[4] or 0),
                is_unique=bool(row[5]),
                is_primary=bool(row[6]),
                columns=str(row[7] or ""),
            ))
        return indexes

    def explain_query(self, sql: str) -> str:
        self.ensure_connected()
        try:
            cur = self._connection.cursor()
            cur.execute("SET SHOWPLAN_TEXT ON")
            cur.execute(sql)
            rows = cur.fetchall()
            cur.execute("SET SHOWPLAN_TEXT OFF")
            return "\n".join(str(r[0]) for r in rows)
        except Exception as e:
            return f"EXPLAIN error: {e}"

    # ── Yazma İşlemleri ──────────────────────

    def execute_action(self, sql: str, risk: RiskLevel) -> ActionResult:
        self.ensure_connected()
        start = time.time()
        try:
            cur = self._connection.cursor()
            cur.execute(sql)
            elapsed_ms = (time.time() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Executed: {sql[:100]}",
                execution_time_ms=elapsed_ms,
                affected_rows=cur.rowcount if cur.rowcount >= 0 else 0,
            )
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            return ActionResult(
                success=False,
                message=str(e)[:300],
                execution_time_ms=elapsed_ms,
            )
