"""
Telegram Mesaj Formatlayıcı
══════════════════════════
Tanı raporları, alert'ler, durum mesajlarını
Telegram Markdown formatına çevirir.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("dba_agent.telegram.formatter")


def _lang() -> str:
    try:
        from dba_agent.config import get_config
        return get_config().agent_language
    except Exception:
        return "tr"

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

    lang = _lang()
    severity_e = SEVERITY_EMOJI.get(report.severity, "⚪")
    category_e = CATEGORY_EMOJI.get(report.category, "📋")

    if lang == "en":
        evidence_label = "Evidence"
        actions_label = "Recommended Actions"
        title = "DBA Agent Diagnosis Report"
        severity_label = "Severity"
        category_label = "Category"
        db_label = "Database"
        duration_label = "Duration"
        root_cause_label = "Root Cause"
        unknown_action = "Unknown"
        root_cause_unknown = "Could not be determined"
        error_label = "Error"
        db_default = "default"
    else:
        evidence_label = "Kanıtlar"
        actions_label = "Önerilen Aksiyonlar"
        title = "DBA Agent Tanı Raporu"
        severity_label = "Şiddet"
        category_label = "Kategori"
        db_label = "Veritabanı"
        duration_label = "Süre"
        root_cause_label = "Root Cause"
        unknown_action = "Bilinmiyor"
        root_cause_unknown = "Belirlenemedi"
        error_label = "Hata"
        db_default = "varsayılan"

    evidence_text = ""
    if report.evidence:
        evidence_lines = "\n".join(f"  • {e}" for e in report.evidence[:10])
        evidence_text = f"\n📋 *{evidence_label}:*\n{evidence_lines}\n"

    actions_text = ""
    if report.recommended_actions:
        action_lines = []
        for a in report.recommended_actions[:5]:
            risk = a.get("risk", "safe")
            risk_e = RISK_EMOJI.get(risk, "⚪")
            action = a.get("action", unknown_action)
            sql = a.get("sql", "")
            line = f"  {risk_e} {action}"
            if sql:
                line += f"\n    `{sql[:100]}`"
            action_lines.append(line)
        actions_text = f"\n💡 *{actions_label}:*\n" + "\n".join(action_lines) + "\n"

    text = (
        f"🔍 *{title}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{severity_e} {severity_label}: *{report.severity.upper()}*\n"
        f"{category_e} {category_label}: *{report.category}*\n"
        f"🖥️ {db_label}: `{report.db_name or db_default}`\n"
        f"⏱️ {duration_label}: {report.total_duration_sec}s\n\n"
        f"🎯 *{root_cause_label}:*\n{report.root_cause or root_cause_unknown}\n"
        f"{evidence_text}"
        f"{actions_text}"
    )

    if report.error:
        text += f"\n⚠️ *{error_label}:* {report.error[:200]}\n"

    text += f"\n🏷️ `{report.alert_id}`"

    return text


def format_alert_notification(alert_data: Dict[str, Any]) -> str:
    """
    Gelen alert'i bildirim formatına çevir.
    notify-worker'dan veya API'den gelen alert verisi.
    """
    lang = _lang()
    status = alert_data.get("status", "unknown")
    db_name = alert_data.get("db_name", "")
    severity = alert_data.get("severity", "warning")

    if lang == "en":
        description = alert_data.get("description", alert_data.get("message", "Unknown alert"))
        severity_label = "Severity"
        diagnosing_msg = "Diagnosis starting automatically..."
    else:
        description = alert_data.get("description", alert_data.get("message", "Bilinmeyen alert"))
        severity_label = "Şiddet"
        diagnosing_msg = "Tanı otomatik başlatılıyor..."

    severity_e = SEVERITY_EMOJI.get(severity, "⚪")
    status_e = "🔥" if status == "firing" else "✅" if status == "resolved" else "⚠️"

    text = (
        f"{status_e} *Alert: {status.upper()}*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{severity_e} {severity_label}: {severity}\n"
    )

    if db_name:
        text += f"🖥️ DB: `{db_name}`\n"

    text += f"\n📝 {description[:500]}\n\n🕐 {diagnosing_msg}"

    return text


def format_health_summary(
    llm_ok: bool,
    db_statuses: Dict[str, Dict],
    tool_count: int,
    llm_stats: Dict,
) -> str:
    """Sistem sağlık özetini formatla."""
    lang = _lang()
    llm_emoji = "✅" if llm_ok else "❌"

    if lang == "en":
        title = "System Status"
        tools_label = "Tools"
        databases_label = "Databases"
        no_target = "No targets"
        no_connection = "No connection"
        llm_calls_label = "LLM calls"
        success_label = "Success"
    else:
        title = "Sistem Durumu"
        tools_label = "Araçlar"
        databases_label = "Veritabanları"
        no_target = "Hedef yok"
        no_connection = "Bağlantı yok"
        llm_calls_label = "LLM çağrı"
        success_label = "Başarı"

    db_lines = []
    for name, status in db_statuses.items():
        if status.get("connected"):
            db_lines.append(
                f"  ✅ {name}: v{status.get('version', '?')} | "
                f"Score: {status.get('score', '?')}"
            )
        else:
            db_lines.append(f"  ❌ {name}: {status.get('error', no_connection)[:50]}")

    db_text = "\n".join(db_lines) if db_lines else f"  ⚠️ {no_target}"

    return (
        f"📊 *{title}*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 Agent: ✅ v0.2.0\n"
        f"🧠 LLM: {llm_emoji}\n"
        f"🔧 {tools_label}: {tool_count}\n\n"
        f"🖥️ *{databases_label}:*\n{db_text}\n\n"
        f"📈 {llm_calls_label}: {llm_stats.get('total_calls', 0)} | "
        f"{success_label}: {llm_stats.get('success', 0)}"
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
    suffix = "\n\n... (truncated)" if _lang() == "en" else "\n\n... (kısaltıldı)"
    return text[:max_length - 20] + suffix
