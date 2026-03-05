import secrets
from fastapi import Body, Header
from typing import Optional
from server.utils import BaseResponse
from server.db.repository.user_repository import (
    authenticate_user,
    list_users,
    create_user,
    toggle_user_active,
    delete_user,
    change_user_password,
    change_own_password,
    save_token,
    get_user_by_token,
    delete_token,
    cleanup_expired_tokens,
)


def _generate_token() -> str:
    return secrets.token_hex(32)


def _get_current_user(authorization: Optional[str] = None):
    """Get current user from Authorization header token (DB-backed)."""
    if not authorization:
        return None
    return get_user_by_token(token=authorization)


def _require_admin(authorization: Optional[str] = None):
    """Check if current user is admin. Returns (user, error_response) tuple."""
    user = _get_current_user(authorization)
    if not user:
        return None, BaseResponse(code=401, msg="Oturum gecersiz veya suresi dolmus", data=None)
    if not user.get("is_admin"):
        return None, BaseResponse(code=403, msg="Yetkiniz yok", data=None)
    return user, None


def _require_auth(authorization: Optional[str] = None):
    """Check if user is authenticated (any role). Returns (user, error_response) tuple."""
    user = _get_current_user(authorization)
    if not user:
        return None, BaseResponse(code=401, msg="Oturum gecersiz veya suresi dolmus", data=None)
    return user, None


async def login(
    username: str = Body(..., description="Username"),
    password: str = Body(..., description="Password"),
):
    """Authenticate user and return token."""
    user = authenticate_user(username=username, password=password)
    if not user:
        return BaseResponse(code=400, msg="Kullanici adi veya sifre hatali", data=None)

    # Cleanup expired tokens periodically
    cleanup_expired_tokens()

    token = _generate_token()
    save_token(token=token, user_id=user["id"])
    return BaseResponse(
        code=200,
        msg="success",
        data={
            "token": token,
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "is_admin": user["is_admin"],
        },
    )


async def logout(
    authorization: Optional[str] = Header(None),
):
    """Logout and invalidate token."""
    if authorization:
        delete_token(token=authorization)
    return BaseResponse(code=200, msg="success")


async def current_user_info(
    authorization: Optional[str] = Header(None),
):
    """Get current user info from token. Used by WebUI to check session."""
    user, err = _require_auth(authorization)
    if err:
        return err
    return BaseResponse(code=200, msg="success", data={
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "is_admin": user["is_admin"],
    })


async def api_list_users(
    authorization: Optional[str] = Header(None),
):
    """List all users (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err
    users = list_users()
    return BaseResponse(code=200, msg="success", data=users)


async def api_create_user(
    username: str = Body(..., description="New username"),
    password: str = Body(..., description="New password"),
    role: str = Body("user", description="Role: admin or user"),
    authorization: Optional[str] = Header(None),
):
    """Create a new user (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err
    result = create_user(username=username, password=password, role=role)
    if result["success"]:
        return BaseResponse(code=200, msg=result["msg"])
    else:
        return BaseResponse(code=400, msg=result["msg"])


async def api_toggle_user(
    user_id: int = Body(..., description="User ID to toggle", embed=True),
    authorization: Optional[str] = Header(None),
):
    """Toggle user active status (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err
    result = toggle_user_active(user_id=user_id)
    if result["success"]:
        return BaseResponse(code=200, msg=result["msg"], data={"is_active": result.get("is_active")})
    else:
        return BaseResponse(code=400, msg=result["msg"])


async def api_delete_user(
    user_id: int = Body(..., description="User ID to delete", embed=True),
    authorization: Optional[str] = Header(None),
):
    """Delete a user (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err
    result = delete_user(user_id=user_id)
    if result["success"]:
        return BaseResponse(code=200, msg=result["msg"])
    else:
        return BaseResponse(code=400, msg=result["msg"])


async def api_change_password(
    user_id: int = Body(..., description="User ID", embed=True),
    new_password: str = Body(..., description="New password", embed=True),
    authorization: Optional[str] = Header(None),
):
    """Change any user's password (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err
    result = change_user_password(user_id=user_id, new_password=new_password)
    if result["success"]:
        return BaseResponse(code=200, msg=result["msg"])
    else:
        return BaseResponse(code=400, msg=result["msg"])


async def api_change_my_password(
    current_password: str = Body(..., description="Current password (SHA-256 hex)"),
    new_password: str = Body(..., description="New password (SHA-256 hex)"),
    authorization: Optional[str] = Header(None),
):
    """User changes their own password. Requires current password verification."""
    user, err = _require_auth(authorization)
    if err:
        return err
    result = change_own_password(
        user_id=user["id"],
        current_password=current_password,
        new_password=new_password,
    )
    if result["success"]:
        return BaseResponse(code=200, msg=result["msg"])
    else:
        return BaseResponse(code=400, msg=result["msg"])
