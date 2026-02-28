"""
AI Agent Gateway API — Anomivox entegrasyonu

AI Agent Gateway'e bağlanarak:
- Config okuma/yazma (openclaw.json)
- Channel yönetimi (Telegram, WhatsApp, Discord, Slack)
- Mesaj gönderme
- Sağlık durumu
- Skill yönetimi
"""
import json
import os
import logging
import asyncio
import aiohttp
from fastapi import Body, Header
from typing import Optional

logger = logging.getLogger("openclaw_api")

# ── AI Agent config dosyası yolu ──────────────────────────
OPENCLAW_CONFIG_DIR = os.environ.get(
    "OPENCLAW_CONFIG_DIR",
    os.path.join(os.path.expanduser("~"), ".openclaw")
)
OPENCLAW_CONFIG_PATH = os.path.join(OPENCLAW_CONFIG_DIR, "openclaw.json")


def _get_gateway_url():
    """AI Agent Gateway URL"""
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
            logger.error(f"AI Agent config read error: {e}")
    return {}


def _write_config(config: dict):
    """openclaw.json dosyasını yaz"""
    os.makedirs(OPENCLAW_CONFIG_DIR, exist_ok=True)
    try:
        with open(OPENCLAW_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("AI Agent config saved")
    except Exception as e:
        logger.error(f"AI Agent config write error: {e}")
        raise


# ── Gateway Health ────────────────────────────────────────
async def openclaw_health(
    authorization: Optional[str] = Header(None)
):
    """AI Agent Gateway sağlık durumu"""
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
                    return {"code": 200, "msg": "AI Agent Gateway aktif", "data": {
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
    """AI Agent yapılandırmasını getir"""
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

    # openai-responses wrapper ile kaydedilmiş Ollama modelleri:
    # config'de "openai/llama3.1:8b" olarak durur ama UI'da "ollama/llama3.1:8b" göstermeli
    # Bunu tespit etmek için providers içinde openai + api:openai-responses + ollama baseUrl var mı bak
    _providers = config.get("models", {}).get("providers", {})
    _openai_prov = _providers.get("openai", {})
    _is_ollama_wrapper = (
        _openai_prov.get("api") == "openai-responses"
        and "11434" in _openai_prov.get("baseUrl", "")
    )
    if _is_ollama_wrapper and safe_config["model"].startswith("openai/"):
        safe_config["model"] = "ollama/" + safe_config["model"].split("/", 1)[1]

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

    # Telegram alert ayarları (telegram_alert_config.py'den)
    try:
        from server.telegram.telegram_alert_api import _read_config as _read_tg_alert, _get_bot_info
        tg_alert = _read_tg_alert()
        safe_config["telegram_admin_chat_id"] = tg_alert.get("admin_chat_id", "")
        safe_config["telegram_extra_chat_ids"] = tg_alert.get("extra_chat_ids", "")
        safe_config["telegram_notify_alert"] = tg_alert.get("notify_on_alert", True)
        safe_config["telegram_notify_resolved"] = tg_alert.get("notify_on_resolved", True)
        safe_config["telegram_notify_diagnosis"] = tg_alert.get("notify_on_diagnosis", True)
        # Bot username
        if tg_token:
            info = _get_bot_info(tg_token)
            if info.get("ok"):
                safe_config["telegram_bot_username"] = info.get("username", "")
    except Exception as e:
        logger.warning(f"Telegram alert config read error: {e}")
        safe_config["telegram_admin_chat_id"] = ""
        safe_config["telegram_extra_chat_ids"] = ""
        safe_config["telegram_notify_alert"] = True
        safe_config["telegram_notify_resolved"] = True
        safe_config["telegram_notify_diagnosis"] = True

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

    # Ollama — Explicit provider ayarlarından veya env'den oku
    # openai wrapper üzerinden de olabilir (fetch-failed bug fix)
    ollama_provider = (
        config.get("models", {}).get("providers", {}).get("ollama", {})
        or config.get("models", {}).get("providers", {}).get("openai", {})
    )
    ollama_url = ollama_provider.get("baseUrl", "") or os.environ.get("OLLAMA_BASE_URL", "")
    # baseUrl openai wrapper ise "/v1" suffix'ini temizle
    if ollama_url.endswith("/v1"):
        ollama_url = ollama_url[:-3]
    ollama_api_key = ollama_provider.get("apiKey", "") or os.environ.get("OLLAMA_API_KEY", "")
    safe_config["ollama_url"] = ollama_url
    safe_config["ollama_api_key_set"] = bool(ollama_api_key)

    # Ollama model parametreleri — agents.defaults.contextTokens + agents.defaults.models[model].params
    defaults = config.get("agents", {}).get("defaults", {})
    safe_config["ollama_context_tokens"] = defaults.get("contextTokens", 0)
    # Model-level params (temperature, num_predict, vb.)
    model_key = safe_config.get("model", "")
    models_catalog = defaults.get("models", {})
    # model_key "ollama/X" formatında, config'de "openai/X" olarak yazılıyor (wrapper)
    # Her iki formatta da ara
    model_id_only = model_key.split("/", 1)[1] if "/" in model_key else model_key
    model_entry = (
        models_catalog.get(model_key, {})
        or models_catalog.get(f"openai/{model_id_only}", {})
        or models_catalog.get(f"ollama/{model_id_only}", {})
    )
    model_params = model_entry.get("params", {})
    # UI için JSON string olarak döndür
    safe_config["ollama_model_params"] = json.dumps(model_params, ensure_ascii=False) if model_params else ""

    return {"code": 200, "msg": "success", "data": safe_config}


async def save_openclaw_config(
    data: dict = Body(...),
    authorization: Optional[str] = Header(None)
):
    """AI Agent yapılandırmasını kaydet"""
    try:
        config = _read_config()

        # Agent/Model — yeni format: agents.defaults.model.primary
        if "model" in data:
            agents = config.setdefault("agents", {})
            defaults = agents.setdefault("defaults", {})
            model_cfg = defaults.setdefault("model", {})
            raw_model = data["model"]  # örn: "ollama/llama3.1:8b"
            # openai-responses wrapper kullanan Ollama modelleri için
            # primary key'i provider ile eşleşmeli: "openai/llama3.1:8b"
            if raw_model.startswith("ollama/"):
                model_id_only = raw_model.split("/", 1)[1]
                model_cfg["primary"] = f"openai/{model_id_only}"
            else:
                model_cfg["primary"] = raw_model
            model_cfg.setdefault("fallbacks", [])
            # Eski format varsa temizle
            if "agent" in config and "model" in config.get("agent", {}):
                config["agent"].pop("model", None)
                if not config["agent"]:
                    config.pop("agent", None)

        # API Key — OpenClaw config'e YAZILMAZ (env var olarak geçer)
        # apiKey config'te tanınmayan bir key, GROQ_API_KEY vb. docker env olarak verilir
        # Eğer config'te kalmışsa temizle
        agents_d = config.get("agents", {}).get("defaults", {})
        agents_d.pop("apiKey", None)

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
            tg = config["channels"].setdefault("telegram", {})
            tg["enabled"] = True
            if "telegram_bot_token" in data and data["telegram_bot_token"]:
                tg["botToken"] = data["telegram_bot_token"]
            if "telegram_allow_from" in data:
                allow_list = data["telegram_allow_from"]
                tg["allowFrom"] = allow_list
                # allowFrom doluysa allowlist, boşsa open — böylece herkes yazabilir
                tg["dmPolicy"] = "allowlist" if allow_list else "open"
            # Varsayılanları koru
            tg.setdefault("groupPolicy", "allowlist")
            tg.setdefault("streaming", "off")
            if "telegram_groups" in data:
                tg["groups"] = data["telegram_groups"]

        # Telegram alert ayarlarını telegram_alert_config.py'ye de yaz
        try:
            from server.telegram.telegram_alert_api import _read_config as _read_tg, _write_config as _write_tg
            tg_alert = _read_tg()
            # Bot token — OpenClaw'dan al
            tg_ch = config.get("channels", {}).get("telegram", {})
            bot_token = tg_ch.get("botToken", "") or tg_alert.get("bot_token", "")
            tg_alert["bot_token"] = bot_token
            tg_alert["enabled"] = data.get("telegram_enabled", tg_alert.get("enabled", True))
            if "telegram_admin_chat_id" in data:
                tg_alert["admin_chat_id"] = str(data["telegram_admin_chat_id"]).strip()
            if "telegram_extra_chat_ids" in data:
                tg_alert["extra_chat_ids"] = str(data["telegram_extra_chat_ids"]).strip()
            if "telegram_notify_alert" in data:
                tg_alert["notify_on_alert"] = bool(data["telegram_notify_alert"])
            if "telegram_notify_resolved" in data:
                tg_alert["notify_on_resolved"] = bool(data["telegram_notify_resolved"])
            if "telegram_notify_diagnosis" in data:
                tg_alert["notify_on_diagnosis"] = bool(data["telegram_notify_diagnosis"])
            _write_tg(tg_alert)
        except Exception as e:
            logger.error(f"Telegram alert config write error: {e}")

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
            
        # SSRF Bypass (Required for local Ollama in Docker networks)
        browser = config.setdefault("browser", {})
        browser.setdefault("ssrfPolicy", {})["dangerouslyAllowPrivateNetwork"] = True

        # Ollama
        model_str = data.get("model", "")
        if model_str.startswith("ollama/"):
            ollama_url = str(data.get("ollama_url", "")).strip()
            ollama_key = str(data.get("ollama_api_key", "")).strip() or "ollama-local"
            model_id = model_str.split("/", 1)[1] if "/" in model_str else model_str

            # Explicit provider ayarı — openai-responses wrapper (fetch-failed bug fix)
            models_section = config.setdefault("models", {})
            providers_section = models_section.setdefault("providers", {})
            providers_section.pop("ollama", None)  # Eskisini temizle
            providers_section["openai"] = {
                "apiKey": ollama_key,
                "api": "openai-responses",
                "baseUrl": f"{ollama_url.rstrip('/')}/v1" if ollama_url else "http://host.docker.internal:11434/v1",
                "models": [
                    {
                        "id": model_id,
                        "name": model_id,
                        "reasoning": False,
                        "input": ["text"],
                        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                        "contextWindow": 131072,
                        "maxTokens": 1310720,
                    }
                ],
            }

            # Env section
            env_cfg = config.setdefault("env", {})
            env_cfg["OLLAMA_API_KEY"] = ollama_key
            if ollama_url:
                env_cfg["OLLAMA_BASE_URL"] = ollama_url

            # .env dosyası
            dotenv_path = os.path.join(OPENCLAW_CONFIG_DIR, ".env")
            try:
                os.makedirs(os.path.dirname(dotenv_path), exist_ok=True)
                with open(dotenv_path, "w") as f:
                    f.write(f'OLLAMA_API_KEY="{ollama_key}"\n')
                    if ollama_url:
                        f.write(f'OLLAMA_BASE_URL="{ollama_url}"\n')
            except Exception as e:
                logger.error(f"OpenClaw .env write error: {e}")

            # ── Ollama Model Parametreleri ──────────────────────────────────
            # agents.defaults.contextTokens  →  context penceresi (tokens)
            # agents.defaults.models["openai/<id>"]["params"]  →  temperature, num_predict vb.
            # Bu path OpenClaw Zod şemasına göre tamamen geçerlidir.
            agents_def = config.setdefault("agents", {}).setdefault("defaults", {})
            # Eski hatalı key'i temizle (önceki oturumdan kalmış olabilir)
            agents_def.pop("params", None)

            # context_tokens
            context_tokens_raw = data.get("ollama_context_tokens", 0)
            try:
                context_tokens = int(context_tokens_raw)
            except (TypeError, ValueError):
                context_tokens = 0
            if context_tokens > 0:
                agents_def["contextTokens"] = context_tokens
            else:
                agents_def.pop("contextTokens", None)

            # model-level params (temperature, num_predict, num_ctx vb.)
            params_raw = str(data.get("ollama_model_params", "")).strip()
            model_full_key = f"openai/{model_id}"  # provider/model formatı
            models_catalog = agents_def.setdefault("models", {})
            if params_raw:
                try:
                    extra_params = json.loads(params_raw)
                    if isinstance(extra_params, dict) and extra_params:
                        models_catalog[model_full_key] = {"params": extra_params}
                    else:
                        models_catalog.pop(model_full_key, None)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"ollama_model_params parse hatası, atlanıyor: {e}")
                    models_catalog.pop(model_full_key, None)
            else:
                models_catalog.pop(model_full_key, None)
            # Boş katalog varsa temizle
            if not models_catalog:
                agents_def.pop("models", None)

        # API Key — provider'a göre docker/env olarak set etmek isterseniz (opsiyonel)
        # Buraları dokunmuyoruz.
        
        _write_config(config)
        return {"code": 200, "msg": "AI Agent ayarları kaydedildi"}
    except Exception as e:
        return {"code": 500, "msg": f"Kaydetme hatası: {str(e)[:200]}"}


# ── Mesaj Gönder ──────────────────────────────────────────
async def openclaw_send_message(
    data: dict = Body(...),
    authorization: Optional[str] = Header(None)
):
    """AI Agent üzerinden mesaj gönder"""
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
    """AI Agent aktif channel'ları listele"""
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
    """AI Agent Gateway'i yeniden başlat (Docker container restart)"""
    try:
        connector = aiohttp.UnixConnector(path="/var/run/docker.sock")
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                f"http://localhost/containers/{OPENCLAW_CONTAINER}/restart",
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 204:
                    return {"code": 200, "msg": "Gateway yeniden başlatılıyor"}
                else:
                    body = await resp.text()
                    return {"code": resp.status, "msg": f"Docker restart hatası: {body[:200]}"}
    except Exception as e:
        return {"code": 500, "msg": f"Restart hatası: {str(e)[:200]}"}


# ── Model Listesi ─────────────────────────────────────────
# Model kataloğu OpenClaw CLI'dan çekilir ve bellekte cache'lenir.
_models_cache: dict = {"data": None, "ts": 0}
_MODELS_CACHE_TTL = 600  # 10 dakika

OPENCLAW_CONTAINER = os.environ.get("OPENCLAW_CONTAINER_NAME", "anomivox-ai-agent-1")


async def _docker_exec(container: str, cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Docker socket API üzerinden container'da komut çalıştır"""
    import urllib.parse
    try:
        connector = aiohttp.UnixConnector(path="/var/run/docker.sock")
        async with aiohttp.ClientSession(connector=connector) as session:
            # 1. exec oluştur
            create_url = f"http://localhost/containers/{container}/exec"
            create_body = {
                "AttachStdout": True,
                "AttachStderr": True,
                "Cmd": cmd,
            }
            async with session.post(create_url, json=create_body) as resp:
                if resp.status != 201:
                    err = await resp.text()
                    return 1, "", f"exec create failed ({resp.status}): {err[:200]}"
                exec_id = (await resp.json())["Id"]

            # 2. exec başlat
            start_url = f"http://localhost/exec/{exec_id}/start"
            async with session.post(start_url, json={"Detach": False}) as resp:
                raw = await asyncio.wait_for(resp.read(), timeout=timeout)
                # Docker demux: ilk 8 byte header, kalan data
                output = _demux_docker_stream(raw)

            # 3. exit code al
            inspect_url = f"http://localhost/exec/{exec_id}/json"
            async with session.get(inspect_url) as resp:
                info = await resp.json()
                exit_code = info.get("ExitCode", -1)

            return exit_code, output, ""
    except Exception as e:
        return 1, "", str(e)[:300]


def _demux_docker_stream(data: bytes) -> str:
    """Docker stream multiplexing format'ını parse et"""
    output = []
    pos = 0
    while pos + 8 <= len(data):
        # header: [stream_type(1), 0, 0, 0, size(4)]
        stream_type = data[pos]
        size = int.from_bytes(data[pos+4:pos+8], "big")
        pos += 8
        if pos + size > len(data):
            # Kalan veriyi al
            output.append(data[pos:].decode("utf-8", errors="replace"))
            break
        chunk = data[pos:pos+size].decode("utf-8", errors="replace")
        if stream_type in (1, 2):  # stdout veya stderr
            output.append(chunk)
        pos += size
    # Eğer demux başarısızsa, raw olarak dön
    if not output and data:
        return data.decode("utf-8", errors="replace")
    return "".join(output)


async def _exec_openclaw_models_list() -> list:
    """AI Agent container'ından model listesini al"""
    try:
        exit_code, stdout, stderr = await _docker_exec(
            OPENCLAW_CONTAINER,
            ["openclaw", "models", "list", "--all", "--json"],
            timeout=30,
        )
        if exit_code == 0 and stdout:
            result = json.loads(stdout)
            return result.get("models", [])
        else:
            logger.error(f"ai-agent models list failed (exit={exit_code}): {stderr[:200]}")
            return []
    except json.JSONDecodeError as e:
        logger.error(f"Model list JSON parse error: {e}")
        return []
    except Exception as e:
        logger.error(f"Model list error: {e}")
        return []


async def openclaw_models(
    provider: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """AI Agent'un desteklediği model kataloğunu döndür"""
    import time
    now = time.time()

    # Cache kontrolü
    if _models_cache["data"] and (now - _models_cache["ts"]) < _MODELS_CACHE_TTL:
        models = _models_cache["data"]
    else:
        models = await _exec_openclaw_models_list()
        if models:
            _models_cache["data"] = models
            _models_cache["ts"] = now
        else:
            models = _models_cache["data"] or []

    # Provider filtresi
    if provider:
        provider_lower = provider.lower()
        models = [m for m in models if m.get("key", "").startswith(f"{provider_lower}/")]

    # Provider'a göre grupla
    providers = {}
    for m in models:
        key = m.get("key", "")
        p = key.split("/")[0] if "/" in key else "other"
        if p not in providers:
            providers[p] = []
        providers[p].append({
            "key": key,
            "name": m.get("name", key),
            "context_window": m.get("contextWindow", 0),
            "available": m.get("available", False),
            "input": m.get("input", "text"),
        })

    return {"code": 200, "msg": "success", "data": {
        "total": len(models),
        "providers": providers,
    }}
