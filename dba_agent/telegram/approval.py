"""
Telegram Onay Mekanizması
═════════════════════════
Riskli aksiyonlar için inline keyboard ile
onay alma / reddetme sistemi.

Approval timeout: TelegramConfig.approval_timeout (varsayılan 3600s)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.constants import ParseMode

from dba_agent.config import get_config

logger = logging.getLogger("dba_agent.telegram.approval")

# ── Bekleyen onaylar ─────────────────────────
_pending_approvals: Dict[str, Dict[str, Any]] = {}


def create_approval_keyboard(alert_id: str) -> InlineKeyboardMarkup:
    """
    Riskli aksiyonlar için onay/red butonları oluştur.

    Args:
        alert_id: Tanı alert ID'si

    Returns:
        InlineKeyboardMarkup
    """
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Onayla",
                callback_data=f"approve:{alert_id}",
            ),
            InlineKeyboardButton(
                "❌ Reddet",
                callback_data=f"reject:{alert_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                "📋 Detay Göster",
                callback_data=f"detail:{alert_id}",
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def register_pending_approval(
    alert_id: str,
    actions: list,
    report_dict: Dict[str, Any],
) -> None:
    """
    Onay bekleyen aksiyon kaydet.

    Args:
        alert_id: Tanı alert ID
        actions: Önerilen aksiyonlar listesi
        report_dict: Tam rapor dict'i
    """
    config = get_config().telegram
    _pending_approvals[alert_id] = {
        "actions": actions,
        "report": report_dict,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(seconds=config.approval_timeout),
        "status": "pending",
    }
    logger.info(f"Onay kaydedildi: {alert_id}, {len(actions)} aksiyon")


def get_pending_approval(alert_id: str) -> Optional[Dict[str, Any]]:
    """Bekleyen onayı getir."""
    approval = _pending_approvals.get(alert_id)
    if not approval:
        return None

    # Timeout kontrolü
    if datetime.now() > approval["expires_at"]:
        approval["status"] = "expired"
        _pending_approvals.pop(alert_id, None)
        return None

    return approval


async def handle_approval(
    query: CallbackQuery,
    data: str,
    approved: bool,
) -> None:
    """
    Onay/red callback handler.

    Args:
        query: Telegram CallbackQuery
        data: Callback data string
        approved: True = onaylandı, False = reddedildi
    """
    # alert_id'yi parse et
    parts = data.split(":", 1)
    if len(parts) < 2:
        await query.edit_message_text("❌ Geçersiz callback verisi.")
        return

    alert_id = parts[1]
    approval = get_pending_approval(alert_id)

    if not approval:
        await query.edit_message_text(
            "⏰ *Onay süresi doldu veya bulunamadı.*\n"
            "Yeni bir tanı başlatabilirsiniz: /diagnose",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if approved:
        approval["status"] = "approved"
        approval["approved_by"] = str(query.from_user.id)
        approval["approved_at"] = datetime.now().isoformat()

        await query.edit_message_text(
            f"✅ *Aksiyonlar onaylandı!*\n\n"
            f"🏷️ Alert: `{alert_id}`\n"
            f"👤 Onaylayan: {query.from_user.first_name}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"⏳ Aksiyonlar uygulanıyor...",
            parse_mode=ParseMode.MARKDOWN,
        )

        # Aksiyonları uygula (arka plan)
        asyncio.create_task(
            _execute_approved_actions(
                str(query.message.chat.id),
                alert_id,
                approval["actions"],
            )
        )

    else:
        approval["status"] = "rejected"
        approval["rejected_by"] = str(query.from_user.id)

        await query.edit_message_text(
            f"❌ *Aksiyonlar reddedildi*\n\n"
            f"🏷️ Alert: `{alert_id}`\n"
            f"👤 Reddeden: {query.from_user.first_name}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"Tanı raporu geçerli kalacak, aksiyonlar uygulanmadı.",
            parse_mode=ParseMode.MARKDOWN,
        )

    # Temizlik
    _pending_approvals.pop(alert_id, None)


async def _execute_approved_actions(
    chat_id: str,
    alert_id: str,
    actions: list,
) -> None:
    """
    Onaylanan aksiyonları uygula.

    Şu an sadece bildirim gönderir — gerçek uygulama
    Faz 5'te executor üzerinden yapılacak.
    """
    from dba_agent.telegram.bot import get_bot
    from dba_agent.security.audit import AuditLogger

    bot = get_bot()
    audit = AuditLogger()

    try:
        results = []
        for i, action in enumerate(actions, 1):
            action_desc = action.get("action", "Bilinmeyen")
            risk = action.get("risk", "safe")
            sql = action.get("sql", "")

            # Audit log
            audit.log(
                action_type="approved_action",
                target=alert_id,
                command=sql or action_desc,
                risk_level=risk,
                result="pending",
                metadata={"step": i, "total": len(actions)},
            )

            # TODO: Faz 5 — Executor üzerinden gerçek SQL/OS komutu çalıştır
            results.append(f"  {i}. ⏳ {action_desc} — (henüz uygulanmadı)")

        result_text = (
            f"📋 *Aksiyon Sonuçları*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷️ Alert: `{alert_id}`\n\n"
            + "\n".join(results)
            + "\n\n⚠️ _Not: Otomatik aksiyon uygulama Faz 5'te aktif edilecek._"
        )

        await bot.send_message(chat_id, result_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Aksiyon uygulama hatası: {e}", exc_info=True)
        await bot.send_message(
            chat_id,
            f"❌ Aksiyon uygulama hatası:\n`{str(e)[:300]}`",
            parse_mode=ParseMode.MARKDOWN,
        )


def cleanup_expired_approvals() -> int:
    """Süresi dolmuş onayları temizle. Dönen: silinen sayısı."""
    now = datetime.now()
    expired = [
        aid for aid, data in _pending_approvals.items()
        if now > data["expires_at"]
    ]
    for aid in expired:
        _pending_approvals.pop(aid, None)
    if expired:
        logger.info(f"{len(expired)} expired approval temizlendi.")
    return len(expired)
