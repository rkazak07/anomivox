"""
Anomivox ClawBot API — REST Endpoints

Endpoints:
  POST /clawbot/ask          — ClawBot'a mesaj gönder (db_id desteği)
  GET  /clawbot/health       — ClawBot sağlık durumu
  GET  /clawbot/skills       — Mevcut skill listesi
  GET  /clawbot/config       — ClawBot genel ayarları (admin)
  POST /clawbot/config       — ClawBot genel ayarları kaydet (admin)
  GET  /clawbot/databases    — DB bağlantılarını listele (admin)
  POST /clawbot/databases    — DB bağlantısı ekle/güncelle (admin)
  DELETE /clawbot/databases  — DB bağlantısı sil (admin)
  POST /clawbot/databases/test — DB bağlantısı test et (admin)
"""

import os
import sys
import re
import json
import uuid
import asyncio
import logging
from typing import Optional, List
from fastapi import Body, Request, Query

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from server.utils import BaseResponse

logger = logging.getLogger("anomivox.clawbot.api")


# ── Auth helper ─────────────────────────────────────────────

def _require_admin(request: Request):
    from server.auth.auth_api import _active_tokens
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    session = _active_tokens.get(token)
    if not session or not session.get("is_admin"):
        return False
    return True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  POST /clawbot/ask — Ana sohbet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def clawbot_ask(
    request: Request,
    message: str = Body(..., embed=True),
    use_llm: bool = Body(True, embed=True),
    db_id: str = Body(None, embed=True),
) -> BaseResponse:
    if not message or not message.strip():
        return BaseResponse(code=400, msg="Mesaj boş olamaz")
    try:
        from server.clawbot.engine import process_message
        result = await process_message(
            message=message.strip(),
            channel="webui",
            user_id="webui",
            use_llm_enrichment=use_llm,
            db_id=db_id,
        )
        return BaseResponse(code=200, msg="OK", data={
            "response": result["response"],
            "intent": result["intent"],
            "elapsed_sec": result.get("elapsed_sec", 0),
            "timestamp": result.get("timestamp", ""),
            "db_id": result.get("db_id", "default"),
        })
    except ConnectionError as e:
        return BaseResponse(code=503, msg=f"DB bağlantı hatası: {str(e)[:200]}")
    except Exception as e:
        logger.error(f"ClawBot ask error: {e}", exc_info=True)
        return BaseResponse(code=500, msg=f"ClawBot hatası: {str(e)[:200]}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GET /clawbot/health
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def clawbot_health() -> BaseResponse:
    from configs.clawbot_config import load_db_connections, get_llm_api_url, get_llm_model, CLAWBOT_AGENT_MODE
    status = {"status": "ok", "databases": [], "agent_mode": CLAWBOT_AGENT_MODE, "llm_model": get_llm_model()}

    connections = load_db_connections()
    import psycopg2
    for conn_info in connections:
        db_status = {"id": conn_info["id"], "name": conn_info["name"], "connected": False}
        if conn_info.get("enabled", True):
            try:
                c = psycopg2.connect(
                    host=conn_info["host"], port=conn_info.get("port", 5432),
                    user=conn_info["user"], password=conn_info["password"],
                    dbname=conn_info["dbname"], connect_timeout=5,
                )
                c.close()
                db_status["connected"] = True
            except Exception as e:
                db_status["error"] = str(e)[:100]
        status["databases"].append(db_status)

    return BaseResponse(code=200, msg="OK", data=status)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GET /clawbot/skills
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def clawbot_skills() -> BaseResponse:
    from server.clawbot.skills import SKILL_REGISTRY, ACTION_SKILLS
    skills = []
    for name, info in SKILL_REGISTRY.items():
        skills.append({"name": name, "description": info["description"], "type": "query", "keywords": info["keywords"][:5]})
    for name, info in ACTION_SKILLS.items():
        skills.append({"name": name, "description": info["description"], "type": "action", "requires_param": info["requires_param"]})
    return BaseResponse(code=200, msg="OK", data={"skills": skills})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DATABASE CRUD — Multi-DB yönetimi
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def list_databases(request: Request) -> BaseResponse:
    if not _require_admin(request):
        return BaseResponse(code=403, msg="Admin yetkisi gerekli")
    from configs.clawbot_config import load_db_connections
    connections = load_db_connections()
    # Şifreleri maskele
    safe = []
    for c in connections:
        item = {**c}
        if item.get("password"):
            item["password"] = "••••••••"
            item["password_set"] = True
        else:
            item["password_set"] = False
        safe.append(item)
    return BaseResponse(code=200, msg="OK", data=safe)


async def save_database(
    request: Request,
    id: str = Body(None, embed=True),
    name: str = Body(..., embed=True),
    host: str = Body(..., embed=True),
    port: int = Body(5432, embed=True),
    user: str = Body(..., embed=True),
    password: str = Body("", embed=True),
    dbname: str = Body(..., embed=True),
    is_default: bool = Body(False, embed=True),
    enabled: bool = Body(True, embed=True),
) -> BaseResponse:
    if not _require_admin(request):
        return BaseResponse(code=403, msg="Admin yetkisi gerekli")

    from configs.clawbot_config import load_db_connections, save_db_connections
    connections = load_db_connections()

    if id:
        # Güncelle
        found = False
        for c in connections:
            if c["id"] == id:
                if not password or password == "••••••••":
                    password = c.get("password", "")
                c["name"] = name
                c["host"] = host
                c["port"] = port
                c["user"] = user
                c["password"] = password
                c["dbname"] = dbname
                c["enabled"] = enabled
                if is_default:
                    for other in connections:
                        other["is_default"] = False
                    c["is_default"] = True
                found = True
                break
        if not found:
            return BaseResponse(code=404, msg="Bağlantı bulunamadı")
    else:
        # Yeni ekle
        new_id = str(uuid.uuid4())[:8]
        new_conn = {
            "id": new_id,
            "name": name,
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "dbname": dbname,
            "is_default": is_default,
            "enabled": enabled,
        }
        if is_default:
            for c in connections:
                c["is_default"] = False
        if not connections:
            new_conn["is_default"] = True
        connections.append(new_conn)

    save_db_connections(connections)
    return BaseResponse(code=200, msg="Veritabanı bağlantısı kaydedildi")


async def delete_database(
    request: Request,
    id: str = Body(..., embed=True),
) -> BaseResponse:
    if not _require_admin(request):
        return BaseResponse(code=403, msg="Admin yetkisi gerekli")

    from configs.clawbot_config import load_db_connections, save_db_connections
    connections = load_db_connections()
    new_list = [c for c in connections if c["id"] != id]
    if len(new_list) == len(connections):
        return BaseResponse(code=404, msg="Bağlantı bulunamadı")

    # Silinen default ise ilkini default yap
    if new_list and not any(c.get("is_default") for c in new_list):
        new_list[0]["is_default"] = True

    save_db_connections(new_list)
    return BaseResponse(code=200, msg="Bağlantı silindi")


async def test_database(
    request: Request,
    host: str = Body(..., embed=True),
    port: int = Body(5432, embed=True),
    user: str = Body(..., embed=True),
    password: str = Body("", embed=True),
    dbname: str = Body(..., embed=True),
    id: str = Body(None, embed=True),
) -> BaseResponse:
    if not _require_admin(request):
        return BaseResponse(code=403, msg="Admin yetkisi gerekli")

    # Şifre maskeli geldiyse mevcut bağlantıdan al
    if id and (not password or password == "••••••••"):
        from configs.clawbot_config import load_db_connections
        for c in load_db_connections():
            if c["id"] == id:
                password = c.get("password", "")
                break

    import psycopg2
    try:
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password,
            dbname=dbname, connect_timeout=10,
        )
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0].split(",")[0]
        cur.execute("SELECT pg_database_size(%s);", (dbname,))
        size = cur.fetchone()[0]
        cur.close()
        conn.close()

        size_str = f"{size / 1024 / 1024:.1f} MB" if size < 1024**3 else f"{size / 1024**3:.2f} GB"
        return BaseResponse(code=200, msg="Bağlantı başarılı", data={
            "version": version, "size": size_str, "connected": True
        })
    except Exception as e:
        return BaseResponse(code=500, msg=f"Bağlantı hatası: {str(e)[:300]}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIG — Genel ayarlar + Agent/LLM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "configs", "clawbot_config.py"
)


