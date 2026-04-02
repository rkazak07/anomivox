"""
LLM Provider Config API
=========================
FastAPI endpoints for reading/writing LLM provider settings from the UI.
"""

from fastapi import Body
from server.utils import BaseResponse
from configs import logger, log_verbose
from configs.model_settings_config import (
    get_model_settings_config,
    save_model_settings_config,
)


def api_get_llm_config() -> BaseResponse:
    """Return current LLM provider settings (api_keys masked)."""
    try:
        config = get_model_settings_config(masked=True)
        return BaseResponse(code=200, msg="Success", data=config)
    except Exception as e:
        logger.error("Error getting LLM config: %s", e,
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=str(e))


def api_save_llm_config(
    llm_models: list = Body(None),
    temperature: float = Body(None),
    max_tokens: int = Body(None),
    history_len: int = Body(None),
    online_llm_model: dict = Body(None),
) -> BaseResponse:
    """Save LLM provider settings. Empty/masked api_key values are preserved."""
    try:
        update = {}
        if llm_models is not None:
            update["llm_models"] = llm_models
        if temperature is not None:
            update["temperature"] = temperature
        if max_tokens is not None:
            update["max_tokens"] = max_tokens
        if history_len is not None:
            update["history_len"] = history_len
        if online_llm_model is not None:
            update["online_llm_model"] = online_llm_model

        config = save_model_settings_config(update)
        logger.info("LLM config saved: %s", {k: v for k, v in update.items() if k != "online_llm_model"})
        return BaseResponse(code=200, msg="LLM config saved", data=config)
    except Exception as e:
        logger.error("Error saving LLM config: %s", e,
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=str(e))
