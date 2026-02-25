"""
WhatsApp Bot Yapılandırma API'si
— Settings sayfasından WhatsApp ayarlarını okuma/yazma
"""
import os
import re
from fastapi import Body, Header
from typing import Optional
from server.utils import BaseResponse
from server.auth.auth_api import _require_admin


CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs", "whatsapp_config.py")


def _read_config() -> dict:
    """whatsapp_config.py'den mevcut ayarları oku."""
    config = {
        "access_token": "",
        "phone_number_id": "",
        "business_account_id": "",
        "verify_token": "anomivox_whatsapp_verify_2024",
        "allowed_numbers": "",
        "notify_on_alert": True,
        "notify_on_diagnosis": True,
        "auto_diagnose": False,
        "health_check_interval": 300,
        "slow_query_threshold": 5.0,
    }

    if not os.path.exists(CONFIG_PATH):
        return config

    with open(CONFIG_PATH, "r") as f:
        content = f.read()

    # Access token
    m = re.search(r'WHATSAPP_ACCESS_TOKEN\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["access_token"] = m.group(1)

    # Phone Number ID
    m = re.search(r'WHATSAPP_PHONE_NUMBER_ID\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["phone_number_id"] = m.group(1)

    # Business Account ID
    m = re.search(r'WHATSAPP_BUSINESS_ACCOUNT_ID\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["business_account_id"] = m.group(1)

    # Verify Token
    m = re.search(r'WHATSAPP_VERIFY_TOKEN\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["verify_token"] = m.group(1)

    # Allowed numbers
    m = re.search(r'WHATSAPP_ALLOWED_NUMBERS.*?os\.getenv\([^,]+,\s*"([^"]*)"\)', content, re.DOTALL)
    if m:
        config["allowed_numbers"] = m.group(1)

    # Booleans
    m = re.search(r'WHATSAPP_NOTIFY_ON_ALERT\s*=\s*(True|False)', content)
    if m:
        config["notify_on_alert"] = m.group(1) == "True"

    m = re.search(r'WHATSAPP_NOTIFY_ON_DIAGNOSIS\s*=\s*(True|False)', content)
    if m:
        config["notify_on_diagnosis"] = m.group(1) == "True"

    m = re.search(r'WHATSAPP_AUTO_DIAGNOSE\s*=\s*(True|False)', content)
    if m:
        config["auto_diagnose"] = m.group(1) == "True"

    # Health check interval
    m = re.search(r'WHATSAPP_HEALTH_CHECK_INTERVAL\s*=\s*(\d+)', content)
    if m:
        config["health_check_interval"] = int(m.group(1))

    # Slow query threshold
    m = re.search(r'WHATSAPP_SLOW_QUERY_THRESHOLD\s*=\s*([\d.]+)', content)
    if m:
        config["slow_query_threshold"] = float(m.group(1))

    return config


def _write_config(config: dict):
    """whatsapp_config.py'ye ayarları yaz."""
    content = '''import os

# ─────────────────────────────────────────
# WhatsApp Business Cloud API Yapılandırması
# ─────────────────────────────────────────

# Meta Developer Console'dan alınan kalıcı erişim token'ı
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "{access_token}")

# WhatsApp Business Phone Number ID (Meta Console → WhatsApp → API Setup)
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "{phone_number_id}")

# WhatsApp Business Account ID
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "{business_account_id}")

# Webhook Verify Token (Meta webhook doğrulama için)
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "{verify_token}")

# Mesaj alabilecek yetkili telefon numaraları (uluslararası formatta)
WHATSAPP_ALLOWED_NUMBERS = [
    num.strip()
    for num in os.getenv("WHATSAPP_ALLOWED_NUMBERS", "{allowed_numbers}").split(",")
    if num.strip()
]

# Anomivox API adresi (Docker iç ağdan erişim)
WHATSAPP_API_URL = os.getenv("ANOMIVOX_API_URL", "http://api:7861")

# Prometheus API adresi
WHATSAPP_PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

# PostgreSQL bağlantı bilgileri
WHATSAPP_PG_HOST = os.getenv("PG_HOST", "postgres_db")
WHATSAPP_PG_PORT = int(os.getenv("PG_PORT", "5432"))
WHATSAPP_PG_USER = os.getenv("PG_USER", "test")
WHATSAPP_PG_PASSWORD = os.getenv("PG_PASSWORD", "Test123_456")
WHATSAPP_PG_DB = os.getenv("PG_DB", "anomivox")

# Bildirim ayarları
WHATSAPP_NOTIFY_ON_ALERT = {notify_on_alert}
WHATSAPP_NOTIFY_ON_DIAGNOSIS = {notify_on_diagnosis}
WHATSAPP_AUTO_DIAGNOSE = {auto_diagnose}

# Proaktif izleme
WHATSAPP_HEALTH_CHECK_INTERVAL = {health_check_interval}
WHATSAPP_SLOW_QUERY_THRESHOLD = {slow_query_threshold}
'''.format(
        access_token=config.get("access_token", ""),
        phone_number_id=config.get("phone_number_id", ""),
        business_account_id=config.get("business_account_id", ""),
        verify_token=config.get("verify_token", "anomivox_whatsapp_verify_2024"),
        allowed_numbers=config.get("allowed_numbers", ""),
        notify_on_alert=config.get("notify_on_alert", True),
        notify_on_diagnosis=config.get("notify_on_diagnosis", True),
        auto_diagnose=config.get("auto_diagnose", False),
        health_check_interval=config.get("health_check_interval", 300),
        slow_query_threshold=config.get("slow_query_threshold", 5.0),
    )

    with open(CONFIG_PATH, "w") as f:
        f.write(content)


async def get_whatsapp_config(
    authorization: Optional[str] = Header(None),
):
    """WhatsApp yapılandırmasını getir (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err

    config = _read_config()
    # Token'ı maskele (güvenlik)
    if config["access_token"]:
        token = config["access_token"]
        if len(token) > 10:
            config["access_token_masked"] = token[:6] + "•" * (len(token) - 10) + token[-4:]
        else:
            config["access_token_masked"] = "•" * len(token)
        config["access_token_set"] = True
    else:
        config["access_token_masked"] = ""
        config["access_token_set"] = False

    # Token'ı response'da gönderme
    del config["access_token"]

    return BaseResponse(code=200, msg="success", data=config)


async def save_whatsapp_config(
    access_token: Optional[str] = Body(None, description="Access token (boş gönderilirse değiştirilmez)"),
    phone_number_id: str = Body("", description="Phone Number ID"),
    business_account_id: str = Body("", description="Business Account ID"),
    verify_token: str = Body("anomivox_whatsapp_verify_2024", description="Webhook Verify Token"),
    allowed_numbers: str = Body("", description="Yetkili telefon numaraları (virgülle ayrılmış)"),
    notify_on_alert: bool = Body(True, description="Alert bildirimi"),
    notify_on_diagnosis: bool = Body(True, description="Teşhis bildirimi"),
    auto_diagnose: bool = Body(False, description="Otomatik teşhis"),
    health_check_interval: int = Body(300, description="Sağlık kontrolü aralığı (saniye)"),
    slow_query_threshold: float = Body(5.0, description="Yavaş sorgu eşiği (saniye)"),
    authorization: Optional[str] = Header(None),
):
    """WhatsApp yapılandırmasını kaydet (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err

    # Mevcut config'i oku
    current = _read_config()

    # Token boş gönderilmişse mevcut token'ı koru
    if access_token is None or access_token == "":
        access_token = current.get("access_token", "")

    new_config = {
        "access_token": access_token,
        "phone_number_id": phone_number_id,
        "business_account_id": business_account_id,
        "verify_token": verify_token,
        "allowed_numbers": allowed_numbers,
        "notify_on_alert": notify_on_alert,
        "notify_on_diagnosis": notify_on_diagnosis,
        "auto_diagnose": auto_diagnose,
        "health_check_interval": health_check_interval,
        "slow_query_threshold": slow_query_threshold,
    }

    try:
        _write_config(new_config)
        return BaseResponse(code=200, msg="WhatsApp ayarları kaydedildi")
    except Exception as e:
        return BaseResponse(code=500, msg=f"Kaydetme hatası: {str(e)}")


async def test_whatsapp_connection(
    authorization: Optional[str] = Header(None),
):
    """WhatsApp API bağlantısını test et (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err

    config = _read_config()
    access_token = config.get("access_token", "")
    phone_number_id = config.get("phone_number_id", "")

    if not access_token:
        return BaseResponse(code=400, msg="Access Token ayarlanmamış", data={"connected": False})

    if not phone_number_id:
        return BaseResponse(code=400, msg="Phone Number ID ayarlanmamış", data={"connected": False})

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Phone number bilgilerini kontrol et
            url = f"https://graph.facebook.com/v21.0/{phone_number_id}"
            headers = {"Authorization": f"Bearer {access_token}"}
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()

            if resp.status != 200 or data.get("error"):
                error_msg = data.get("error", {}).get("message", "Bilinmeyen hata")
                return BaseResponse(
                    code=400,
                    msg=f"WhatsApp API hatası: {error_msg}",
                    data={"connected": False}
                )

            display_name = data.get("verified_name", data.get("display_phone_number", ""))

            return BaseResponse(
                code=200,
                msg="Bağlantı başarılı",
                data={
                    "connected": True,
                    "phone_number": data.get("display_phone_number", ""),
                    "verified_name": display_name,
                    "quality_rating": data.get("quality_rating", ""),
                }
            )
    except ImportError:
        return BaseResponse(code=500, msg="aiohttp paketi yüklü değil", data={"connected": False})
    except Exception as e:
        return BaseResponse(code=500, msg=f"Bağlantı hatası: {str(e)}", data={"connected": False})
