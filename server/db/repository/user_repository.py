import os
import secrets
import bcrypt
from datetime import datetime, timedelta
from server.db.models.user_model import UserModel, TokenModel, PasswordResetTokenModel
from server.db.session import with_session
from typing import Optional, List, Dict

RESET_TOKEN_EXPIRY_MINUTES = 30


def _hash_password(sha256_hex: str) -> str:
    """Hash a SHA-256 hex string with bcrypt for secure storage.

    Client sends SHA-256(plaintext). We bcrypt that to protect against
    DB leaks — the bcrypt hash cannot be replayed directly as a password.
    """
    return bcrypt.hashpw(sha256_hex.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _verify_password(sha256_hex: str, stored_hash: str) -> bool:
    """Verify SHA-256 hex against a bcrypt hash."""
    try:
        return bcrypt.checkpw(sha256_hex.encode('utf-8'), stored_hash.encode('utf-8'))
    except Exception:
        return False


def _is_bcrypt_hash(value: str) -> bool:
    """Return True if value looks like a bcrypt hash."""
    return value.startswith(('$2b$', '$2a$', '$2y$'))


# ── Token expiration (saat) ──────────────────────────────────────────────────
TOKEN_EXPIRY_HOURS = 24


@with_session
def init_admin_user(session):
    """Create default admin user if not exists. Migrates legacy hash if env var is set."""
    import hashlib
    import logging
    logger = logging.getLogger(__name__)
    default_pwd = os.environ.get("ADMIN_DEFAULT_PASSWORD")

    admin = session.query(UserModel).filter_by(username='admin').first()
    if not admin:
        pwd = default_pwd or secrets.token_urlsafe(16)
        sha256_of_pwd = hashlib.sha256(pwd.encode('utf-8')).hexdigest()
        admin = UserModel(
            username='admin',
            password_hash=_hash_password(sha256_of_pwd),
            role='admin',
            is_active=True
        )
        session.add(admin)
        if not default_pwd:
            logger.warning(
                "ADMIN_DEFAULT_PASSWORD env var not set. "
                "Generated random admin password — set it via env var before deploying."
            )
    else:
        if admin.role != 'admin':
            admin.role = 'admin'
        # Migrate: if DB still has a legacy SHA-256 hash and env var is set, update the password
        if default_pwd and not _is_bcrypt_hash(admin.password_hash):
            sha256_of_pwd = hashlib.sha256(default_pwd.encode('utf-8')).hexdigest()
            admin.password_hash = _hash_password(sha256_of_pwd)
            logger.info("Admin password migrated to bcrypt with ADMIN_DEFAULT_PASSWORD.")
    return True


@with_session
def authenticate_user(session, username: str, password: str) -> Optional[Dict]:
    """Authenticate user with username and password.

    Client sends SHA-256(plaintext). Server stores bcrypt(SHA-256(plaintext)).
    Legacy accounts still storing a raw SHA-256 hex are migrated to bcrypt on login.
    """
    user = session.query(UserModel).filter_by(username=username).first()
    if not user:
        return None

    if _is_bcrypt_hash(user.password_hash):
        # Modern path: bcrypt verification
        if not _verify_password(password, user.password_hash):
            return None
    else:
        # Legacy path: raw SHA-256 hex in DB — verify then migrate to bcrypt
        if user.password_hash != password:
            return None
        user.password_hash = _hash_password(password)  # upgrade in-place

    if not user.is_active:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "tenant_id": user.tenant_id,
    }


# ── Token DB operations ─────────────────────────────────────────────────────

@with_session
def save_token(session, token: str, user_id: int) -> None:
    """Persist token to PostgreSQL and write to Redis cache."""
    expires_at = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    t = TokenModel(token=token, user_id=user_id, expires_at=expires_at)
    session.add(t)
    # Flush to get any DB errors before caching
    session.flush()

    user = session.query(UserModel).filter_by(id=user_id).first()
    if user:
        from server.db.redis_client import cache_token
        user_data = {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
            "tenant_id": user.tenant_id,
        }
        cache_token(token, user_data, ttl_seconds=TOKEN_EXPIRY_HOURS * 3600)


