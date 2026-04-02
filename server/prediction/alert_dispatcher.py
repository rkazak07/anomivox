"""
Predictive Alert Dispatcher
═════════════════════════════
Tahminlere dayalı uyarı gönderimi — Telegram + e-posta.
Cooldown mekanizmasıyla aynı metrik için 1 saat içinde tekrar alert gönderilmez.
"""

import logging
import time
from typing import Dict

logger = logging.getLogger("server.prediction.alert_dispatcher")

_cooldown: Dict[str, float] = {}
COOLDOWN_SECONDS = 3600  # 1 saat


def can_alert(key: str) -> bool:
    last = _cooldown.get(key, 0)
    return (time.time() - last) > COOLDOWN_SECONDS


def mark_alerted(key: str):
    _cooldown[key] = time.time()


async def send_predictive_alert(
    metric: str,
    current_value: float,
    forecast_value: float,
    breach_at_minutes: int,
    threshold: float,
    db_target: str = "default",
):
    """Predictive alert gönder (Telegram + mail)."""
    key = f"{metric}:{db_target}"
    if not can_alert(key):
        logger.debug(f"Cooldown aktif, alert atlandı: {key}")
        return

    message = (
        f"⚠️ *Tahminli Eşik Uyarısı*\n"
        f"Metrik: `{metric}`\n"
        f"DB: `{db_target}`\n"
        f"Mevcut değer: `{current_value:.1f}`\n"
        f"Tahmini değer: `{forecast_value:.1f}` (eşik: `{threshold:.1f}`)\n"
        f"Tahmini süre: ~{breach_at_minutes} dakika içinde"
    )

    # Telegram
    try:
        from configs.telegram_settings_config import get_telegram_settings_config
        from server.telegram.telegram_alert_service import send_alert
        tg_config = get_telegram_settings_config()
        if tg_config.get('bot_token') and tg_config.get('chat_id'):
            await send_alert(message)
    except Exception as e:
        logger.warning(f"Telegram alert gönderilemedi: {e}")

    # Mail
    try:
        from configs.mail_settings_config import get_mail_settings_config
        from server.mail_service.mail_service import send_mail
        mail_config = get_mail_settings_config()
        if mail_config.get('smtp_server') and mail_config.get('to_email'):
            subject = f"[Anomivox] Tahminli Eşik Uyarısı: {metric}"
            await send_mail(subject=subject, body=message.replace('*', '').replace('`', ''))
    except Exception as e:
        logger.warning(f"Mail alert gönderilemedi: {e}")

    mark_alerted(key)
    logger.info(f"Predictive alert gönderildi: {key} — {breach_at_minutes}dk içinde eşik aşımı")
