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

# ── Aktif aksiyon task'ları (GC ve hata takibi için) ──
_pending_tasks: set = set()

# ── Cooldown kaydı: {action_key: last_executed_at} ──
_cooldown_registry: Dict[str, datetime] = {}


def _cooldown_key(action: Dict[str, Any]) -> str:
    """Aksiyon için benzersiz cooldown anahtarı üret."""
    action_name = action.get("action", "unknown")
    target = action.get("target_db", "") or action.get("table", "") or ""
    return f"{action_name}:{target}"


def _check_cooldown(action: Dict[str, Any]) -> Optional[str]:
    """
    Aksiyon cooldown'da mı kontrol et.
    Cooldown'da ise kalan süreyi (dakika) döndürür, değilse None.
    Cooldown süresi env DBA_COOLDOWN_MINUTES (varsayılan 30 dk).
    """
    import os
    cooldown_minutes = int(os.getenv("DBA_COOLDOWN_MINUTES", "30"))
    key = _cooldown_key(action)
    last_run = _cooldown_registry.get(key)
    if last_run is None:
        return None
    elapsed = (datetime.now() - last_run).total_seconds() / 60
    if elapsed < cooldown_minutes:
        remaining = int(cooldown_minutes - elapsed)
        return f"{remaining} dakika"
    return None


def _update_cooldown(action: Dict[str, Any]) -> None:
    """Aksiyon başarıyla çalıştırıldıktan sonra cooldown'u güncelle."""
    key = _cooldown_key(action)
    _cooldown_registry[key] = datetime.now()


def _is_in_maintenance_window() -> bool:
    """
    Şu anki saat bakım penceresinde mi?
    DBA_MAINTENANCE_START / DBA_MAINTENANCE_END boşsa her zaman True döner.
    """
    config = get_config().security
    if not config.maintenance_start or not config.maintenance_end:
        return True  # Kısıtlama yok

    from datetime import time as dtime
    now = datetime.now().time()
    try:
        sh, sm = map(int, config.maintenance_start.split(":"))
        eh, em = map(int, config.maintenance_end.split(":"))
        start = dtime(sh, sm)
        end = dtime(eh, em)
        if start <= end:
            return start <= now <= end
        else:
            # Gece yarısını aşan pencere: ör. 22:00 - 06:00
            return now >= start or now <= end
    except Exception:
        return True  # Parse hatası → kısıtlama yok


def _on_action_task_done(task: "asyncio.Task") -> None:
    """Task tamamlandığında GC'den temizle, beklenmeyen hatayı logla."""
    _pending_tasks.discard(task)
    if task.cancelled():
        logger.warning("Aksiyon task'ı iptal edildi.")
        return
    exc = task.exception()
    if exc:
        logger.error(f"Aksiyon task'ı başarısız: {exc}", exc_info=exc)