def _read_config() -> dict:
    if not os.path.exists(_CONFIG_PATH):
        return {}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    config = {}
    str_patterns = {
        "agent_mode": r'CLAWBOT_AGENT_MODE\s*=.*?["\']([^"\']*)["\']',
        "llm_provider": r'CLAWBOT_LLM_PROVIDER\s*=.*?["\']([^"\']*)["\']',
        "llm_model": r'CLAWBOT_LLM_MODEL\s*=.*?["\']([^"\']*)["\']',
        "llm_api_key": r'CLAWBOT_LLM_API_KEY\s*=.*?["\']([^"\']*)["\']',
        "llm_api_url": r'CLAWBOT_LLM_API_URL\s*=.*?["\']([^"\']*)["\']',
        "local_model": r'CLAWBOT_LOCAL_MODEL\s*=.*?["\']([^"\']*)["\']',
        "local_api_url": r'CLAWBOT_LOCAL_API_URL\s*=.*?["\']([^"\']*)["\']',
        "proactive_channels": r'CLAWBOT_PROACTIVE_CHANNELS\s*=.*?["\']([^"\']*)["\']',
    }
    int_patterns = {
        "llm_max_tokens": r'CLAWBOT_LLM_MAX_TOKENS\s*=.*?(\d+)',
        "proactive_interval": r'CLAWBOT_PROACTIVE_INTERVAL\s*=.*?(\d+)',
        "slow_query_threshold": r'CLAWBOT_SLOW_QUERY_THRESHOLD\s*=.*?(\d+)',
    }
    float_patterns = {
        "llm_temperature": r'CLAWBOT_LLM_TEMPERATURE\s*=.*?([0-9.]+)',
    }
    bool_patterns = {
        "use_llm": r'CLAWBOT_USE_LLM\s*=.*?["\']([^"\']*)["\']',
        "require_action_confirm": r'CLAWBOT_REQUIRE_ACTION_CONFIRM\s*=.*?["\']([^"\']*)["\']',
    }

    for key, pat in str_patterns.items():
        m = re.search(pat, content)
        if m:
            config[key] = m.group(1)

    for key, pat in int_patterns.items():
        m = re.search(pat, content)
        if m:
            config[key] = int(m.group(1))

    for key, pat in float_patterns.items():
        m = re.search(pat, content)
        if m:
            try:
                config[key] = float(m.group(1))
            except ValueError:
                pass

    for key, pat in bool_patterns.items():
        m = re.search(pat, content)
        if m:
            config[key] = m.group(1).lower() in ("true", "1", "yes")

    return config


