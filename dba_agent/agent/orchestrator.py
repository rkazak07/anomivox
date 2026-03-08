"""
Orchestrator — Ana Orkestratör
══════════════════════════════
Alert → Triage → Plan → Execute → Analyze → (Verify) → Report

Tam tanı pipeline'ını yönetir.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dba_agent.agent.planner import DiagnosisPlan, Planner, TriageResult
from dba_agent.agent.executor import ExecutionResult, Executor
from dba_agent.agent.verifier import Verifier, VerificationResult
from dba_agent.agent.prompts import get_prompts, RISK_EMOJIS
from dba_agent.config import get_config
from dba_agent.inference import TaskType, get_llm_client, ModelRouter
from dba_agent.security.audit import AuditLogger

logger = logging.getLogger("dba_agent.agent.orchestrator")


@dataclass
class DiagnosisReport:
    """Tam tanı raporu."""
    # Meta
    alert_id: str = ""
    alert_text: str = ""
    db_name: str = ""
    db_type: str = "postgresql"
    total_duration_sec: float = 0

    # Triage
    triage: Optional[TriageResult] = None
    severity: str = "info"
    category: str = "unknown"

    # Plan & Execution
    plan: Optional[DiagnosisPlan] = None
    execution: Optional[ExecutionResult] = None

    # Sonuçlar
    root_cause: str = ""
    evidence: List[str] = field(default_factory=list)
    recommended_actions: List[Dict[str, Any]] = field(default_factory=list)

    # Doğrulama (opsiyonel)
    verification: Optional[VerificationResult] = None

    # Rapor
    report_text: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable dict."""
        return {
            "alert_id": self.alert_id,
            "alert_text": self.alert_text[:200],
            "db_name": self.db_name,
            "db_type": self.db_type,
            "total_duration_sec": self.total_duration_sec,
            "severity": self.severity,
            "category": self.category,
            "root_cause": self.root_cause,
            "evidence": self.evidence,
            "recommended_actions": self.recommended_actions,
            "steps_count": len(self.execution.steps) if self.execution else 0,
            "report_text": self.report_text,
            "error": self.error,
        }


