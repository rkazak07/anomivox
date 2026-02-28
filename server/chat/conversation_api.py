"""
AI Chat - Conversation yonetimi API'si

Kurallar:
- Normal kullanici: yalnizca kendi konusmalarini gorebilir / adlandirabililir.
  Silme islemi sadece admin yetkisindedir.
- Admin kullanici: tum kullanicilarin konusmalarini gorebilir, adlandirabililir
  ve silebilir. Admin baska kullanicilarin konusmalarini silebilir ama yazamaz.
"""
import logging
from fastapi import Body, Header
from pydantic import BaseModel
from typing import Optional

from server.utils import BaseResponse
from server.auth.auth_api import _get_current_user
from server.db.repository.conversation_repository import (
    add_conversation_to_db,
    get_conversation_by_id,
    list_conversations,
    rename_conversation,
    delete_conversation,
    get_conversation_messages,
)

logger = logging.getLogger("conversation_api")


# -- Pydantic request modelleri -----------------------------------------------
class CreateConversationRequest(BaseModel):
    name: str = "Yeni Sohbet"
    chat_type: str = "llm_chat"


class RenameConversationRequest(BaseModel):
    conversation_id: str
    name: str


class DeleteConversationRequest(BaseModel):
    conversation_id: str


# -- Yardimci -----------------------------------------------------------------
def _auth(authorization: Optional[str]) -> tuple:
    """Token dogrula. (user_dict, error_response) dondurur."""
    user = _get_current_user(authorization)
    if not user:
        return None, BaseResponse(code=401, msg="Oturum gecersiz", data=None)
    return user, None


# -- Konusma olustur ----------------------------------------------------------
async def api_create_conversation(
    body: CreateConversationRequest,
    authorization: Optional[str] = Header(None),
):
    """Yeni konusma baslat. Oturumdaki kullaniciya atanir."""
    user, err = _auth(authorization)
    if err:
        return err
    conv_id = add_conversation_to_db(
        chat_type=body.chat_type,
        name=body.name,
        user_id=user["id"],
    )
    return BaseResponse(code=200, msg="success", data={"conversation_id": conv_id})


# -- Konusma listesi ----------------------------------------------------------
async def api_list_conversations(
    target_user_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
):
    """
    Konusmalari listele.
    - Normal kullanici: kendi konusmalarini gorur.
    - Admin: tum kullanicilari (veya target_user_id ile belirli birini) gorur.
    """
    user, err = _auth(authorization)
    if err:
        return err

    convs = list_conversations(
        user_id=user["id"],
        is_admin=user.get("is_admin", False),
        target_user_id=target_user_id if user.get("is_admin") else None,
    )
    return BaseResponse(code=200, msg="success", data=convs)


# -- Konusma mesajlari --------------------------------------------------------
async def api_conversation_messages(
    conversation_id: str,
    authorization: Optional[str] = Header(None),
):
    """
    Bir konusmanin mesajlarini getir.
    - Normal kullanici: yalnizca kendi konusmasi icin.
    - Admin: herhangi bir konusma icin.
    """
    user, err = _auth(authorization)
    if err:
        return err

    messages = get_conversation_messages(
        conversation_id=conversation_id,
        user_id=user["id"],
        is_admin=user.get("is_admin", False),
    )
    if messages is None:
        return BaseResponse(code=403, msg="Bu konusmaya erisim yetkiniz yok", data=None)
    return BaseResponse(code=200, msg="success", data=messages)


# -- Konusma yeniden adlandir -------------------------------------------------
async def api_rename_conversation(
    body: RenameConversationRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Konusmayi yeniden adlandir.
    - Normal kullanici: sadece kendi konusmasini adlandirabililir.
    - Admin: herhangi bir konusmayi adlandirabililir.
    """
    user, err = _auth(authorization)
    if err:
        return err

    ok = rename_conversation(
        conversation_id=body.conversation_id,
        name=body.name,
        user_id=user["id"],
        is_admin=user.get("is_admin", False),
    )
    if not ok:
        return BaseResponse(code=403, msg="Yetkiniz yok veya konusma bulunamadi", data=None)
    return BaseResponse(code=200, msg="Isim guncellendi")


# -- Konusma sil (SADECE ADMIN) -----------------------------------------------
async def api_delete_conversation(
    body: DeleteConversationRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Konusmayi sil. SADECE admin kullanici silebilir.
    Normal kullanicilar bu islemi yapamazlar.
    """
    user, err = _auth(authorization)
    if err:
        return err

    if not user.get("is_admin", False):
        return BaseResponse(code=403, msg="Konusma silme islemi sadece yonetici yetkisi gerektirir", data=None)

    ok = delete_conversation(
        conversation_id=body.conversation_id,
        user_id=user["id"],
        is_admin=True,
    )
    if not ok:
        return BaseResponse(code=404, msg="Konusma bulunamadi", data=None)
    return BaseResponse(code=200, msg="Konusma silindi")
