"""
DBA Agent — Ana Giriş Noktası
═════════════════════════════
Agent'ı başlatır, health check endpoint sağlar.
"""

import asyncio
import logging
import os
import sys
import time

import uvicorn
from fastapi import FastAPI, HTTPException

from dba_agent.config import get_config, reload_config, sync_from_json

# ── Logging ──────────────────────────────────
logging.basicConfig(
    level=os.getenv("DBA_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dba_agent")

# ── FastAPI App (health check + webhook) ─────
app = FastAPI(
    title="Anomivox DBA Agent",
    version="0.2.0",
    docs_url="/docs",
)


@app.on_event("startup")
async def startup_event():
    """Uygulama başlarken tool'ları kaydet, Telegram bot ve monitoring başlat."""
    from dba_agent.tools import register_all_tools
    registry = register_all_tools()
    logger.info(f"Registered {len(registry.list_tools())} tools")

    # ── Telegram Bot başlat ──────────────────
    try:
        from dba_agent.telegram.bot import get_bot
        bot = get_bot()
        if bot.is_configured:
            await bot.start()
            logger.info("✅ Telegram bot polling aktif")
        else:
            logger.warning("Telegram bot token tanımlı değil, bot başlatılmadı.")
    except Exception as e:
        logger.error(f"Telegram bot başlatma hatası: {e}", exc_info=True)

    # ── Proaktif İzleme Başlat ───────────────
    try:
        from dba_agent.monitoring import get_health_monitor
        monitor = get_health_monitor()
        await monitor.start()
        logger.info(
            f"✅ Proaktif izleme aktif — interval: {monitor.thresholds.check_interval_sec}s"
        )
    except Exception as e:
        logger.error(f"Proaktif izleme başlatma hatası: {e}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapanırken Telegram bot ve monitoring'i durdur."""
    try:
        from dba_agent.monitoring import get_health_monitor
        monitor = get_health_monitor()
        await monitor.stop()
    except Exception as e:
        logger.error(f"Proaktif izleme durdurma hatası: {e}")

    try:
        from dba_agent.telegram.bot import get_bot
        bot = get_bot()
        await bot.stop()
    except Exception as e:
        logger.error(f"Telegram bot durdurma hatası: {e}")


@app.get("/health")
async def health():
    """Health check endpoint."""
    from dba_agent.inference import get_llm_client
    config = get_config()
    llm = get_llm_client()
    return {
        "status": "ok",
        "version": "0.2.0",
        "language": config.agent_language,
        "db_targets": [t.display_name for t in config.database.targets],
        "ssh_targets": [t.display_name for t in config.ssh.targets],
        "llm_stats": llm.stats,
    }


@app.get("/health/llm")
async def health_llm():
    """LLM bağlantı kontrolü."""
    from dba_agent.inference import get_llm_client
    client = get_llm_client()
    return client.health_check()


@app.get("/health/db")
async def health_db():
    """Veritabanı bağlantı kontrolü."""
    from dba_agent.db import get_all_adapters
    results = {}
    for name, adapter in get_all_adapters().items():
        try:
            adapter.connect()
            health = adapter.get_health()
            results[name] = {
                "connected": True,
                "version": health.version,
                "score": health.health_score,
                "connections": f"{health.active_connections}/{health.max_connections}",
                "cache_hit": f"{health.cache_hit_ratio:.1%}",
            }
        except Exception as e:
            results[name] = {"connected": False, "error": str(e)}
        finally:
            adapter.disconnect()
    return results


@app.get("/health/monitor")
async def health_monitor():
    """Proaktif izleme durumu."""
    from dba_agent.monitoring import get_health_monitor
    monitor = get_health_monitor()
    return monitor.stats


@app.post("/api/maintenance/run")
async def run_maintenance(body: dict):
    """Zamanlanmış bakım görevi çalıştır (server scheduler tarafından çağrılır)."""
    task_type = body.get('task_type', '')
    db_target_name = body.get('db_target_name', '')
    if not task_type or not db_target_name:
        return {'success': False, 'output': 'task_type ve db_target_name zorunlu.'}
    from dba_agent.scheduler.maintenance_executor import run_maintenance as _run
    result = await _run(task_type=task_type, db_target_name=db_target_name)
    # Audit log
    try:
        from dba_agent.security.audit import AuditLogger
        AuditLogger().log(
            action_type='scheduled_maintenance',
            target=db_target_name,
            command=task_type,
            risk_level='low',
            result='success' if result.get('success') else 'failed',
            metadata={'output': result.get('output', '')[:500]},
        )
    except Exception:
        pass
    return result


@app.post("/api/agent/monitor/start")
async def monitor_start():
    """Proaktif izlemeyi başlat."""
    from dba_agent.monitoring import get_health_monitor
    monitor = get_health_monitor()
    if not monitor.is_running:
        await monitor.start()
        return {"status": "started"}
    return {"status": "already_running"}


@app.post("/api/agent/monitor/stop")
async def monitor_stop():
    """Proaktif izlemeyi durdur."""
    from dba_agent.monitoring import get_health_monitor
    monitor = get_health_monitor()
    await monitor.stop()
    return {"status": "stopped"}


@app.get("/health/telegram")
async def health_telegram():
    """Telegram bot durum kontrolü."""
    from dba_agent.telegram.bot import get_bot
    bot = get_bot()
    config = get_config().telegram
    return {
        "configured": bot.is_configured,
        "running": bot._running,
        "admin_chat_id": config.admin_chat_id,
        "extra_chat_ids": config.extra_chat_ids,
        "approval_timeout": config.approval_timeout,
    }


@app.post("/api/agent/alert")
async def receive_alert(request: dict):
    """
    Alert webhook — notify-worker'dan alert alır.
    Otomatik triage + diagnosis başlatır.
    Sonucu Telegram'a gönderir.
    """
    logger.info(f"Alert received: {request.get('status', 'unknown')}")
    
    # ── Telegram'a alert bildirimi gönder ────
    try:
        from dba_agent.telegram.bot import get_bot
        from dba_agent.telegram.formatter import format_alert_notification
        bot = get_bot()
        if bot._running:
            alert_msg = format_alert_notification(request)
            await bot.broadcast(alert_msg)
    except Exception as e:
        logger.error(f"Telegram alert bildirimi hatası: {e}")
    
    from dba_agent.agent import get_orchestrator
    orchestrator = get_orchestrator()
    
    # Alert'ten bilgi çıkar
    alert_text = request.get("description", request.get("message", str(request)))
    db_name = request.get("db_name", "")
    metrics = request.get("metrics_summary", "")
    
    report = await orchestrator.diagnose(
        alert_text=alert_text,
        db_name=db_name,
        metrics_summary=metrics,
    )
    
    # ── Tanı raporunu Telegram'a gönder ──────
    try:
        from dba_agent.telegram.bot import get_bot
        bot = get_bot()
        if bot._running and report.report_text:
            await bot.broadcast(report.report_text)
    except Exception as e:
        logger.error(f"Telegram rapor gönderme hatası: {e}")
    
    return {
        "status": "diagnosed",
        "alert_id": report.alert_id,
        "severity": report.severity,
        "root_cause": report.root_cause,
        "duration_sec": report.total_duration_sec,
        "report": report.report_text,
    }


@app.post("/api/agent/diagnose")
async def diagnose(request: dict):
    """
    Manuel tanı endpoint'i.
    
    Body:
    {
        "alert_text": "CPU %95 üzerinde son 10 dakika",
        "db_name": "",         // opsiyonel, boş = varsayılan DB
        "db_type": "postgresql",
        "db_host": "",
        "mode": "plan",        // "plan" | "freeform"
        "skip_triage": false
    }
    """
    from dba_agent.agent import get_orchestrator
    
    alert_text = request.get("alert_text", "")
    if not alert_text:
        raise HTTPException(status_code=400, detail="alert_text is required")
    
    orchestrator = get_orchestrator()
    
    report = await orchestrator.diagnose(
        alert_text=alert_text,
        db_name=request.get("db_name", ""),
        db_type=request.get("db_type", "postgresql"),
        db_host=request.get("db_host", ""),
        mode=request.get("mode", "plan"),
        skip_triage=request.get("skip_triage", False),
        metrics_summary=request.get("metrics_summary", ""),
    )
    
    return report.to_dict()


@app.get("/api/agent/tools")
async def list_tools():
    """Kayıtlı araçları listele."""
    from dba_agent.tools import get_tool_registry
    registry = get_tool_registry()
    tools = registry.list_tools()
    return {
        "count": len(tools),
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "risk": t.risk_level,
            }
            for t in tools
        ],
    }


