"""
OpenClaw Gateway API — Anomivox entegrasyonu

OpenClaw Gateway'e bağlanarak:
- Config okuma/yazma (openclaw.json)
- Channel yönetimi (Telegram, WhatsApp, Discord, Slack)
- Mesaj gönderme
- Sağlık durumu
- Skill yönetimi
"""
import json
import os
import logging
import aiohttp
from fastapi import Body, Header
from typing import Optional

logger = logging.getLogger("openclaw_api")

# ── OpenClaw config dosyası yolu ──────────────────────────
OPENCLAW_CONFIG_DIR = os.environ.get(
    "OPENCLAW_CONFIG_DIR",
    os.path.join(os.path.expanduser("~"), ".openclaw")
)
OPENCLAW_CONFIG_PATH = os.path.join(OPENCLAW_CONFIG_DIR, "openclaw.json")


def _get_gateway_url():
    """OpenClaw Gateway URL"""
    host = os.environ.get("OPENCLAW_GATEWAY_HOST", "openclaw")
    port = os.environ.get("OPENCLAW_GATEWAY_PORT", "18789")
    return f"http://{host}:{port}"


def _read_config() -> dict:
    """openclaw.json dosyasını oku"""
    if os.path.exists(OPENCLAW_CONFIG_PATH):
        try:
            with open(OPENCLAW_CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"OpenClaw config read error: {e}")
    return {}


def _write_config(config: dict):
    """openclaw.json dosyasını yaz"""
    os.makedirs(OPENCLAW_CONFIG_DIR, exist_ok=True)
    try:
        with open(OPENCLAW_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("OpenClaw config saved")
    except Exception as e:
        logger.error(f"OpenClaw config write error: {e}")
        raise


# ── Gateway Health ────────────────────────────────────────
async def openclaw_health(
    authorization: Optional[str] = Header(None)
):
    """OpenClaw Gateway sağlık durumu"""
    try:
        gateway_url = _get_gateway_url()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{gateway_url}/api/health",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    # Yeni sürüm HTML döner, JSON dönerse parse et
                    content_type = resp.headers.get("content-type", "")
                    details = {}
                    if "json" in content_type:
                        try:
                            details = await resp.json()
                        except Exception:
                            pass
                    return {"code": 200, "msg": "OpenClaw Gateway aktif", "data": {
                        "status": "online",
                        "gateway_url": gateway_url,
                        "details": details,
                    }}
                else:
                    return {"code": 200, "msg": "Gateway erişilemez", "data": {
                        "status": "offline",
                        "gateway_url": gateway_url,
                        "http_status": resp.status,
                    }}
    except Exception as e:
        return {"code": 200, "msg": f"Gateway bağlantı hatası: {str(e)[:100]}", "data": {
            "status": "offline",
            "gateway_url": _get_gateway_url(),
            "error": str(e)[:200],
        }}


# ── Config CRUD ───────────────────────────────────────────
async def get_openclaw_config(
    authorization: Optional[str] = Header(None)
):
    """OpenClaw yapılandırmasını getir"""
    config = _read_config()

    # Token/key alanlarını maskele
    safe_config = {}

    # Agent/Model — yeni format: agents.defaults.model.primary
    # Eski format: agent.model (geriye uyumluluk)
    agents = config.get("agents", {})
    defaults = agents.get("defaults", {})
    model_cfg = defaults.get("model", {})
    new_model = model_cfg.get("primary", "")

    # Eski format fallback
    agent = config.get("agent", {})
    old_model = agent.get("model", "")
    if isinstance(old_model, dict):
        old_model = old_model.get("primary", "")

    safe_config["model"] = new_model or old_model or "anthropic/claude-opus-4-6"

    # API Key — sadece set olup olmadığını döndür
    api_key_env_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }
    model_str = safe_config["model"]
    provider = model_str.split("/")[0] if "/" in model_str else ""
    env_key = api_key_env_map.get(provider, "")
    config_api_key = defaults.get("apiKey", "") or agent.get("apiKey", "")
    env_api_key = os.environ.get(env_key, "") if env_key else ""
    safe_config["api_key_set"] = bool(config_api_key or env_api_key)

    # Gateway
    gw = config.get("gateway", {})
    safe_config["gateway_port"] = gw.get("port", 18789)
    safe_config["gateway_bind"] = gw.get("bind", "lan")

    # Channels
    channels = config.get("channels", {})

    # Telegram
    tg = channels.get("telegram", {})
    tg_token = tg.get("botToken", "")
    safe_config["telegram_enabled"] = tg.get("enabled", bool(tg_token))
    safe_config["telegram_bot_token_set"] = bool(tg_token)
    safe_config["telegram_allow_from"] = tg.get("allowFrom", [])
    tg_groups = tg.get("groups", {})
    safe_config["telegram_groups"] = tg_groups

    # WhatsApp
    wa = channels.get("whatsapp", {})
    safe_config["whatsapp_enabled"] = wa.get("enabled", bool(wa))
    safe_config["whatsapp_allow_from"] = wa.get("allowFrom", [])
    wa_groups = wa.get("groups", {})
    safe_config["whatsapp_groups"] = wa_groups

    # Discord
    dc = channels.get("discord", {})
    dc_token = dc.get("token", "")
    safe_config["discord_enabled"] = dc.get("enabled", bool(dc_token))
    safe_config["discord_bot_token_set"] = bool(dc_token)
    safe_config["discord_allow_from"] = dc.get("allowFrom", [])

    # Slack
    sl = channels.get("slack", {})
    sl_token = sl.get("botToken", "")
    safe_config["slack_enabled"] = sl.get("enabled", bool(sl_token))
    safe_config["slack_bot_token_set"] = bool(sl_token)

    # Skills
    skills = config.get("skills", {})
    safe_config["skills"] = list(skills.keys()) if isinstance(skills, dict) else []

    # Browser
    browser = config.get("browser", {})
    safe_config["browser_enabled"] = browser.get("enabled", False)

    return {"code": 200, "msg": "success", "data": safe_config}


