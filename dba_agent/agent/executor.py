"""
Executor — Plan Uygulayıcı (ReAct Loop)
════════════════════════════════════════
Planner'ın oluşturduğu adımları sırayla çalıştırır.
Her adımda: Thought → Action → Observation döngüsü.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dba_agent.agent.prompts import get_prompts
from dba_agent.config import get_config
from dba_agent.inference import TaskType, get_llm_client, ModelRouter
from dba_agent.tools.registry import get_tool_registry

logger = logging.getLogger("dba_agent.agent.executor")


@dataclass
class StepResult:
    """Tek adım sonucu."""
    step_num: int
    tool_name: str
    args: Dict[str, Any] = field(default_factory=dict)
    thought: str = ""
    observation: str = ""
    success: bool = True
    duration_sec: float = 0


@dataclass
class ExecutionResult:
    """Tüm çalıştırma sonucu."""
    steps: List[StepResult] = field(default_factory=list)
    root_cause: str = ""
    evidence: List[str] = field(default_factory=list)
    recommended_actions: List[Dict[str, Any]] = field(default_factory=list)
    total_duration_sec: float = 0
    success: bool = True
    error: str = ""


class Executor:
    """
    Plan uygulayıcı — ReAct döngüsü.
    
    İki mod:
    1. Plan-based: Planner'ın oluşturduğu adımları sırayla çalıştır
    2. Free-form: LLM kendi adımlarını belirler (daha esnek ama yavaş)
    """

    def __init__(self, max_steps: int = 6):
        self.client = get_llm_client()
        self.router = ModelRouter()
        self.registry = get_tool_registry()
        self.max_steps = max_steps

    async def execute_plan(
        self,
        plan_steps: List[Dict[str, Any]],
        db_name: str = "",
        db_type: str = "postgresql",
    ) -> ExecutionResult:
        """
        Planlı çalıştırma — Planner'ın adımlarını sırayla uygula.
        
        Args:
            plan_steps: [{"step": 1, "tool": "get_health", "args": {}, "reason": "..."}]
            db_name: Hedef veritabanı
            db_type: Veritabanı tipi
            
        Returns:
            ExecutionResult
        """
        result = ExecutionResult()
        start_time = time.time()

        logger.info(f"Executing plan: {len(plan_steps)} steps")

        for step_def in plan_steps[:self.max_steps]:
            step_num = step_def.get("step", len(result.steps) + 1)
            tool_name = step_def.get("tool", "")
            args = step_def.get("args", {})
            reason = step_def.get("reason", "")

            if not tool_name:
                continue

            # DB name inject
            if "db_name" not in args and db_name:
                args["db_name"] = db_name

            logger.info(f"Step {step_num}: {tool_name}({args}) — {reason}")

            step_start = time.time()
            tool_result = await self.registry.execute(tool_name, **args)
            step_duration = time.time() - step_start

            step = StepResult(
                step_num=step_num,
                tool_name=tool_name,
                args=args,
                thought=reason,
                observation=json.dumps(tool_result.get("result", {}), ensure_ascii=False, default=str)[:2000],
                success=tool_result.get("success", False),
                duration_sec=round(step_duration, 1),
            )
            result.steps.append(step)

            if not step.success:
                logger.warning(f"Step {step_num} failed: {tool_result.get('error')}")

        result.total_duration_sec = round(time.time() - start_time, 1)

        # LLM ile sonuçları analiz et
        await self._analyze_results(result, db_name, db_type)

        logger.info(
            f"Execution complete: {len(result.steps)} steps in "
            f"{result.total_duration_sec}s, root_cause: {result.root_cause[:80]}"
        )
        return result

    async def execute_freeform(
        self,
        alert_description: str,
        db_name: str = "",
        db_type: str = "postgresql",
        context: str = "",
    ) -> ExecutionResult:
        """
        Serbest çalıştırma — LLM kendi adımlarını belirler.
        ReAct döngüsü: Thought → Action → Observation → ... → Finish
        
        Daha yavaş ama beklenmedik durumlar için daha esnek.
        """
        result = ExecutionResult()
        start_time = time.time()
        params = self.router.get_params(TaskType.DIAGNOSIS)

        lang = get_config().agent_language
        prompts = get_prompts(lang)
        no_steps_yet = "No steps yet." if lang == "en" else "Henüz adım yok."

        tool_descriptions = self.registry.get_tool_descriptions(max_risk="safe")
        system_prompt = prompts["EXECUTOR_SYSTEM"].format(
            available_tools=tool_descriptions,
            max_steps=self.max_steps,
        )

        previous_steps_text = ""

        for step_num in range(1, self.max_steps + 1):
            user_prompt = prompts["EXECUTOR_USER"].format(
                plan=alert_description,
                db_name=db_name,
                db_type=db_type,
                previous_steps=previous_steps_text or no_steps_yet,
            )

            try:
                response = await self.client.achat(
                    prompt=user_prompt,
                    model=params["model"],
                    system_prompt=system_prompt,
                    temperature=params["temperature"],
                    max_tokens=params["max_tokens"],
                )

                # JSON parse
                data = json.loads(response.strip().strip("```json").strip("```"))
                thought = data.get("thought", "")
                action = data.get("action", "")

                # Finish durumu
                if action == "finish":
                    finish_result = data.get("result", {})
                    result.root_cause = finish_result.get("root_cause", "")
                    result.evidence = finish_result.get("evidence", [])
                    result.recommended_actions = finish_result.get("recommended_actions", [])
                    break

                # Tool çalıştır
                args = data.get("args", {})
                if "db_name" not in args and db_name:
                    args["db_name"] = db_name

                step_start = time.time()
                tool_result = await self.registry.execute(action, **args)
                step_duration = time.time() - step_start

                observation = json.dumps(
                    tool_result.get("result", tool_result.get("error", "")),
                    ensure_ascii=False, default=str,
                )[:1500]

                step = StepResult(
                    step_num=step_num,
                    tool_name=action,
                    args=args,
                    thought=thought,
                    observation=observation,
                    success=tool_result.get("success", False),
                    duration_sec=round(step_duration, 1),
                )
                result.steps.append(step)

                # Geçmişe ekle
                if lang == "en":
                    previous_steps_text += (
                        f"\nStep {step_num}:\n"
                        f"  Thought: {thought}\n"
                        f"  Tool: {action}({json.dumps(args, ensure_ascii=False)})\n"
                        f"  Result: {observation[:500]}\n"
                    )
                else:
                    previous_steps_text += (
                        f"\nAdım {step_num}:\n"
                        f"  Düşünce: {thought}\n"
                        f"  Araç: {action}({json.dumps(args, ensure_ascii=False)})\n"
                        f"  Sonuç: {observation[:500]}\n"
                    )

            except json.JSONDecodeError:
                logger.warning(f"Step {step_num}: JSON parse failed")
                result.steps.append(StepResult(
                    step_num=step_num,
                    tool_name="parse_error",
                    thought=response[:200] if 'response' in dir() else "Parse error",
                    success=False,
                ))
            except Exception as e:
                logger.error(f"Step {step_num} error: {e}")
                break

        result.total_duration_sec = round(time.time() - start_time, 1)

        # Eğer finish olmadan bittiyse, toplanan veriyle analiz et
        if not result.root_cause:
            await self._analyze_results(result, db_name, db_type)

        return result

    async def _analyze_results(
        self,
        result: ExecutionResult,
        db_name: str,
        db_type: str,
    ) -> None:
        """Toplanan tool sonuçlarını LLM ile analiz et — root cause bul."""
        lang = get_config().agent_language

        if not result.steps:
            result.root_cause = "Insufficient data collected" if lang == "en" else "Yeterli veri toplanamadı"
            return

        params = self.router.get_params(TaskType.DIAGNOSIS)

        if lang == "en":
            observations = "\n".join(
                f"Tool: {s.tool_name}\nResult: {s.observation[:500]}\n"
                for s in result.steps if s.success
            )
            prompt = f"""Analyze the following database diagnostic results.

