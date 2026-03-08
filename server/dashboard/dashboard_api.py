"""
Dashboard API — Anomivox Platform Dashboard

4 ana bölüm:
1. Platform Genel Bakış (overview) — Sağlık skoru, KPI'lar, altyapı özeti
2. Servis Sağlık Durumu (health checks)
3. Aktivite Akışı (activity) — Son teşhisler ve olaylar timeline
4. Pipeline Zincir Durumu (Prometheus → Alertmanager → Notify → API → Diagnosis)
"""
import os
import json
import logging
import asyncio
import glob
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import Counter

import aiohttp
from fastapi import Body

from server.utils import BaseResponse
from configs import DIAGNOSTIC_RESULTS_PATH

logger = logging.getLogger("dashboard_api")

# ── Servis URL'leri (Docker Compose servis isimleri) ──────
SERVICES = {
    "api":           {"url": os.environ.get("API_URL",           "http://api:7861"),         "check": "/server/configs",      "method": "POST"},
    "litellm":       {"url": os.environ.get("LITELLM_BASE_URL",  "http://ai-agent-gateway:4000"), "check": "/health",          "method": "GET"},
    "prometheus":    {"url": os.environ.get("PROMETHEUS_URL",    "http://prometheus:9090"),   "check": "/api/v1/query?query=up","method": "GET"},
    "alertmanager":  {"url": os.environ.get("ALERTMANAGER_URL",  "http://alertmanager:9093"), "check": "/-/healthy",           "method": "GET"},
    "notify_worker": {"url": os.environ.get("NOTIFY_URL",        "http://notify-worker:8023"),"check": "/health",              "method": "GET"},
    "dba_agent":     {"url": os.environ.get("DBA_AGENT_URL",     "http://dba-agent:8100"),    "check": "/health",              "method": "GET"},
}

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

DB_TARGETS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs", "db_targets.json")

TIMEOUT = aiohttp.ClientTimeout(total=5)


# ── Yardımcı fonksiyonlar ─────────────────────────────────
async def _check_service(name: str, info: dict) -> dict:
    """Tek bir servisi HTTP ile kontrol et"""
    url = info["url"].rstrip("/") + info["check"]
    method = info["method"].lower()
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            fn = getattr(session, method)
            async with fn(url) as resp:
                online = resp.status < 500
                return {"name": name, "status": "online" if online else "degraded", "code": resp.status}
    except asyncio.TimeoutError:
        return {"name": name, "status": "timeout", "code": None}
    except Exception as e:
        return {"name": name, "status": "offline", "code": None, "error": str(e)[:80]}


async def _check_redis() -> dict:
    """Redis'i PING komutu ile kontrol et"""
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL, socket_connect_timeout=3, socket_timeout=3)
        pong = await r.ping()
        await r.aclose()
        if pong:
            return {"name": "redis", "status": "online", "code": None}
        return {"name": "redis", "status": "degraded", "code": None}
    except ImportError:
        # redis paketi yüklü değilse, TCP socket ile kontrol et
        try:
            from urllib.parse import urlparse
            parsed = urlparse(REDIS_URL)
            host = parsed.hostname or "localhost"
            port = parsed.port or 6379
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=3
            )
            writer.close()
            await writer.wait_closed()
            return {"name": "redis", "status": "online", "code": None}
        except Exception as e:
            return {"name": "redis", "status": "offline", "code": None, "error": str(e)[:80]}
    except Exception as e:
        return {"name": "redis", "status": "offline", "code": None, "error": str(e)[:80]}


async def _all_health_checks() -> List[dict]:
    tasks = [_check_service(name, info) for name, info in SERVICES.items()]
    tasks.append(_check_redis())
    return await asyncio.gather(*tasks)


def _load_db_targets() -> list:
    """db_targets.json'dan hedef listesini yükle"""
    try:
        if os.path.exists(DB_TARGETS_PATH):
            with open(DB_TARGETS_PATH, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"db_targets.json okunamadı: {e}")
    return []