class Orchestrator:
    """
    Ana orkestratör — tam tanı pipeline'ı.
    
    Pipeline:
    1. Triage: Alert'i sınıflandır (severity, category)
    2. Plan: Tanı planı oluştur (hangi tool'lar, hangi sırayla)
    3. Execute: Planı uygula (tool çağrıları + veri toplama)
    4. Analyze: Root cause belirle
    5. Report: Telegram formatında rapor oluştur
    
    Opsiyonel:
    6. Propose: Aksiyon öner (risk > safe ise onay bekle)
    7. Verify: Aksiyonu doğrula (before/after)
    """

    def __init__(self):
        self.planner = Planner()
        self.executor = Executor()
        self.verifier = Verifier()
        self.client = get_llm_client()
        self.router = ModelRouter()
        self.audit = AuditLogger()

    async def diagnose(
        self,
        alert_text: str,
        db_name: str = "",
        db_type: str = "postgresql",
        db_host: str = "",
        alert_id: str = "",
        metrics_summary: str = "",
        health_score: int = -1,
        skip_triage: bool = False,
        mode: str = "plan",  # "plan" | "freeform"
    ) -> DiagnosisReport:
        """
        Tam tanı pipeline'ı çalıştır.
        
        Args:
            alert_text: Alert açıklaması
            db_name: Hedef DB adı
            db_type: postgresql | mysql
            db_host: DB host
            alert_id: Opsiyonel tracking ID
            metrics_summary: Prometheus metrikleri özeti
            health_score: Mevcut sağlık skoru
            skip_triage: Triage'i atla (direkt plan)
            mode: "plan" (planner → executor) veya "freeform" (LLM-driven ReAct)
            
        Returns:
            DiagnosisReport
        """
        report = DiagnosisReport(
            alert_id=alert_id or f"diag-{int(time.time())}",
            alert_text=alert_text,
            db_name=db_name,
            db_type=db_type,
        )
        start_time = time.time()

        logger.info(f"{'═' * 50}")
        logger.info(f"  Diagnosis started: {report.alert_id}")
        logger.info(f"  Alert: {alert_text[:100]}")
        logger.info(f"  DB: {db_name} ({db_type})")
        logger.info(f"  Mode: {mode}")
        logger.info(f"{'═' * 50}")

        # ── Audit log ────────────────────────────────────
        self.audit.log(
            action_type="diagnosis",
            target=db_name or "default",
            command=f"diagnose_start:{report.alert_id}",
            risk_level="safe",
            result="started",
            metadata={"alert_text": alert_text[:200]},
        )

        try:
            # ── STEP 1: Triage ───────────────────────────
            if not skip_triage:
                logger.info("[1/4] Triage başlıyor...")
                triage_start = time.time()

                report.triage = await self.planner.triage(
                    alert_text=alert_text,
                    metrics_summary=metrics_summary,
                )
                report.severity = report.triage.severity
                report.category = report.triage.category

                logger.info(
                    f"[1/4] Triage tamamlandı: severity={report.severity}, "
                    f"category={report.category}, "
                    f"action_needed={report.triage.requires_action} "
                    f"({time.time() - triage_start:.1f}s)"
                )

                # Info ve action gerektirmeyen alert'ler için erken çıkış
                if report.severity == "info" and not report.triage.requires_action:
                    report.root_cause = report.triage.summary
                    lang = get_config().agent_language
                    if lang == "en":
                        report.report_text = (
                            f"ℹ️ *Info Alert*\n\n"
                            f"📊 Alert: {alert_text[:100]}\n"
                            f"📝 Summary: {report.triage.summary}\n"
                            f"✅ No action required."
                        )
                    else:
                        report.report_text = (
                            f"ℹ️ *Info Alert*\n\n"
                            f"📊 Alert: {alert_text[:100]}\n"
                            f"📝 Özet: {report.triage.summary}\n"
                            f"✅ Aksiyon gerektirmiyor."
                        )
                    report.total_duration_sec = round(time.time() - start_time, 1)
                    return report
            else:
                report.severity = "warning"
                report.category = "unknown"

            # ── STEP 2: Plan / Execute ───────────────────
            if mode == "freeform":
                # Freeform: LLM kendi yolunu çizer
                logger.info("[2/4] Freeform execution başlıyor...")
                report.execution = await self.executor.execute_freeform(
                    alert_description=alert_text,
                    db_name=db_name,
                    db_type=db_type,
                    context=f"Severity: {report.severity}, Category: {report.category}",
                )
            else:
                # Planlı: Triage → Plan → Execute
                logger.info("[2/4] Plan oluşturuluyor...")

                # Health score lazımsa çek
                if health_score < 0:
                    try:
                        from dba_agent.db import get_adapter
                        adapter = get_adapter(db_name)
                        with adapter:
                            h = adapter.get_health()
                            health_score = h.health_score
                    except Exception:
                        health_score = 0

                report.plan = await self.planner.create_plan(
                    alert_type=report.category,
                    severity=report.severity,
                    description=alert_text,
                    db_name=db_name,
                    db_type=db_type,
                    db_host=db_host,
                    health_score=health_score,
                )

                logger.info(
                    f"[2/4] Plan hazır: {len(report.plan.steps)} adım, "
                    f"hipotez: {report.plan.initial_hypothesis[:80]}"
                )

                # ── STEP 3: Execute ──────────────────────
                logger.info("[3/4] Plan uygulanıyor...")
                report.execution = await self.executor.execute_plan(
                    plan_steps=report.plan.steps,
                    db_name=db_name,
                    db_type=db_type,
                )

            # ── Sonuçları doldur ─────────────────────────
            if report.execution:
                report.root_cause = report.execution.root_cause
                report.evidence = report.execution.evidence
                report.recommended_actions = report.execution.recommended_actions

                logger.info(
                    f"[3/4] Execution tamamlandı: {len(report.execution.steps)} adım, "
                    f"{report.execution.total_duration_sec}s, "
                    f"root_cause: {report.root_cause[:80]}"
                )

            # ── STEP 4: Report ───────────────────────────
            logger.info("[4/4] Rapor oluşturuluyor...")
            report.report_text = await self._generate_report(report)

            report.total_duration_sec = round(time.time() - start_time, 1)

            logger.info(f"{'═' * 50}")
            logger.info(f"  Diagnosis completed: {report.alert_id}")
            logger.info(f"  Duration: {report.total_duration_sec}s")
            logger.info(f"  Root Cause: {report.root_cause[:100]}")
            logger.info(f"  Actions: {len(report.recommended_actions)}")
            logger.info(f"{'═' * 50}")

            self.audit.log(
                action_type="diagnosis",
                target=db_name or "default",
                command=f"diagnose_complete:{report.alert_id}",
                risk_level="safe",
                result="completed",
                metadata={"root_cause": report.root_cause[:200], "duration": report.total_duration_sec},
            )

            return report

        except Exception as e:
            logger.error(f"Diagnosis failed: {e}", exc_info=True)
            report.error = str(e)
            report.total_duration_sec = round(time.time() - start_time, 1)

            self.audit.log(
                action_type="diagnosis",
                target=db_name or "default",
                command=f"diagnose_error:{report.alert_id}",
                risk_level="safe",
                result="failed",
                metadata={"error": str(e)[:200]},
            )
            return report

    async def _generate_report(self, report: DiagnosisReport) -> str:
        """LLM ile Telegram formatında rapor oluştur."""
        params = self.router.get_params(TaskType.REPORT)
        lang = get_config().agent_language
        prompts = get_prompts(lang)

        if lang == "en":
            none_label = "None"
            no_history = "No historical records yet (Phase 4)"
            fallback_title = "DBA Agent Diagnosis Report"
            duration_label = "Duration"
            evidence_label = "Evidence"
            actions_label = "Recommendations"
        else:
            none_label = "Yok"
            no_history = "Henüz geçmiş kayıt yok (Faz 4'te eklenecek)"
            fallback_title = "DBA Agent Tanı Raporu"
            duration_label = "Süre"
            evidence_label = "Kanıtlar"
            actions_label = "Öneriler"

        evidence_text = "\n".join(f"- {e}" for e in report.evidence) if report.evidence else none_label
        actions_text = "\n".join(
            f"- [{a.get('risk', 'safe')}] {a.get('action', '')}: {a.get('sql', '-')}"
            for a in report.recommended_actions
        ) if report.recommended_actions else none_label

        prompt = prompts["REPORT_USER"].format(
            alert_type=report.category,
            db_name=report.db_name,
            diagnosis_duration=f"{report.total_duration_sec}s",
            root_cause=report.root_cause,
            evidence=evidence_text,
            recommended_actions=actions_text,
            similar_incidents=no_history,
        )

        try:
            response = await self.client.achat(
                prompt=prompt,
                model=params["model"],
                system_prompt=prompts["REPORT_SYSTEM"],
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            risk_line = ""
            if report.recommended_actions:
                risk = report.recommended_actions[0].get("risk", "safe")
                risk_line = f"\n⚡ Risk: {RISK_EMOJIS.get(risk, risk)}"

            return (
                f"🔍 *{fallback_title}*\n\n"
                f"📊 Alert: {report.category}\n"
                f"🖥️ DB: {report.db_name}\n"
                f"⏱️ {duration_label}: {report.total_duration_sec}s\n\n"
                f"🎯 *Root Cause:*\n{report.root_cause}\n\n"
                f"📋 *{evidence_label}:*\n{evidence_text}\n\n"
                f"💡 *{actions_label}:*\n{actions_text}"
                f"{risk_line}"
            )


# ── Singleton ────────────────────────────────

_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Orchestrator singleton'ı döndürür."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
