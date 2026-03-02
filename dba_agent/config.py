"""
DBA Agent Konfigürasyonu
════════════════════════
Tüm ayarlar env variable'lardan okunur, varsayılan değerler
mevcut configs/ modülüyle uyumludur.

NOT: Mevcut configs/model_config.py, diagnose_config.py vb.
     dosyalara DOKUNMAZ. Kendi konfigürasyonunu yönetir.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ─────────────────────────────────────────────
# LiteLLM / Inference Konfigürasyonu
# ─────────────────────────────────────────────

@dataclass
class InferenceConfig:
    """LiteLLM proxy ve model routing konfigürasyonu."""

    # LiteLLM proxy adresi (docker-compose içi)
    litellm_base_url: str = os.getenv(
        "LITELLM_BASE_URL", "http://litellm-proxy:4000"
    )
    litellm_api_key: str = os.getenv("LITELLM_API_KEY", "sk-anomivox-local")

    # Ollama direkt erişim (LiteLLM bypass — fallback)
    ollama_base_url: str = os.getenv(
        "OLLAMA_BASE_URL", "http://192.168.1.202:11434"
    )

    # Model tahsisi
    reasoning_model: str = os.getenv(
        "DBA_REASONING_MODEL", "ollama/llama3.1:8b"
    )
    sql_model: str = os.getenv(
        "DBA_SQL_MODEL", "ollama/sqlcoder:latest"
    )
    triage_model: str = os.getenv(
        "DBA_TRIAGE_MODEL", "ollama/llama3.2:1b"
    )
    fallback_model: str = os.getenv(
        "DBA_FALLBACK_MODEL", "ollama/llama3:8b"
    )

    # Timeout ayarları (saniye) — CPU-only Ollama için yüksek
    request_timeout: int = int(os.getenv("DBA_REQUEST_TIMEOUT", "300"))
    stream_timeout: int = int(os.getenv("DBA_STREAM_TIMEOUT", "360"))
    max_retries: int = int(os.getenv("DBA_MAX_RETRIES", "0"))

    # Context / generation limitleri — CPU-only için düşük
    max_context_tokens: int = int(os.getenv("DBA_MAX_CONTEXT", "2048"))
    max_output_tokens: int = int(os.getenv("DBA_MAX_OUTPUT", "512"))
    temperature: float = float(os.getenv("DBA_TEMPERATURE", "0.1"))


# ─────────────────────────────────────────────
# Veritabanı Konfigürasyonu (Monitör Edilen DB'ler)
# ─────────────────────────────────────────────

@dataclass
class DatabaseTarget:
    """Monitör edilecek tek bir veritabanı hedefi."""
    name: str
    db_type: str  # postgresql, mysql, mariadb, oracle, mssql
    host: str
    port: int
    user: str
    password: str
    database: str
    service_name: str = ""  # Oracle için
    ssl: bool = False
    readonly_user: str = ""
    readonly_password: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.db_type}@{self.host}:{self.port}/{self.database})"


@dataclass
class DatabaseConfig:
    """Tüm monitör edilen veritabanları."""

    targets: List[DatabaseTarget] = field(default_factory=list)

    # Sorgu timeout'ları (saniye)
    diagnostic_query_timeout: int = int(
        os.getenv("DBA_DIAG_QUERY_TIMEOUT", "10")
    )
    action_query_timeout: int = int(
        os.getenv("DBA_ACTION_QUERY_TIMEOUT", "60")
    )
    max_connections: int = int(
        os.getenv("DBA_MAX_CONNECTIONS", "3")
    )

    def __post_init__(self):
        """Env'den varsayılan target oluştur (mevcut configs ile uyumlu)."""
        if not self.targets:
            self.targets = [
                DatabaseTarget(
                    name=os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "anomivox")),
                    db_type=os.getenv("DB_TYPE", "postgresql"),
                    host=os.getenv("DB_HOST", os.getenv("PG_HOST", "postgres_db")),
                    port=int(os.getenv("DB_PORT", os.getenv("PG_PORT", "5432"))),
                    user=os.getenv("DB_USER", os.getenv("PG_USER", "test")),
                    password=os.getenv("DB_PASSWORD", os.getenv("PG_PASSWORD", "Test123_456")),
                    database=os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "anomivox")),
                ),
            ]