async def save_openclaw_config(
    data: dict = Body(...),
    authorization: Optional[str] = Header(None)
):
    """OpenClaw yapılandırmasını kaydet"""
    try:
        config = _read_config()

        # Agent/Model — yeni format: agents.defaults.model.primary
        if "model" in data:
            agents = config.setdefault("agents", {})
            defaults = agents.setdefault("defaults", {})
            model_cfg = defaults.setdefault("model", {})
            model_cfg["primary"] = data["model"]
            # Eski format varsa temizle
            if "agent" in config and "model" in config.get("agent", {}):
                config["agent"].pop("model", None)
                if not config["agent"]:
                    config.pop("agent", None)

        # API Key — sağlayıcıya göre agents.defaults.apiKey olarak sakla
        if "api_key" in data and data["api_key"]:
            agents = config.setdefault("agents", {})
            defaults = agents.setdefault("defaults", {})
            defaults["apiKey"] = data["api_key"]

        # Gateway
        if "gateway_port" in data:
            config.setdefault("gateway", {})["port"] = int(data["gateway_port"])
        if "gateway_bind" in data:
            config.setdefault("gateway", {})["bind"] = data["gateway_bind"]

        # Channels
        config.setdefault("channels", {})

        # Telegram
        if data.get("telegram_enabled") is False:
            config["channels"].pop("telegram", None)
        else:
            if "telegram_bot_token" in data and data["telegram_bot_token"]:
                config["channels"].setdefault("telegram", {})["botToken"] = data["telegram_bot_token"]
            if "telegram_allow_from" in data:
                config["channels"].setdefault("telegram", {})["allowFrom"] = data["telegram_allow_from"]
            if "telegram_groups" in data:
                config["channels"].setdefault("telegram", {})["groups"] = data["telegram_groups"]

        # WhatsApp
        if data.get("whatsapp_enabled") is False:
            config["channels"].pop("whatsapp", None)
        else:
            if data.get("whatsapp_enabled") is True:
                config["channels"].setdefault("whatsapp", {})
            if "whatsapp_allow_from" in data:
                config["channels"].setdefault("whatsapp", {})["allowFrom"] = data["whatsapp_allow_from"]
            if "whatsapp_groups" in data:
                config["channels"].setdefault("whatsapp", {})["groups"] = data["whatsapp_groups"]

        # Discord
        if data.get("discord_enabled") is False:
            config["channels"].pop("discord", None)
        else:
            if "discord_bot_token" in data and data["discord_bot_token"]:
                config["channels"].setdefault("discord", {})["token"] = data["discord_bot_token"]
            if "discord_allow_from" in data:
                config["channels"].setdefault("discord", {})["allowFrom"] = data["discord_allow_from"]

        # Slack
        if data.get("slack_enabled") is False:
            config["channels"].pop("slack", None)
        else:
            if "slack_bot_token" in data and data["slack_bot_token"]:
                config["channels"].setdefault("slack", {})["botToken"] = data["slack_bot_token"]
            if "slack_app_token" in data and data["slack_app_token"]:
                config["channels"].setdefault("slack", {})["appToken"] = data["slack_app_token"]

        # Browser
        if "browser_enabled" in data:
            config.setdefault("browser", {})["enabled"] = bool(data["browser_enabled"])

        _write_config(config)
        return {"code": 200, "msg": "OpenClaw ayarları kaydedildi"}
    except Exception as e:
        return {"code": 500, "msg": f"Kaydetme hatası: {str(e)[:200]}"}