def create_approval_keyboard(alert_id: str) -> InlineKeyboardMarkup:
    """
    Riskli aksiyonlar için onay/red butonları oluştur.

    Args:
        alert_id: Tanı alert ID'si

    Returns:
        InlineKeyboardMarkup
    """
    lang = get_config().agent_language
    if lang == "en":
        lbl_approve = "✅ Approve"
        lbl_reject = "❌ Reject"
        lbl_detail = "📋 Show Details"
    else:
        lbl_approve = "✅ Onayla"
        lbl_reject = "❌ Reddet"
        lbl_detail = "📋 Detay Göster"

    keyboard = [
        [
            InlineKeyboardButton(lbl_approve, callback_data=f"approve:{alert_id}"),
            InlineKeyboardButton(lbl_reject, callback_data=f"reject:{alert_id}"),
        ],
        [
            InlineKeyboardButton(lbl_detail, callback_data=f"detail:{alert_id}"),
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
    cfg = get_config()
    tg = cfg.telegram

    # HIGH risk var mı? Varsa multi-approval gerekebilir
    has_high_risk = any(a.get("risk", "safe") == "high" for a in actions)
    required = tg.required_approvals if has_high_risk else 1

    _pending_approvals[alert_id] = {
        "actions": actions,
        "report": report_dict,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(seconds=tg.approval_timeout),
        "status": "pending",
        # Multi-approval alanları
        "required_approvals": required,
        "approved_by": [],     # Onaylayanların chat_id listesi
        "rejected_by": [],
    }
    logger.info(
        f"Onay kaydedildi: {alert_id}, {len(actions)} aksiyon, "
        f"gerekli onay: {required}"
    )


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

    cfg = get_config()
    lang = cfg.agent_language
    user_id = str(query.from_user.id)
    user_name = query.from_user.first_name
    _chat_id = str(query.message.chat.id)
    tg_cfg = cfg.telegram

    if not approval:
        if lang == "en":
            expire_msg = "⏰ *Approval expired or not found.*\nStart a new diagnosis: /diagnose"
        else:
            expire_msg = "⏰ *Onay süresi doldu veya bulunamadı.*\nYeni bir tanı başlatabilirsiniz: /diagnose"
        await query.edit_message_text(expire_msg, parse_mode=ParseMode.MARKDOWN)
        return

    # Yetkili DBA kontrolü
    approver_ids = tg_cfg.approver_ids
    if approver_ids and user_id not in approver_ids:
        if lang == "en":
            await query.answer("⛔ You are not authorized to approve/reject actions.", show_alert=True)
        else:
            await query.answer("⛔ Aksiyon onaylama yetkiniz yok.", show_alert=True)
        return

    required = approval.get("required_approvals", 1)

    if approved:
        # Aynı kişi iki kez onaylayamasın
        if user_id in approval["approved_by"]:
            if lang == "en":
                await query.answer("ℹ️ You already approved this.", show_alert=True)
            else:
                await query.answer("ℹ️ Bu aksiyonu zaten onayladınız.", show_alert=True)
            return

        approval["approved_by"].append(user_id)
        current = len(approval["approved_by"])

        if current < required:
            # Yeterli onay yok, beklemeye devam
            if lang == "en":
                wait_msg = (
                    f"✅ *Approval {current}/{required} received*\n\n"
                    f"🏷️ Alert: `{alert_id}`\n"
                    f"👤 Approved by: {user_name}\n"
                    f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"⏳ Waiting for {required - current} more approval(s)..."
                )
            else:
                wait_msg = (
                    f"✅ *Onay {current}/{required} alındı*\n\n"
                    f"🏷️ Alert: `{alert_id}`\n"
                    f"👤 Onaylayan: {user_name}\n"
                    f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"⏳ {required - current} onay daha bekleniyor..."
                )
            await query.edit_message_text(wait_msg, parse_mode=ParseMode.MARKDOWN)
            return

        # Yeterli onay toplandı — yürüt
        approval["status"] = "approved"
        approval["approved_at"] = datetime.now().isoformat()

        if lang == "en":
            approved_msg = (
                f"✅ *Actions approved! ({current}/{required})*\n\n"
                f"🏷️ Alert: `{alert_id}`\n"
                f"👤 Final approval: {user_name}\n"
                f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"⏳ Applying actions..."
            )
        else:
            approved_msg = (
                f"✅ *Aksiyonlar onaylandı! ({current}/{required})*\n\n"
                f"🏷️ Alert: `{alert_id}`\n"
                f"👤 Son onaylayan: {user_name}\n"
                f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"⏳ Aksiyonlar uygulanıyor..."
            )
        await query.edit_message_text(approved_msg, parse_mode=ParseMode.MARKDOWN)

        # Aksiyonları uygula — task referansını sakla (GC + hata takibi)
        task = asyncio.create_task(
            _execute_approved_actions(_chat_id, alert_id, approval["actions"])
        )
        _pending_tasks.add(task)
        task.add_done_callback(_on_action_task_done)

    else:
        approval["status"] = "rejected"
        approval["rejected_by"].append(user_id)

        if lang == "en":
            rejected_msg = (
                f"❌ *Actions rejected*\n\n"
                f"🏷️ Alert: `{alert_id}`\n"
                f"👤 Rejected by: {user_name}\n"
                f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"Diagnosis report remains valid, no actions applied."
            )
        else:
            rejected_msg = (
                f"❌ *Aksiyonlar reddedildi*\n\n"
                f"🏷️ Alert: `{alert_id}`\n"
                f"👤 Reddeden: {user_name}\n"
                f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"Tanı raporu geçerli kalacak, aksiyonlar uygulanmadı."
            )
        await query.edit_message_text(rejected_msg, parse_mode=ParseMode.MARKDOWN)

    # Temizlik (red veya yeterli onay)
    if approval.get("status") in ("approved", "rejected"):
        _pending_approvals.pop(alert_id, None)


async def _execute_approved_actions(
    chat_id: str,
    alert_id: str,
    actions: list,
) -> None:
    """
    Onaylanan aksiyonları uygula.

    Her aksiyon için:
    1. Before snapshot al
    2. SQL/SSH yürüt
    3. After snapshot al
    4. Verifier ile karşılaştır
    5. Rollback öner gerekiyorsa bildir
    """
    from dba_agent.telegram.bot import get_bot
    from dba_agent.security.audit import AuditLogger
    from dba_agent.agent.verifier import Verifier
    from dba_agent.db import resolve_target_name

    bot = get_bot()
    audit = AuditLogger()
    verifier = Verifier()
    cfg = get_config()
    dry_run = cfg.security.dry_run
    lang = cfg.agent_language

    # Dil sabitleri
    if lang == "en":
        _lbl_dry_run = "DRY-RUN"
        _lbl_cooldown = "cooldown active, retry in"
        _lbl_maint = "HIGH risk action only allowed during maintenance window"
        _lbl_skipped = "previous step failed, skipped"
        _lbl_no_cmd = "(no executable command found)"
        _lbl_forbidden_pfx = ""
        _lbl_rollback_rec = "Rollback recommended:"
        _lbl_results_title = "Action Results"
        _lbl_feedback_q = "💬 *Did this fix the issue?*\nYour feedback improves future recommendations."
        _lbl_feedback_good = "👍 Worked"
        _lbl_feedback_bad = "👎 Didn't Work"
        _lbl_feedback_partial = "😐 Partially"
    else:
        _lbl_dry_run = "DRY-RUN"
        _lbl_cooldown = "cooldown aktif, tekrar denenebilir:"
        _lbl_maint = "HIGH risk aksiyon yalnızca bakım penceresinde uygulanabilir"
        _lbl_skipped = "önceki adım başarısız, atlandı"
        _lbl_no_cmd = "(çalıştırılabilir komut bulunamadı)"
        _lbl_forbidden_pfx = ""
        _lbl_rollback_rec = "Rollback önerilir:"
        _lbl_results_title = "Aksiyon Sonuçları"
        _lbl_feedback_q = "💬 *Bu çözüm işe yaradı mı?*\nGeri bildiriminiz gelecek önerileri iyileştirir."
        _lbl_feedback_good = "👍 İşe Yaradı"
        _lbl_feedback_bad = "👎 İşe Yaramadı"
        _lbl_feedback_partial = "😐 Kısmen"

    if dry_run:
        logger.warning(f"[DRY-RUN] Aksiyonlar yürütülmeyecek — alert={alert_id}")

    try:
        results = []
        staged_stopped = False  # Verifier başarısız olunca sonraki adımları durdur
        for i, action in enumerate(actions, 1):
            if staged_stopped:
                action_desc_skip = action.get("action", "Bilinmeyen")
                results.append(f"  {i}. ⏭️ {action_desc_skip} — {_lbl_skipped}")
                continue
            action_desc = action.get("action", "Bilinmeyen")
            risk = action.get("risk", "safe")
            sql = action.get("sql", "")
            os_cmd = action.get("os_command", "")
            # B7: target_db'yi config'deki gerçek isimle doğrula/normalize et
            db_name = resolve_target_name(action.get("target_db"))

            # Audit log — başlangıç
            audit.log(
                action_type="approved_action",
                target=alert_id,
                command=sql or os_cmd or action_desc,
                risk_level=risk,
                result="pending",
                metadata={"step": i, "total": len(actions), "target_db": db_name},
            )

            # ── Dry-run kısa devre ──
            if dry_run:
                results.append(
                    f"  {i}. 🔍 [{_lbl_dry_run}] {action_desc}\n"
                    f"     SQL: `{sql[:100]}`\n"
                    f"     OS: `{os_cmd[:100]}`\n"
                    f"     Risk: `{risk}`"
                )
                audit.log(
                    action_type="dry_run",
                    target=alert_id,
                    command=sql or os_cmd or action_desc,
                    risk_level=risk,
                    result="dry_run",
                )
                continue

            # ── Cooldown kontrolü ──
            cooldown_remaining = _check_cooldown(action)
            if cooldown_remaining:
                results.append(
                    f"  {i}. ⏳ {action_desc} — {_lbl_cooldown} {cooldown_remaining}"
                )
                continue

            # ── Maintenance window kontrolü (HIGH risk) ──
            if risk == "high" and not _is_in_maintenance_window():
                config_sec = get_config().security
                results.append(
                    f"  {i}. ⏸️ {action_desc} — "
                    f"{_lbl_maint} "
                    f"({config_sec.maintenance_start}–{config_sec.maintenance_end})"
                )
                audit.log(
                    action_type="approved_action",
                    target=alert_id,
                    command=sql or os_cmd or action_desc,
                    risk_level=risk,
                    result="blocked_maintenance_window",
                )
                continue

            # ── Before snapshot ──
            before_snapshot = verifier.take_snapshot(db_name)

            if sql:
                try:
                    from dba_agent.tools.db_action_tools import _check_sql_forbidden
                    from dba_agent.db import get_adapter
                    from dba_agent.db.adapter import RiskLevel

                    # Güvenlik kontrolü
                    forbidden = _check_sql_forbidden(sql)
                    if forbidden:
                        results.append(f"  {i}. ❌ {action_desc} — {forbidden}")
                        audit.log(
                            action_type="approved_action",
                            target=alert_id,
                            command=sql,
                            risk_level=risk,
                            result="forbidden",
                        )
                        continue

                    risk_level = getattr(RiskLevel, risk.upper(), RiskLevel.MEDIUM)
                    with get_adapter(db_name) as adapter:
                        action_result = adapter.execute_action(sql, risk_level)

                    # ── After snapshot + Verify ──
                    after_snapshot = verifier.take_snapshot(db_name)
                    verification = await verifier.verify(
                        command=sql,
                        risk_level=risk,
                        target=db_name or "default",
                        before_snapshot=before_snapshot,
                        after_snapshot=after_snapshot,
                    )

                    status = "✅" if action_result.success else "❌"
                    verify_line = ""
                    if verification.improvement:
                        verify_line = f"\n     📊 {verification.improvement}"
                    if verification.needs_rollback:
                        verify_line += f"\n     ⚠️ *{_lbl_rollback_rec}* {verification.rollback_reason}"
                        staged_stopped = True  # Kademeli yürütme: sonraki adımları durdur

                    results.append(f"  {i}. {status} {action_desc} — {action_result.message}{verify_line}")

                    audit.log(
                        action_type="approved_action",
                        target=alert_id,
                        command=sql,
                        risk_level=risk,
                        result="success" if action_result.success else "failed",
                        metadata={
                            "verify_success": verification.success,
                            "needs_rollback": verification.needs_rollback,
                            "improvement": verification.improvement[:200] if verification.improvement else "",
                        },
                    )

                    # Cooldown güncelle (başarılı veya başarısız — tekrar tetiklenmesin)
                    _update_cooldown(action)

                    # Rollback bilgisi kaydet (başarılı aksiyonlar için)
                    if action_result.success:
                        rollback_sql = action.get("rollback_sql", "")
                        if not rollback_sql:
                            # Basit SET komutu için otomatik rollback SQL üret
                            old_val = action.get("old_value", "")
                            param = action.get("param", "")
                            if param and old_val:
                                rollback_sql = f"ALTER SYSTEM SET {param} = '{old_val}'; SELECT pg_reload_conf();"
                        if rollback_sql:
                            audit.log_rollback_info(
                                target=db_name or "default",
                                action=action_desc,
                                applied_sql=sql,
                                rollback_sql=rollback_sql,
                                param=action.get("param"),
                                old_value=action.get("old_value"),
                                new_value=action.get("new_value"),
                            )

                except Exception as e:
                    results.append(f"  {i}. ❌ {action_desc} — Hata: {str(e)[:100]}")

            elif os_cmd:
                try:
                    from dba_agent.tools.ssh_executor import SSHExecutor
                    from dba_agent.tools.os_tools import _get_ssh_target

                    target = _get_ssh_target()
                    executor = SSHExecutor(target)
                    ssh_result = executor.run(os_cmd)

                    # ── After snapshot + Verify ──
                    after_snapshot = verifier.take_snapshot(db_name)
                    verification = await verifier.verify(
                        command=os_cmd,
                        risk_level=risk,
                        target=str(target),
                        before_snapshot=before_snapshot,
                        after_snapshot=after_snapshot,
                    )

                    status = "✅" if ssh_result.success else "❌"
                    verify_line = ""
                    if verification.improvement:
                        verify_line = f"\n     📊 {verification.improvement}"

                    results.append(f"  {i}. {status} {action_desc}{verify_line}")
                    if not ssh_result.success:
                        results[-1] += f" — {ssh_result.stderr[:100]}"

                    audit.log(
                        action_type="approved_action",
                        target=alert_id,
                        command=os_cmd,
                        risk_level=risk,
                        result="success" if ssh_result.success else "failed",
                        metadata={
                            "verify_success": verification.success,
                            "needs_rollback": verification.needs_rollback,
                        },
                    )

                except Exception as e:
                    results.append(f"  {i}. ❌ {action_desc} — SSH Hata: {str(e)[:100]}")

            else:
                results.append(f"  {i}. ⏳ {action_desc} — {_lbl_no_cmd}")

        result_text = (
            f"📋 *{_lbl_results_title}*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷️ Alert: `{alert_id}`\n\n"
            + "\n".join(results)
        )

        await bot.send_message(chat_id, result_text, parse_mode=ParseMode.MARKDOWN)

        # Incident store'a kaydet (tüm aksiyonlar tamamlandıktan sonra)
        incident_id = None
        try:
            from dba_agent.memory import get_incident_store
            approval_data = _pending_approvals.get(alert_id) or {}
            report_dict = approval_data.get("report", {})
            overall_success = all("✅" in r for r in results if r.strip())

            # Son snapshot'ı al (genel durum için)
            final_snapshot = verifier.take_snapshot()

            store = get_incident_store()
            incident_id = store.save_incident(
                alert_type=report_dict.get("category", "unknown"),
                alert_text=report_dict.get("alert_text", alert_id),
                root_cause=report_dict.get("root_cause", ""),
                actions_taken=actions,
                health_before={},
                health_after=final_snapshot,
                success=overall_success,
                db_name=report_dict.get("db_name", ""),
            )
        except Exception as e:
            logger.warning(f"Incident store kayıt hatası: {e}")

        # Feedback butonu gönder
        if incident_id:
            try:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                feedback_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(_lbl_feedback_good, callback_data=f"feedback_good:{incident_id}"),
                        InlineKeyboardButton(_lbl_feedback_bad, callback_data=f"feedback_bad:{incident_id}"),
                        InlineKeyboardButton(_lbl_feedback_partial, callback_data=f"feedback_partial:{incident_id}"),
                    ]
                ])
                await bot.send_message(
                    chat_id,
                    _lbl_feedback_q,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=feedback_keyboard,
                )
            except Exception as e:
                logger.warning(f"Feedback butonu gönderilemedi: {e}")

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
