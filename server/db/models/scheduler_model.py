from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, func
from server.db.base import Base


class ScheduledTaskModel(Base):
    """Zamanlanmış bakım görevi."""
    __tablename__ = 'scheduled_task'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment='Görev adı')
    task_type = Column(String(50), nullable=False, comment='VACUUM|REINDEX|ANALYZE|LOG_ROTATE|STATS_COLLECT')
    db_target_name = Column(String(100), nullable=False, comment='DB hedef adı (db_targets.json)')
    cron_expression = Column(String(50), nullable=False, comment='Cron ifadesi, örn: 0 2 * * 0')
    is_active = Column(Boolean, default=True, comment='Aktif mi?')
    risk_level = Column(String(20), default='LOW', comment='LOW|MEDIUM|HIGH')
    maintenance_window_start = Column(String(5), nullable=True, comment='HH:MM — bakım penceresi başlangıcı')
    maintenance_window_end = Column(String(5), nullable=True, comment='HH:MM — bakım penceresi bitişi')
    last_run_at = Column(DateTime, nullable=True, comment='Son çalışma zamanı')
    last_run_status = Column(String(20), nullable=True, comment='success|failed|skipped')
    last_run_output = Column(Text, nullable=True, comment='Son çalışma çıktısı')
    created_by = Column(Integer, nullable=True, comment='Oluşturan kullanıcı ID')
    create_time = Column(DateTime, default=func.now())
    update_time = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ScheduledTask(id={self.id}, name='{self.name}', type='{self.task_type}', cron='{self.cron_expression}')>"
