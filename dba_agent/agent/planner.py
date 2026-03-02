"""
Planner — Tanı Planlayıcısı
════════════════════════════
Alert'i sınıflandırır ve adım adım tanı planı oluşturur.
İki aşama: Triage (hızlı, llama3.2:1b) → Plan (detaylı, llama3.1:8b)
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dba_agent.agent.prompts import (
    PLANNER_SYSTEM,
    PLANNER_USER,
    TRIAGE_SYSTEM,
    TRIAGE_USER,
)
from dba_agent.inference import TaskType, get_llm_client, ModelRouter
from dba_agent.tools.registry import get_tool_registry

logger = logging.getLogger("dba_agent.agent.planner")


@dataclass
class TriageResult:
    """Triage sonucu."""
    severity: str = "warning"  # critical, warning, info
    category: str = "unknown"  # cpu, memory, io, disk, lock, query, ...
    requires_action: bool = False
    summary: str = ""
    raw_response: str = ""


@dataclass
class DiagnosisPlan:
    """Tanı planı."""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    initial_hypothesis: str = ""
    expected_root_causes: List[str] = field(default_factory=list)
    raw_response: str = ""


class Planner:
    """
    Tanı planlayıcısı.
    
    1. Triage: Alert'i hızlıca sınıflandır (llama3.2:1b, <3s)
    2. Plan: Detaylı tanı planı oluştur (llama3.1:8b, ~10s)
    """

    def __init__(self):
        self.client = get_llm_client()
        self.router = ModelRouter()
        self.registry = get_tool_registry()

    async def triage(
        self,
        alert_text: str,
        metrics_summary: str = "",
    ) -> TriageResult:
        """
        Hızlı alert sınıflandırma.
        
        Args:
            alert_text: Alert mesajı
            metrics_summary: Opsiyonel metrik özeti
            
        Returns:
            TriageResult
        """
        params = self.router.get_params(TaskType.TRIAGE)

        prompt = TRIAGE_USER.format(
            alert_text=alert_text,
            metrics_summary=metrics_summary or "Metrik bilgisi yok",
        )

        logger.info(f"Triage starting: {alert_text[:80]}...")

        try:
            response = await self.client.achat(
                prompt=prompt,
                model=params["model"],
                system_prompt=TRIAGE_SYSTEM,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
            )

            result = TriageResult(raw_response=response)

            # JSON parse
            try:
                data = json.loads(response.strip().strip("```json").strip("```"))
                result.severity = data.get("severity", "warning")
                result.category = data.get("category", "unknown")
                result.requires_action = data.get("requires_action", False)
                result.summary = data.get("summary", "")
            except json.JSONDecodeError:
                logger.warning(f"Triage JSON parse failed, using defaults")
                result.summary = response[:200]
                result.requires_action = True

            logger.info(
                f"Triage complete: severity={result.severity}, "
                f"category={result.category}, action={result.requires_action}"
            )
            return result

        except Exception as e:
            logger.error(f"Triage failed: {e}")
            return TriageResult(
                severity="warning",
                category="unknown",
                requires_action=True,
                summary=f"Triage failed: {e}",
            )

    async def create_plan(
        self,
        alert_type: str,
        severity: str,
        description: str,
        db_name: str,
        db_type: str,
        db_host: str,
        health_score: int = 0,
        duration: str = "",
        context: str = "",
    ) -> DiagnosisPlan:
        """
        Detaylı tanı planı oluştur.
        
        Args:
            alert_type: Alert tipi (cpu, memory, lock, vb.)
            severity: Şiddet (critical, warning, info)
            description: Alert açıklaması
            db_name: Veritabanı adı
            db_type: Veritabanı tipi (postgresql, mysql)
            db_host: Veritabanı host
            health_score: Sağlık puanı (0-100)
            duration: Alert süresi
            context: Ek bağlam (opsiyonel)
            
        Returns:
            DiagnosisPlan
        """
        params = self.router.get_params(TaskType.PLANNING)

        # Kullanılabilir araçları al
        tool_descriptions = self.registry.get_tool_descriptions(max_risk="safe")

        system_prompt = PLANNER_SYSTEM.format(available_tools=tool_descriptions)
        user_prompt = PLANNER_USER.format(
            alert_type=alert_type,
            severity=severity,
            description=description,
            db_name=db_name,
            db_type=db_type,
            db_host=db_host,
            health_score=health_score,
            duration=duration or "bilinmiyor",
            context=context or "Ek bağlam yok",
        )

        logger.info(f"Planning diagnosis for: {alert_type} ({severity})")

        try:
            response = await self.client.achat(
                prompt=user_prompt,
                model=params["model"],
                system_prompt=system_prompt,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
            )

            plan = DiagnosisPlan(raw_response=response)

            # JSON parse
            try:
                data = json.loads(response.strip().strip("```json").strip("```"))
                plan.steps = data.get("diagnosis_plan", [])
                plan.initial_hypothesis = data.get("initial_hypothesis", "")
                plan.expected_root_causes = data.get("expected_root_causes", [])
            except json.JSONDecodeError:
                logger.warning("Plan JSON parse failed, creating basic plan")
                plan.steps = [
                    {"step": 1, "tool": "get_health", "args": {}, "reason": "Genel durum kontrolü"},
                    {"step": 2, "tool": "get_slow_queries", "args": {"limit": 10}, "reason": "Yavaş sorgu tespiti"},
                    {"step": 3, "tool": "get_active_connections", "args": {}, "reason": "Bağlantı durumu"},
                ]
                plan.initial_hypothesis = "Plan oluşturulamadı, varsayılan adımlar kullanılıyor"

            logger.info(f"Plan created: {len(plan.steps)} steps, hypothesis: {plan.initial_hypothesis[:80]}")
            return plan

        except Exception as e:
            logger.error(f"Planning failed: {e}")
            # Fallback plan
            return DiagnosisPlan(
                steps=[
                    {"step": 1, "tool": "get_health", "args": {}, "reason": "Genel durum kontrolü"},
                    {"step": 2, "tool": "get_active_connections", "args": {}, "reason": "Bağlantı kontrolü"},
                ],
                initial_hypothesis=f"Planlama hatası: {e}",
            )
