from fastapi import Body
from configs import logger, log_verbose, LLM_MODELS, HTTPX_DEFAULT_TIMEOUT
from server.utils import (BaseResponse, fschat_controller_address, list_config_llm_models,
                          get_httpx_client, get_model_worker_config)
from typing import List
import os, httpx


def llm_model() -> BaseResponse:
    """Return configured LLM_MODELS + AI-Gateway (LiteLLM) models (prefixed with 'litellm/')."""
    models = list(LLM_MODELS)

    # ── Fetch LiteLLM proxy runtime models ─────────────────
    litellm_base = os.environ.get("LITELLM_BASE_URL", "http://ai-agent-gateway:4000")
    litellm_key = os.environ.get("LITELLM_MASTER_KEY",
                                 os.environ.get("LITELLM_API_KEY", "sk-anomivox-local"))
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(
                f"{litellm_base}/v1/models",
                headers={"Authorization": f"Bearer {litellm_key}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    model_id = m.get("id", "")
                    if model_id:
                        prefixed = f"ai-gw-agent/{model_id}"
                        if prefixed not in models:
                            models.append(prefixed)
    except Exception as e:
        logger.debug(f"LiteLLM model list fetch skipped: {e}")

    return BaseResponse(data=models)
def list_running_models(
    controller_address: str = Body(None, description="FastChat controller server address", examples=[fschat_controller_address()]),
    placeholder: str = Body(None, description="This parameter is unused, placeholder only"),
) -> BaseResponse:
    '''
    Get the list of loaded models and their configuration from FastChat controller
    '''
    try:
        controller_address = controller_address or fschat_controller_address()
        with get_httpx_client() as client:
            r = client.post(controller_address + "/list_models")
            models = r.json()["models"]
            data = {m: get_model_config(m).data for m in models}
            return BaseResponse(data=data)
    except Exception as e:
        logger.error(f'{e.__class__.__name__}: {e}',
                        exc_info=e if log_verbose else None)
        return BaseResponse(
            code=500,
            data={},
            msg=f"failed to get available models from controller: {controller_address}. Hata:  {e}")


def list_config_models(
    types: List[str] = Body(["local", "online"], description="Model configuration type, e.g. local, online, worker"),
    placeholder: str = Body(None, description="Placeholder, no actual effect")
) -> BaseResponse:
    '''
    Get the list of models configured in local configs
    '''
    data = {}
    for type, models in list_config_llm_models().items():
        if type in types:
            data[type] = {m: get_model_config(m).data for m in models}
    return BaseResponse(data=data)


def get_model_config(
    model_name: str = Body(description="LLM model name in configuration"),
    placeholder: str = Body(None, description="Placeholder, no actual effect")
) -> BaseResponse:
    '''
    Get LLM model configuration (merged)
    '''
    config = {}
    for k, v in get_model_worker_config(model_name=model_name).items():
        if not (k == "worker_class"
            or "key" in k.lower()
            or "secret" in k.lower()
            or k.lower().endswith("id")):
            config[k] = v

    return BaseResponse(data=config)


def stop_llm_model(
    model_name: str = Body(..., description="LLM model name to stop", examples=[LLM_MODELS[0]]),
    controller_address: str = Body(None, description="FastChat controller server address", examples=[fschat_controller_address()])
) -> BaseResponse:
    '''
    Request FastChat controller to stop an LLM model.
    Note: Due to FastChat's implementation, this actually stops the model_worker where the LLM model is running.
    '''
    try:
        controller_address = controller_address or fschat_controller_address()
        with get_httpx_client() as client:
            r = client.post(
                controller_address + "/release_worker",
                json={"model_name": model_name},
            )
            return r.json()
    except Exception as e:
        logger.error(f'{e.__class__.__name__}: {e}',
                        exc_info=e if log_verbose else None)
        return BaseResponse(
            code=500,
            msg=f"failed to stop LLM model {model_name} from controller: {controller_address}. Hata:  {e}")


def change_llm_model(
    model_name: str = Body(..., description="Currently running model", examples=[LLM_MODELS[0]]),
    new_model_name: str = Body(..., description="New model to switch to", examples=[LLM_MODELS[0]]),
    controller_address: str = Body(None, description="FastChat controller server address", examples=[fschat_controller_address()])
):
    '''
    Request FastChat controller to switch LLM model.
    '''
    try:
        controller_address = controller_address or fschat_controller_address()
        with get_httpx_client() as client:
            r = client.post(
                controller_address + "/release_worker",
                json={"model_name": model_name, "new_model_name": new_model_name},
                timeout=HTTPX_DEFAULT_TIMEOUT, # wait for new worker_model
            )
            return r.json()
    except Exception as e:
        logger.error(f'{e.__class__.__name__}: {e}',
                        exc_info=e if log_verbose else None)
        return BaseResponse(
            code=500,
            msg=f"failed to switch LLM model from controller: {controller_address}. Hata:  {e}")


def list_search_engines() -> BaseResponse:
    from server.chat.search_engine_chat import SEARCH_ENGINES

    return BaseResponse(data=list(SEARCH_ENGINES))
