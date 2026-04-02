from datetime import datetime
from typing import List, Dict, Optional
from server.db.session import with_session
from server.db.models.scheduler_model import ScheduledTaskModel


def _to_dict(t: ScheduledTaskModel) -> Dict:
    return {
        'id': t.id,
        'name': t.name,
        'task_type': t.task_type,
        'db_target_name': t.db_target_name,
        'cron_expression': t.cron_expression,
        'is_active': t.is_active,
        'risk_level': t.risk_level,
        'maintenance_window_start': t.maintenance_window_start,
        'maintenance_window_end': t.maintenance_window_end,
        'last_run_at': t.last_run_at.isoformat() if t.last_run_at else None,
        'last_run_status': t.last_run_status,
        'last_run_output': t.last_run_output,
        'created_by': t.created_by,
        'create_time': t.create_time.isoformat() if t.create_time else None,
    }


@with_session
def list_scheduled_tasks(session, active_only: bool = False) -> List[Dict]:
    q = session.query(ScheduledTaskModel)
    if active_only:
        q = q.filter_by(is_active=True)
    return [_to_dict(t) for t in q.order_by(ScheduledTaskModel.create_time.desc()).all()]


@with_session
def get_task_by_id(session, task_id: int) -> Optional[Dict]:
    t = session.query(ScheduledTaskModel).filter_by(id=task_id).first()
    return _to_dict(t) if t else None


@with_session
def create_scheduled_task(session, name: str, task_type: str, db_target_name: str,
                           cron_expression: str, risk_level: str = 'LOW',
                           maintenance_window_start: str = None,
                           maintenance_window_end: str = None,
                           created_by: int = None) -> Dict:
    t = ScheduledTaskModel(
        name=name,
        task_type=task_type,
        db_target_name=db_target_name,
        cron_expression=cron_expression,
        risk_level=risk_level,
        maintenance_window_start=maintenance_window_start,
        maintenance_window_end=maintenance_window_end,
        created_by=created_by,
    )
    session.add(t)
    session.flush()
    return _to_dict(t)


@with_session
def update_scheduled_task(session, task_id: int, **fields) -> Optional[Dict]:
    t = session.query(ScheduledTaskModel).filter_by(id=task_id).first()
    if not t:
        return None
    for k, v in fields.items():
        if hasattr(t, k):
            setattr(t, k, v)
    return _to_dict(t)


@with_session
def delete_scheduled_task(session, task_id: int) -> bool:
    t = session.query(ScheduledTaskModel).filter_by(id=task_id).first()
    if not t:
        return False
    session.delete(t)
    return True


@with_session
def update_task_run_result(session, task_id: int, status: str, output: str) -> None:
    t = session.query(ScheduledTaskModel).filter_by(id=task_id).first()
    if t:
        t.last_run_at = datetime.utcnow()
        t.last_run_status = status
        t.last_run_output = output[:4000] if output else ''
