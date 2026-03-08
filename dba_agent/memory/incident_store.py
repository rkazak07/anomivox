"""
Incident Memory Store — Olay Hafızası
═══════════════════════════════════════
Her tanı + aksiyon + sonucu kaydeder.
Benzer geçmiş vakaları ChromaDB üzerinden RAG ile getirir.

Kullanım:
    store = IncidentStore()
    store.save_incident(incident_data)
    similar = store.find_similar(alert_description, top_k=3)
    stats = store.get_action_stats()
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("dba_agent.memory.incident_store")

# Incident store dosya yolu (JSON Lines)
INCIDENT_LOG_PATH = os.getenv(
    "DBA_INCIDENT_LOG_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "logs", "dba_incident_store.jsonl"
    ),
)


class IncidentStore:
    """
    Olay hafızası — tanı sonuçlarını ve aksiyon başarı oranlarını saklar.

    Depolama:
    - JSON Lines dosyası (her satır bir incident)
    - ChromaDB (RAG retrieval için — opsiyonel)

    ChromaDB bağlanamıyorsa JSON Lines ile devam eder.
    """

    def __init__(self, log_path: Optional[str] = None, use_chroma: bool = True):
        self.log_path = log_path or INCIDENT_LOG_PATH
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

        self._chroma_collection = None
        if use_chroma:
            self._init_chroma()

    def _init_chroma(self) -> None:
        """ChromaDB koleksiyonunu başlat (hata olursa sessizce geç)."""
        try:
            import chromadb
            chroma_path = os.getenv(
                "CHROMA_DB_PATH",
                os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "chroma_db"
                ),
            )
            client = chromadb.PersistentClient(path=chroma_path)
            self._chroma_collection = client.get_or_create_collection(
                name="dba_incidents",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("IncidentStore: ChromaDB koleksiyonu hazır.")
        except Exception as e:
            logger.warning(f"IncidentStore: ChromaDB başlatılamadı, sadece JSONL kullanılacak: {e}")
            self._chroma_collection = None

    def save_incident(
        self,
        alert_type: str,
        alert_text: str,
        root_cause: str,
        actions_taken: List[Dict[str, Any]],
        health_before: Dict[str, Any],
        health_after: Dict[str, Any],
        success: bool,
        db_name: str = "",
        feedback_score: Optional[float] = None,
    ) -> str:
        """
        Incident kaydını sakla.

        Args:
            alert_type: Anomali kategorisi
            alert_text: Ham alert açıklaması
            root_cause: Tespit edilen kök neden
            actions_taken: Uygulanan aksiyonlar listesi
            health_before: Aksiyon öncesi metrikler
            health_after: Aksiyon sonrası metrikler
            success: Aksiyonlar başarılı mı?
            db_name: Hedef DB
            feedback_score: DBA geri bildirimi (0.0–1.0), None = henüz yok

        Returns:
            incident_id
        """
        incident_id = str(uuid.uuid4())[:12]
        record = {
            "incident_id": incident_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert_type": alert_type,
            "alert_text": alert_text[:500],
            "root_cause": root_cause[:500],
            "actions_taken": actions_taken,
            "health_before": health_before,
            "health_after": health_after,
            "success": success,
            "db_name": db_name,
            "feedback_score": feedback_score,
            # Özet metrik: health skoru değişimi
            "health_delta": (
                health_after.get("health_score", 0) - health_before.get("health_score", 0)
                if health_before and health_after else None
            ),
        }

        # JSONL'a yaz
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            logger.error(f"Incident JSONL yazma hatası: {e}")

        # ChromaDB'ye ekle (RAG için)
        if self._chroma_collection is not None:
            try:
                doc_text = (
                    f"Alert: {alert_text[:200]}\n"
                    f"Root Cause: {root_cause[:200]}\n"
                    f"Actions: {', '.join(a.get('action', '') for a in actions_taken)}"
                )
                self._chroma_collection.add(
                    ids=[incident_id],
                    documents=[doc_text],
                    metadatas=[{
                        "alert_type": alert_type,
                        "root_cause": root_cause[:200],
                        "success": str(success),
                        "db_name": db_name,
                        "health_delta": str(record["health_delta"]),
                        "feedback_score": str(feedback_score or ""),
                        "timestamp": record["timestamp"],
                    }],
                )
            except Exception as e:
                logger.warning(f"ChromaDB incident kaydetme hatası: {e}")

        logger.info(f"Incident kaydedildi: {incident_id} (success={success})")
        return incident_id

    def find_similar(
        self,
        alert_text: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Benzer geçmiş vakaları getir (ChromaDB similarity search).

        Args:
            alert_text: Mevcut alert açıklaması
            top_k: Kaç sonuç getirilsin

        Returns:
            En benzer incident'ların listesi (metadata + distance)
        """
        if self._chroma_collection is None:
            return self._find_similar_jsonl(alert_text, top_k)

        try:
            results = self._chroma_collection.query(
                query_texts=[alert_text],
                n_results=min(top_k, max(1, self._chroma_collection.count())),
                include=["metadatas", "documents", "distances"],
            )
            similar = []
            for i, meta in enumerate(results["metadatas"][0]):
                similar.append({
                    "document": results["documents"][0][i],
                    "distance": results["distances"][0][i],
                    "alert_type": meta.get("alert_type", ""),
                    "root_cause": meta.get("root_cause", ""),
                    "success": meta.get("success") == "True",
                    "health_delta": meta.get("health_delta", ""),
                    "feedback_score": meta.get("feedback_score", ""),
                    "timestamp": meta.get("timestamp", ""),
                })
            return similar
        except Exception as e:
            logger.warning(f"ChromaDB benzer vaka sorgusu başarısız: {e}")
            return self._find_similar_jsonl(alert_text, top_k)

    def _find_similar_jsonl(
        self, alert_text: str, top_k: int
    ) -> List[Dict[str, Any]]:
        """
        ChromaDB yoksa basit keyword eşleşmesiyle benzer vaka ara.
        """
        try:
            records = self._load_all()
            alert_words = set(alert_text.lower().split())
            scored = []
            for rec in records:
                text = f"{rec.get('alert_text', '')} {rec.get('root_cause', '')}".lower()
                overlap = sum(1 for w in alert_words if w in text)
                if overlap > 0:
                    scored.append((overlap, rec))
            scored.sort(reverse=True, key=lambda x: x[0])
            return [
                {
                    "document": f"Alert: {r.get('alert_text', '')[:100]}\nRoot Cause: {r.get('root_cause', '')[:100]}",
                    "distance": 1.0 - (score / max(len(alert_words), 1)),
                    "alert_type": r.get("alert_type", ""),
                    "root_cause": r.get("root_cause", ""),
                    "success": r.get("success", False),
                    "health_delta": str(r.get("health_delta", "")),
                    "feedback_score": str(r.get("feedback_score", "")),
                    "timestamp": r.get("timestamp", ""),
                }
                for score, r in scored[:top_k]
            ]
        except Exception as e:
            logger.error(f"JSONL benzer vaka arama hatası: {e}")
            return []

    def get_action_stats(self) -> Dict[str, Any]:
        """
        Aksiyon başarı istatistiklerini hesapla.

        Returns:
            {
              "total": int,
              "success_rate": float,
              "by_action": {"vacuum_table": {"count": 5, "success_rate": 0.8}, ...},
              "avg_health_delta": float,
            }
        """
        try:
            records = self._load_all()
            if not records:
                return {"total": 0, "success_rate": 0.0, "by_action": {}, "avg_health_delta": 0.0}

            total = len(records)
            successes = sum(1 for r in records if r.get("success"))
            health_deltas = [r["health_delta"] for r in records if r.get("health_delta") is not None]

            by_action: Dict[str, Dict] = {}
            for rec in records:
                for action in rec.get("actions_taken", []):
                    name = action.get("action", "unknown")
                    if name not in by_action:
                        by_action[name] = {"count": 0, "successes": 0}
                    by_action[name]["count"] += 1
                    if rec.get("success"):
                        by_action[name]["successes"] += 1

            return {
                "total": total,
                "success_rate": round(successes / total, 2) if total else 0.0,
                "by_action": {
                    k: {
                        "count": v["count"],
                        "success_rate": round(v["successes"] / v["count"], 2) if v["count"] else 0.0,
                    }
                    for k, v in sorted(by_action.items(), key=lambda x: -x[1]["count"])
                },
                "avg_health_delta": round(sum(health_deltas) / len(health_deltas), 1) if health_deltas else 0.0,
            }
        except Exception as e:
            logger.error(f"Action stats hesaplama hatası: {e}")
            return {"total": 0, "success_rate": 0.0, "by_action": {}, "avg_health_delta": 0.0}

    def update_feedback(self, incident_id: str, score: float) -> bool:
        """
        DBA geri bildirimini güncelle (0.0 = kötü, 1.0 = çok iyi).
        JSONL'ı yeniden yazar.
        """
        try:
            records = self._load_all()
            updated = False
            for rec in records:
                if rec.get("incident_id") == incident_id:
                    rec["feedback_score"] = round(score, 2)
                    updated = True
                    break
            if updated:
                with open(self.log_path, "w") as f:
                    for rec in records:
                        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                logger.info(f"Feedback güncellendi: {incident_id} → {score}")
            return updated
        except Exception as e:
            logger.error(f"Feedback güncelleme hatası: {e}")
            return False

    def _load_all(self) -> List[Dict[str, Any]]:
        """Tüm incident kayıtlarını JSONL'dan yükle."""
        records = []
        if not os.path.exists(self.log_path):
            return records
        with open(self.log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records


# ─── Singleton ────────────────────────────────
_store: Optional[IncidentStore] = None


def get_incident_store() -> IncidentStore:
    """Global IncidentStore singleton."""
    global _store
    if _store is None:
        _store = IncidentStore()
    return _store
