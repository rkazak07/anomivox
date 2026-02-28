import hashlib
from server.db.models.user_model import UserModel
from server.db.session import with_session
from typing import Optional, List, Dict


def _hash_password(password: str) -> str:
    """Hash password with SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


@with_session
def init_admin_user(session):
    """Create default admin user if not exists."""
    admin = session.query(UserModel).filter_by(username='admin').first()
    if not admin:
        admin = UserModel(
            username='admin',
            password_hash=_hash_password('Jsue3M6i*42NuNQe9nAosQRFVoxFqMpN1'),
            is_admin=True,
            is_active=True
        )
        session.add(admin)
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
    # Client sends SHA-256 hex hash — compare directly
    if user.password_hash != password:
        # Backward compat: maybe it's plain text (old client)
        if user.password_hash != _hash_password(password):
            return None
    if not user.is_active:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "is_active": user.is_active
    }


@with_session
def list_users(session) -> List[Dict]:
    """List all users."""
    users = session.query(UserModel).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "create_time": str(u.create_time) if u.create_time else None
        }
        for u in users
    ]


@with_session
def create_user(session, username: str, password: str) -> Dict:
    """Create a new user.
    
    Password comes pre-hashed (SHA-256 hex) from the client.
    Store directly as password_hash.
    """
    existing = session.query(UserModel).filter_by(username=username).first()
    if existing:
        return {"success": False, "msg": "Bu kullanıcı adı zaten mevcut"}
    # Client already sends SHA-256 hex — store directly
    # If it looks like a hex hash (64 chars), use as-is; otherwise hash it
    pwd_hash = password if len(password) == 64 else _hash_password(password)
    user = UserModel(
        username=username,
        password_hash=pwd_hash,
        is_admin=False,
        is_active=True
    )
    session.add(user)
    return {"success": True, "msg": "Kullanıcı başarıyla oluşturuldu"}


@with_session
def toggle_user_active(session, user_id: int) -> Dict:
    """Toggle user active status."""
    user = session.query(UserModel).filter_by(id=user_id).first()
    if not user:
        return {"success": False, "msg": "Kullanıcı bulunamadı"}
    if user.is_admin:
        return {"success": False, "msg": "Admin kullanıcısı devre dışı bırakılamaz"}
    user.is_active = not user.is_active
    status = "aktif" if user.is_active else "devre dışı"
    return {"success": True, "msg": f"Kullanıcı {status} edildi", "is_active": user.is_active}


@with_session
def delete_user(session, user_id: int) -> Dict:
    """Delete a user."""
    user = session.query(UserModel).filter_by(id=user_id).first()
    if not user:
        return {"success": False, "msg": "Kullanıcı bulunamadı"}
    if user.is_admin:
        return {"success": False, "msg": "Admin kullanıcısı silinemez"}
    session.delete(user)
    return {"success": True, "msg": "Kullanıcı silindi"}


@with_session
def change_user_password(session, user_id: int, new_password: str) -> Dict:
    """Change a user's password.
    
    Password comes pre-hashed (SHA-256 hex) from the client.
    """
    user = session.query(UserModel).filter_by(id=user_id).first()
    if not user:
        return {"success": False, "msg": "Kullanıcı bulunamadı"}
    # Client already sends SHA-256 hex — store directly
    pwd_hash = new_password if len(new_password) == 64 else _hash_password(new_password)
    user.password_hash = pwd_hash
    return {"success": True, "msg": "Şifre başarıyla değiştirildi"}
