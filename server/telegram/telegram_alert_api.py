"""
Telegram Alert Bildirimleri — Config API

Settings UI'dan Telegram bot token, chat_id ve bildirim
tercihlerini yönetir.
"""
import os
import re
import logging
import requests
from fastapi import Body, Header
from typing import Optional

logger = logging.getLogger("telegram_alert_api")

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "configs", "telegram_alert_config.py"
)


def _read_config() -> dict:
    """telegram_alert_config.py'den mevcut ayarları oku.
    Token bulunamazsa openclaw.json'dan da dener."""
    config = {
        "enabled": True,
        "bot_token": "",
        "bot_token_set": False,
        "admin_chat_id": "",
        "extra_chat_ids": "",
        "notify_on_alert": True,
        "notify_on_resolved": True,
        "notify_on_diagnosis": True,
        "bot_username": "",
    }
    if not os.path.exists(CONFIG_PATH):
        # Config dosyası yoksa, OpenClaw'dan token almayı dene
        token = _get_token_from_openclaw()
        if token:
            config["bot_token"] = token
            config["bot_token_set"] = True
        return config

    try:
        with open(CONFIG_PATH, "r") as f:
            content = f.read()

        def extract(key, default=""):
            m = re.search(rf'^{key}\s*=\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
            if m:
                val = m.group(1)
                return val
            m2 = re.search(rf'^{key}\s*=\s*(True|False)', content, re.MULTILINE)
            if m2:
                return m2.group(1) == "True"
            return default

        token = extract("TELEGRAM_BOT_TOKEN", "")
        # Token yoksa OpenClaw'dan al
        if not token:
            token = _get_token_from_openclaw()
        config["bot_token"] = token
        config["bot_token_set"] = bool(token)
        config["enabled"] = extract("TELEGRAM_ALERT_ENABLED", True)
        if isinstance(config["enabled"], str):
            config["enabled"] = config["enabled"] == "True"
        config["admin_chat_id"] = extract("TELEGRAM_ADMIN_CHAT_ID", "")
        config["extra_chat_ids"] = extract("TELEGRAM_EXTRA_CHAT_IDS", "")
        config["notify_on_alert"] = extract("NOTIFY_ON_ALERT", True)
        if isinstance(config["notify_on_alert"], str):
            config["notify_on_alert"] = config["notify_on_alert"] == "True"
        config["notify_on_resolved"] = extract("NOTIFY_ON_RESOLVED", True)
        if isinstance(config["notify_on_resolved"], str):
            config["notify_on_resolved"] = config["notify_on_resolved"] == "True"
        config["notify_on_diagnosis"] = extract("NOTIFY_ON_DIAGNOSIS", True)
        if isinstance(config["notify_on_diagnosis"], str):
            config["notify_on_diagnosis"] = config["notify_on_diagnosis"] == "True"

    except Exception as e:
        logger.error(f"Config read error: {e}")

    return config


def _get_token_from_openclaw() -> str:
    """openclaw.json'dan Telegram bot token'ı al"""
    try:
        openclaw_dir = os.environ.get(
            "OPENCLAW_CONFIG_DIR",
            os.path.join(os.path.expanduser("~"), ".openclaw")
        )
        openclaw_path = os.path.join(openclaw_dir, "openclaw.json")
        if os.path.exists(openclaw_path):
            import json
            with open(openclaw_path, "r") as f:
                oc = json.load(f)
            return oc.get("channels", {}).get("telegram", {}).get("botToken", "")
    except Exception as e:
        logger.warning(f"OpenClaw config read for token: {e}")
    return ""


def _write_config(config: dict):
    """telegram_alert_config.py'ye ayarları yaz."""
    token = config.get("bot_token", "")
    content = f'''# ═════════════════════════════════════════════════════════
# Telegram Alert Bildirimleri Yapılandırması
# ═════════════════════════════════════════════════════════
# Bu dosya Settings UI'dan otomatik güncellenir.
# Manuel düzenleme yapmayın.

TELEGRAM_ALERT_ENABLED = {config.get("enabled", True)}

# @Anomivoxbot — BotFather'dan alınan token
TELEGRAM_BOT_TOKEN = "{token}"

# Bildirimlerin gönderileceği admin chat ID
TELEGRAM_ADMIN_CHAT_ID = "{config.get("admin_chat_id", "")}"

# Ek alıcı chat ID'ler (virgülle ayrılmış)
TELEGRAM_EXTRA_CHAT_IDS = "{config.get("extra_chat_ids", "")}"

# Bildirim tercihleri
NOTIFY_ON_ALERT = {config.get("notify_on_alert", True)}
NOTIFY_ON_RESOLVED = {config.get("notify_on_resolved", True)}
NOTIFY_ON_DIAGNOSIS = {config.get("notify_on_diagnosis", True)}
'''
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        f.write(content)
    logger.info("Telegram alert config saved")


def _get_bot_info(token: str) -> dict:
    """Telegram Bot API — getMe ile bot bilgisini al"""
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                bot = data["result"]
                return {
                    "ok": True,
                    "username": bot.get("username", ""),
                    "first_name": bot.get("first_name", ""),
                    "id": bot.get("id", ""),
                }
        return {"ok": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ── API Endpoints ─────────────────────────────────────────

async def get_telegram_alert_config(
    authorization: Optional[str] = Header(None)
):
    """Telegram alert ayarlarını getir"""
    config = _read_config()
    # Token'ı maskele
    safe = dict(config)
    safe.pop("bot_token", None)

    # Bot bilgisini al
    if config["bot_token_set"]:
        info = _get_bot_info(config["bot_token"])
        if info.get("ok"):
            safe["bot_username"] = info["username"]
            safe["bot_name"] = info["first_name"]
            safe["bot_id"] = info["id"]

    return {"code": 200, "msg": "success", "data": safe}


async def save_telegram_alert_config(
    data: dict = Body(...),
    authorization: Optional[str] = Header(None)
):
    """Telegram alert ayarlarını kaydet"""
    try:
        config = _read_config()

        if "enabled" in data:
            config["enabled"] = bool(data["enabled"])
        if "bot_token" in data and data["bot_token"]:
            config["bot_token"] = data["bot_token"]
        if "admin_chat_id" in data:
            config["admin_chat_id"] = str(data["admin_chat_id"]).strip()
        if "extra_chat_ids" in data:
            config["extra_chat_ids"] = str(data["extra_chat_ids"]).strip()
        if "notify_on_alert" in data:
            config["notify_on_alert"] = bool(data["notify_on_alert"])
        if "notify_on_resolved" in data:
            config["notify_on_resolved"] = bool(data["notify_on_resolved"])
        if "notify_on_diagnosis" in data:
            config["notify_on_diagnosis"] = bool(data["notify_on_diagnosis"])

        _write_config(config)
        return {"code": 200, "msg": "Telegram alert ayarları kaydedildi"}
    except Exception as e:
        return {"code": 500, "msg": f"Kaydetme hatası: {str(e)[:200]}"}


async def test_telegram_alert(
    authorization: Optional[str] = Header(None)
):
    """Telegram'a test mesajı gönder"""
    config = _read_config()

    if not config.get("bot_token"):
        return {"code": 400, "msg": "Bot token ayarlanmamış"}

    # Bot doğrula
    info = _get_bot_info(config["bot_token"])
    if not info.get("ok"):
        return {"code": 400, "msg": f"Bot token geçersiz: {info.get('error', '?')}"}

    chat_id = config.get("admin_chat_id", "").strip()
    if not chat_id:
        return {"code": 400, "msg": "Admin Chat ID boş. Önce 'Chat ID Bul' ile Chat ID'nizi öğrenin, kaydedin ve tekrar deneyin."}

    # Test mesajı gönder
    try:
        msg = (
            "✅ *Anomivox Telegram Bağlantı Testi*\n\n"
            f"🤖 Bot: @{info.get('username', '?')}\n"
            f"📡 Chat ID: `{chat_id}`\n"
            f"⏰ Zaman: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "Telegram alert bildirimleri başarıyla yapılandırıldı! 🎉\n"
            "Prometheus alertleri bu kanala gönderilecek."
        )
        resp = requests.post(
            f"https://api.telegram.org/bot{config['bot_token']}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            return {"code": 200, "msg": "Test mesajı başarıyla gönderildi!", "data": {
                "bot_username": info.get("username"),
                "chat_id": chat_id,
            }}
        else:
            error = resp.json().get("description", resp.text[:200])
            return {"code": 400, "msg": f"Telegram hatası: {error}"}
    except Exception as e:
        return {"code": 500, "msg": f"Gönderme hatası: {str(e)[:200]}"}


async def telegram_get_chat_id(
    authorization: Optional[str] = Header(None)
):
    """Bot'a gelen son mesajlardan chat_id bul.
    OpenClaw polling yapıyorsa, önce webhook'u kontrol et ve
    geçici olarak getUpdates'e izin ver."""
    config = _read_config()
    if not config.get("bot_token"):
        return {"code": 400, "msg": "Bot token ayarlanmamış"}

    token = config["bot_token"]

    try:
        # 1. Önce webhook durumunu kontrol et
        wh_resp = requests.get(
            f"https://api.telegram.org/bot{token}/getWebhookInfo",
            timeout=10,
        )
        webhook_url = ""
        pending_count = 0
        if wh_resp.status_code == 200:
            wh_data = wh_resp.json().get("result", {})
            webhook_url = wh_data.get("url", "")
            pending_count = wh_data.get("pending_update_count", 0)

        # 2. Eğer webhook aktifse, geçici olarak kaldır
        had_webhook = bool(webhook_url)
        if had_webhook:
            requests.post(
                f"https://api.telegram.org/bot{token}/deleteWebhook",
                json={"drop_pending_updates": False},
                timeout=10,
            )
            import time
            time.sleep(0.5)

        # 3. getUpdates dene
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"limit": 50, "timeout": 2},
            timeout=15,
        )

        # 4. Webhook'u geri koy
        if had_webhook:
            requests.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json={"url": webhook_url},
                timeout=10,
            )

        if resp.status_code == 200:
            data = resp.json()
            chats = []
            seen = set()
            for update in data.get("result", []):
                # message, edited_message, my_chat_member gibi farklı update tiplerini kontrol et
                for key in ("message", "edited_message", "my_chat_member", "chat_member"):
                    msg_or_event = update.get(key, {})
                    chat = msg_or_event.get("chat", {})
                    if not chat:
                        continue
                    chat_id = chat.get("id")
                    if chat_id and chat_id not in seen:
                        seen.add(chat_id)
                        chats.append({
                            "chat_id": chat_id,
                            "type": chat.get("type", ""),
                            "title": chat.get("title", ""),
                            "username": chat.get("username", ""),
                            "first_name": chat.get("first_name", ""),
                        })
            hint = ""
            if not chats:
                hint = "Sonuç bulunamadı. Telegram'da bota /start yazın, 10 saniye bekleyin, sonra tekrar deneyin."
            return {"code": 200, "msg": "success", "data": {
                "chats": chats,
                "had_webhook": had_webhook,
                "hint": hint,
            }}
        return {"code": 400, "msg": f"Telegram API hatası: {resp.status_code}"}
    except Exception as e:
        return {"code": 500, "msg": str(e)[:200]}