@app.post("/api/agent/test-llm")
async def test_llm(request: dict):
    """LLM test endpoint — doğrudan LLM çağrısı."""
    from dba_agent.inference import get_llm_client, ModelRouter, TaskType
    
    prompt = request.get("prompt", "Merhaba, sen kimsin?")
    task = request.get("task", "chat")
    
    client = get_llm_client()
    router = ModelRouter()
    
    try:
        task_type = TaskType(task)
    except ValueError:
        task_type = TaskType.CHAT
    
    params = router.get_params(task_type)
    
    response = client.chat(
        prompt=prompt,
        model=params["model"],
        system_prompt="Anomivox DBA Agent'sın. Kısa ve net cevap ver.",
        temperature=params["temperature"],
        max_tokens=params["max_tokens"],
    )
    
    return {
        "model": params["model"],
        "task": task_type.value,
        "response": response,
        "stats": client.stats,
    }


@app.post("/api/agent/sync-config")
async def sync_config():
    """
    UI'dan DB bağlantısı değiştiğinde config'i yeniden yükle.
    db_targets.json dosyasını okuyup DBA Agent config'ini günceller.
    Böylece yeni eklenen DB/SSH bilgileri hemen aktif olur.
    """
    try:
        config = sync_from_json()
        return {
            "status": "ok",
            "db_targets": [t.display_name for t in config.database.targets],
            "ssh_targets": [t.display_name for t in config.ssh.targets],
            "db_count": len(config.database.targets),
            "ssh_count": len(config.ssh.targets),
        }
    except Exception as e:
        logger.error(f"Config sync hatası: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/reload-config")
