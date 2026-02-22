import pdb
import urllib
from server.utils import BaseResponse, ListResponse
from server.knowledge_base.utils import validate_kb_name
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.db.repository.knowledge_base_repository import list_kbs_from_db, get_kb_detail
from configs import EMBEDDING_MODEL, logger, log_verbose, DEFAULT_VS_TYPES
from fastapi import Body


def list_kbs():
    # Get List of Knowledge Base
    return BaseResponse(code=200, data=list_kbs_from_db())

def kb_detail(knowledge_base_name: str) -> BaseResponse:
    # Get List of Knowledge Base
    return BaseResponse(
        code=200,
        message="Knowledge base details retrieved successfully",
        data=get_kb_detail(knowledge_base_name))

def create_kb(
        knowledge_base_name: str = Body(..., examples=["samples"]),
        info: str = Body(default=""),
        embed_model: str = Body(EMBEDDING_MODEL),
        ) -> BaseResponse:
    print("====DEFAULT_VS_TYPES===", DEFAULT_VS_TYPES)
    # Create selected knowledge base
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")
    if knowledge_base_name is None or knowledge_base_name.strip() == "":
        return BaseResponse(code=404, msg="Knowledge base name cannot be empty, please re-enter")
    for vs_type in DEFAULT_VS_TYPES:
        kb = KBServiceFactory.get_service_by_name(knowledge_base_name, vs_type)
        if kb is not None:
            continue
        kb = KBServiceFactory.get_service(
            knowledge_base_name, vs_type, embed_model)
        try:
            if info:
                kb.kb_info = info
            kb.create_kb()
        except Exception as e:
            msg = f"Error creating knowledge base: {e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                         exc_info=e if log_verbose else None)
            continue

    return BaseResponse(code=200, msg=f"Knowledge base {knowledge_base_name} added successfully")


def delete_kb(
    knowledge_base_name: str = Body(..., examples=["samples"])
    ) -> BaseResponse:
    # Delete selected knowledge base
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")
    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)

    for vs_type in DEFAULT_VS_TYPES:
        kb = KBServiceFactory.get_service(knowledge_base_name, vs_type)
        if kb is None:
            continue

        try:
            status = kb.clear_vs()
            status = kb.drop_kb()
            if not status:
                return BaseResponse(
                    code=500, msg=f"Failed to delete knowledge base {knowledge_base_name}")
        except Exception as e:
            msg = f"Unexpected error while deleting knowledge base: {e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                         exc_info=e if log_verbose else None)
            return BaseResponse(code=500, msg=msg)

    return BaseResponse(code=200, msg=f"Knowledge base {knowledge_base_name} deleted successfully")
