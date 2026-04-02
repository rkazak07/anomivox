import uuid
from typing import List, Dict, Optional
from server.db.session import with_session
from server.db.models.tenant_model import TenantModel
from server.db.models.user_model import UserModel

DEFAULT_TENANT_ID = '00000000-0000-0000-0000-000000000001'


def _to_dict(t: TenantModel) -> Dict:
    return {
        'id': t.id,
        'name': t.name,
        'display_name': t.display_name,
        'is_active': t.is_active,
        'create_time': t.create_time.isoformat() if t.create_time else None,
    }


@with_session
def list_tenants(session) -> List[Dict]:
    return [_to_dict(t) for t in session.query(TenantModel).order_by(TenantModel.create_time).all()]


@with_session
def get_tenant_by_id(session, tenant_id: str) -> Optional[Dict]:
    t = session.query(TenantModel).filter_by(id=tenant_id).first()
    return _to_dict(t) if t else None


@with_session
def create_tenant(session, name: str, display_name: str = None) -> Dict:
    t = TenantModel(id=str(uuid.uuid4()), name=name, display_name=display_name or name)
    session.add(t)
    session.flush()
    return _to_dict(t)


@with_session
def delete_tenant(session, tenant_id: str) -> bool:
    if tenant_id == DEFAULT_TENANT_ID:
        return False  # Default tenant silinemez
    t = session.query(TenantModel).filter_by(id=tenant_id).first()
    if not t:
        return False
    # Kullanıcıları default tenant'a taşı
    session.query(UserModel).filter_by(tenant_id=tenant_id).update({'tenant_id': DEFAULT_TENANT_ID})
    session.delete(t)
    return True


@with_session
def assign_user_to_tenant(session, user_id: int, tenant_id: str) -> bool:
    user = session.query(UserModel).filter_by(id=user_id).first()
    tenant = session.query(TenantModel).filter_by(id=tenant_id).first()
    if not user or not tenant:
        return False
    user.tenant_id = tenant_id
    return True


@with_session
def list_tenant_users(session, tenant_id: str) -> List[Dict]:
    users = session.query(UserModel).filter_by(tenant_id=tenant_id).all()
    return [{'id': u.id, 'username': u.username, 'role': u.role, 'is_active': u.is_active} for u in users]
