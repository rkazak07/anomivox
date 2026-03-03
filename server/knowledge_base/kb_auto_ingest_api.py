"""
Knowledge Base Auto-Ingest API
================================
FastAPI endpoints for configuring and managing the auto-ingest feature.
"""

from fastapi import Body
from server.utils import BaseResponse
from configs import logger, log_verbose
from configs.kb_auto_ingest_config import (
    get_kb_auto_ingest_config,
    save_kb_auto_ingest_config,
)
from server.knowledge_base.kb_auto_ingest import (
    ingest_from_file,
    get_ingest_stats,
)


def api_get_auto_ingest_config() -> BaseResponse:
    """Return current auto-ingest configuration."""
    try:
        config = get_kb_auto_ingest_config()
        return BaseResponse(code=200, msg="Success", data=config)
    except Exception as e:
        logger.error(f"Error getting auto-ingest config: {e}",
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=str(e))


def api_save_auto_ingest_config(
    enabled: bool = Body(None),
    target_kb_name: str = Body(None),
    embed_model: str = Body(None),
    auto_create_kb: bool = Body(None),
    include_metrics: bool = Body(None),
    include_root_cause: bool = Body(None),
    include_solution: bool = Body(None),
    min_severity: str = Body(None),
    chunk_size: int = Body(None),
    chunk_overlap: int = Body(None),
    max_history_docs: int = Body(None),
) -> BaseResponse:
    """Save auto-ingest configuration."""
    try:
        update = {}
        if enabled is not None:
            update["enabled"] = enabled
        if target_kb_name is not None:
            update["target_kb_name"] = target_kb_name
        if embed_model is not None:
            update["embed_model"] = embed_model
        if auto_create_kb is not None:
            update["auto_create_kb"] = auto_create_kb
        if include_metrics is not None:
            update["include_metrics"] = include_metrics
        if include_root_cause is not None:
            update["include_root_cause"] = include_root_cause
        if include_solution is not None:
            update["include_solution"] = include_solution
        if min_severity is not None:
            update["min_severity"] = min_severity
        if chunk_size is not None:
            update["chunk_size"] = chunk_size
        if chunk_overlap is not None:
            update["chunk_overlap"] = chunk_overlap
        if max_history_docs is not None:
            update["max_history_docs"] = max_history_docs

        config = save_kb_auto_ingest_config(update)
        return BaseResponse(code=200, msg="Auto-ingest configuration saved", data=config)
    except Exception as e:
        logger.error(f"Error saving auto-ingest config: {e}",
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=str(e))


def api_manual_ingest(
    file_path: str = Body(..., description="Path to diagnosis result file"),
) -> BaseResponse:
    """Manually trigger ingestion of a diagnosis file into KB."""
    try:
        result = ingest_from_file(file_path)
        code = 200 if result["success"] else 500
        return BaseResponse(code=code, msg=result["message"])
    except Exception as e:
        logger.error(f"Error during manual ingest: {e}",
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=str(e))


def api_ingest_stats() -> BaseResponse:
    """Return statistics about auto-ingested diagnosis documents."""
    try:
        stats = get_ingest_stats()
        return BaseResponse(code=200, msg="Success", data=stats)
    except Exception as e:
        logger.error(f"Error getting ingest stats: {e}",
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=str(e))
