from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from server.db.base import Base


class UserModel(Base):
    """User model for authentication and user management."""
    __tablename__ = 'app_user'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='User ID')
    username = Column(String(50), unique=True, nullable=False, comment='Username')
    password_hash = Column(String(128), nullable=False, comment='Hashed password')
    email = Column(String(255), nullable=True, comment='Email address')
    role = Column(String(20), default='user', nullable=False, comment='Role: admin or user')
    is_active = Column(Boolean, default=True, comment='Active status')
    tenant_id = Column(String(36), nullable=True, index=True, comment='Tenant UUID')
    create_time = Column(DateTime, default=func.now(), comment='Creation time')
    update_time = Column(DateTime, default=func.now(), onupdate=func.now(), comment='Update time')

    # Backward compat
    @property
    def is_admin(self):
        return self.role == 'admin'

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}', is_active={self.is_active})>"


class TokenModel(Base):
    """Persistent token storage with expiration."""
    __tablename__ = 'auth_token'

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)


class PasswordResetTokenModel(Base):
    """One-time password reset tokens sent via email."""
    __tablename__ = 'password_reset_token'

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
