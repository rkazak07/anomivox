from sqlalchemy import Column, Integer, String, DateTime, JSON, func

from server.db.base import Base


class ChatHistoryModel(Base):
    """
    """
    __tablename__ = 'chat_history'
    id = Column(String(32), primary_key=True, comment='Chat record ID')
    chat_type = Column(String(50), comment='Chat type')
    query = Column(String(4096), comment='User question')
    response = Column(String(4096), comment='Model response')
    meta_data = Column(JSON, default={})
    feedback_score = Column(Integer, default=-1, comment='User rating')
    feedback_reason = Column(String(255), default='', comment='User rating reason')
    create_time = Column(DateTime, default=func.now(), comment='Creation time')

    def __repr__(self):
        return f"<ChatHistory(id='{self.id}', chat_type='{self.chat_type}', query='{self.query}', response='{self.response}',meta_data='{self.meta_data}',feedback_score='{self.feedback_score}',feedback_reason='{self.feedback_reason}', create_time='{self.create_time}')>"