def _scan_diagnoses(hours: int = 24) -> dict:
    """Teşhis dosyalarını tara, istatistikleri döndür"""
    cutoff = datetime.now() - timedelta(hours=hours)
    cutoff_ts = int(cutoff.timestamp())

    total = 0
    success = 0
    failed = 0
    all_diagnoses = []
    severity_counts = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
    models_used = Counter()

    if not os.path.exists(DIAGNOSTIC_RESULTS_PATH):
        return {
            "total": 0, "success": 0, "failed": 0,
            "success_rate": 0, "severity_counts": severity_counts,
            "all_diagnoses": [], "models_used": {},
        }

    for model_dir in os.listdir(DIAGNOSTIC_RESULTS_PATH):
        if model_dir == "examples":
            continue
        folder = os.path.join(DIAGNOSTIC_RESULTS_PATH, model_dir)
        if not os.path.isdir(folder):
            continue
        for fname in glob.glob(os.path.join(folder, "*.json")) + glob.glob(os.path.join(folder, "*.jsonl")):
            try:
                base = os.path.splitext(os.path.basename(fname))[0]
                ts = int(base)
            except (ValueError, TypeError):
                continue

            if ts < cutoff_ts:
                continue

            total += 1
            models_used[model_dir] += 1
            try:
                with open(fname, "r") as f:
                    data = json.load(f)

                has_result = bool(data.get("diagnosis") or data.get("report") or data.get("messages"))
                if has_result:
                    success += 1
                else:
                    failed += 1

                alerts = data.get("alerts", [])
                for alert in alerts:
                    level = alert.get("alert_level", "INFO").upper()
                    if level in severity_counts:
                        severity_counts[level] += 1
                    else:
                        severity_counts["INFO"] += 1

                all_diagnoses.append({
                    "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp": ts,
                    "model": model_dir,
                    "file": os.path.basename(fname),
                    "has_result": has_result,
                    "alert_count": len(alerts),
                    "alert_names": [a.get("alert_name", "") for a in alerts[:3]],
                    "severity": alerts[0].get("alert_level", "INFO").upper() if alerts else "INFO",
                })
            except Exception as e:
                logger.warning(f"Failed to read {fname}: {e}")
                failed += 1
                total = max(total, 1)

    all_diagnoses.sort(key=lambda x: x["timestamp"], reverse=True)

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "success_rate": round(success / total * 100, 1) if total > 0 else 0,
        "severity_counts": severity_counts,
        "all_diagnoses": all_diagnoses,
        "models_used": dict(models_used),
    }


# ── Endpoint 1: Platform Genel Bakış ──────────────────────
async def dashboard_overview(hours: int = Body(24, description="Kaç saatlik veri", embed=True)):
    """
    Anomivox platform genel bakış — tek endpoint ile tüm dashboard verisi.
    Platform sağlık skoru, KPI'lar, altyapı hedef özeti, servis durumları,
    pipeline durumu ve son aktiviteler.
    """
    # Paralel: servis kontrolleri
    health_results = await _all_health_checks()
    total_svc = len(health_results)
    online_svc = sum(1 for r in health_results if r["status"] == "online")

    # Teşhis istatistikleri
    diag = _scan_diagnoses(hours)

    # DB hedefleri
    targets = _load_db_targets()
    db_type_counts = Counter(t.get("db_type", "unknown") for t in targets)
    ssh_enabled = sum(1 for t in targets if t.get("ssh_enabled"))
    targets_ok = sum(1 for t in targets if t.get("last_status") == "ok")

    # Platform sağlık skoru (0-100)
    scores = []
    # Servis sağlığı (%40 ağırlık)
    svc_score = (online_svc / total_svc * 100) if total_svc > 0 else 0
    scores.append(svc_score * 0.4)
    # Teşhis başarı oranı (%30 ağırlık)
    scores.append(diag["success_rate"] * 0.3)
    # Hedef bağlantı durumu (%20 ağırlık)
    target_score = (targets_ok / len(targets) * 100) if targets else 100
    scores.append(target_score * 0.2)
    # Kritik alert yokluğu (%10 ağırlık)
    crit_count = diag["severity_counts"]["CRITICAL"]
    alert_score = max(0, 100 - crit_count * 25)
    scores.append(alert_score * 0.1)

    platform_score = round(sum(scores), 1)

    # Son 10 aktivite
    recent_activities = diag["all_diagnoses"][:10]

    return BaseResponse(
        code=200,
        msg="OK",
        data={
            # Platform Sağlık Skoru
            "platform_score": platform_score,
            "platform_status": "healthy" if platform_score >= 80 else ("warning" if platform_score >= 50 else "critical"),

            # KPI Kartları
            "kpi": {
                "services_online": online_svc,
                "services_total": total_svc,
                "targets_total": len(targets),
                "targets_ok": targets_ok,
                "diagnoses_total": diag["total"],
                "diagnoses_success_rate": diag["success_rate"],
                "critical_alerts": crit_count,
                "warning_alerts": diag["severity_counts"]["WARNING"],
            },

            # Altyapı Hedef Özeti
            "infrastructure": {
                "db_types": dict(db_type_counts),
                "ssh_enabled": ssh_enabled,
                "total_targets": len(targets),
                "targets": [
                    {
                        "name": t.get("name", ""),
                        "db_type": t.get("db_type", ""),
                        "host": t.get("host", ""),
                        "status": t.get("last_status", "unknown"),
                        "ssh": t.get("ssh_enabled", False),
                    }
                    for t in targets
                ],
            },

            # Servis Durumları
            "services": health_results,

            # Teşhis İstatistikleri
            "diagnosis": {
                "period_hours": hours,
                "total": diag["total"],
                "success": diag["success"],
                "failed": diag["failed"],
                "success_rate": diag["success_rate"],
                "severity_counts": diag["severity_counts"],
                "models_used": diag["models_used"],
            },

            # Son Aktiviteler
            "recent_activity": recent_activities,

            "generated_at": datetime.now().isoformat(),
        }
    )


