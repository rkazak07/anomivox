"""
Oracle Database Adapter
═══════════════════════
Oracle veritabanı diagnostik sorguları ve aksiyon yürütme.
Driver: oracledb (thin mode — Oracle Client gerektirmez)
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

logger = logging.getLogger("dba_agent.db.oracle")


class OracleAdapter(DatabaseAdapter):
    """Oracle veritabanı adapter'ı (oracledb thin mode)."""

    def __init__(self, target: DatabaseTarget):
        super().__init__(target)
        self._connection = None

    # ── Bağlantı Yönetimi ────────────────────

    def connect(self) -> None:
        import oracledb
        service_name = getattr(self.target, "service_name", "") or self.target.database
        dsn = oracledb.makedsn(
            self.target.host,
            self.target.port,
            service_name=service_name,
        )
        self._connection = oracledb.connect(
            user=self.target.user,
            password=self.target.password,
            dsn=dsn,
        )
        self._connection.autocommit = True
        logger.info(f"Connected to Oracle: {self.display_name}")

    def disconnect(self) -> None:
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            logger.info(f"Disconnected from Oracle: {self.display_name}")
        self._connection = None

    def is_connected(self) -> bool:
        if self._connection is None:
            return False
        try:
            self._connection.ping()
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
                row_count=cur.rowcount,
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
            db_type="oracle",
            host=self.target.host,
            database=self.target.database,
        )

        # Version
        try:
            r = self.execute_query("SELECT banner FROM v$version WHERE ROWNUM = 1")
            if r.rows:
                health.version = str(r.rows[0][0])
        except Exception:
            pass

        # Uptime
        try:
            r = self.execute_query(
                "SELECT (SYSDATE - startup_time) * 86400 FROM v$instance"
            )
            if r.rows:
                health.uptime_sec = int(r.rows[0][0])
        except Exception:
            pass

        # Connections
        try:
            r = self.execute_query(
                "SELECT COUNT(*) FROM v$session WHERE type = 'USER'"
            )
            if r.rows:
                health.active_connections = int(r.rows[0][0])
        except Exception:
            pass

        try:
            r = self.execute_query("SELECT value FROM v$parameter WHERE name = 'sessions'")
            if r.rows:
                health.max_connections = int(r.rows[0][0])
        except Exception:
            pass

        # Database size
        try:
            r = self.execute_query(
                "SELECT SUM(bytes) / 1024 / 1024 FROM dba_data_files"
            )
            if r.rows and r.rows[0][0]:
                health.database_size_mb = float(r.rows[0][0])
        except Exception:
            pass

        # Buffer cache hit ratio
        try:
            r = self.execute_query("""
                SELECT 1 - (phy.value / (cur.value + con.value)) AS hit_ratio
                FROM v$sysstat phy, v$sysstat cur, v$sysstat con
                WHERE phy.name = 'physical reads'
                  AND cur.name = 'db block gets'
                  AND con.name = 'consistent gets'
                  AND (cur.value + con.value) > 0
            """)
            if r.rows and r.rows[0][0]:
                health.cache_hit_ratio = float(r.rows[0][0])
        except Exception:
            pass

        # Long running queries
        try:
            r = self.execute_query("""
                SELECT COUNT(*) FROM v$session
                WHERE type = 'USER' AND status = 'ACTIVE'
                  AND last_call_et > 5
            """)
            if r.rows:
                health.long_running_queries = int(r.rows[0][0])
        except Exception:
            pass

        # Blocked locks
        try:
            r = self.execute_query("""
                SELECT COUNT(*) FROM v$lock
                WHERE block > 0
            """)
            if r.rows:
                health.blocked_locks = int(r.rows[0][0])
        except Exception:
            pass

        return health

    def get_active_connections(self) -> List[ConnectionInfo]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT sid, username, schemaname, status, sql_id,
                   last_call_et, machine, program
            FROM v$session
            WHERE type = 'USER' AND username IS NOT NULL
            ORDER BY last_call_et DESC
        """)
        conns = []
        for row in r.rows:
            conns.append(ConnectionInfo(
                pid=int(row[0]),
                user=str(row[1] or ""),
                database=str(row[2] or ""),
                state=str(row[3] or ""),
                query=str(row[4] or ""),  # SQL_ID
                duration_sec=float(row[5] or 0),
                client_addr=str(row[6] or ""),
                application_name=str(row[7] or ""),
            ))
        return conns

    def get_long_running_queries(self, threshold_sec: float = 1.0) -> List[ConnectionInfo]:
        self.ensure_connected()
        r = self.execute_query(f"""
            SELECT s.sid, s.username, s.schemaname, s.status,
                   q.sql_text, s.last_call_et, s.machine, s.program
            FROM v$session s
            LEFT JOIN v$sqlarea q ON s.sql_id = q.sql_id
            WHERE s.type = 'USER' AND s.status = 'ACTIVE'
              AND s.last_call_et > {int(threshold_sec)}
            ORDER BY s.last_call_et DESC
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
            SELECT w.sid AS waiting_sid,
                   h.sid AS holding_sid,
                   w.type AS lock_type,
                   o.object_name,
                   w.lmode,
                   w.request
            FROM v$lock w
            JOIN v$lock h ON w.id1 = h.id1 AND w.id2 = h.id2 AND h.block > 0
            LEFT JOIN v$locked_object lo ON lo.session_id = w.sid
            LEFT JOIN dba_objects o ON o.object_id = lo.object_id
            WHERE w.request > 0
        """)
        locks = []
        for row in r.rows:
            locks.append(LockInfo(
                pid=int(row[1]),  # holding SID
                lock_type=str(row[2] or ""),
                table=str(row[3] or ""),
                mode=f"lmode={row[4]}, request={row[5]}",
                granted=False,
                waiting_pid=int(row[0]),
            ))
        return locks

    def get_slow_queries(self, limit: int = 20) -> List[SlowQueryInfo]:
        self.ensure_connected()
        r = self.execute_query(f"""
            SELECT sql_text, executions, elapsed_time / 1000 AS total_ms,
                   CASE WHEN executions > 0 THEN elapsed_time / executions / 1000 ELSE 0 END AS mean_ms,
                   rows_processed, buffer_gets, disk_reads
            FROM v$sqlarea
            WHERE executions > 0
            ORDER BY elapsed_time DESC
            FETCH FIRST {limit} ROWS ONLY
        """)
        queries = []
        for row in r.rows:
            queries.append(SlowQueryInfo(
                query=str(row[0] or "")[:500],
                calls=int(row[1] or 0),
                total_time_ms=float(row[2] or 0),
                mean_time_ms=float(row[3] or 0),
                rows=int(row[4] or 0),
                shared_blks_hit=int(row[5] or 0),
                shared_blks_read=int(row[6] or 0),
            ))
        return queries

    def get_table_stats(self, schema: str = "public") -> List[TableStats]:
        self.ensure_connected()
        owner = schema.upper() if schema != "public" else self.target.user.upper()
        r = self.execute_query(f"""
            SELECT t.owner, t.table_name, t.num_rows,
                   s.bytes AS total_bytes,
                   NVL(i.index_bytes, 0),
                   t.last_analyzed
            FROM dba_tables t
            LEFT JOIN dba_segments s ON s.segment_name = t.table_name
                AND s.owner = t.owner AND s.segment_type = 'TABLE'
            LEFT JOIN (
                SELECT table_owner, table_name, SUM(bytes) AS index_bytes
                FROM dba_segments
                WHERE segment_type = 'INDEX'
                GROUP BY table_owner, table_name
            ) i ON i.table_owner = t.owner AND i.table_name = t.table_name
            WHERE t.owner = '{owner}'
            ORDER BY NVL(s.bytes, 0) DESC
            FETCH FIRST 50 ROWS ONLY
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
        owner = schema.upper() if schema != "public" else self.target.user.upper()
        r = self.execute_query(f"""
            SELECT i.owner, i.table_name, i.index_name,
                   NVL(s.bytes, 0),
                   i.uniqueness, i.index_type,
                   LISTAGG(ic.column_name, ', ') WITHIN GROUP (ORDER BY ic.column_position)
            FROM dba_indexes i
            LEFT JOIN dba_segments s ON s.segment_name = i.index_name
                AND s.owner = i.owner AND s.segment_type = 'INDEX'
            LEFT JOIN dba_ind_columns ic ON ic.index_owner = i.owner
                AND ic.index_name = i.index_name
            WHERE i.owner = '{owner}'
            GROUP BY i.owner, i.table_name, i.index_name,
                     s.bytes, i.uniqueness, i.index_type
            ORDER BY NVL(s.bytes, 0) DESC
            FETCH FIRST 50 ROWS ONLY
        """)
        indexes = []
        for row in r.rows:
            is_unique = str(row[4] or "") == "UNIQUE"
            indexes.append(IndexStats(
                schema=str(row[0] or ""),
                table_name=str(row[1] or ""),
                index_name=str(row[2] or ""),
                index_size_bytes=int(row[3] or 0),
                is_unique=is_unique,
                is_primary=False,  # Oracle PK constraints
                columns=str(row[6] or ""),
            ))
        return indexes

    def explain_query(self, sql: str) -> str:
        self.ensure_connected()
        try:
            cur = self._connection.cursor()
            cur.execute(f"EXPLAIN PLAN FOR {sql}")
            cur.execute(
                "SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY())"
            )
            rows = cur.fetchall()
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
