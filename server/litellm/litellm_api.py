"""
LiteLLM Proxy Management API — Anomivox WebUI entegrasyonu

LiteLLM proxy üzerinden:
- Model listeleme / ekleme / silme
- Sağlık durumu kontrolü
- Model test (chat completion)
- Config güncelleme (litellm_config.yaml)
"""
import json
import os
import logging
import yaml
import aiohttp
from fastapi import Body
from typing import Optional

logger = logging.getLogger("litellm_api")

# ── LiteLLM Proxy konfigürasyonu ──────────────────────────
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://litellm-proxy:4000")
LITELLM_API_KEY = os.environ.get("LITELLM_MASTER_KEY", os.environ.get("LITELLM_API_KEY", "sk-anomivox-local"))
LITELLM_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "litellm_config.yaml")


def _read_config() -> dict:
    """litellm_config.yaml dosyasını oku"""
    if os.path.exists(LITELLM_CONFIG_PATH):
        try:
            with open(LITELLM_CONFIG_PATH, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"LiteLLM config read error: {e}")
    return {}


def _write_config(config: dict):
    """litellm_config.yaml dosyasını yaz"""
    try:
        with open(LITELLM_CONFIG_PATH, "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("LiteLLM config saved")
    except Exception as e:
        logger.error(f"LiteLLM config write error: {e}")
        raise


# ── Health ────────────────────────────────────────────────
async def litellm_health():
    """LiteLLM Proxy sağlık durumu — /v1/models ile kontrol (daha hızlı)"""
    try:
        async with aiohttp.ClientSession() as session:
            # /v1/models daha güvenilir — /health Ollama timeout yapabiliyor
            async with session.get(
                f"{LITELLM_BASE_URL}/v1/models",
                headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = {}
                    try:
                        data = await resp.json()
                    except Exception:
                        pass
                    model_count = len(data.get("data", []))
                    return {"code": 200, "msg": "LiteLLM Proxy aktif", "data": {
                        "status": "online",
                        "proxy_url": LITELLM_BASE_URL,
                        "model_count": model_count,
                        "details": data,
                    }}
                else:
                    return {"code": 200, "msg": "Proxy erişilemez", "data": {
                        "status": "offline",
                        "proxy_url": LITELLM_BASE_URL,
                        "http_status": resp.status,
                    }}
    except Exception as e:
        return {"code": 200, "msg": f"Proxy bağlantı hatası: {str(e)[:100]}", "data": {
            "status": "offline",
            "proxy_url": LITELLM_BASE_URL,
            "error": str(e)[:200],
        }}


# ── Model Listesi ────────────────────────────────────────
async def litellm_list_models():
    """LiteLLM proxy'de tanımlı modelleri listele (config + runtime)"""
    try:
        config = _read_config()
        config_models = config.get("model_list", [])

        # Proxy'den runtime model listesi al
        runtime_models = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{LITELLM_BASE_URL}/v1/models",
                    headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        runtime_models = [m.get("id", "") for m in data.get("data", [])]
        except Exception as e:
            logger.warning(f"Runtime model list fetch failed: {e}")

        # Config modellerini zenginleştir
        models = []
        for m in config_models:
            model_name = m.get("model_name", "")
            litellm_params = m.get("litellm_params", {})
            model_info = m.get("model_info", {})

            # Ollama model bilgileri
            ollama_params = litellm_params.get("model_kwargs", {})
            base_url = litellm_params.get("api_base", "")

            models.append({
                "model_name": model_name,
                "litellm_model": litellm_params.get("model", ""),
                "api_base": base_url,
                "timeout": litellm_params.get("timeout", 300),
                "num_ctx": ollama_params.get("num_ctx", 0),
                "num_predict": ollama_params.get("num_predict", 0),
                "is_active": model_name in runtime_models or f"ollama/{model_name}" in runtime_models,
                "model_info": model_info,
            })

        return {"code": 200, "msg": "success", "data": {
            "models": models,
            "runtime_models": runtime_models,
            "config_path": LITELLM_CONFIG_PATH,
        }}
    except Exception as e:
        return {"code": 500, "msg": f"Model listesi alınamadı: {str(e)[:200]}", "data": None}


# ── Model Ekleme ─────────────────────────────────────────
async def litellm_add_model(
    model_name: str = Body(..., description="Model adı (ör: llama3.1:8b)"),
    litellm_model: str = Body(..., description="LiteLLM model ID (ör: ollama/llama3.1:8b)"),
    api_base: str = Body("", description="API base URL (ör: http://192.168.1.202:11434)"),
    timeout: int = Body(300, description="Timeout (saniye)"),
    num_ctx: int = Body(2048, description="Context window token sayısı"),
    num_predict: int = Body(256, description="Max output token"),
    role: str = Body("", description="Model rolü: reasoning, sql, triage, fallback"),
    stream_timeout: int = Body(300, description="Stream timeout (saniye)"),
):
    """Yeni model ekle"""
    try:
        config = _read_config()
        model_list = config.setdefault("model_list", [])

        # Aynı isimde model var mı kontrol et
        existing = [i for i, m in enumerate(model_list) if m.get("model_name") == model_name]
        
        new_model = {
            "model_name": model_name,
            "litellm_params": {
                "model": litellm_model,
                "timeout": timeout,
                "stream_timeout": stream_timeout,
                "num_retries": 0,
            },
        }

        # API base varsa ekle
        if api_base:
            new_model["litellm_params"]["api_base"] = api_base

        # Ollama parametreleri
        if litellm_model.startswith("ollama/"):
            new_model["litellm_params"]["model_kwargs"] = {
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            }

        # Role bilgisi varsa model_info'ya ekle
        if role:
            new_model["model_info"] = {"role": role}

        if existing:
            # Güncelle
            model_list[existing[0]] = new_model
            msg = f"Model '{model_name}' güncellendi"
        else:
            # Ekle
            model_list.append(new_model)
            msg = f"Model '{model_name}' eklendi"

        _write_config(config)
        return {"code": 200, "msg": msg, "data": new_model}
    except Exception as e:
        return {"code": 500, "msg": f"Model eklenemedi: {str(e)[:200]}", "data": None}


# ── Model Silme ──────────────────────────────────────────
async def litellm_remove_model(
    model_name: str = Body(..., description="Silinecek model adı"),
):
    """Model sil"""
    try:
        config = _read_config()
        model_list = config.get("model_list", [])
        
        original_count = len(model_list)
        config["model_list"] = [m for m in model_list if m.get("model_name") != model_name]
        
        if len(config["model_list"]) == original_count:
            return {"code": 404, "msg": f"Model '{model_name}' bulunamadı", "data": None}

        _write_config(config)
        return {"code": 200, "msg": f"Model '{model_name}' silindi", "data": None}
    except Exception as e:
        return {"code": 500, "msg": f"Model silinemedi: {str(e)[:200]}", "data": None}


# ── Model Test ───────────────────────────────────────────
async def litellm_test_model(
    model_name: str = Body(..., description="Test edilecek model adı"),
    prompt: str = Body("Merhaba, kısaca kendini tanıt.", description="Test prompt"),
):
    """Model chat completion testi"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 64,
                "temperature": 0.3,
            }
            async with session.post(
                f"{LITELLM_BASE_URL}/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {LITELLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    choice = data.get("choices", [{}])[0]
                    usage = data.get("usage", {})
                    return {"code": 200, "msg": "Test başarılı", "data": {
                        "model": data.get("model", model_name),
                        "response": choice.get("message", {}).get("content", ""),
                        "tokens": usage.get("total_tokens", 0),
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                    }}
                else:
                    error_text = await resp.text()
                    return {"code": resp.status, "msg": f"Model yanıt vermedi: {error_text[:200]}", "data": None}
    except Exception as e:
        return {"code": 500, "msg": f"Test hatası: {str(e)[:200]}", "data": None}


# ── DBA Agent Health ─────────────────────────────────────
async def dba_agent_health():
    """DBA Agent sağlık durumu"""
    dba_url = os.environ.get("DBA_AGENT_URL", "http://dba-agent:8100")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{dba_url}/health",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"code": 200, "msg": "DBA Agent aktif", "data": data}
                else:
                    return {"code": 200, "msg": "DBA Agent erişilemez", "data": {
                        "status": "offline",
                        "http_status": resp.status,
                    }}
    except Exception as e:
        return {"code": 200, "msg": f"DBA Agent bağlantı hatası: {str(e)[:100]}", "data": {
            "status": "offline",
            "error": str(e)[:200],
        }}


# ── Config Getir (tam YAML) ─────────────────────────────
async def litellm_get_config():
    """Tüm LiteLLM config'ini getir"""
    try:
        config = _read_config()
        # API key'leri gizle
        general = config.get("general_settings", {})
        if "master_key" in general:
            general["master_key"] = "***"
        return {"code": 200, "msg": "success", "data": config}
    except Exception as e:
        return {"code": 500, "msg": f"Config okunamadı: {str(e)[:200]}", "data": None}


# ── Genel Ayarlar Güncelle ───────────────────────────────
async def litellm_update_settings(
    request_timeout: int = Body(300, description="Genel request timeout (saniye)"),
    num_retries: int = Body(0, description="Retry sayısı"),
    cache: bool = Body(True, description="Cache aktif mi"),
):
    """LiteLLM genel ayarlarını güncelle"""
    try:
        config = _read_config()

        # litellm_settings güncelle
        settings = config.setdefault("litellm_settings", {})
        settings["request_timeout"] = request_timeout
        settings["num_retries"] = num_retries
        settings["cache"] = cache

        _write_config(config)
        return {"code": 200, "msg": "Ayarlar güncellendi", "data": {
            "request_timeout": request_timeout,
            "num_retries": num_retries,
            "cache": cache,
        }}
    except Exception as e:
        return {"code": 500, "msg": f"Ayarlar güncellenemedi: {str(e)[:200]}", "data": None}
