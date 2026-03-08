"""
DBA Agent Konfigürasyonu
════════════════════════
Tüm ayarlar env variable'lardan okunur, varsayılan değerler
mevcut configs/ modülüyle uyumludur.

UI'dan girilen DB bağlantıları configs/db_targets.json'a yazılır.
Bu dosya mevcutsa, ENV değişkenlerine göre ÖNCELİKLİ olarak okunur.

NOT: Mevcut configs/model_config.py, diagnose_config.py vb.
     dosyalara DOKUNMAZ. Kendi konfigürasyonunu yönetir.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("dba_agent.config")

# ── db_targets.json yolu (Settings UI ile paylaşılan) ────
DB_TARGETS_JSON = os.getenv(
    "DB_TARGETS_JSON",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "db_targets.json"),
)


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
    # SSH bilgileri — db_targets.json'dan gelir
    ssh_enabled: bool = False
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_password: str = ""
    ssh_key_path: str = ""
    # Meta
    target_id: str = ""  # db_targets.json ID
    is_primary: bool = False

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.db_type}@{self.host}:{self.port}/{self.database})"


def _load_db_targets_json() -> list:
    """configs/db_targets.json dosyasından UI kayıtlı target'ları yükle."""
    json_path = DB_TARGETS_JSON
    if not os.path.exists(json_path):
        return []
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data
    except Exception as e:
        logger.warning(f"db_targets.json okunamadı: {e}")
        return []


