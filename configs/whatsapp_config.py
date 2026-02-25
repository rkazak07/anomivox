import os

# ─────────────────────────────────────────
# WhatsApp Business Cloud API Yapılandırması
# ─────────────────────────────────────────

# Meta Developer Console'dan alınan kalıcı erişim token'ı
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")

# WhatsApp Business Phone Number ID (Meta Console → WhatsApp → API Setup)
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")

# WhatsApp Business Account ID
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")

# Webhook Verify Token (Meta webhook doğrulama için)
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "anomivox_whatsapp_verify_2024")

# Mesaj alabilecek yetkili telefon numaraları (uluslararası formatta)
# Boşsa herkes kullanabilir
WHATSAPP_ALLOWED_NUMBERS = [
    num.strip()
    for num in os.getenv("WHATSAPP_ALLOWED_NUMBERS", "").split(",")
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
WHATSAPP_NOTIFY_ON_ALERT = True          # Prometheus alert geldiğinde bildir
WHATSAPP_NOTIFY_ON_DIAGNOSIS = True      # Teşhis tamamlandığında bildir
WHATSAPP_AUTO_DIAGNOSE = False           # Alert gelince otomatik teşhis başlat

# Proaktif izleme
WHATSAPP_HEALTH_CHECK_INTERVAL = 300     # Sağlık kontrolü aralığı (saniye)
WHATSAPP_SLOW_QUERY_THRESHOLD = 5.0      # Yavaş sorgu eşiği (saniye)
