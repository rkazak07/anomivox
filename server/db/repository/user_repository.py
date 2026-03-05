import hashlib
import secrets
from datetime import datetime, timedelta
from server.db.models.user_model import UserModel, TokenModel, PasswordResetTokenModel
from server.db.session import with_session
from typing import Optional, List, Dict

RESET_TOKEN_EXPIRY_MINUTES = 30


def _hash_password(password: str) -> str:
    """Hash password with SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


# ── Token expiration (saat) ──────────────────────────────────────────────────
TOKEN_EXPIRY_HOURS = 24


@with_session
def init_admin_user(session):
    """Create default admin user if not exists."""
    admin = session.query(UserModel).filter_by(username='admin').first()
    if not admin:
        admin = UserModel(
            username='admin',
            password_hash=_hash_password('Jsue3M6i*42NuNQe9nAosQRFVoxFqMpN1'),
            role='admin',
            is_active=True
        )
        session.add(admin)
    elif admin.role != 'admin':
        admin.role = 'admin'
    return True


@with_session
def authenticate_user(session, username: str, password: str) -> Optional[Dict]:
    """Authenticate user with username and password.

    Password comes pre-hashed (SHA-256 hex) from the client.
    DB stores SHA-256 hex hash, so we compare directly.
    For backward compatibility, also try hashing the input
    in case it's a plain text password.
    """
    user = session.query(UserModel).filter_by(username=username).first()
    if not user:
        return None
    # Client sends SHA-256 hex hash - compare directly
    if user.password_hash != password:
        # Backward compat: maybe it's plain text (old client)
        if user.password_hash != _hash_password(password):
            return None
    if not user.is_active:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_admin": user.is_admin,
        "is_active": user.is_active
    }


# ── Token DB operations ─────────────────────────────────────────────────────

@with_session
def save_token(session, token: str, user_id: int) -> None:
    """Persist token to database with expiration."""
    expires_at = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    t = TokenModel(token=token, user_id=user_id, expires_at=expires_at)
    session.add(t)


@with_session
def get_user_by_token(session, token: str) -> Optional[Dict]:
    """Retrieve user by valid (non-expired) token."""
    t = session.query(TokenModel).filter_by(token=token).first()
    if not t:
        return None
    if datetime.utcnow() > t.expires_at:
        session.delete(t)
        return None
    user = session.query(UserModel).filter_by(id=t.user_id).first()
    if not user or not user.is_active:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_admin": user.is_admin,
        "is_active": user.is_active
    }


@with_session
def delete_token(session, token: str) -> None:
    """Remove token from database (logout)."""
    t = session.query(TokenModel).filter_by(token=token).first()
    if t:
        session.delete(t)


@with_session
def cleanup_expired_tokens(session) -> int:
    """Remove all expired tokens. Returns count deleted."""
    now = datetime.utcnow()
    count = session.query(TokenModel).filter(TokenModel.expires_at < now).delete()
    return count


# ── User CRUD ────────────────────────────────────────────────────────────────

@with_session
def list_users(session) -> List[Dict]:
    """List all users."""
    users = session.query(UserModel).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "create_time": str(u.create_time) if u.create_time else None
        }
        for u in users
    ]


@with_session
def create_user(session, username: str, password: str, role: str = "user", email: str = None) -> Dict:
    """Create a new user."""
    if role not in ("admin", "user"):
        return {"success": False, "msg": "Gecersiz rol. 'admin' veya 'user' olmali"}
    existing = session.query(UserModel).filter_by(username=username).first()
    if existing:
        return {"success": False, "msg": "Bu kullanici adi zaten mevcut"}
    pwd_hash = password if len(password) == 64 else _hash_password(password)
    user = UserModel(
        username=username,
        password_hash=pwd_hash,
        email=email,
        role=role,
        is_active=True
    )
    session.add(user)
    return {"success": True, "msg": "Kullanici basariyla olusturuldu"}


@with_session
def update_user_email(session, user_id: int, email: str) -> Dict:
    """Update a user's email address (admin action)."""
    user = session.query(UserModel).filter_by(id=user_id).first()
    if not user:
        return {"success": False, "msg": "Kullanici bulunamadi"}
    user.email = email
    return {"success": True, "msg": "E-posta guncellendi"}


