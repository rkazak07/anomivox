"""
E-Posta Bildirim Yapılandırma API'si
— Settings sayfasından mail ayarlarını okuma/yazma/test
"""
import os
import re
from fastapi import Body, Header
from typing import Optional
from server.utils import BaseResponse
from server.auth.auth_api import _require_admin


CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs", "mail_config.py")


def _read_config() -> dict:
    """mail_config.py'den mevcut ayarları oku."""
    config = {
        "smtp_host": "",
        "smtp_port": 587,
        "use_tls": True,
        "use_ssl": False,
        "username": "",
        "password": "",
        "from_name": "Anomivox",
        "from_address": "",
        "recipients": "",
        "notify_on_alert": True,
        "notify_on_diagnosis": True,
        "notify_on_health": False,
        "health_check_interval": 300,
        "slow_query_threshold": 5.0,
    }

    if not os.path.exists(CONFIG_PATH):
        return config

    with open(CONFIG_PATH, "r") as f:
        content = f.read()

    # SMTP Host
    m = re.search(r'MAIL_SMTP_HOST\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["smtp_host"] = m.group(1)

    # SMTP Port
    m = re.search(r'MAIL_SMTP_PORT\s*=.*?os\.getenv\([^,]+,\s*"(\d+)"\)', content)
    if m:
        config["smtp_port"] = int(m.group(1))

    # TLS
    m = re.search(r'MAIL_SMTP_USE_TLS\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["use_tls"] = m.group(1).lower() in ("true", "1", "yes")

    # SSL
    m = re.search(r'MAIL_SMTP_USE_SSL\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["use_ssl"] = m.group(1).lower() in ("true", "1", "yes")

    # Username
    m = re.search(r'MAIL_USERNAME\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["username"] = m.group(1)

    # Password
    m = re.search(r'MAIL_PASSWORD\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["password"] = m.group(1)

    # From name
    m = re.search(r'MAIL_FROM_NAME\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["from_name"] = m.group(1)

    # From address
    m = re.search(r'MAIL_FROM_ADDRESS\s*=\s*os\.getenv\([^,]+,\s*"([^"]*)"\)', content)
    if m:
        config["from_address"] = m.group(1)

    # Recipients
    m = re.search(r'MAIL_RECIPIENTS.*?os\.getenv\([^,]+,\s*"([^"]*)"\)', content, re.DOTALL)
    if m:
        config["recipients"] = m.group(1)

    # Booleans
    m = re.search(r'MAIL_NOTIFY_ON_ALERT\s*=\s*(True|False)', content)
    if m:
        config["notify_on_alert"] = m.group(1) == "True"

    m = re.search(r'MAIL_NOTIFY_ON_DIAGNOSIS\s*=\s*(True|False)', content)
    if m:
        config["notify_on_diagnosis"] = m.group(1) == "True"

    m = re.search(r'MAIL_NOTIFY_ON_HEALTH\s*=\s*(True|False)', content)
    if m:
        config["notify_on_health"] = m.group(1) == "True"

    # Health check interval
    m = re.search(r'MAIL_HEALTH_CHECK_INTERVAL\s*=\s*(\d+)', content)
    if m:
        config["health_check_interval"] = int(m.group(1))

    # Slow query threshold
    m = re.search(r'MAIL_SLOW_QUERY_THRESHOLD\s*=\s*([\d.]+)', content)
    if m:
        config["slow_query_threshold"] = float(m.group(1))

    return config


def _write_config(config: dict):
    """mail_config.py'ye ayarları yaz."""
    content = '''import os

# ─────────────────────────────────────────
# E-Posta (SMTP) Bildirim Yapılandırması
# ─────────────────────────────────────────

# SMTP sunucu bilgileri
MAIL_SMTP_HOST = os.getenv("MAIL_SMTP_HOST", "{smtp_host}")
MAIL_SMTP_PORT = int(os.getenv("MAIL_SMTP_PORT", "{smtp_port}"))
MAIL_SMTP_USE_TLS = os.getenv("MAIL_SMTP_USE_TLS", "{use_tls}").lower() in ("true", "1", "yes")
MAIL_SMTP_USE_SSL = os.getenv("MAIL_SMTP_USE_SSL", "{use_ssl}").lower() in ("true", "1", "yes")

# Gönderici hesap bilgileri
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "{username}")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "{password}")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "{from_name}")
MAIL_FROM_ADDRESS = os.getenv("MAIL_FROM_ADDRESS", "{from_address}")

# Alıcılar (virgülle ayrılmış)
MAIL_RECIPIENTS = [
    addr.strip()
    for addr in os.getenv("MAIL_RECIPIENTS", "{recipients}").split(",")
    if addr.strip()
]

# Bildirim ayarları
MAIL_NOTIFY_ON_ALERT = {notify_on_alert}
MAIL_NOTIFY_ON_DIAGNOSIS = {notify_on_diagnosis}
MAIL_NOTIFY_ON_HEALTH = {notify_on_health}

# Proaktif izleme
MAIL_HEALTH_CHECK_INTERVAL = {health_check_interval}
MAIL_SLOW_QUERY_THRESHOLD = {slow_query_threshold}
'''.format(
        smtp_host=config.get("smtp_host", ""),
        smtp_port=config.get("smtp_port", 587),
        use_tls=config.get("use_tls", True),
        use_ssl=config.get("use_ssl", False),
        username=config.get("username", ""),
        password=config.get("password", ""),
        from_name=config.get("from_name", "Anomivox"),
        from_address=config.get("from_address", ""),
        recipients=config.get("recipients", ""),
        notify_on_alert=config.get("notify_on_alert", True),
        notify_on_diagnosis=config.get("notify_on_diagnosis", True),
        notify_on_health=config.get("notify_on_health", False),
        health_check_interval=config.get("health_check_interval", 300),
        slow_query_threshold=config.get("slow_query_threshold", 5.0),
    )

    with open(CONFIG_PATH, "w") as f:
        f.write(content)


async def get_mail_config(
    authorization: Optional[str] = Header(None),
):
    """Mail yapılandırmasını getir (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err

    config = _read_config()

    # Şifreyi maskele
    if config["password"]:
        pw = config["password"]
        if len(pw) > 4:
            config["password_masked"] = pw[:2] + "•" * (len(pw) - 4) + pw[-2:]
        else:
            config["password_masked"] = "•" * len(pw)
        config["password_set"] = True
    else:
        config["password_masked"] = ""
        config["password_set"] = False

    # Şifreyi response'da gönderme
    del config["password"]

    return BaseResponse(code=200, msg="success", data=config)


async def save_mail_config(
    smtp_host: str = Body("", description="SMTP sunucu adresi"),
    smtp_port: int = Body(587, description="SMTP port"),
    use_tls: bool = Body(True, description="STARTTLS kullan"),
    use_ssl: bool = Body(False, description="SSL/TLS kullan"),
    username: str = Body("", description="SMTP kullanıcı adı"),
    password: Optional[str] = Body(None, description="SMTP şifre (boş gönderilirse değiştirilmez)"),
    from_name: str = Body("Anomivox", description="Gönderen adı"),
    from_address: str = Body("", description="Gönderen e-posta adresi"),
    recipients: str = Body("", description="Alıcı e-posta adresleri (virgülle ayrılmış)"),
    notify_on_alert: bool = Body(True, description="Alert bildirimi"),
    notify_on_diagnosis: bool = Body(True, description="Teşhis bildirimi"),
    notify_on_health: bool = Body(False, description="Sağlık uyarısı bildirimi"),
    health_check_interval: int = Body(300, description="Sağlık kontrolü aralığı (saniye)"),
    slow_query_threshold: float = Body(5.0, description="Yavaş sorgu eşiği (saniye)"),
    authorization: Optional[str] = Header(None),
):
    """Mail yapılandırmasını kaydet (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err

    current = _read_config()

    # Şifre boş gönderilmişse mevcut şifreyi koru
    if password is None or password == "":
        password = current.get("password", "")

    new_config = {
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "username": username,
        "password": password,
        "from_name": from_name,
        "from_address": from_address,
        "recipients": recipients,
        "notify_on_alert": notify_on_alert,
        "notify_on_diagnosis": notify_on_diagnosis,
        "notify_on_health": notify_on_health,
        "health_check_interval": health_check_interval,
        "slow_query_threshold": slow_query_threshold,
    }

    try:
        _write_config(new_config)
        return BaseResponse(code=200, msg="Mail ayarları kaydedildi")
    except Exception as e:
        return BaseResponse(code=500, msg=f"Kaydetme hatası: {str(e)}")


async def test_mail_connection(
    authorization: Optional[str] = Header(None),
):
    """SMTP bağlantısını test et ve test maili gönder (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err

    config = _read_config()
    smtp_host = config.get("smtp_host", "")
    username = config.get("username", "")
    password = config.get("password", "")

    if not smtp_host:
        return BaseResponse(code=400, msg="SMTP sunucu adresi ayarlanmamış", data={"connected": False})

    if not username:
        return BaseResponse(code=400, msg="SMTP kullanıcı adı ayarlanmamış", data={"connected": False})

    try:
        import smtplib
        import ssl

        smtp_port = config.get("smtp_port", 587)
        use_tls = config.get("use_tls", True)
        use_ssl = config.get("use_ssl", False)

        if use_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            if use_tls:
                server.starttls()

        if username and password:
            server.login(username, password)

        # Test maili gönder
        from_addr = config.get("from_address") or username
        recipients = [addr.strip() for addr in config.get("recipients", "").split(",") if addr.strip()]

        mail_sent = False
        if recipients:
            try:
                from email.mime.text import MIMEText
                msg = MIMEText(
                    "✅ Anomivox SMTP bağlantı testi başarılı!\n\n"
                    f"Sunucu: {smtp_host}:{smtp_port}\n"
                    f"Kullanıcı: {username}\n"
                    f"TLS: {use_tls} | SSL: {use_ssl}",
                    "plain", "utf-8"
                )
                msg["Subject"] = "✅ Anomivox — SMTP Bağlantı Testi"
                msg["From"] = f"{config.get('from_name', 'Anomivox')} <{from_addr}>"
                msg["To"] = ", ".join(recipients)
                server.sendmail(from_addr, recipients, msg.as_string())
                mail_sent = True
            except Exception as e:
                logger_msg = f"Test maili gönderilemedi: {e}"

        server.quit()

        return BaseResponse(
            code=200,
            msg="SMTP bağlantısı başarılı",
            data={
                "connected": True,
                "smtp_host": smtp_host,
                "smtp_port": smtp_port,
                "username": username,
                "mail_sent": mail_sent,
                "recipients_count": len(recipients) if recipients else 0,
            }
        )

    except smtplib.SMTPAuthenticationError:
        return BaseResponse(
            code=400,
            msg="SMTP kimlik doğrulama hatası — kullanıcı adı veya şifre yanlış",
            data={"connected": False}
        )
    except smtplib.SMTPConnectError:
        return BaseResponse(
            code=400,
            msg=f"SMTP sunucusuna bağlanılamadı: {smtp_host}:{config.get('smtp_port', 587)}",
            data={"connected": False}
        )
    except Exception as e:
        return BaseResponse(
            code=500,
            msg=f"SMTP bağlantı hatası: {str(e)}",
            data={"connected": False}
        )
