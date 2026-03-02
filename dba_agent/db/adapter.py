"""
Database Adapter — Abstract Base
═════════════════════════════════
Tüm veritabanı tipleri için ortak arayüz.
Mevcut prometheus_service_docker/app.py'deki multi-DB pattern'den türetildi.
Orijinal koda DOKUNMAZ — kendi soyutlamasını sağlar.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from dba_agent.config import DatabaseTarget

logger = logging.getLogger("dba_agent.db")


# ─────────────────────────────────────────────
# Veri Modelleri
# ─────────────────────────────────────────────

class RiskLevel(Enum):
    """İşlem risk seviyesi."""
    SAFE = "safe"           # 🟢 SELECT, EXPLAIN — otomatik
    LOW = "low"             # 🟡 CREATE INDEX CONCURRENTLY, ANALYZE
    MEDIUM = "medium"       # 🟠 ALTER TABLE, REINDEX
    HIGH = "high"           # 🔴 DROP INDEX, KILL SESSION
    FORBIDDEN = "forbidden" # ⛔ DROP TABLE, TRUNCATE


@dataclass
class QueryResult:
    """Sorgu sonucu."""
    columns: List[str] = field(default_factory=list)
    rows: List[Tuple] = field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0
    error: Optional[str] = None
    success: bool = True

    @property
    def as_dicts(self) -> List[Dict[str, Any]]:
        """Satırları dict listesi olarak döndür."""
        return [dict(zip(self.columns, row)) for row in self.rows]

    @property
    def summary(self) -> str:
        """Kısa özet."""
        if self.error:
            return f"ERROR: {self.error}"
        return f"{self.row_count} rows in {self.execution_time_ms:.0f}ms"


@dataclass
class ConnectionInfo:
    """Aktif bağlantı bilgisi."""
    pid: int
    user: str
    database: str
    state: str
    query: str = ""
    duration_sec: float = 0
    client_addr: str = ""
    application_name: str = ""


@dataclass
class SlowQueryInfo:
    """Yavaş sorgu bilgisi."""
    query: str
    calls: int = 0
    total_time_ms: float = 0
    mean_time_ms: float = 0
    rows: int = 0
    shared_blks_hit: int = 0
    shared_blks_read: int = 0

    @property
    def hit_ratio(self) -> float:
        total = self.shared_blks_hit + self.shared_blks_read
        return self.shared_blks_hit / total if total > 0 else 0


@dataclass
class LockInfo:
    """Kilit bilgisi."""
    pid: int
    lock_type: str
    table: str
    mode: str
    granted: bool
    waiting_pid: Optional[int] = None
    duration_sec: float = 0
    query: str = ""


@dataclass
class TableStats:
    """Tablo istatistikleri."""
    schema: str
    table_name: str
    row_count: int = 0
    total_size_bytes: int = 0
    index_size_bytes: int = 0
    dead_rows: int = 0
    last_vacuum: Optional[datetime] = None
    last_analyze: Optional[datetime] = None
    seq_scan: int = 0
    idx_scan: int = 0

    @property
    def total_size_mb(self) -> float:
        return self.total_size_bytes / (1024 * 1024)

    @property
    def needs_vacuum(self) -> bool:
        return self.dead_rows > max(1000, self.row_count * 0.1)


@dataclass
class IndexStats:
    """Index istatistikleri."""
    schema: str
    table_name: str
    index_name: str
    index_size_bytes: int = 0
    index_scans: int = 0
    is_unique: bool = False
    is_primary: bool = False
    columns: str = ""

    @property
    def is_unused(self) -> bool:
        """Hiç kullanılmamış index."""
        return self.index_scans == 0 and not self.is_primary and not self.is_unique

    @property
    def index_size_mb(self) -> float:
        return self.index_size_bytes / (1024 * 1024)


@dataclass
class DatabaseHealth:
    """Veritabanı genel sağlık durumu."""
    db_type: str
    host: str
    database: str
    version: str = ""
    uptime_sec: int = 0
    active_connections: int = 0
    max_connections: int = 0
    database_size_mb: float = 0
    cache_hit_ratio: float = 0
    replication_lag_sec: float = 0
    long_running_queries: int = 0
    blocked_locks: int = 0
    dead_rows_total: int = 0

    @property
    def connection_usage_pct(self) -> float:
        if self.max_connections == 0:
            return 0
        return (self.active_connections / self.max_connections) * 100

    @property
    def health_score(self) -> int:
        """0-100 arası sağlık puanı."""
        score = 100
        if self.connection_usage_pct > 80:
            score -= 20
        if self.cache_hit_ratio < 0.95:
            score -= int((0.95 - self.cache_hit_ratio) * 100)
        if self.long_running_queries > 5:
            score -= 15
        if self.blocked_locks > 0:
            score -= 20
        return max(0, score)


@dataclass
class ActionResult:
    """Yazma işlemi sonucu."""
    success: bool
    message: str
    execution_time_ms: float = 0
    affected_rows: int = 0
    before_snapshot: Optional[Dict[str, Any]] = None
    after_snapshot: Optional[Dict[str, Any]] = None
    rollback_sql: Optional[str] = None


# ─────────────────────────────────────────────
# Abstract Adapter
# ─────────────────────────────────────────────

class DatabaseAdapter(ABC):
    """
    Veritabanı adapter arayüzü.
    Her DB tipi (PostgreSQL, MySQL, vb.) bu sınıfı implement eder.
    """

    def __init__(self, target: DatabaseTarget):
        self.target = target
        self._connection = None

    @property
    def display_name(self) -> str:
        return self.target.display_name

    # ── Bağlantı Yönetimi ────────────────────

    @abstractmethod
    def connect(self) -> None:
        """Bağlantı aç."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Bağlantı kapat."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Bağlantı durumu."""
        ...

    def ensure_connected(self) -> None:
        """Bağlantı yoksa aç."""
        if not self.is_connected():
            self.connect()

    # ── Diagnostik Sorgular (READ-ONLY) ──────

    @abstractmethod
    def execute_query(self, sql: str, params: Optional[tuple] = None,
                      timeout: int = 10) -> QueryResult:
        """Read-only SQL sorgusu çalıştır."""
        ...

    @abstractmethod
    def get_health(self) -> DatabaseHealth:
        """Genel sağlık durumu."""
        ...

    @abstractmethod
    def get_active_connections(self) -> List[ConnectionInfo]:
        """Aktif bağlantılar."""
        ...

    @abstractmethod
    def get_long_running_queries(self, threshold_sec: float = 1.0) -> List[ConnectionInfo]:
        """Uzun süren sorgular."""
        ...

    @abstractmethod
    def get_blocked_locks(self) -> List[LockInfo]:
        """Engellenmiş kilitler."""
        ...

    @abstractmethod
    def get_slow_queries(self, limit: int = 20) -> List[SlowQueryInfo]:
        """En yavaş sorgular (pg_stat_statements / performance_schema)."""
        ...

    @abstractmethod
    def get_table_stats(self, schema: str = "public") -> List[TableStats]:
        """Tablo istatistikleri."""
        ...

    @abstractmethod
    def get_index_stats(self, schema: str = "public") -> List[IndexStats]:
        """Index istatistikleri."""
        ...

    @abstractmethod
    def explain_query(self, sql: str) -> str:
        """EXPLAIN ANALYZE çıktısı."""
        ...

    # ── Yazma İşlemleri (ONAY GEREKTİRİR) ───

    @abstractmethod
    def execute_action(self, sql: str, risk: RiskLevel) -> ActionResult:
        """Yazma işlemi çalıştır (onay gerektirir)."""
        ...

    # ── Yardımcılar ──────────────────────────

    def get_diagnostic_summary(self) -> Dict[str, Any]:
        """
        Tek seferde tüm diagnostik bilgileri topla.
        Telegram'a gönderilecek özet için.
        """
        self.ensure_connected()
        health = self.get_health()
        return {
            "health": health,
            "health_score": health.health_score,
            "active_connections": len(self.get_active_connections()),
            "long_running": len(self.get_long_running_queries()),
            "blocked_locks": len(self.get_blocked_locks()),
            "top_slow_queries": self.get_slow_queries(limit=5),
        }

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.display_name}>"
