import uuid
from sqlalchemy import Column, String, Boolean, DateTime, func
from server.db.base import Base


class TenantModel(Base):
    """Tenant (organization) model."""
    __tablename__ = 'tenant'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False, comment='Tenant slug')
    display_name = Column(String(200), nullable=True, comment='Görünen ad')
    is_active = Column(Boolean, default=True)
    create_time = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<Tenant(id='{self.id}', name='{self.name}')>"
