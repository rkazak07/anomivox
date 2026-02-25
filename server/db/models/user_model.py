from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from server.db.base import Base


class UserModel(Base):
    """User model for authentication and user management."""
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='User ID')
    username = Column(String(50), unique=True, nullable=False, comment='Username')
    password_hash = Column(String(128), nullable=False, comment='Hashed password')
    is_admin = Column(Boolean, default=False, comment='Admin flag')
    is_active = Column(Boolean, default=True, comment='Active status')
    create_time = Column(DateTime, default=func.now(), comment='Creation time')
    update_time = Column(DateTime, default=func.now(), onupdate=func.now(), comment='Update time')

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', is_admin={self.is_admin}, is_active={self.is_active})>"
