"""
Telegram Bot Yapılandırma API'si
— Settings sayfasından Telegram ayarlarını okuma/yazma
"""
import os
import re
from fastapi import Body, Header
from typing import Optional
from server.utils import BaseResponse
from server.auth.auth_api import _require_admin


CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs", "telegram_config.py")


def _read_config() -> dict:
    """telegram_config.py'den mevcut ayarları oku."""
    config = {
        "bot_token": "",
        "chat_id": "",
        "allowed_users": "",
        "notify_on_alert": True,
        "notify_on_diagnosis": True,
        "auto_diagnose": True,
        "health_check_interval": 300,
        "slow_query_threshold": 5.0,
    }

    if not os.path.exists(CONFIG_PATH):
        return config

    with open(CONFIG_PATH, "r") as f:
        content = f.read()

    # Bot token
    m = re.search(r'TELEGRAM_BOT_TOKEN\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["bot_token"] = m.group(1)

    # Chat ID
    m = re.search(r'TELEGRAM_CHAT_ID\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["chat_id"] = m.group(1)

    # Allowed users
    m = re.search(r'TELEGRAM_ALLOWED_USERS.*?os\.getenv\([^,]+,\s*"([^"]*)"\)', content, re.DOTALL)
    if m:
        config["allowed_users"] = m.group(1)

    # Booleans
    m = re.search(r'TELEGRAM_NOTIFY_ON_ALERT\s*=\s*(True|False)', content)
    if m:
        config["notify_on_alert"] = m.group(1) == "True"

    m = re.search(r'TELEGRAM_NOTIFY_ON_DIAGNOSIS\s*=\s*(True|False)', content)
    if m:
        config["notify_on_diagnosis"] = m.group(1) == "True"

    m = re.search(r'TELEGRAM_AUTO_DIAGNOSE\s*=\s*(True|False)', content)
    if m:
        config["auto_diagnose"] = m.group(1) == "True"

    # Health check interval
    m = re.search(r'TELEGRAM_HEALTH_CHECK_INTERVAL\s*=\s*(\d+)', content)
    if m:
        config["health_check_interval"] = int(m.group(1))

    # Slow query threshold
    m = re.search(r'TELEGRAM_SLOW_QUERY_THRESHOLD\s*=\s*([\d.]+)', content)
    if m:
        config["slow_query_threshold"] = float(m.group(1))

    return config


def _write_config(config: dict):
    """telegram_config.py'ye ayarları yaz."""
    content = '''import os

# ─────────────────────────────────────────
# Telegram Bot Yapılandırması
# ─────────────────────────────────────────

# BotFather'dan alınan token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "{bot_token}")

# Bildirimlerin gönderileceği chat ID (grup veya kişisel)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "{chat_id}")

# Bot'a komut gönderebilecek yetkili kullanıcı ID'leri
TELEGRAM_ALLOWED_USERS = [
    int(uid.strip())
    for uid in os.getenv("TELEGRAM_ALLOWED_USERS", "{allowed_users}").split(",")
    if uid.strip()
]

# Anomivox API adresi (Docker iç ağdan erişim)
ANOMIVOX_API_URL = os.getenv("ANOMIVOX_API_URL", "http://api:7861")

# Prometheus API adresi
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

# PostgreSQL bağlantı bilgileri
TELEGRAM_PG_HOST = os.getenv("PG_HOST", "postgres_db")
TELEGRAM_PG_PORT = int(os.getenv("PG_PORT", "5432"))
TELEGRAM_PG_USER = os.getenv("PG_USER", "test")
TELEGRAM_PG_PASSWORD = os.getenv("PG_PASSWORD", "Test123_456")
TELEGRAM_PG_DB = os.getenv("PG_DB", "anomivox")

# Bildirim ayarları
TELEGRAM_NOTIFY_ON_ALERT = {notify_on_alert}
TELEGRAM_NOTIFY_ON_DIAGNOSIS = {notify_on_diagnosis}
TELEGRAM_AUTO_DIAGNOSE = {auto_diagnose}

# Proaktif izleme
TELEGRAM_HEALTH_CHECK_INTERVAL = {health_check_interval}
TELEGRAM_SLOW_QUERY_THRESHOLD = {slow_query_threshold}
'''.format(
        bot_token=config.get("bot_token", ""),
        chat_id=config.get("chat_id", ""),
        allowed_users=config.get("allowed_users", ""),
        notify_on_alert=config.get("notify_on_alert", True),
        notify_on_diagnosis=config.get("notify_on_diagnosis", True),
        auto_diagnose=config.get("auto_diagnose", True),
        health_check_interval=config.get("health_check_interval", 300),
        slow_query_threshold=config.get("slow_query_threshold", 5.0),
    )

    with open(CONFIG_PATH, "w") as f:
        f.write(content)


async def get_telegram_config(
    authorization: Optional[str] = Header(None),
):
    """Telegram yapılandırmasını getir (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err

    config = _read_config()
    # Token'ı maskele (güvenlik)
    if config["bot_token"]:
        token = config["bot_token"]
        if len(token) > 10:
            config["bot_token_masked"] = token[:6] + "•" * (len(token) - 10) + token[-4:]
        else:
            config["bot_token_masked"] = "•" * len(token)
        config["bot_token_set"] = True
    else:
        config["bot_token_masked"] = ""
        config["bot_token_set"] = False

    # Token'ı response'da gönderme
    del config["bot_token"]

    return BaseResponse(code=200, msg="success", data=config)


async def save_telegram_config(
    bot_token: Optional[str] = Body(None, description="Bot token (boş gönderilirse değiştirilmez)"),
    chat_id: str = Body("", description="Chat ID"),
    allowed_users: str = Body("", description="Yetkili kullanıcı ID'leri (virgülle ayrılmış)"),
    notify_on_alert: bool = Body(True, description="Alert bildirimi"),
    notify_on_diagnosis: bool = Body(True, description="Teşhis bildirimi"),
    auto_diagnose: bool = Body(True, description="Otomatik teşhis"),
    health_check_interval: int = Body(300, description="Sağlık kontrolü aralığı (saniye)"),
    slow_query_threshold: float = Body(5.0, description="Yavaş sorgu eşiği (saniye)"),
    authorization: Optional[str] = Header(None),
):
    """Telegram yapılandırmasını kaydet (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err

    # Mevcut config'i oku
    current = _read_config()

    # Token boş gönderilmişse mevcut token'ı koru
    if bot_token is None or bot_token == "":
        bot_token = current.get("bot_token", "")

    new_config = {
        "bot_token": bot_token,
        "chat_id": chat_id,
        "allowed_users": allowed_users,
        "notify_on_alert": notify_on_alert,
        "notify_on_diagnosis": notify_on_diagnosis,
        "auto_diagnose": auto_diagnose,
        "health_check_interval": health_check_interval,
        "slow_query_threshold": slow_query_threshold,
    }

    try:
        _write_config(new_config)
        return BaseResponse(code=200, msg="Telegram ayarları kaydedildi")
    except Exception as e:
        return BaseResponse(code=500, msg=f"Kaydetme hatası: {str(e)}")


async def test_telegram_connection(
    authorization: Optional[str] = Header(None),
):
    """Telegram bot bağlantısını test et (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err

    config = _read_config()
    bot_token = config.get("bot_token", "")
    chat_id = config.get("chat_id", "")

    if not bot_token:
        return BaseResponse(code=400, msg="Bot token ayarlanmamış", data={"connected": False})

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Bot bilgilerini kontrol et
            async with session.get(f"https://api.telegram.org/bot{bot_token}/getMe") as resp:
                data = await resp.json()

            if not data.get("ok"):
                return BaseResponse(
                    code=400,
                    msg=f"Geçersiz bot token: {data.get('description', 'Bilinmeyen hata')}",
                    data={"connected": False}
                )

            bot_info = data.get("result", {})
            bot_name = bot_info.get("first_name", "")
            bot_username = bot_info.get("username", "")

            # Chat ID varsa mesaj göndermeyi dene
            message_sent = False
            if chat_id:
                try:
                    test_msg = f"✅ Anomivox Telegram Bot bağlantı testi başarılı!\n\n🤖 Bot: @{bot_username}"
                    async with session.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={"chat_id": chat_id, "text": test_msg, "parse_mode": "Markdown"}
                    ) as msg_resp:
                        msg_data = await msg_resp.json()
                        message_sent = msg_data.get("ok", False)
                except Exception:
                    pass

            return BaseResponse(
                code=200,
                msg="Bağlantı başarılı",
                data={
                    "connected": True,
                    "bot_name": bot_name,
                    "bot_username": f"@{bot_username}",
                    "message_sent": message_sent,
                }
            )

    except Exception as e:
        return BaseResponse(
            code=500,
            msg=f"Bağlantı hatası: {str(e)}",
            data={"connected": False}
        )
