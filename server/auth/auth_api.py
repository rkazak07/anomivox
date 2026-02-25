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
)

# Simple token store: token -> user_info
_active_tokens = {}


def _generate_token() -> str:
    return secrets.token_hex(32)


def _get_current_user(authorization: Optional[str] = None):
    """Get current user from Authorization header token."""
    if not authorization:
        return None
    return _active_tokens.get(authorization)


def _require_admin(authorization: Optional[str] = None):
    """Check if current user is admin. Returns (user, error_response) tuple."""
    user = _get_current_user(authorization)
    if not user:
        return None, BaseResponse(code=401, msg="Oturum geçersiz", data=None)
    if not user.get("is_admin"):
        return None, BaseResponse(code=403, msg="Yetkiniz yok", data=None)
    return user, None


async def login(
    username: str = Body(..., description="Username"),
    password: str = Body(..., description="Password"),
):
    """Authenticate user and return token."""
    user = authenticate_user(username=username, password=password)
    if not user:
        return BaseResponse(code=400, msg="Kullanıcı adı veya şifre hatalı", data=None)

    token = _generate_token()
    _active_tokens[token] = user
    return BaseResponse(
        code=200,
        msg="success",
        data={
            "token": token,
            "username": user["username"],
            "is_admin": user["is_admin"],
        },
    )


async def logout(
    authorization: Optional[str] = Header(None),
):
    """Logout and invalidate token."""
    if authorization:
        _active_tokens.pop(authorization, None)
    return BaseResponse(code=200, msg="success")


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
    authorization: Optional[str] = Header(None),
):
    """Create a new user (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err
    result = create_user(username=username, password=password)
    if result["success"]:
        return BaseResponse(code=200, msg=result["msg"])
    else:
        return BaseResponse(code=400, msg=result["msg"])


async def api_toggle_user(
    user_id: int = Body(..., description="User ID to toggle"),
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
    user_id: int = Body(..., description="User ID to delete"),
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
    user_id: int = Body(..., description="User ID"),
    new_password: str = Body(..., description="New password"),
    authorization: Optional[str] = Header(None),
):
    """Change user password (admin only)."""
    user, err = _require_admin(authorization)
    if err:
        return err
    result = change_user_password(user_id=user_id, new_password=new_password)
    if result["success"]:
        return BaseResponse(code=200, msg=result["msg"])
    else:
        return BaseResponse(code=400, msg=result["msg"])