@with_session
def get_user_by_token(session, token: str) -> Optional[Dict]:
    """Retrieve user by valid (non-expired) token.

    1. Redis cache'e bak (hızlı yol)
    2. Cache miss ise PostgreSQL'den oku, bulunursa cache'e yaz
    """
    from server.db.redis_client import get_cached_token, cache_token, invalidate_token

    # 1. Redis cache
    cached = get_cached_token(token)
    if cached:
        return cached

    # 2. PostgreSQL fallback
    t = session.query(TokenModel).filter_by(token=token).first()
    if not t:
        return None
    if datetime.utcnow() > t.expires_at:
        session.delete(t)
        invalidate_token(token)
        return None
    user = session.query(UserModel).filter_by(id=t.user_id).first()
    if not user or not user.is_active:
        return None
    user_data = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "tenant_id": user.tenant_id,
    }
    # Cache'e yaz (kalan TTL hesapla)
    remaining = int((t.expires_at - datetime.utcnow()).total_seconds())
    if remaining > 0:
        cache_token(token, user_data, ttl_seconds=remaining)
    return user_data


@with_session
def delete_token(session, token: str) -> None:
    """Remove token from PostgreSQL and Redis (logout)."""
    from server.db.redis_client import invalidate_token
    t = session.query(TokenModel).filter_by(token=token).first()
    if t:
        session.delete(t)
    invalidate_token(token)


@with_session
def cleanup_expired_tokens(session) -> int:
    """Remove all expired tokens from PostgreSQL. Returns count deleted."""
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
    user = UserModel(
        username=username,
        password_hash=_hash_password(password),
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
    tokens = [t.token for t in session.query(TokenModel).filter_by(user_id=user_id).all()]
    session.query(TokenModel).filter_by(user_id=user_id).delete()
    session.delete(user)
    from server.db.redis_client import invalidate_user_tokens
    invalidate_user_tokens(user_id, tokens)
    return {"success": True, "msg": "Kullanici silindi"}


@with_session
def change_user_password(session, user_id: int, new_password: str) -> Dict:
    """Change a user's password (admin action, invalidates all tokens)."""
    user = session.query(UserModel).filter_by(id=user_id).first()
    if not user:
        return {"success": False, "msg": "Kullanici bulunamadi"}
    user.password_hash = _hash_password(new_password)
    tokens = [t.token for t in session.query(TokenModel).filter_by(user_id=user_id).all()]
    session.query(TokenModel).filter_by(user_id=user_id).delete()
    from server.db.redis_client import invalidate_user_tokens
    invalidate_user_tokens(user_id, tokens)
    return {"success": True, "msg": "Sifre basariyla degistirildi"}


@with_session
def change_own_password(session, user_id: int, current_password: str, new_password: str) -> Dict:
    """User changes their own password. Requires current password verification."""
    user = session.query(UserModel).filter_by(id=user_id).first()
    if not user:
        return {"success": False, "msg": "Kullanici bulunamadi"}
    # Mevcut sifre dogrulama
    if _is_bcrypt_hash(user.password_hash):
        if not _verify_password(current_password, user.password_hash):
            return {"success": False, "msg": "Mevcut sifre yanlis"}
    else:
        # Legacy: raw SHA-256 in DB
        if user.password_hash != current_password:
            return {"success": False, "msg": "Mevcut sifre yanlis"}
    user.password_hash = _hash_password(new_password)
    tokens = [t.token for t in session.query(TokenModel).filter_by(user_id=user_id).all()]
    session.query(TokenModel).filter_by(user_id=user_id).delete()
    from server.db.redis_client import invalidate_user_tokens
    invalidate_user_tokens(user_id, tokens)
    return {"success": True, "msg": "Sifre basariyla degistirildi"}