# ─────────────────────────────────────────────
# SSH / OS Konfigürasyonu
# ─────────────────────────────────────────────

@dataclass
class SSHTarget:
    """SSH ile erişilecek sunucu."""
    name: str
    host: str
    user: str = "anomivox"
    port: int = 22
    key_path: str = ""  # Boşsa default ~/.ssh/id_rsa
    role: str = "database"  # database, application, monitoring
    allowed_services: List[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.role}@{self.host})"


@dataclass
class SSHConfig:
    """Tüm SSH hedefleri."""
    targets: List[SSHTarget] = field(default_factory=list)
    command_timeout: int = int(os.getenv("DBA_SSH_TIMEOUT", "30"))


# ─────────────────────────────────────────────
# Telegram Konfigürasyonu
# ─────────────────────────────────────────────

@dataclass
class TelegramConfig:
    """Telegram Bot API konfigürasyonu."""
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    admin_chat_id: str = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
    extra_chat_ids: str = os.getenv("TELEGRAM_CHAT_IDS", "")
    approval_timeout: int = int(
        os.getenv("DBA_APPROVAL_TIMEOUT", "3600")
    )  # 1 saat

    @property
    def all_chat_ids(self) -> List[str]:
        ids = []
        if self.admin_chat_id:
            ids.append(self.admin_chat_id)
        if self.extra_chat_ids:
            ids.extend([c.strip() for c in self.extra_chat_ids.split(",") if c.strip()])
        return ids


# ─────────────────────────────────────────────
# Prometheus Konfigürasyonu
# ─────────────────────────────────────────────

@dataclass
class PrometheusConfig:
    """Prometheus bağlantı ayarları."""
    url: str = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
    query_timeout: int = int(os.getenv("DBA_PROM_TIMEOUT", "10"))


# ─────────────────────────────────────────────
# Güvenlik Konfigürasyonu
# ─────────────────────────────────────────────

@dataclass
class SecurityConfig:
    """SQL ve OS komut güvenlik ayarları."""

    # SQL — FORBIDDEN kalıplar (regex)
    forbidden_sql_patterns: List[str] = field(default_factory=lambda: [
        r"DROP\s+(TABLE|DATABASE|SCHEMA)\s+",
        r"TRUNCATE\s+",
        r"DELETE\s+FROM\s+\w+\s*;?\s*$",  # WHERE'siz DELETE
        r"ALTER\s+TABLE\s+\w+\s+DROP\s+COLUMN",
        r"GRANT\s+ALL",
        r"CREATE\s+USER",
        r"ALTER\s+ROLE.*SUPERUSER",
    ])

    # OS — FORBIDDEN komutlar
    forbidden_os_commands: List[str] = field(default_factory=lambda: [
        "rm -rf",
        "mkfs",
        "dd if=",
        "shutdown",
        "reboot",
        "init 0",
        "init 6",
        ":(){ :|:& };:",  # fork bomb
        "> /dev/sda",
    ])

    # Otomatik onay (SAFE seviyesi)
    auto_approve_safe: bool = True


# ─────────────────────────────────────────────
# Agent Konfigürasyonu (Ana)
# ─────────────────────────────────────────────

@dataclass
class AgentConfig:
    """DBA Agent ana konfigürasyonu — tüm alt config'leri birleştirir."""

    inference: InferenceConfig = field(default_factory=InferenceConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ssh: SSHConfig = field(default_factory=SSHConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    prometheus: PrometheusConfig = field(default_factory=PrometheusConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    # Agent davranışı
    agent_language: str = os.getenv("DBA_AGENT_LANGUAGE", "tr")
    log_level: str = os.getenv("DBA_LOG_LEVEL", "INFO")
    enable_auto_diagnose: bool = os.getenv(
        "DBA_AUTO_DIAGNOSE", "true"
    ).lower() == "true"

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Environment variable'lardan config oluştur."""
        return cls()


# ─── Singleton instance ──────────────────────
_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    """Global config instance döndürür."""
    global _config
    if _config is None:
        _config = AgentConfig.from_env()
    return _config


def reload_config() -> AgentConfig:
    """Config'i yeniden yükler (runtime config değişikliği için)."""
    global _config
    _config = AgentConfig.from_env()
    return _config
