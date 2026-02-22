from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, JSON, func

from server.db.base import Base


class SummaryChunkModel(Base):
    """
    Chunk summary model for storing chunk segments of each doc_id in file_doc.
        User input: User uploads file, can fill in file description, generates doc_id in file_doc, stored in summary_chunk
        Vector store construction: Creates index on summary_context in summary_chunk table, builds vector store, meta_data is vector store metadata (doc_ids)

    """
    __tablename__ = 'summary_chunk'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='ID')
    kb_name = Column(String(50), comment='Knowledge base name')
    summary_context = Column(String(255), comment='Summary text')
    summary_id = Column(String(255), comment='Summary vector ID')
    doc_ids = Column(String(1024), comment='Vector store ID association list')
    meta_data = Column(JSON, default={})

    def __repr__(self):
        return (f"<SummaryChunk(id='{self.id}', kb_name='{self.kb_name}', summary_context='{self.summary_context}',"
                f" doc_ids='{self.doc_ids}', metadata='{self.metadata}')>")