def _json_targets_to_database_targets(json_list: list) -> List[DatabaseTarget]:
    """
    db_targets.json formatındaki dict listesini
    DatabaseTarget dataclass listesine çevirir.
    Primary target'ı listenin başına koyar.
    """
    targets = []
    for t in json_list:
        try:
            dt = DatabaseTarget(
                name=t.get("name", "unnamed"),
                db_type=t.get("db_type", "postgresql"),
                host=t.get("host", "localhost"),
                port=int(t.get("port", 5432)),
                user=t.get("user", ""),
                password=t.get("password", ""),
                database=t.get("dbname", t.get("database", "")),
                ssh_enabled=bool(t.get("ssh_enabled", False)),
                ssh_host=t.get("ssh_host", ""),
                ssh_port=int(t.get("ssh_port", 22)),
                ssh_user=t.get("ssh_user", ""),
                ssh_password=t.get("ssh_password", ""),
                ssh_key_path=t.get("ssh_key_path", ""),
                target_id=t.get("id", ""),
                is_primary=bool(t.get("is_primary", False)),
            )
            targets.append(dt)
        except Exception as e:
            logger.warning(f"Target parse hatası ({t.get('name', '?')}): {e}")

    # Primary olanı başa al
    targets.sort(key=lambda x: (not x.is_primary, x.name))
    return targets


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
        """
        Öncelik sırası:
        1. configs/db_targets.json (UI'dan girilen)
        2. ENV değişkenleri (Docker compose default)
        """
        if not self.targets:
            # ── 1) db_targets.json'dan yükle ────
            json_targets = _json_targets_to_database_targets(
                _load_db_targets_json()
            )
            if json_targets:
                self.targets = json_targets
                logger.info(
                    f"db_targets.json'dan {len(json_targets)} DB target yüklendi: "
                    f"{[t.display_name for t in json_targets]}"
                )
                return

            # ── 2) Env fallback — Docker compose default ────
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
            logger.info("ENV'den varsayılan DB target oluşturuldu (db_targets.json bulunamadı)")

    def reload_from_json(self):
        """db_targets.json değişince runtime'da yeniden yükle."""
        json_targets = _json_targets_to_database_targets(
            _load_db_targets_json()
        )
        if json_targets:
            self.targets = json_targets
            logger.info(f"DB targets yeniden yüklendi: {len(json_targets)} target")
            return True
        return False


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
    password: str = ""  # SSH password (key yoksa)
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

    def __post_init__(self):
        """
        SSH target'ları yükle.
        Öncelik sırası:
        1. db_targets.json'daki ssh_enabled=true olan kayıtlar
        2. ENV değişkenleri (DBA_SSH_HOST vb.)
        """
        if not self.targets:
            # ── 1) db_targets.json'daki SSH bilgileri ────
            json_list = _load_db_targets_json()
            for t in json_list:
                if t.get("ssh_enabled") and t.get("ssh_host"):
                    allowed_str = os.getenv("DBA_SSH_ALLOWED_SERVICES", "postgresql,mysql,nginx,docker")
                    allowed = [s.strip() for s in allowed_str.split(",") if s.strip()]
                    self.targets.append(SSHTarget(
                        name=t.get("name", "unknown"),
                        host=t["ssh_host"],
                        user=t.get("ssh_user", "root"),
                        port=int(t.get("ssh_port", 22)),
                        key_path=t.get("ssh_key_path", ""),
                        password=t.get("ssh_password", ""),
                        role="database",
                        allowed_services=allowed,
                    ))

            if self.targets:
                logger.info(
                    f"db_targets.json'dan {len(self.targets)} SSH target yüklendi: "
                    f"{[t.display_name for t in self.targets]}"
                )
                return

            # ── 2) Env fallback ────
            ssh_host = os.getenv("DBA_SSH_HOST", "")
            if ssh_host:
                allowed_str = os.getenv("DBA_SSH_ALLOWED_SERVICES", "postgresql,mysql,nginx,docker")
                allowed = [s.strip() for s in allowed_str.split(",") if s.strip()]

                self.targets.append(SSHTarget(
                    name=os.getenv("DBA_SSH_NAME", "db-server"),
                    host=ssh_host,
                    user=os.getenv("DBA_SSH_USER", "anomivox"),
                    port=int(os.getenv("DBA_SSH_PORT", "22")),
                    key_path=os.getenv("DBA_SSH_KEY_PATH", ""),
                    role=os.getenv("DBA_SSH_ROLE", "database"),
                    allowed_services=allowed,
                ))

    def reload_from_json(self):
        """db_targets.json değişince SSH target'ları yeniden yükle."""
        new_targets = []
        json_list = _load_db_targets_json()
        for t in json_list:
            if t.get("ssh_enabled") and t.get("ssh_host"):
                allowed_str = os.getenv("DBA_SSH_ALLOWED_SERVICES", "postgresql,mysql,nginx,docker")
                allowed = [s.strip() for s in allowed_str.split(",") if s.strip()]
                new_targets.append(SSHTarget(
                    name=t.get("name", "unknown"),
                    host=t["ssh_host"],
                    user=t.get("ssh_user", "root"),
                    port=int(t.get("ssh_port", 22)),
                    key_path=t.get("ssh_key_path", ""),
                    password=t.get("ssh_password", ""),
                    role="database",
                    allowed_services=allowed,
                ))
        if new_targets:
            self.targets = new_targets
            logger.info(f"SSH targets yeniden yüklendi: {len(new_targets)} target")
            return True
        return False


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

    # Multi-approval: DBA_APPROVERS = "123456,789012" (virgül ayrımlı chat ID'leri)
    # Boş ise sadece TELEGRAM_ADMIN_CHAT_ID kullanılır
    approvers_raw: str = os.getenv("DBA_APPROVERS", "")
    # HIGH risk için gereken minimum onay sayısı (varsayılan: 1)
    required_approvals: int = int(os.getenv("DBA_REQUIRED_APPROVALS", "1"))

    @property
    def all_chat_ids(self) -> List[str]:
        ids = []
        if self.admin_chat_id:
            ids.append(self.admin_chat_id)
        if self.extra_chat_ids:
            ids.extend([c.strip() for c in self.extra_chat_ids.split(",") if c.strip()])
        return ids

    @property
    def approver_ids(self) -> List[str]:
        """Multi-approval için yetkili DBA chat ID'leri."""
        ids = []
        if self.approvers_raw:
            ids = [c.strip() for c in self.approvers_raw.split(",") if c.strip()]
        if not ids and self.admin_chat_id:
            ids = [self.admin_chat_id]
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

    # Otomatik onay seviyeleri
    auto_approve_safe: bool = True
    auto_approve_low: bool = os.getenv("DBA_AUTO_APPROVE_LOW", "false").lower() == "true"

    # Dry-run: aksiyonlar yürütülmez, sadece loglanır
    dry_run: bool = os.getenv("DBA_DRY_RUN", "false").lower() == "true"

    # Bakım penceresi — HIGH riskli aksiyonlar sadece bu saatler arasında uygulanır
    # Format: "HH:MM" (24 saat), boş string = kısıtlama yok
    maintenance_start: str = os.getenv("DBA_MAINTENANCE_START", "")
    maintenance_end: str = os.getenv("DBA_MAINTENANCE_END", "")


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
    logger.info(
        f"Config yeniden yüklendi — "
        f"DB targets: {len(_config.database.targets)}, "
        f"SSH targets: {len(_config.ssh.targets)}"
    )
    return _config


def sync_from_json() -> AgentConfig:
    """
    db_targets.json değişince çağrılır.
    Sadece DB ve SSH target'ları günceller, diğer config'leri korur.
    """
    global _config
    if _config is None:
        _config = AgentConfig.from_env()
    _config.database.reload_from_json()
    _config.ssh.reload_from_json()
    return _config
