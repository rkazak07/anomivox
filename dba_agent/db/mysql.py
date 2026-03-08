"""
MySQL/MariaDB Adapter
═════════════════════
MySQL diagnostik sorguları.
Mevcut prometheus_service_docker/app.py'deki _diag_mysql() fonksiyonundan
ilham alınmıştır. Orijinal koda DOKUNMAZ.
"""

import logging
import time
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

logger = logging.getLogger("dba_agent.db.mysql")


class MySQLAdapter(DatabaseAdapter):
    """MySQL / MariaDB veritabanı adapter'ı."""

    def __init__(self, target: DatabaseTarget):
        super().__init__(target)
        self._connection = None

    # ── Bağlantı Yönetimi ────────────────────

    def connect(self) -> None:
        import mysql.connector
        self._connection = mysql.connector.connect(
            host=self.target.host,
            port=self.target.port,
            user=self.target.user,
            password=self.target.password,
            database=self.target.database,
            connect_timeout=5,
            autocommit=True,
        )
        logger.info(f"Connected to MySQL: {self.display_name}")

    def disconnect(self) -> None:
        if self._connection and self._connection.is_connected():
            self._connection.close()
            logger.info(f"Disconnected from MySQL: {self.display_name}")
        self._connection = None

    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.is_connected()

    # ── Diagnostik Sorgular ──────────────────

    def execute_query(self, sql: str, params: Optional[tuple] = None,
                      timeout: int = 10) -> QueryResult:
        self.ensure_connected()
        start = time.time()
        try:
            cur = self._connection.cursor()
            # MAX_EXECUTION_TIME is MySQL 5.7.8+ only; not supported on MariaDB
            try:
                cur.execute(f"SET SESSION MAX_EXECUTION_TIME = {timeout * 1000}")
            except Exception:
                pass  # Silently skip on MariaDB / older MySQL
            cur.execute(sql, params)
            elapsed_ms = (time.time() - start) * 1000

            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return QueryResult(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    execution_time_ms=elapsed_ms,
                )
            else:
                return QueryResult(
                    row_count=cur.rowcount,
                    execution_time_ms=elapsed_ms,
                )
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            logger.error(f"Query error: {e}")
            return QueryResult(
                error=str(e),
                success=False,
                execution_time_ms=elapsed_ms,
            )

    def get_health(self) -> DatabaseHealth:
        self.ensure_connected()
        health = DatabaseHealth(
            db_type="mysql",
            host=self.target.host,
            database=self.target.database,
        )

        # Version
        r = self.execute_query("SELECT VERSION()")
        if r.rows:
            health.version = str(r.rows[0][0])

        # Uptime
        r = self.execute_query("SHOW STATUS LIKE 'Uptime'")
        if r.rows:
            health.uptime_sec = int(r.rows[0][1] or 0)

        # Connections
        r = self.execute_query(
            "SELECT COUNT(*) FROM information_schema.PROCESSLIST"
        )
        if r.rows:
            health.active_connections = int(r.rows[0][0] or 0)

        r = self.execute_query("SHOW VARIABLES LIKE 'max_connections'")
        if r.rows:
            health.max_connections = int(r.rows[0][1] or 0)

        # DB size
        r = self.execute_query("""
            SELECT SUM(data_length + index_length) / (1024*1024)
            FROM information_schema.TABLES
            WHERE table_schema = %s
        """, (self.target.database,))
        if r.rows and r.rows[0][0]:
            health.database_size_mb = float(r.rows[0][0])

        # Buffer pool hit ratio
        r = self.execute_query("""
            SELECT
                (1 - (
                    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
                     WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads')
                    /
                    NULLIF((SELECT VARIABLE_VALUE FROM performance_schema.global_status
                     WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests'), 0)
                )) AS hit_ratio
        """)
        if r.rows and r.rows[0][0]:
            health.cache_hit_ratio = float(r.rows[0][0])

        return health

    def get_active_connections(self) -> List[ConnectionInfo]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT ID, USER, DB, COMMAND,
                   COALESCE(INFO, ''),
                   TIME,
                   COALESCE(HOST, '')
            FROM information_schema.PROCESSLIST
            ORDER BY TIME DESC
        """)
        return [
            ConnectionInfo(
                pid=int(row[0]),
                user=str(row[1] or ""),
                database=str(row[2] or ""),
                state=str(row[3] or ""),
                query=str(row[4] or ""),
                duration_sec=float(row[5] or 0),
                client_addr=str(row[6] or "").split(":")[0],
            )
            for row in r.rows
        ]

    def get_long_running_queries(self, threshold_sec: float = 1.0) -> List[ConnectionInfo]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT ID, USER, DB, COMMAND,
                   COALESCE(INFO, ''),
                   TIME,
                   COALESCE(HOST, '')
            FROM information_schema.PROCESSLIST
            WHERE COMMAND != 'Sleep'
              AND TIME > %s
            ORDER BY TIME DESC
        """, (int(threshold_sec),))
        return [
            ConnectionInfo(
                pid=int(row[0]),
                user=str(row[1] or ""),
                database=str(row[2] or ""),
                state=str(row[3] or ""),
                query=str(row[4] or ""),
                duration_sec=float(row[5] or 0),
                client_addr=str(row[6] or "").split(":")[0],
            )
            for row in r.rows
        ]

    def get_blocked_locks(self) -> List[LockInfo]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT r.trx_id AS waiting_trx_id,
                   r.trx_mysql_thread_id AS waiting_pid,
                   b.trx_id AS blocking_trx_id,
                   b.trx_mysql_thread_id AS blocking_pid,
                   r.trx_query AS waiting_query
            FROM information_schema.INNODB_LOCK_WAITS w
            JOIN information_schema.INNODB_TRX b ON b.trx_id = w.blocking_trx_id
            JOIN information_schema.INNODB_TRX r ON r.trx_id = w.requesting_trx_id
            LIMIT 20
        """)
        if not r.success:
            # MySQL 8.0+ uses performance_schema
            r = self.execute_query("""
                SELECT r.ENGINE_TRANSACTION_ID,
                       r.THREAD_ID,
                       b.ENGINE_TRANSACTION_ID,
                       b.THREAD_ID,
                       ''
                FROM performance_schema.data_lock_waits w
                JOIN performance_schema.data_locks bl ON bl.ENGINE_LOCK_ID = w.BLOCKING_ENGINE_LOCK_ID
                JOIN performance_schema.data_locks rl ON rl.ENGINE_LOCK_ID = w.REQUESTING_ENGINE_LOCK_ID
                JOIN information_schema.INNODB_TRX b ON b.trx_id = bl.ENGINE_TRANSACTION_ID
                JOIN information_schema.INNODB_TRX r ON r.trx_id = rl.ENGINE_TRANSACTION_ID
                LIMIT 20
            """)
        return [
            LockInfo(
                pid=int(row[1] or 0),
                lock_type="innodb",
                table="",
                mode="blocked",
                granted=False,
                waiting_pid=int(row[3] or 0),
                query=str(row[4] or ""),
            )
            for row in r.rows
        ] if r.success else []

    def get_slow_queries(self, limit: int = 20) -> List[SlowQueryInfo]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT DIGEST_TEXT, COUNT_STAR, SUM_TIMER_WAIT/1e9,
                   AVG_TIMER_WAIT/1e9, SUM_ROWS_EXAMINED
            FROM performance_schema.events_statements_summary_by_digest
            WHERE SCHEMA_NAME = %s
              AND DIGEST_TEXT IS NOT NULL
            ORDER BY AVG_TIMER_WAIT DESC
            LIMIT %s
        """, (self.target.database, limit))
        return [
            SlowQueryInfo(
                query=str(row[0] or ""),
                calls=int(row[1] or 0),
                total_time_ms=float(row[2] or 0),
                mean_time_ms=float(row[3] or 0),
                rows=int(row[4] or 0),
            )
            for row in r.rows
        ] if r.success else []

    def get_table_stats(self, schema: str = "") -> List[TableStats]:
        schema = schema or self.target.database
        self.ensure_connected()
        r = self.execute_query("""
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_ROWS,
                   DATA_LENGTH + INDEX_LENGTH AS total_size,
                   INDEX_LENGTH
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY total_size DESC
            LIMIT 50
        """, (schema,))
        return [
            TableStats(
                schema=str(row[0] or ""),
                table_name=str(row[1] or ""),
                row_count=int(row[2] or 0),
                total_size_bytes=int(row[3] or 0),
                index_size_bytes=int(row[4] or 0),
            )
            for row in r.rows
        ]

    def get_index_stats(self, schema: str = "") -> List[IndexStats]:
        schema = schema or self.target.database
        self.ensure_connected()
        r = self.execute_query("""
            SELECT TABLE_SCHEMA, TABLE_NAME, INDEX_NAME,
                   STAT_VALUE * @@innodb_page_size AS idx_size,
                   0 AS idx_scan,
                   NON_UNIQUE = 0 AS is_unique,
                   INDEX_NAME = 'PRIMARY' AS is_primary,
                   GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS columns
            FROM information_schema.STATISTICS s
            LEFT JOIN mysql.innodb_index_stats ist
                ON ist.database_name = s.TABLE_SCHEMA
                AND ist.table_name = s.TABLE_NAME
                AND ist.index_name = s.INDEX_NAME
                AND ist.stat_name = 'size'
            WHERE s.TABLE_SCHEMA = %s
            GROUP BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, STAT_VALUE, NON_UNIQUE
            ORDER BY idx_size DESC
            LIMIT 100
        """, (schema,))
        return [
            IndexStats(
                schema=str(row[0] or ""),
                table_name=str(row[1] or ""),
                index_name=str(row[2] or ""),
                index_size_bytes=int(row[3] or 0),
                index_scans=int(row[4] or 0),
                is_unique=bool(row[5]),
                is_primary=bool(row[6]),
                columns=str(row[7] or ""),
            )
            for row in r.rows
        ] if r.success else []

    def explain_query(self, sql: str) -> str:
        self.ensure_connected()
        clean = sql.strip().upper()
        if not (clean.startswith("SELECT") or clean.startswith("WITH")):
            return "ERROR: Only SELECT/WITH queries can be explained"

        r = self.execute_query(f"EXPLAIN {sql}")
        if r.success and r.rows:
            lines = ["\t".join(r.columns)]
            for row in r.rows:
                lines.append("\t".join(str(c) for c in row))
            return "\n".join(lines)
        return r.error or "No explain output"

    # ── Yazma İşlemleri ──────────────────────

    def execute_action(self, sql: str, risk: RiskLevel) -> ActionResult:
        self.ensure_connected()
        if risk == RiskLevel.FORBIDDEN:
            return ActionResult(
                success=False,
                message="FORBIDDEN: Bu işlem güvenlik politikası gereği engellenmiştir.",
            )

        start = time.time()
        try:
            cur = self._connection.cursor()
            self._connection.autocommit = False
            cur.execute(sql)
            elapsed_ms = (time.time() - start) * 1000
            self._connection.commit()
            self._connection.autocommit = True
            return ActionResult(
                success=True,
                message=f"OK: {cur.rowcount} rows affected",
                execution_time_ms=elapsed_ms,
                affected_rows=cur.rowcount or 0,
            )
        except Exception as e:
            self._connection.rollback()
            self._connection.autocommit = True
            elapsed_ms = (time.time() - start) * 1000
            logger.error(f"Action error: {e}")
            return ActionResult(
                success=False,
                message=str(e),
                execution_time_ms=elapsed_ms,
            )
