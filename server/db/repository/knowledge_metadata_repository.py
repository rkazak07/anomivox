from server.db.models.knowledge_metadata_model import SummaryChunkModel
from server.db.session import with_session
from typing import List, Dict


@with_session
def list_summary_from_db(session,
                         kb_name: str,
                         metadata: Dict = {},
                         ) -> List[Dict]:
    '''
    List chunk summaries of a knowledge base.
    Return format: [{"id": str, "summary_context": str, "doc_ids": str}, ...]
    '''
    docs = session.query(SummaryChunkModel).filter_by(kb_name=kb_name)

    for k, v in metadata.items():
        docs = docs.filter(SummaryChunkModel.meta_data[k].as_string() == str(v))

    return [{"id": x.id,
             "summary_context": x.summary_context,
             "summary_id": x.summary_id,
             "doc_ids": x.doc_ids,
             "metadata": x.metadata} for x in docs.all()]


@with_session
def delete_summary_from_db(session,
                           kb_name: str
                           ) -> List[Dict]:
    '''
    Delete knowledge base chunk summaries and return the deleted chunk summaries.
    Return format: [{"id": str, "summary_context": str, "doc_ids": str}, ...]
    '''
    docs = list_summary_from_db(kb_name=kb_name)
    query = session.query(SummaryChunkModel).filter_by(kb_name=kb_name)
    query.delete()
    session.commit()
    return docs


@with_session
def add_summary_to_db(session,
                      kb_name: str,
                      summary_infos: List[Dict]):
    '''
    summary_infos format: [{"summary_context": str, "doc_ids": str}, ...]
    '''
    for summary in summary_infos:
        obj = SummaryChunkModel(
            kb_name=kb_name,
            summary_context=summary["summary_context"],
            summary_id=summary["summary_id"],
            doc_ids=summary["doc_ids"],
            meta_data=summary["metadata"],
        )
        session.add(obj)

    session.commit()
    return True


@with_session
def count_summary_from_db(session, kb_name: str) -> int:
    return session.query(SummaryChunkModel).filter_by(kb_name=kb_name).count()