async def reload_config_endpoint():
    """Config'i tamamen yeniden yükle (env + json)."""
    try:
        config = reload_config()
        return {
            "status": "ok",
            "db_targets": [t.display_name for t in config.database.targets],
            "ssh_targets": [t.display_name for t in config.ssh.targets],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/config-status")
async def config_status():
    """Aktif config durumunu göster — hangi DB'lere bağlı, SSH var mı."""
    config = get_config()
    return {
        "db_targets": [
            {
                "name": t.name,
                "db_type": t.db_type,
                "host": t.host,
                "port": t.port,
                "user": t.user,
                "database": t.database,
                "is_primary": t.is_primary,
                "ssh_enabled": t.ssh_enabled,
                "ssh_host": t.ssh_host if t.ssh_enabled else None,
            }
            for t in config.database.targets
        ],
        "ssh_targets": [
            {
                "name": t.name,
                "host": t.host,
                "user": t.user,
                "port": t.port,
                "role": t.role,
            }
            for t in config.ssh.targets
        ],
        "config_source": "db_targets.json" if config.database.targets and getattr(config.database.targets[0], 'target_id', '') else "env",
    }


def main():
    """Agent'ı başlat."""
    config = get_config()
    logger.info("=" * 60)
    logger.info("  Anomivox DBA Agent v0.2.0 başlatılıyor...")
    logger.info(f"  Dil: {config.agent_language}")
    logger.info(f"  LiteLLM: {config.inference.litellm_base_url}")
    logger.info(f"  Ollama: {config.inference.ollama_base_url}")
    logger.info(f"  DB Targets: {[t.display_name for t in config.database.targets]}")
    logger.info(f"  Auto-diagnose: {config.enable_auto_diagnose}")
    tg_status = "✅ Token var" if config.telegram.bot_token else "❌ Token yok"
    logger.info(f"  Telegram Bot: {tg_status}")
    logger.info("=" * 60)

    uvicorn.run(
        "dba_agent.main:app",
        host="0.0.0.0",
        port=8100,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