@with_session
def get_user_by_email(session, email: str) -> Optional[Dict]:
    """Find an active user by email address."""
    user = session.query(UserModel).filter_by(email=email, is_active=True).first()
    if not user:
        return None
    return {"id": user.id, "username": user.username, "email": user.email}


@with_session
def create_reset_token(session, user_id: int) -> str:
    """Create a password reset token (invalidates previous ones)."""
    session.query(PasswordResetTokenModel).filter_by(user_id=user_id).delete()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)
    rt = PasswordResetTokenModel(token=token, user_id=user_id, expires_at=expires_at, used=False)
    session.add(rt)
    return token


@with_session
def consume_reset_token(session, token: str) -> Optional[int]:
    """Validate and consume a reset token. Returns user_id or None."""
    rt = session.query(PasswordResetTokenModel).filter_by(token=token, used=False).first()
    if not rt:
        return None
    if datetime.utcnow() > rt.expires_at:
        session.delete(rt)
        return None
    rt.used = True
    return rt.user_id


@with_session
def toggle_user_active(session, user_id: int) -> Dict:
    """Toggle user active status. Last active admin cannot be deactivated."""
    user = session.query(UserModel).filter_by(id=user_id).first()
    if not user:
        return {"success": False, "msg": "Kullanici bulunamadi"}
    # Son aktif admin devre disi birakilamasin
    if user.role == 'admin' and user.is_active:
        active_admin_count = session.query(UserModel).filter_by(role='admin', is_active=True).count()
        if active_admin_count <= 1:
            return {"success": False, "msg": "Son aktif admin devre disi birakilamaz"}
    user.is_active = not user.is_active
    status = "aktif" if user.is_active else "devre disi"
    return {"success": True, "msg": f"Kullanici {status} edildi", "is_active": user.is_active}


@with_session
def delete_user(session, user_id: int) -> Dict:
    """Delete a user. Last admin cannot be deleted."""
    user = session.query(UserModel).filter_by(id=user_id).first()
    if not user:
        return {"success": False, "msg": "Kullanici bulunamadi"}
    # Son admin silinemez
    if user.role == 'admin':
        admin_count = session.query(UserModel).filter_by(role='admin').count()
        if admin_count <= 1:
            return {"success": False, "msg": "Son admin kullanici silinemez"}
    session.query(TokenModel).filter_by(user_id=user_id).delete()
    session.delete(user)
    return {"success": True, "msg": "Kullanici silindi"}


@with_session
def change_user_password(session, user_id: int, new_password: str) -> Dict:
    """Change a user's password (admin action, invalidates all tokens)."""
    user = session.query(UserModel).filter_by(id=user_id).first()
    if not user:
        return {"success": False, "msg": "Kullanici bulunamadi"}
    pwd_hash = new_password if len(new_password) == 64 else _hash_password(new_password)
    user.password_hash = pwd_hash
    session.query(TokenModel).filter_by(user_id=user_id).delete()
    return {"success": True, "msg": "Sifre basariyla degistirildi"}


@with_session
def change_own_password(session, user_id: int, current_password: str, new_password: str) -> Dict:
    """User changes their own password. Requires current password verification."""
    user = session.query(UserModel).filter_by(id=user_id).first()
    if not user:
        return {"success": False, "msg": "Kullanici bulunamadi"}
    # Mevcut sifre dogrulama
    current_hash = current_password if len(current_password) == 64 else _hash_password(current_password)
    if user.password_hash != current_hash:
        return {"success": False, "msg": "Mevcut sifre yanlis"}
    new_hash = new_password if len(new_password) == 64 else _hash_password(new_password)
    user.password_hash = new_hash
    session.query(TokenModel).filter_by(user_id=user_id).delete()
    return {"success": True, "msg": "Sifre basariyla degistirildi"}
