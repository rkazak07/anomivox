"""
Telegram Mesaj Formatlayıcı
══════════════════════════
Tanı raporları, alert'ler, durum mesajlarını
Telegram Markdown formatına çevirir.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("dba_agent.telegram.formatter")

# ── Severity emojileri ────────────────────────
SEVERITY_EMOJI = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
}

# ── Risk emojileri ────────────────────────────
RISK_EMOJI = {
    "safe": "🟢",
    "low": "🟡",
    "medium": "🟠",
    "high": "🔴",
    "critical": "⛔",
}

# ── Kategori emojileri ────────────────────────
CATEGORY_EMOJI = {
    "cpu": "🔥",
    "memory": "🧠",
    "io": "💾",
    "disk": "💽",
    "lock": "🔒",
    "query": "🐌",
    "replication": "🔄",
    "connection": "🔗",
    "network": "🌐",
    "os": "🖥️",
    "config": "⚙️",
}


def format_diagnosis_report(report) -> str:
    """
    DiagnosisReport nesnesini Telegram Markdown formatına çevir.

    Orchestrator zaten _generate_report ile Telegram formatında
    rapor oluşturur. Bu fonksiyon fallback olarak kullanılır veya
    report_text boş olduğunda devreye girer.
    """
    # report_text mevcutsa direkt dön
    if hasattr(report, "report_text") and report.report_text:
        return report.report_text

    severity_e = SEVERITY_EMOJI.get(report.severity, "⚪")
    category_e = CATEGORY_EMOJI.get(report.category, "📋")

    # Kanıtlar
    evidence_text = ""
    if report.evidence:
        evidence_lines = "\n".join(f"  • {e}" for e in report.evidence[:10])
        evidence_text = f"\n📋 *Kanıtlar:*\n{evidence_lines}\n"

    # Öneriler
    actions_text = ""
    if report.recommended_actions:
        action_lines = []
        for a in report.recommended_actions[:5]:
            risk = a.get("risk", "safe")
            risk_e = RISK_EMOJI.get(risk, "⚪")
            action = a.get("action", "Bilinmiyor")
            sql = a.get("sql", "")
            line = f"  {risk_e} {action}"
            if sql:
                line += f"\n    `{sql[:100]}`"
            action_lines.append(line)
        actions_text = f"\n💡 *Önerilen Aksiyonlar:*\n" + "\n".join(action_lines) + "\n"

    # Ana rapor
    text = (
        f"🔍 *DBA Agent Tanı Raporu*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{severity_e} Şiddet: *{report.severity.upper()}*\n"
        f"{category_e} Kategori: *{report.category}*\n"
        f"🖥️ Veritabanı: `{report.db_name or 'varsayılan'}`\n"
        f"⏱️ Süre: {report.total_duration_sec}s\n\n"
        f"🎯 *Root Cause:*\n{report.root_cause or 'Belirlenemedi'}\n"
        f"{evidence_text}"
        f"{actions_text}"
    )

    if report.error:
        text += f"\n⚠️ *Hata:* {report.error[:200]}\n"

    text += f"\n🏷️ `{report.alert_id}`"

    return text


def format_alert_notification(alert_data: Dict[str, Any]) -> str:
    """
    Gelen alert'i bildirim formatına çevir.
    notify-worker'dan veya API'den gelen alert verisi.
    """
    status = alert_data.get("status", "unknown")
    description = alert_data.get("description", alert_data.get("message", "Bilinmeyen alert"))
    db_name = alert_data.get("db_name", "")
    severity = alert_data.get("severity", "warning")

    severity_e = SEVERITY_EMOJI.get(severity, "⚪")
    status_e = "🔥" if status == "firing" else "✅" if status == "resolved" else "⚠️"

    text = (
        f"{status_e} *Alert: {status.upper()}*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{severity_e} Şiddet: {severity}\n"
    )

    if db_name:
        text += f"🖥️ DB: `{db_name}`\n"

    text += (
        f"\n📝 {description[:500]}\n\n"
        f"🕐 Tanı otomatik başlatılıyor..."
    )

    return text


def format_health_summary(
    llm_ok: bool,
    db_statuses: Dict[str, Dict],
    tool_count: int,
    llm_stats: Dict,
) -> str:
    """Sistem sağlık özetini formatla."""
    llm_emoji = "✅" if llm_ok else "❌"

    db_lines = []
    for name, status in db_statuses.items():
        if status.get("connected"):
            db_lines.append(
                f"  ✅ {name}: v{status.get('version', '?')} | "
                f"Score: {status.get('score', '?')}"
            )
        else:
            db_lines.append(f"  ❌ {name}: {status.get('error', 'Bağlantı yok')[:50]}")

    db_text = "\n".join(db_lines) if db_lines else "  ⚠️ Hedef yok"

    return (
        f"📊 *Sistem Durumu*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 Agent: ✅ v0.2.0\n"
        f"🧠 LLM: {llm_emoji}\n"
        f"🔧 Araçlar: {tool_count}\n\n"
        f"🖥️ *Veritabanları:*\n{db_text}\n\n"
        f"📈 LLM çağrı: {llm_stats.get('total_calls', 0)} | "
        f"Başarı: {llm_stats.get('success', 0)}"
    )


def escape_markdown(text: str) -> str:
    """
    Telegram Markdown V1 için özel karakterleri escape et.
    Markdown V1'de *, _, `, [ gibi karakterler.
    """
    special_chars = ["_", "*", "`", "["]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


def truncate_text(text: str, max_length: int = 4000) -> str:
    """Metni Telegram limiti içinde tut."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 20] + "\n\n... (kısaltıldı)"
