"""
Audit Logger
═════════════
Tüm agent aksiyonlarını loglar — SQL, OS komutları, onay kararları.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("dba_agent.security.audit")

# Audit log dosya yolu
AUDIT_LOG_PATH = os.getenv(
    "DBA_AUDIT_LOG_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "dba_agent_audit.jsonl")
)


class AuditLogger:
    """
    JSON Lines formatında audit log yazıcı.
    Her satır bir aksiyon kaydı.
    """

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path or AUDIT_LOG_PATH
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log(
        self,
        action_type: str,
        target: str,
        command: str,
        risk_level: str,
        approved_by: Optional[str] = None,
        result: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Audit log kaydı yaz.
        
        Args:
            action_type: "sql", "os_command", "approval", "diagnosis"
            target: Hedef DB/sunucu adı
            command: Çalıştırılan komut
            risk_level: "safe", "low", "medium", "high", "forbidden"
            approved_by: Onaylayan kullanıcı (Telegram user_id)
            result: Sonuç ("success", "failed", "rejected", "timeout")
            metadata: Ek bilgiler
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "target": target,
            "command": command,
            "risk_level": risk_level,
            "approved_by": approved_by,
            "result": result,
            "metadata": metadata or {},
        }

        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.debug(f"Audit: {action_type} on {target} → {result}")
        except Exception as e:
            logger.error(f"Audit log write error: {e}")

    def log_sql(
        self, target: str, sql: str, risk: str,
        approved_by: Optional[str] = None, result: str = "pending",
        execution_time_ms: float = 0,
    ) -> None:
        """SQL komutu log kaydı."""
        self.log(
            action_type="sql",
            target=target,
            command=sql,
            risk_level=risk,
            approved_by=approved_by,
            result=result,
            metadata={"execution_time_ms": execution_time_ms},
        )

    def log_os_command(
        self, target: str, command: str, risk: str,
        approved_by: Optional[str] = None, result: str = "pending",
        output: str = "",
    ) -> None:
        """OS komutu log kaydı."""
        self.log(
            action_type="os_command",
            target=target,
            command=command,
            risk_level=risk,
            approved_by=approved_by,
            result=result,
            metadata={"output_preview": output[:500]},
        )

    def log_diagnosis(
        self, target: str, alert_type: str,
        root_cause: str = "", solution: str = "",
    ) -> None:
        """Diagnosis sonucu log kaydı."""
        self.log(
            action_type="diagnosis",
            target=target,
            command=f"diagnose:{alert_type}",
            risk_level="safe",
            result="completed",
            metadata={
                "alert_type": alert_type,
                "root_cause": root_cause,
                "solution": solution,
            },
        )

    def log_approval(
        self, target: str, command: str, risk: str,
        user_id: str, decision: str,
    ) -> None:
        """Onay kararı log kaydı."""
        self.log(
            action_type="approval",
            target=target,
            command=command,
            risk_level=risk,
            approved_by=user_id,
            result=decision,  # "approved", "rejected", "deferred"
        )


# ─── Singleton ────────────────────────────────
_audit: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Global audit logger singleton."""
    global _audit
    if _audit is None:
        _audit = AuditLogger()
    return _audit