def _write_config(cfg: dict):
    template = '''"""
ClawBot — Otonom DB Asistanı Yapılandırması
"""
import os
import json

CLAWBOT_DB_CONNECTIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clawbot_databases.json")

CLAWBOT_AGENT_MODE = os.environ.get("CLAWBOT_AGENT_MODE", "{agent_mode}")
CLAWBOT_LLM_PROVIDER = os.environ.get("CLAWBOT_LLM_PROVIDER", "{llm_provider}")
CLAWBOT_LLM_MODEL = os.environ.get("CLAWBOT_LLM_MODEL", "{llm_model}")
CLAWBOT_LLM_API_KEY = os.environ.get("CLAWBOT_LLM_API_KEY", "{llm_api_key}")
CLAWBOT_LLM_API_URL = os.environ.get("CLAWBOT_LLM_API_URL", "{llm_api_url}")
CLAWBOT_LLM_TEMPERATURE = float(os.environ.get("CLAWBOT_LLM_TEMPERATURE", "{llm_temperature}"))
CLAWBOT_LLM_MAX_TOKENS = int(os.environ.get("CLAWBOT_LLM_MAX_TOKENS", "{llm_max_tokens}"))
CLAWBOT_LOCAL_MODEL = os.environ.get("CLAWBOT_LOCAL_MODEL", "{local_model}")
CLAWBOT_LOCAL_API_URL = os.environ.get("CLAWBOT_LOCAL_API_URL", "{local_api_url}")
CLAWBOT_USE_LLM = bool(os.environ.get("CLAWBOT_USE_LLM", "{use_llm}").lower() in ("true", "1", "yes"))
CLAWBOT_PROACTIVE_INTERVAL = int(os.environ.get("CLAWBOT_PROACTIVE_INTERVAL", "{proactive_interval}"))
CLAWBOT_PROACTIVE_CHANNELS = os.environ.get("CLAWBOT_PROACTIVE_CHANNELS", "{proactive_channels}")
CLAWBOT_SLOW_QUERY_THRESHOLD = int(os.environ.get("CLAWBOT_SLOW_QUERY_THRESHOLD", "{slow_query_threshold}"))
CLAWBOT_REQUIRE_ACTION_CONFIRM = bool(os.environ.get("CLAWBOT_REQUIRE_ACTION_CONFIRM", "{require_action_confirm}").lower() in ("true", "1", "yes"))

CLAWBOT_PG_HOST = os.environ.get("CLAWBOT_PG_HOST", "postgres_db")
CLAWBOT_PG_PORT = int(os.environ.get("CLAWBOT_PG_PORT", "5432"))
CLAWBOT_PG_USER = os.environ.get("CLAWBOT_PG_USER", "test")
CLAWBOT_PG_PASSWORD = os.environ.get("CLAWBOT_PG_PASSWORD", "Test123_456")
CLAWBOT_PG_DB = os.environ.get("CLAWBOT_PG_DB", "anomivox")

LLM_PROVIDER_URLS = {{
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "deepseek": "https://api.deepseek.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
    "custom": "",
}}

def get_llm_api_url():
    if CLAWBOT_AGENT_MODE == "local":
        return CLAWBOT_LOCAL_API_URL
    if CLAWBOT_LLM_API_URL:
        return CLAWBOT_LLM_API_URL
    return LLM_PROVIDER_URLS.get(CLAWBOT_LLM_PROVIDER, "")

def get_llm_model():
    if CLAWBOT_AGENT_MODE == "local":
        return CLAWBOT_LOCAL_MODEL
    return CLAWBOT_LLM_MODEL

def load_db_connections():
    if not os.path.exists(CLAWBOT_DB_CONNECTIONS_FILE):
        default_conn = [{{"id":"default","name":"Anomivox (Default)","host":CLAWBOT_PG_HOST,"port":CLAWBOT_PG_PORT,"user":CLAWBOT_PG_USER,"password":CLAWBOT_PG_PASSWORD,"dbname":CLAWBOT_PG_DB,"is_default":True,"enabled":True}}]
        save_db_connections(default_conn)
        return default_conn
    try:
        with open(CLAWBOT_DB_CONNECTIONS_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_db_connections(connections):
    with open(CLAWBOT_DB_CONNECTIONS_FILE,"w",encoding="utf-8") as f:
        json.dump(connections,f,ensure_ascii=False,indent=2)

def get_db_connection_by_id(db_id=None):
    connections = load_db_connections()
    if not connections:
        return None
    if db_id:
        for c in connections:
            if c["id"]==db_id and c.get("enabled",True):
                return c
        return None
    for c in connections:
        if c.get("is_default") and c.get("enabled",True):
            return c
    for c in connections:
        if c.get("enabled",True):
            return c
    return None
'''
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(template.format(**cfg))