Database: {db_name} ({db_type})

Collected Data:
{observations}

Respond ONLY in the following JSON format:
{{"root_cause": "root cause", "evidence": ["evidence 1", "evidence 2"], "recommended_actions": [{{"action": "description", "sql": "SQL if any", "risk": "safe|low|medium|high", "reason": "why"}}]}}"""
            system_prompt = "You are an experienced DBA. Analyze database diagnostic data and determine the root cause."
            not_determined = "Could not be determined"
            analysis_failed = "Analysis could not be completed"
        else:
            observations = "\n".join(
                f"Tool: {s.tool_name}\nSonuç: {s.observation[:500]}\n"
                for s in result.steps if s.success
            )
            prompt = f"""Aşağıdaki veritabanı diagnostik sonuçlarını analiz et.

Veritabanı: {db_name} ({db_type})

Toplanan Veriler:
{observations}

SADECE aşağıdaki JSON formatında yanıt ver:
{{"root_cause": "temel sebep", "evidence": ["kanıt 1", "kanıt 2"], "recommended_actions": [{{"action": "açıklama", "sql": "varsa SQL", "risk": "safe|low|medium|high", "reason": "neden"}}]}}"""
            system_prompt = "Sen deneyimli bir DBA'sın. Veritabanı diagnostik verilerini analiz et ve root cause belirle."
            not_determined = "Belirlenemedi"
            analysis_failed = "Analiz tamamlanamadı"

        try:
            response = await self.client.achat(
                prompt=prompt,
                model=params["model"],
                system_prompt=system_prompt,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
            )

            data = json.loads(response.strip().strip("```json").strip("```"))
            result.root_cause = data.get("root_cause", not_determined)
            result.evidence = data.get("evidence", [])
            result.recommended_actions = data.get("recommended_actions", [])

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            result.root_cause = analysis_failed
            result.error = str(e)
