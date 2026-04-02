"""
Scheduler API
═════════════
Zamanlanmış bakım görevleri için CRUD endpoint'leri.
"""

from fastapi import Header
from server.utils import BaseResponse
from server.db.repository.scheduler_repository import (
    list_scheduled_tasks, get_task_by_id, create_scheduled_task,
    update_scheduled_task, delete_scheduled_task,
)
from server.auth.auth_api import _require_admin
from typing import Optional
from pydantic import BaseModel


class TaskCreateBody(BaseModel):
    name: str
    task_type: str
    db_target_name: str
    cron_expression: str
    risk_level: str = 'LOW'
    maintenance_window_start: Optional[str] = None
    maintenance_window_end: Optional[str] = None


class TaskUpdateBody(BaseModel):
    id: int
    name: Optional[str] = None
    task_type: Optional[str] = None
    db_target_name: Optional[str] = None
    cron_expression: Optional[str] = None
    is_active: Optional[bool] = None
    risk_level: Optional[str] = None
    maintenance_window_start: Optional[str] = None
    maintenance_window_end: Optional[str] = None


class TaskDeleteBody(BaseModel):
    id: int


class TaskRunBody(BaseModel):
    id: int


async def api_list_tasks(Authorization: str = Header(None)):
    _, err = _require_admin(Authorization)
    if err:
        return err
    tasks = list_scheduled_tasks()
    return BaseResponse(data=tasks)


async def api_create_task(body: TaskCreateBody, Authorization: str = Header(None)):
    user, err = _require_admin(Authorization)
    if err:
        return err
    task = create_scheduled_task(
        name=body.name,
        task_type=body.task_type,
        db_target_name=body.db_target_name,
        cron_expression=body.cron_expression,
        risk_level=body.risk_level,
        maintenance_window_start=body.maintenance_window_start,
        maintenance_window_end=body.maintenance_window_end,
        created_by=user.get('id'),
    )
    from server.scheduler.scheduler_service import register_task
    register_task(task)
    return BaseResponse(data=task, msg='Görev oluşturuldu.')


async def api_update_task(body: TaskUpdateBody, Authorization: str = Header(None)):
    _, err = _require_admin(Authorization)
    if err:
        return err
    fields = {k: v for k, v in body.dict().items() if k != 'id' and v is not None}
    task = update_scheduled_task(body.id, **fields)
    if not task:
        return BaseResponse(code=404, msg='Görev bulunamadı.')
    from server.scheduler.scheduler_service import register_task, unregister_task
    if task.get('is_active'):
        register_task(task)
    else:
        unregister_task(body.id)
    return BaseResponse(data=task, msg='Görev güncellendi.')


async def api_delete_task(body: TaskDeleteBody, Authorization: str = Header(None)):
    _, err = _require_admin(Authorization)
    if err:
        return err
    ok = delete_scheduled_task(body.id)
    if not ok:
        return BaseResponse(code=404, msg='Görev bulunamadı.')
    from server.scheduler.scheduler_service import unregister_task
    unregister_task(body.id)
    return BaseResponse(msg='Görev silindi.')


async def api_run_task_now(body: TaskRunBody, Authorization: str = Header(None)):
    _, err = _require_admin(Authorization)
    if err:
        return err
    task = get_task_by_id(body.id)
    if not task:
        return BaseResponse(code=404, msg='Görev bulunamadı.')
    import asyncio
    from server.scheduler.scheduler_service import _execute_task
    asyncio.create_task(_execute_task(body.id))
    return BaseResponse(msg='Görev çalıştırılıyor.')
