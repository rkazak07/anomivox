from server.db.session import with_session
import uuid
from server.db.models.conversation_model import ConversationModel
from server.db.models.message_model import MessageModel
from typing import List, Dict, Optional


@with_session
def add_conversation_to_db(session, chat_type, name="", conversation_id=None, user_id=None):
    """Yeni konuşma oluştur."""
    if not conversation_id:
        conversation_id = uuid.uuid4().hex
    c = ConversationModel(id=conversation_id, chat_type=chat_type, name=name, user_id=user_id)
    session.add(c)
    return c.id


@with_session
def get_conversation_by_id(session, conversation_id: str) -> Optional[Dict]:
    """ID ile konuşma getir."""
    c = session.query(ConversationModel).filter_by(id=conversation_id).first()
    if not c:
        return None
    return {
        "id": c.id,
        "name": c.name,
        "chat_type": c.chat_type,
        "user_id": c.user_id,
        "create_time": str(c.create_time) if c.create_time else None,
    }


@with_session
def rename_conversation(session, conversation_id: str, name: str, user_id: int = None, is_admin: bool = False) -> bool:
    """Konuşmayı yeniden adlandır. Admin tümünü, normal user sadece kendi konuşmasını değiştirebilir."""
    c = session.query(ConversationModel).filter_by(id=conversation_id).first()
    if not c:
        return False
    if not is_admin and c.user_id != user_id:
        return False
    c.name = name
    return True


@with_session
def delete_conversation(session, conversation_id: str, user_id: int = None, is_admin: bool = False) -> bool:
    """Konuşmayı ve mesajlarını sil. Admin tümünü, normal user sadece kendi konuşmasını silebilir."""
    c = session.query(ConversationModel).filter_by(id=conversation_id).first()
    if not c:
        return False
    if not is_admin and c.user_id != user_id:
        return False
    # Mesajları da sil
    session.query(MessageModel).filter_by(conversation_id=conversation_id).delete()
    session.delete(c)
    return True


@with_session
def list_conversations(session, user_id: int = None, is_admin: bool = False, target_user_id: int = None) -> List[Dict]:
    """
    Konuşmaları listele:
    - Admin: tüm kullanıcıların (veya belirli bir kullanıcının) konuşmalarını görür.
    - Normal user: sadece kendi konuşmalarını görür.
    """
    q = session.query(ConversationModel)
    if is_admin:
        if target_user_id is not None:
            q = q.filter_by(user_id=target_user_id)
        # target_user_id yoksa tümünü döner
    else:
        q = q.filter_by(user_id=user_id)
    q = q.order_by(ConversationModel.create_time.desc())
    convs = q.all()
    return [
        {
            "id": c.id,
            "name": c.name or "Yeni Sohbet",
            "chat_type": c.chat_type,
            "user_id": c.user_id,
            "create_time": str(c.create_time) if c.create_time else None,
        }
        for c in convs
    ]


@with_session
def get_conversation_messages(session, conversation_id: str, user_id: int = None, is_admin: bool = False) -> Optional[List[Dict]]:
    """
    Konuşma mesajlarını getir.
    - Admin tüm konuşmaları görebilir.
    - Normal user sadece kendi konuşmasını görebilir.
    """
    c = session.query(ConversationModel).filter_by(id=conversation_id).first()
    if not c:
        return None
    if not is_admin and c.user_id != user_id:
        return None  # Yetkisiz erişim

    messages = (
        session.query(MessageModel)
        .filter_by(conversation_id=conversation_id)
        .order_by(MessageModel.create_time.asc())
        .all()
    )
    return [
        {
            "id": m.id,
            "role": "user",
            "content": m.query,
            "time": str(m.create_time) if m.create_time else None,
        }
        if True else {}
        for m in messages
        # Her mesaj için hem user hem assistant satırı döndür
    ] and _flatten_messages(messages)


def _flatten_messages(messages) -> List[Dict]:
    """Her DB mesajını user + assistant çifti olarak döndür."""
    result = []
    for m in messages:
        result.append({
            "id": m.id + "_q",
            "role": "user",
            "content": m.query or "",
            "time": str(m.create_time) if m.create_time else None,
        })
        if m.response:
            result.append({
                "id": m.id + "_r",
                "role": "assistant",
                "content": m.response or "",
                "time": str(m.create_time) if m.create_time else None,
            })
    return result

