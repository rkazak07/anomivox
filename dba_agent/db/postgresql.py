"""
PostgreSQL Adapter
══════════════════
PostgreSQL diagnostik sorguları.
Mevcut prometheus_service_docker/app.py'deki _diag_postgresql() fonksiyonundan
ilham alınmıştır. Orijinal koda DOKUNMAZ.
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

logger = logging.getLogger("dba_agent.db.postgresql")


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL veritabanı adapter'ı."""

    def __init__(self, target: DatabaseTarget):
        super().__init__(target)
        self._connection = None

    # ── Bağlantı Yönetimi ────────────────────

    def connect(self) -> None:
        import psycopg2
        self._connection = psycopg2.connect(
            host=self.target.host,
            port=self.target.port,
            user=self.target.user,
            password=self.target.password,
            dbname=self.target.database,
            connect_timeout=5,
            options="-c statement_timeout=10000",  # 10s default
        )
        self._connection.autocommit = True
        logger.info(f"Connected to PostgreSQL: {self.display_name}")

    def disconnect(self) -> None:
        if self._connection and not self._connection.closed:
            self._connection.close()
            logger.info(f"Disconnected from PostgreSQL: {self.display_name}")
        self._connection = None

    def is_connected(self) -> bool:
        return self._connection is not None and not self._connection.closed

    # ── Diagnostik Sorgular ──────────────────

    def execute_query(self, sql: str, params: Optional[tuple] = None,
                      timeout: int = 10) -> QueryResult:
        self.ensure_connected()
        start = time.time()
        try:
            cur = self._connection.cursor()
            cur.execute(f"SET statement_timeout = {timeout * 1000}")
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
            db_type="postgresql",
            host=self.target.host,
            database=self.target.database,
        )

        # Version
        r = self.execute_query("SELECT version()")
        if r.rows:
            health.version = str(r.rows[0][0]).split(",")[0]

        # Uptime
        r = self.execute_query(
            "SELECT EXTRACT(EPOCH FROM (now() - pg_postmaster_start_time()))::int"
        )
        if r.rows:
            health.uptime_sec = int(r.rows[0][0] or 0)

        # Connections
        r = self.execute_query(
            "SELECT count(*) FROM pg_stat_activity WHERE state IS NOT NULL"
        )
        if r.rows:
            health.active_connections = int(r.rows[0][0] or 0)

        r = self.execute_query("SHOW max_connections")
        if r.rows:
            health.max_connections = int(r.rows[0][0] or 0)

        # DB size
        r = self.execute_query(
            "SELECT pg_database_size(current_database()) / (1024*1024)::float"
        )
        if r.rows:
            health.database_size_mb = float(r.rows[0][0] or 0)

        # Cache hit ratio
        r = self.execute_query("""
            SELECT COALESCE(
                sum(blks_hit)::float / NULLIF(sum(blks_hit) + sum(blks_read), 0),
                0
            ) FROM pg_stat_database WHERE datname = current_database()
        """)
        if r.rows:
            health.cache_hit_ratio = float(r.rows[0][0] or 0)

        # Long running queries
        r = self.execute_query("""
            SELECT count(*) FROM pg_stat_activity
            WHERE state = 'active'
              AND query NOT LIKE '%pg_stat_activity%'
              AND now() - query_start > interval '1 second'
        """)
        if r.rows:
            health.long_running_queries = int(r.rows[0][0] or 0)

        # Blocked locks
        r = self.execute_query("""
            SELECT count(*) FROM pg_locks WHERE NOT granted
        """)
        if r.rows:
            health.blocked_locks = int(r.rows[0][0] or 0)

        return health

    def get_active_connections(self) -> List[ConnectionInfo]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT pid, usename, datname, state,
                   COALESCE(query, ''),
                   EXTRACT(EPOCH FROM (now() - query_start))::float AS duration,
                   COALESCE(client_addr::text, ''),
                   COALESCE(application_name, '')
            FROM pg_stat_activity
            WHERE state IS NOT NULL
              AND pid != pg_backend_pid()
            ORDER BY duration DESC NULLS LAST
        """)
        return [
            ConnectionInfo(
                pid=int(row[0]),
                user=str(row[1] or ""),
                database=str(row[2] or ""),
                state=str(row[3] or ""),
                query=str(row[4] or ""),
                duration_sec=float(row[5] or 0),
                client_addr=str(row[6] or ""),
                application_name=str(row[7] or ""),
            )
            for row in r.rows
        ]

    def get_long_running_queries(self, threshold_sec: float = 1.0) -> List[ConnectionInfo]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT pid, usename, datname, state,
                   COALESCE(query, ''),
                   EXTRACT(EPOCH FROM (now() - query_start))::float AS duration,
                   COALESCE(client_addr::text, ''),
                   COALESCE(application_name, '')
            FROM pg_stat_activity
            WHERE state = 'active'
              AND query NOT LIKE '%%pg_stat_activity%%'
              AND now() - query_start > interval '%s seconds'
              AND pid != pg_backend_pid()
            ORDER BY duration DESC
        """ % threshold_sec)
        return [
            ConnectionInfo(
                pid=int(row[0]),
                user=str(row[1] or ""),
                database=str(row[2] or ""),
                state=str(row[3] or ""),
                query=str(row[4] or ""),
                duration_sec=float(row[5] or 0),
                client_addr=str(row[6] or ""),
                application_name=str(row[7] or ""),
            )
            for row in r.rows
        ]

    def get_blocked_locks(self) -> List[LockInfo]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT blocked.pid AS blocked_pid,
                   blocked_activity.query AS blocked_query,
                   blocking.pid AS blocking_pid,
                   blocking_activity.query AS blocking_query,
                   EXTRACT(EPOCH FROM (now() - blocked_activity.query_start))::float
            FROM pg_catalog.pg_locks blocked
            JOIN pg_catalog.pg_stat_activity blocked_activity
                ON blocked_activity.pid = blocked.pid
            JOIN pg_catalog.pg_locks blocking
                ON blocking.locktype = blocked.locktype
                AND blocking.database IS NOT DISTINCT FROM blocked.database
                AND blocking.relation IS NOT DISTINCT FROM blocked.relation
                AND blocking.page IS NOT DISTINCT FROM blocked.page
                AND blocking.tuple IS NOT DISTINCT FROM blocked.tuple
                AND blocking.virtualxid IS NOT DISTINCT FROM blocked.virtualxid
                AND blocking.transactionid IS NOT DISTINCT FROM blocked.transactionid
                AND blocking.classid IS NOT DISTINCT FROM blocked.classid
                AND blocking.objid IS NOT DISTINCT FROM blocked.objid
                AND blocking.objsubid IS NOT DISTINCT FROM blocked.objsubid
                AND blocking.pid != blocked.pid
            JOIN pg_catalog.pg_stat_activity blocking_activity
                ON blocking_activity.pid = blocking.pid
            WHERE NOT blocked.granted
            LIMIT 20
        """)
        return [
            LockInfo(
                pid=int(row[0]),
                lock_type="row",
                table="",
                mode="blocked",
                granted=False,
                waiting_pid=int(row[2]) if row[2] else None,
                duration_sec=float(row[4] or 0),
                query=str(row[1] or ""),
            )
            for row in r.rows
        ]

    def get_slow_queries(self, limit: int = 20) -> List[SlowQueryInfo]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT query, calls, total_exec_time, mean_exec_time, rows,
                   shared_blks_hit, shared_blks_read
            FROM pg_stat_statements
            WHERE query NOT LIKE '%%pg_stat%%'
            ORDER BY mean_exec_time DESC
            LIMIT %s
        """, (limit,))

        if not r.success or r.error:
            # pg_stat_statements extension yüklü olmayabilir
            logger.warning("pg_stat_statements not available, trying pg_stat_activity")
            return []

        return [
            SlowQueryInfo(
                query=str(row[0] or ""),
                calls=int(row[1] or 0),
                total_time_ms=float(row[2] or 0),
                mean_time_ms=float(row[3] or 0),
                rows=int(row[4] or 0),
                shared_blks_hit=int(row[5] or 0),
                shared_blks_read=int(row[6] or 0),
            )
            for row in r.rows
        ]

    def get_table_stats(self, schema: str = "public") -> List[TableStats]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT schemaname, relname,
                   n_live_tup, n_dead_tup,
                   pg_total_relation_size(schemaname || '.' || relname) AS total_size,
                   pg_indexes_size(schemaname || '.' || relname) AS idx_size,
                   last_vacuum, last_analyze,
                   seq_scan, idx_scan
            FROM pg_stat_user_tables
            WHERE schemaname = %s
            ORDER BY n_dead_tup DESC
            LIMIT 50
        """, (schema,))
        return [
            TableStats(
                schema=str(row[0] or ""),
                table_name=str(row[1] or ""),
                row_count=int(row[2] or 0),
                dead_rows=int(row[3] or 0),
                total_size_bytes=int(row[4] or 0),
                index_size_bytes=int(row[5] or 0),
                last_vacuum=row[6],
                last_analyze=row[7],
                seq_scan=int(row[8] or 0),
                idx_scan=int(row[9] or 0),
            )
            for row in r.rows
        ]

    def get_index_stats(self, schema: str = "public") -> List[IndexStats]:
        self.ensure_connected()
        r = self.execute_query("""
            SELECT schemaname, tablename, indexrelname,
                   pg_relation_size(indexrelid) AS idx_size,
                   idx_scan,
                   indisunique, indisprimary,
                   pg_get_indexdef(indexrelid) AS indexdef
            FROM pg_stat_user_indexes
            JOIN pg_index ON pg_stat_user_indexes.indexrelid = pg_index.indexrelid
            WHERE schemaname = %s
            ORDER BY idx_scan ASC
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
        ]

    def explain_query(self, sql: str) -> str:
        self.ensure_connected()
        # Güvenlik: sadece SELECT/WITH sorgularını EXPLAIN yap
        clean = sql.strip().upper()
        if not (clean.startswith("SELECT") or clean.startswith("WITH")):
            return "ERROR: Only SELECT/WITH queries can be explained"

        r = self.execute_query(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql}")
        if r.success and r.rows:
            return "\n".join(str(row[0]) for row in r.rows)
        return r.error or "No explain output"

    # ── Yazma İşlemleri ──────────────────────

    def execute_action(self, sql: str, risk: RiskLevel) -> ActionResult:
        """
        Yazma işlemi — onay sonrası çağrılır.
        Transaction wrapper ile çalışır.
        """
        self.ensure_connected()

        if risk == RiskLevel.FORBIDDEN:
            return ActionResult(
                success=False,
                message="FORBIDDEN: Bu işlem güvenlik politikası gereği engellenmiştir.",
            )

        start = time.time()
        try:
            # Autocommit kapatıp transaction başlat
            self._connection.autocommit = False
            cur = self._connection.cursor()
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