async def get_clawbot_config(request: Request) -> BaseResponse:
    if not _require_admin(request):
        return BaseResponse(code=403, msg="Admin yetkisi gerekli")
    config = _read_config()
    if config.get("llm_api_key"):
        config["llm_api_key_set"] = True
        config["llm_api_key"] = "••••••••"
    else:
        config["llm_api_key_set"] = False
    return BaseResponse(code=200, msg="OK", data=config)


async def save_clawbot_config(
    request: Request,
    agent_mode: str = Body("cloud", embed=True),
    llm_provider: str = Body("groq", embed=True),
    llm_model: str = Body("llama-3.3-70b-versatile", embed=True),
    llm_api_key: str = Body("", embed=True),
    llm_api_url: str = Body("", embed=True),
    llm_temperature: float = Body(0.3, embed=True),
    llm_max_tokens: int = Body(2048, embed=True),
    local_model: str = Body("llama3", embed=True),
    local_api_url: str = Body("http://localhost:11434/v1", embed=True),
    use_llm: bool = Body(True, embed=True),
    proactive_interval: int = Body(300, embed=True),
    proactive_channels: str = Body("telegram,whatsapp,mail", embed=True),
    slow_query_threshold: int = Body(1000, embed=True),
    require_action_confirm: bool = Body(True, embed=True),
) -> BaseResponse:
    if not _require_admin(request):
        return BaseResponse(code=403, msg="Admin yetkisi gerekli")

    current = _read_config()
    if not llm_api_key or llm_api_key == "••••••••":
        llm_api_key = current.get("llm_api_key", "")

    cfg = {
        "agent_mode": agent_mode,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_api_key": llm_api_key,
        "llm_api_url": llm_api_url,
        "llm_temperature": llm_temperature,
        "llm_max_tokens": llm_max_tokens,
        "local_model": local_model,
        "local_api_url": local_api_url,
        "use_llm": str(use_llm),
        "proactive_interval": proactive_interval,
        "proactive_channels": proactive_channels,
        "slow_query_threshold": slow_query_threshold,
        "require_action_confirm": str(require_action_confirm),
    }
    try:
        _write_config(cfg)
        return BaseResponse(code=200, msg="ClawBot ayarları kaydedildi")
    except Exception as e:
        return BaseResponse(code=500, msg=f"Kaydetme hatası: {str(e)[:200]}")
