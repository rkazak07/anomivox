"""
Dashboard API — Anomivox Operasyonel Durum Paneli

3 ana bölüm:
1. Servis Sağlık Durumu (health checks)
2. Teşhis Pipeline Özeti (son 24 saat)
3. Pipeline Zincir Durumu (Prometheus → Alertmanager → Notify → API → Diagnosis)
"""
import os
import json
import logging
import asyncio
import glob
from datetime import datetime, timedelta
from typing import List, Dict, Any

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

TIMEOUT = aiohttp.ClientTimeout(total=5)


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


async def _all_health_checks() -> List[dict]:
    tasks = [_check_service(name, info) for name, info in SERVICES.items()]
    return await asyncio.gather(*tasks)


# ── Endpoint 1: Servis Sağlık Durumu ──────────────────────
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


# ── Endpoint 2: Teşhis Özeti ──────────────────────────────
def dashboard_diagnosis_summary(hours: int = Body(24, description="Kaç saatlik veri", embed=True)):
    """Son N saatteki teşhis istatistikleri"""
    cutoff = datetime.now() - timedelta(hours=hours)
    cutoff_ts = int(cutoff.timestamp())

    total = 0
    success = 0
    failed = 0
    last_diagnoses = []
    severity_counts = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}

    # Tüm model klasörlerini tara
    if os.path.exists(DIAGNOSTIC_RESULTS_PATH):
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
                try:
                    with open(fname, "r") as f:
                        data = json.load(f)

                    # Başarı/başarısız tespiti
                    has_result = bool(data.get("diagnosis") or data.get("report") or data.get("messages"))
                    if has_result:
                        success += 1
                    else:
                        failed += 1

                    # Severity sayımı
                    alerts = data.get("alerts", [])
                    for alert in alerts:
                        level = alert.get("alert_level", "INFO").upper()
                        if level in severity_counts:
                            severity_counts[level] += 1
                        else:
                            severity_counts["INFO"] += 1

                    # Son teşhisler listesi (max 5)
                    if len(last_diagnoses) < 5:
                        last_diagnoses.append({
                            "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                            "model": model_dir,
                            "file": os.path.basename(fname),
                            "has_result": has_result,
                            "alert_names": [a.get("alert_name", "") for a in alerts[:3]],
                        })
                except Exception as e:
                    logger.warning(f"Failed to read {fname}: {e}")
                    failed += 1
                    total = max(total, 1)

    last_diagnoses.sort(key=lambda x: x["time"], reverse=True)

    return BaseResponse(
        code=200,
        msg="OK",
        data={
            "period_hours": hours,
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
            "severity_counts": severity_counts,
            "last_diagnoses": last_diagnoses,
            "generated_at": datetime.now().isoformat(),
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
