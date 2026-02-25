"""
ClawBot — Otonom DB Asistanı Yapılandırması

Multi-DB bağlantıları JSON dosyasında saklanır: configs/clawbot_databases.json
Agent/LLM ayarları burada yapılandırılır.
"""
import os
import json

# ── Multi-DB Bağlantı Dosyası ─────────────────────────────
CLAWBOT_DB_CONNECTIONS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "clawbot_databases.json"
)

# ── Agent / LLM Ayarları ──────────────────────────────────
# "cloud" veya "local"
CLAWBOT_AGENT_MODE = os.environ.get("CLAWBOT_AGENT_MODE", "cloud")

# Cloud LLM ayarları
CLAWBOT_LLM_PROVIDER = os.environ.get("CLAWBOT_LLM_PROVIDER", "groq")
CLAWBOT_LLM_MODEL = os.environ.get("CLAWBOT_LLM_MODEL", "llama-3.3-70b-versatile")
CLAWBOT_LLM_API_KEY = os.environ.get("CLAWBOT_LLM_API_KEY", "")
CLAWBOT_LLM_API_URL = os.environ.get("CLAWBOT_LLM_API_URL", "")
CLAWBOT_LLM_TEMPERATURE = float(os.environ.get("CLAWBOT_LLM_TEMPERATURE", "0.3"))
CLAWBOT_LLM_MAX_TOKENS = int(os.environ.get("CLAWBOT_LLM_MAX_TOKENS", "2048"))

# Local LLM ayarları (Ollama / vLLM / LM Studio)
CLAWBOT_LOCAL_MODEL = os.environ.get("CLAWBOT_LOCAL_MODEL", "llama3")
CLAWBOT_LOCAL_API_URL = os.environ.get("CLAWBOT_LOCAL_API_URL", "http://localhost:11434/v1")

# ── Davranış Ayarları ──────────────────────────────────────
CLAWBOT_USE_LLM = bool(os.environ.get("CLAWBOT_USE_LLM", "True").lower() in ("true", "1", "yes"))
CLAWBOT_PROACTIVE_INTERVAL = int(os.environ.get("CLAWBOT_PROACTIVE_INTERVAL", "300"))
CLAWBOT_PROACTIVE_CHANNELS = os.environ.get("CLAWBOT_PROACTIVE_CHANNELS", "telegram,whatsapp,mail")
CLAWBOT_SLOW_QUERY_THRESHOLD = int(os.environ.get("CLAWBOT_SLOW_QUERY_THRESHOLD", "1000"))
CLAWBOT_REQUIRE_ACTION_CONFIRM = bool(os.environ.get("CLAWBOT_REQUIRE_ACTION_CONFIRM", "True").lower() in ("true", "1", "yes"))

# ── Fallback DB (eski uyumluluk) ──────────────────────────
CLAWBOT_PG_HOST = os.environ.get("CLAWBOT_PG_HOST", "postgres_db")
CLAWBOT_PG_PORT = int(os.environ.get("CLAWBOT_PG_PORT", "5432"))
CLAWBOT_PG_USER = os.environ.get("CLAWBOT_PG_USER", "test")
CLAWBOT_PG_PASSWORD = os.environ.get("CLAWBOT_PG_PASSWORD", "Test123_456")
CLAWBOT_PG_DB = os.environ.get("CLAWBOT_PG_DB", "anomivox")

# ── Provider → Base URL ──────────────────────────────────
LLM_PROVIDER_URLS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "deepseek": "https://api.deepseek.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
    "custom": "",
}


def get_llm_api_url():
    """Provider'a göre LLM API URL'sini döndür."""
    if CLAWBOT_AGENT_MODE == "local":
        return CLAWBOT_LOCAL_API_URL
    if CLAWBOT_LLM_API_URL:
        return CLAWBOT_LLM_API_URL
    return LLM_PROVIDER_URLS.get(CLAWBOT_LLM_PROVIDER, "")


def get_llm_model():
    """Aktif modeli döndür."""
    if CLAWBOT_AGENT_MODE == "local":
        return CLAWBOT_LOCAL_MODEL
    return CLAWBOT_LLM_MODEL


def load_db_connections() -> list:
    """JSON'dan DB bağlantılarını yükle."""
    if not os.path.exists(CLAWBOT_DB_CONNECTIONS_FILE):
        default_conn = [{
            "id": "default",
            "name": "Anomivox (Default)",
            "host": CLAWBOT_PG_HOST,
            "port": CLAWBOT_PG_PORT,
            "user": CLAWBOT_PG_USER,
            "password": CLAWBOT_PG_PASSWORD,
            "dbname": CLAWBOT_PG_DB,
            "is_default": True,
            "enabled": True,
        }]
        save_db_connections(default_conn)
        return default_conn
    try:
        with open(CLAWBOT_DB_CONNECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_db_connections(connections: list):
    """DB bağlantılarını JSON'a kaydet."""
    with open(CLAWBOT_DB_CONNECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(connections, f, ensure_ascii=False, indent=2)


def get_db_connection_by_id(db_id: str = None) -> dict:
    """ID ile DB bağlantısını getir. Yoksa default."""
    connections = load_db_connections()
    if not connections:
        return None
    if db_id:
        for c in connections:
            if c["id"] == db_id and c.get("enabled", True):
                return c
        return None
    for c in connections:
        if c.get("is_default") and c.get("enabled", True):
            return c
    for c in connections:
        if c.get("enabled", True):
            return c
    return None