# ── Endpoint 2: Servis Sağlık Durumu ──────────────────────
async def dashboard_health():
    """Tüm servislerin anlık sağlık durumunu döndür"""
    results = await _all_health_checks()
    total = len(results)
    online = sum(1 for r in results if r["status"] == "online")
    return BaseResponse(
        code=200,
        msg="OK",
        data={
            "services": results,
            "summary": {
                "total": total,
                "online": online,
                "offline": total - online,
                "healthy": online == total,
            },
            "checked_at": datetime.now().isoformat(),
        }
    )


# ── Endpoint 3: Pipeline Zincir Durumu ───────────────────
async def dashboard_pipeline_status():
    """
    Prometheus → Alertmanager → Notify Worker → API → Diagnosis
    zincirinin her halkasının durumunu kontrol et
    """
    steps = []

    # 1. Prometheus
    prom_url = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.get(f"{prom_url}/api/v1/query?query=up") as resp:
                if resp.status == 200:
                    body = await resp.json()
                    targets_up = len(body.get("data", {}).get("result", []))
                    steps.append({"step": "Prometheus", "status": "ok", "detail": f"{targets_up} target(s) up"})
                else:
                    steps.append({"step": "Prometheus", "status": "degraded", "detail": f"HTTP {resp.status}"})
    except Exception as e:
        steps.append({"step": "Prometheus", "status": "offline", "detail": str(e)[:60]})

    # 2. Alertmanager
    am_url = os.environ.get("ALERTMANAGER_URL", "http://alertmanager:9093")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.get(f"{am_url}/-/healthy") as resp:
                ok = resp.status == 200
                steps.append({"step": "Alertmanager", "status": "ok" if ok else "degraded", "detail": f"HTTP {resp.status}"})
    except Exception as e:
        steps.append({"step": "Alertmanager", "status": "offline", "detail": str(e)[:60]})

    # 3. Notify Worker
    nw_url = os.environ.get("NOTIFY_URL", "http://notify-worker:8023")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.get(f"{nw_url}/health") as resp:
                ok = resp.status == 200
                steps.append({"step": "Notify Worker", "status": "ok" if ok else "degraded", "detail": f"HTTP {resp.status}"})
    except Exception as e:
        steps.append({"step": "Notify Worker", "status": "offline", "detail": str(e)[:60]})

    # 4. API
    api_url = os.environ.get("API_URL", "http://api:7861")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.post(f"{api_url}/server/configs", json={}) as resp:
                ok = resp.status < 500
                steps.append({"step": "API", "status": "ok" if ok else "degraded", "detail": f"HTTP {resp.status}"})
    except Exception as e:
        steps.append({"step": "API", "status": "offline", "detail": str(e)[:60]})

    # 5. Diagnosis (son dosya üzerinden)
    diag_ok = False
    diag_detail = "No recent diagnosis"
    if os.path.exists(DIAGNOSTIC_RESULTS_PATH):
        for model_dir in os.listdir(DIAGNOSTIC_RESULTS_PATH):
            if model_dir == "examples":
                continue
            folder = os.path.join(DIAGNOSTIC_RESULTS_PATH, model_dir)
            files = sorted(glob.glob(os.path.join(folder, "*.json")) + glob.glob(os.path.join(folder, "*.jsonl")), reverse=True)
            if files:
                try:
                    ts = int(os.path.splitext(os.path.basename(files[0]))[0])
                    dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                    diag_ok = True
                    diag_detail = f"Last: {dt} ({model_dir})"
                    break
                except Exception:
                    pass
    steps.append({"step": "Diagnosis Engine", "status": "ok" if diag_ok else "warning", "detail": diag_detail})

    all_ok = all(s["status"] == "ok" for s in steps)
    has_issue = any(s["status"] in ("offline", "degraded") for s in steps)

    return BaseResponse(
        code=200,
        msg="OK",
        data={
            "steps": steps,
            "overall": "healthy" if all_ok else ("degraded" if has_issue else "warning"),
            "checked_at": datetime.now().isoformat(),
        }
    )
