"""
Knowledge Base Settings API
==============================
FastAPI endpoints for reading/writing KB general settings from the UI.
"""

import threading
from fastapi import Body
from server.utils import BaseResponse
from configs import logger, log_verbose
from configs.kb_settings_config import (
    get_kb_settings_config,
    save_kb_settings_config,
)


def _preload_embedding_model(model_name: str):
    """Download & warm-up an embedding model in a background thread."""
    try:
        logger.info("⬇️  Pre-loading embedding model: %s …", model_name)
        from server.knowledge_base.kb_cache.base import embeddings_pool
        embeddings_pool.load_embeddings(model=model_name)
        logger.info("✅ Embedding model ready: %s", model_name)
    except Exception as exc:
        logger.error("❌ Failed to pre-load embedding model %s: %s",
                     model_name, exc, exc_info=exc if log_verbose else None)


def api_get_kb_settings() -> BaseResponse:
    """Return current KB general settings."""
    try:
        config = get_kb_settings_config()
        return BaseResponse(code=200, msg="Success", data=config)
    except Exception as e:
        logger.error("Error getting KB settings: %s", e,
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=str(e))


def api_save_kb_settings(
    chunk_size: int = Body(None),
    overlap_size: int = Body(None),
    vector_search_top_k: int = Body(None),
    score_threshold: float = Body(None),
    text_splitter_name: str = Body(None),
    default_vs_type: str = Body(None),
    zh_title_enhance: bool = Body(None),
    embedding_model: str = Body(None),
    default_knowledge_base: str = Body(None),
    vs_type_prompt_total_byte_size: int = Body(None),
) -> BaseResponse:
    """Save KB general settings."""
    try:
        update = {}
        if chunk_size is not None:
            update["chunk_size"] = chunk_size
        if overlap_size is not None:
            update["overlap_size"] = overlap_size
        if vector_search_top_k is not None:
            update["vector_search_top_k"] = vector_search_top_k
        if score_threshold is not None:
            update["score_threshold"] = score_threshold
        if text_splitter_name is not None:
            update["text_splitter_name"] = text_splitter_name
        if default_vs_type is not None:
            update["default_vs_type"] = default_vs_type
        if zh_title_enhance is not None:
            update["zh_title_enhance"] = zh_title_enhance
        if embedding_model is not None:
            update["embedding_model"] = embedding_model
        if default_knowledge_base is not None:
            update["default_knowledge_base"] = default_knowledge_base
        if vs_type_prompt_total_byte_size is not None:
            update["vs_type_prompt_total_byte_size"] = vs_type_prompt_total_byte_size

        config = save_kb_settings_config(update)
        logger.info("KB settings saved: %s", update)

        # If the embedding model changed, pre-load it in a background thread
        # so it gets downloaded immediately and is ready for the next query.
        if embedding_model is not None:
            prev = get_kb_settings_config().get("embedding_model")
            # save_kb_settings_config already updated config, check if new
            if config.get("embedding_model") == embedding_model:
                t = threading.Thread(
                    target=_preload_embedding_model,
                    args=(embedding_model,),
                    daemon=True,
                )
                t.start()

        return BaseResponse(code=200, msg="KB settings saved", data=config)
    except Exception as e:
        logger.error("Error saving KB settings: %s", e,
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=str(e))
