"""
Tenant API
══════════
Multi-tenant yönetimi için CRUD endpoint'leri.
"""

from fastapi import Header
from pydantic import BaseModel
from typing import Optional
from server.utils import BaseResponse
from server.auth.auth_api import _require_admin
from server.db.repository.tenant_repository import (
    list_tenants, create_tenant, delete_tenant,
    assign_user_to_tenant, list_tenant_users,
)


class TenantCreateBody(BaseModel):
    name: str
    display_name: Optional[str] = None


class TenantDeleteBody(BaseModel):
    tenant_id: str


class TenantAssignBody(BaseModel):
    user_id: int
    tenant_id: str


async def api_list_tenants(Authorization: str = Header(None)):
    _, err = _require_admin(Authorization)
    if err:
        return err
    return BaseResponse(data=list_tenants())


async def api_create_tenant(body: TenantCreateBody, Authorization: str = Header(None)):
    _, err = _require_admin(Authorization)
    if err:
        return err
    tenant = create_tenant(name=body.name, display_name=body.display_name)
    return BaseResponse(data=tenant, msg='Tenant oluşturuldu.')


async def api_delete_tenant(body: TenantDeleteBody, Authorization: str = Header(None)):
    _, err = _require_admin(Authorization)
    if err:
        return err
    ok = delete_tenant(tenant_id=body.tenant_id)
    if not ok:
        return BaseResponse(code=400, msg='Tenant silinemiyor (bulunamadı veya default tenant).')
    return BaseResponse(msg='Tenant silindi.')


async def api_assign_user_to_tenant(body: TenantAssignBody, Authorization: str = Header(None)):
    _, err = _require_admin(Authorization)
    if err:
        return err
    ok = assign_user_to_tenant(user_id=body.user_id, tenant_id=body.tenant_id)
    if not ok:
        return BaseResponse(code=404, msg='Kullanıcı veya tenant bulunamadı.')
    return BaseResponse(msg='Kullanıcı tenant\'a atandı.')


async def api_list_tenant_users(tenant_id: str, Authorization: str = Header(None)):
    _, err = _require_admin(Authorization)
    if err:
        return err
    users = list_tenant_users(tenant_id=tenant_id)
    return BaseResponse(data=users)
