"""
Verifier — İşlem Doğrulayıcı
═════════════════════════════
Uygulanan aksiyonun before/after karşılaştırmasını yapar.
Rollback gerekip gerekmediğine karar verir.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from dba_agent.agent.prompts import VERIFIER_SYSTEM, VERIFIER_USER
from dba_agent.db import get_adapter
from dba_agent.inference import TaskType, get_llm_client, ModelRouter

logger = logging.getLogger("dba_agent.agent.verifier")


@dataclass
class VerificationResult:
    """Doğrulama sonucu."""
    success: bool = False
    improvement: str = ""
    before_after: Dict[str, Any] = None
    needs_rollback: bool = False
    rollback_reason: str = ""
    recommendation: str = ""
    raw_response: str = ""

    def __post_init__(self):
        if self.before_after is None:
            self.before_after = {}


class Verifier:
    """
    İşlem doğrulayıcı.
    
    Akış:
    1. Before snapshot al (execute öncesi)
    2. Aksiyon uygulandıktan sonra after snapshot al
    3. LLM ile karşılaştır
    4. Rollback gerekiyorsa bildir
    """

    def __init__(self):
        self.client = get_llm_client()
        self.router = ModelRouter()

    def take_snapshot(self, db_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Veritabanının anlık durumunu kaydet.
        Execute öncesi ve sonrası çağrılır.
        """
        try:
            adapter = get_adapter(db_name)
            with adapter:
                health = adapter.get_health()
                return {
                    "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
                    "health_score": health.health_score,
                    "active_connections": health.active_connections,
                    "cache_hit_ratio": health.cache_hit_ratio,
                    "long_running_queries": health.long_running_queries,
                    "blocked_locks": health.blocked_locks,
                    "database_size_mb": health.database_size_mb,
                }
        except Exception as e:
            logger.error(f"Snapshot failed: {e}")
            return {"error": str(e)}

    async def verify(
        self,
        command: str,
        risk_level: str,
        target: str,
        before_snapshot: Dict[str, Any],
        after_snapshot: Dict[str, Any],
    ) -> VerificationResult:
        """
        Aksiyon sonucunu doğrula.
        
        Args:
            command: Uygulanan SQL/komut
            risk_level: Risk seviyesi
            target: Hedef (DB adı / sunucu)
            before_snapshot: Önceki durum
            after_snapshot: Sonraki durum
            
        Returns:
            VerificationResult
        """
        params = self.router.get_params(TaskType.VERIFICATION)

        # Metrik farkları hesapla
        metrics_diff = self._compute_diff(before_snapshot, after_snapshot)

        prompt = VERIFIER_USER.format(
            command=command,
            risk_level=risk_level,
            target=target,
            before_snapshot=json.dumps(before_snapshot, indent=2, default=str),
            after_snapshot=json.dumps(after_snapshot, indent=2, default=str),
            metrics_diff=json.dumps(metrics_diff, indent=2, default=str),
        )

        logger.info(f"Verifying action: {command[:80]}...")

        try:
            response = await self.client.achat(
                prompt=prompt,
                model=params["model"],
                system_prompt=VERIFIER_SYSTEM,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
            )

            result = VerificationResult(raw_response=response)

            try:
                data = json.loads(response.strip().strip("```json").strip("```"))
                result.success = data.get("success", False)
                result.improvement = data.get("improvement", "")
                result.before_after = data.get("before_after", {})
                result.needs_rollback = data.get("needs_rollback", False)
                result.rollback_reason = data.get("rollback_reason", "")
                result.recommendation = data.get("recommendation", "")
            except json.JSONDecodeError:
                logger.warning("Verification JSON parse failed")
                # Basit karşılaştırma
                result.success = (
                    after_snapshot.get("health_score", 0) >= before_snapshot.get("health_score", 0)
                )
                result.improvement = "LLM analizi başarısız, metrik karşılaştırma kullanıldı"

            logger.info(
                f"Verification complete: success={result.success}, "
                f"rollback={result.needs_rollback}"
            )
            return result

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return VerificationResult(
                success=False,
                improvement=f"Doğrulama hatası: {e}",
                needs_rollback=True,
                rollback_reason="Doğrulama yapılamadı, güvenlik nedeniyle rollback önerilir",
            )

    def _compute_diff(
        self,
        before: Dict[str, Any],
        after: Dict[str, Any],
    ) -> Dict[str, Any]:
        """İki snapshot arasındaki farkları hesapla."""
        diff = {}
        numeric_keys = [
            "health_score", "active_connections", "cache_hit_ratio",
            "long_running_queries", "blocked_locks", "database_size_mb",
        ]
        for key in numeric_keys:
            bval = before.get(key)
            aval = after.get(key)
            if bval is not None and aval is not None:
                try:
                    bval = float(bval)
                    aval = float(aval)
                    change = aval - bval
                    pct_change = ((aval - bval) / bval * 100) if bval != 0 else 0
                    diff[key] = {
                        "before": bval,
                        "after": aval,
                        "change": round(change, 2),
                        "pct_change": f"{pct_change:+.1f}%",
                    }
                except (ValueError, TypeError):
                    pass
        return diff
