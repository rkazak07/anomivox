import os

# ─────────────────────────────────────────
# E-Posta (SMTP) Bildirim Yapılandırması
# ─────────────────────────────────────────

# SMTP sunucu bilgileri
MAIL_SMTP_HOST = os.getenv("MAIL_SMTP_HOST", "")
MAIL_SMTP_PORT = int(os.getenv("MAIL_SMTP_PORT", "587"))
MAIL_SMTP_USE_TLS = os.getenv("MAIL_SMTP_USE_TLS", "True").lower() in ("true", "1", "yes")
MAIL_SMTP_USE_SSL = os.getenv("MAIL_SMTP_USE_SSL", "False").lower() in ("true", "1", "yes")

# Gönderici hesap bilgileri
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Anomivox")
MAIL_FROM_ADDRESS = os.getenv("MAIL_FROM_ADDRESS", "")

# Alıcılar (virgülle ayrılmış)
MAIL_RECIPIENTS = [
    addr.strip()
    for addr in os.getenv("MAIL_RECIPIENTS", "").split(",")
    if addr.strip()
]

# Bildirim ayarları
MAIL_NOTIFY_ON_ALERT = True          # Prometheus alert geldiğinde mail gönder
MAIL_NOTIFY_ON_DIAGNOSIS = True      # Teşhis tamamlandığında mail gönder
MAIL_NOTIFY_ON_HEALTH = False        # Sağlık kontrolü sorunlarında mail gönder

# Proaktif izleme
MAIL_HEALTH_CHECK_INTERVAL = 300     # Sağlık kontrolü aralığı (saniye)
MAIL_SLOW_QUERY_THRESHOLD = 5.0      # Yavaş sorgu eşiği (saniye)
