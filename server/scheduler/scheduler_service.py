"""
Maintenance Scheduler Service
═══════════════════════════════
APScheduler tabanlı zamanlanmış bakım görevi yöneticisi.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("server.scheduler")

_scheduler = None


def get_scheduler():
    """Singleton scheduler instance döndür."""
    global _scheduler
    if _scheduler is None:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


def start_scheduler():
    """Scheduler'ı başlat ve DB'deki aktif görevleri yükle."""
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        logger.info("Maintenance scheduler başlatıldı.")
    _sync_jobs_from_db()


def stop_scheduler():
    """Scheduler'ı durdur."""
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
        logger.info("Maintenance scheduler durduruldu.")


def _sync_jobs_from_db():
    """DB'deki aktif görevleri scheduler'a yükle."""
    try:
        from server.db.repository.scheduler_repository import list_scheduled_tasks
        tasks = list_scheduled_tasks(active_only=True)
        for task in tasks:
            _add_job(task)
        logger.info(f"{len(tasks)} zamanlanmış görev yüklendi.")
    except Exception as e:
        logger.error(f"Scheduler görev yükleme hatası: {e}")


def _add_job(task: dict):
    """Bir görevi APScheduler'a ekle."""
    from apscheduler.triggers.cron import CronTrigger
    sched = get_scheduler()
    job_id = f"task_{task['id']}"
    # Varsa kaldır, yeniden ekle
    if sched.get_job(job_id):
        sched.remove_job(job_id)
    try:
        trigger = CronTrigger.from_crontab(task['cron_expression'])
        sched.add_job(
            _execute_task,
            trigger=trigger,
            id=job_id,
            args=[task['id']],
            replace_existing=True,
            misfire_grace_time=300,
        )
    except Exception as e:
        logger.error(f"Görev {task['id']} eklenemedi: {e}")


def _remove_job(task_id: int):
    sched = get_scheduler()
    job_id = f"task_{task_id}"
    if sched.get_job(job_id):
        sched.remove_job(job_id)


def register_task(task: dict):
    """Yeni görev eklendiğinde çağrılır."""
    if task.get('is_active'):
        _add_job(task)


def unregister_task(task_id: int):
    """Görev silindiğinde/deaktif edildiğinde çağrılır."""
    _remove_job(task_id)


async def _execute_task(task_id: int):
    """Zamanlanmış görevi çalıştır."""
    from server.db.repository.scheduler_repository import get_task_by_id, update_task_run_result
    task = get_task_by_id(task_id)
    if not task or not task.get('is_active'):
        return

    # HIGH risk: bakım penceresi kontrolü
    if task.get('risk_level') == 'HIGH':
        win_start = task.get('maintenance_window_start')
        win_end = task.get('maintenance_window_end')
        if win_start and win_end:
            now_str = datetime.utcnow().strftime('%H:%M')
            if not _in_window(now_str, win_start, win_end):
                logger.info(f"Görev {task_id} bakım penceresi dışında — atlandı.")
                update_task_run_result(task_id, 'skipped', 'Bakım penceresi dışında')
                return

    logger.info(f"Görev çalıştırılıyor: {task['name']} ({task['task_type']})")
    status = 'failed'
    output = ''
    try:
        result = await _run_maintenance(task['task_type'], task['db_target_name'])
        status = 'success' if result.get('success') else 'failed'
        output = result.get('output', '')
        # Audit log
        try:
            from dba_agent.security.audit import AuditLogger
            AuditLogger().log(
                action_type='scheduled_maintenance',
                target=task['db_target_name'],
                command=f"{task['task_type']} — {task['name']}",
                risk_level=task.get('risk_level', 'LOW').lower(),
                result=status,
                metadata={'task_id': task_id},
            )
        except Exception:
            pass
    except Exception as e:
        output = str(e)
        logger.error(f"Görev {task_id} hatası: {e}")
    finally:
        update_task_run_result(task_id, status, output)


async def _run_maintenance(task_type: str, db_target_name: str) -> dict:
    """DBA Agent'a bakım isteği gönder."""
    import aiohttp
    import os
    dba_agent_url = os.environ.get('DBA_AGENT_URL', 'http://localhost:8100')
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{dba_agent_url}/api/maintenance/run",
                json={'task_type': task_type, 'db_target_name': db_target_name},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                data = await resp.json()
                return data
    except Exception as e:
        return {'success': False, 'output': str(e)}


def _in_window(now: str, start: str, end: str) -> bool:
    """Şu anki saat bakım penceresinde mi? HH:MM formatı."""
    return start <= now <= end
