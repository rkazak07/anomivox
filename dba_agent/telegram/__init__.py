"""
Telegram Entegrasyonu (Faz 3)
═════════════════════════════
İnteraktif Telegram Bot:
  - Komut tabanlı etkileşim (/start, /status, /diagnose, /tools, /db, /sql, /run)
  - Akıllı DBA mesaj işleyici (intent → tool → sonuç)
  - Serbest metin soru-cevap (gerçek DB verisiyle)
  - Riskli aksiyon onay mekanizması (inline keyboard)
  - Tanı raporu otomatik gönderim
  - Çoklu chat desteği (admin + extra chat'ler)
"""

from dba_agent.telegram.bot import DBABot, get_bot
from dba_agent.telegram.formatter import (
    format_diagnosis_report,
    format_alert_notification,
    format_health_summary,
)
from dba_agent.telegram.approval import (
    create_approval_keyboard,
    register_pending_approval,
    handle_approval,
)
from dba_agent.telegram.smart_handler import (
    detect_intent,
    execute_tool,
    format_tool_result,
    handle_smart_message,
)

__all__ = [
    "DBABot",
    "get_bot",
    "format_diagnosis_report",
    "format_alert_notification",
    "format_health_summary",
    "create_approval_keyboard",
    "register_pending_approval",
    "handle_approval",
    "detect_intent",
    "execute_tool",
    "format_tool_result",
    "handle_smart_message",
]