# ── Mesaj Gönder ──────────────────────────────────────────
async def openclaw_send_message(
    data: dict = Body(...),
    authorization: Optional[str] = Header(None)
):
    """OpenClaw üzerinden mesaj gönder"""
    message = data.get("message", "")
    channel = data.get("channel", "")  # telegram, whatsapp, discord, slack
    recipient = data.get("recipient", "")

    if not message:
        return {"code": 400, "msg": "Mesaj gerekli"}

    try:
        gateway_url = _get_gateway_url()
        token = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {
            "message": message,
        }
        if channel:
            payload["channel"] = channel
        if recipient:
            payload["to"] = recipient

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{gateway_url}/api/agent/send",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                result = await resp.json() if resp.status == 200 else {"error": await resp.text()}
                return {"code": 200, "msg": "Mesaj gönderildi", "data": result}
    except Exception as e:
        return {"code": 500, "msg": f"Mesaj gönderme hatası: {str(e)[:200]}"}


# ── Channel Yönetimi ─────────────────────────────────────
async def openclaw_channels(
    authorization: Optional[str] = Header(None)
):
    """OpenClaw aktif channel'ları listele"""
    config = _read_config()
    channels = config.get("channels", {})

    result = []
    for name, cfg in channels.items():
        ch = {
            "name": name,
            "enabled": True,
            "configured": False,
        }
        if name == "telegram":
            ch["configured"] = bool(cfg.get("botToken"))
            ch["allow_from"] = cfg.get("allowFrom", [])
        elif name == "whatsapp":
            ch["configured"] = True  # QR based
            ch["allow_from"] = cfg.get("allowFrom", [])
        elif name == "discord":
            ch["configured"] = bool(cfg.get("token"))
            ch["allow_from"] = cfg.get("allowFrom", [])
        elif name == "slack":
            ch["configured"] = bool(cfg.get("botToken") and cfg.get("appToken"))
        result.append(ch)

    return {"code": 200, "msg": "success", "data": result}


# ── Gateway Restart ───────────────────────────────────────
async def openclaw_restart(
    authorization: Optional[str] = Header(None)
):
    """OpenClaw Gateway'i yeniden başlat (config değişikliklerini uygulamak için)"""
    try:
        gateway_url = _get_gateway_url()
        token = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{gateway_url}/api/gateway/restart",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    return {"code": 200, "msg": "Gateway yeniden başlatılıyor"}
                else:
                    return {"code": resp.status, "msg": f"Gateway restart hatası: {resp.status}"}
    except Exception as e:
        return {"code": 500, "msg": f"Restart hatası: {str(e)[:200]}"}
