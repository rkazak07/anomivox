"""
LLM Provider Settings (UI-configurable)
=========================================
Manages runtime-overridable LLM provider settings stored as JSON.
Falls back to model_config.py defaults when no JSON override exists.
"""

import os
import json

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "model_settings.json")

# Defaults mirror model_config.py — these are the overridable subset
_DEFAULT_CONFIG = {
    "llm_models": ["groq-api"],
    "temperature": 0.7,
    "max_tokens": None,
    "history_len": 3,
    "online_llm_model": {
        "groq-api": {
            "model_name": "llama-3.3-70b-versatile",
            "api_base_url": "https://api.groq.com/openai/v1",
            "api_key": "",
        },
        "openai-api": {
            "model_name": "gpt-4-0613",
            "api_base_url": "https://api.openai.com/v1",
            "api_key": "",
            "openai_proxy": "",
        },
        "gemini-api": {
            "model_name": "gemini-2.0-flash",
            "api_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key": "",
        },
        "qwen1.5-vllm": {
            "model_name": "Qwen1.5-14B-Chat",
            "api_base_url": "http://127.0.0.1:8000/v1",
            "api_key": "EMPTY",
        },
    },
}

_MASK_PLACEHOLDER = "••••••••"


def _mask_api_keys(config: dict) -> dict:
    """Return a copy of config with api_key values masked."""
    import copy
    masked = copy.deepcopy(config)
    for provider in masked.get("online_llm_model", {}).values():
        key = provider.get("api_key", "")
        if key and key not in ("", "EMPTY"):
            provider["api_key"] = _MASK_PLACEHOLDER
    return masked


def get_model_settings_config(masked: bool = False) -> dict:
    """Load LLM settings from JSON file, falling back to defaults."""
    # Start from model_config.py current values as defaults
    try:
        from configs import model_config as mc
        defaults = dict(_DEFAULT_CONFIG)
        defaults["llm_models"] = list(getattr(mc, "LLM_MODELS", _DEFAULT_CONFIG["llm_models"]))
        defaults["temperature"] = getattr(mc, "TEMPERATURE", _DEFAULT_CONFIG["temperature"])
        defaults["max_tokens"] = getattr(mc, "MAX_TOKENS", _DEFAULT_CONFIG["max_tokens"])
        defaults["history_len"] = getattr(mc, "HISTORY_LEN", _DEFAULT_CONFIG["history_len"])
        online = getattr(mc, "ONLINE_LLM_MODEL", {})
        for pname, pdata in online.items():
            if pname in defaults["online_llm_model"]:
                defaults["online_llm_model"][pname].update(pdata)
            else:
                defaults["online_llm_model"][pname] = dict(pdata)
    except Exception:
        defaults = dict(_DEFAULT_CONFIG)

    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Merge provider data carefully (preserve defaults for missing providers)
            saved_providers = saved.pop("online_llm_model", {})
            defaults.update(saved)
            for pname, pdata in saved_providers.items():
                if pname in defaults["online_llm_model"]:
                    defaults["online_llm_model"][pname].update(pdata)
                else:
                    defaults["online_llm_model"][pname] = pdata
        except Exception:
            pass

    if masked:
        return _mask_api_keys(defaults)
    return defaults


def save_model_settings_config(config: dict) -> dict:
    """Persist LLM settings to JSON file and hot-reload model_config globals."""
    current = get_model_settings_config(masked=False)

    # Merge provider updates: preserve existing api_key if new value is masked/empty
    incoming_providers = config.pop("online_llm_model", None) or {}
    current_providers = current.get("online_llm_model", {})
    for pname, pdata in incoming_providers.items():
        if pname not in current_providers:
            current_providers[pname] = {}
        for k, v in pdata.items():
            if k == "api_key" and v in ("", _MASK_PLACEHOLDER):
                pass  # keep existing key
            else:
                current_providers[pname][k] = v
    current.update(config)
    current["online_llm_model"] = current_providers

    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)

    _apply_to_globals(current)
    return _mask_api_keys(current)


def _apply_to_globals(config: dict):
    """Hot-reload changed values into the running model_config module."""
    try:
        import configs as configs_pkg
        import configs.model_config as mc

        if "llm_models" in config:
            setattr(mc, "LLM_MODELS", config["llm_models"])
            setattr(configs_pkg, "LLM_MODELS", config["llm_models"])

        if "temperature" in config:
            setattr(mc, "TEMPERATURE", config["temperature"])
            setattr(configs_pkg, "TEMPERATURE", config["temperature"])

        if "max_tokens" in config:
            setattr(mc, "MAX_TOKENS", config["max_tokens"])
            setattr(configs_pkg, "MAX_TOKENS", config["max_tokens"])

        if "history_len" in config:
            setattr(mc, "HISTORY_LEN", config["history_len"])
            setattr(configs_pkg, "HISTORY_LEN", config["history_len"])

        if "online_llm_model" in config:
            current_online = getattr(mc, "ONLINE_LLM_MODEL", {})
            for pname, pdata in config["online_llm_model"].items():
                if pname in current_online:
                    current_online[pname].update(pdata)
                else:
                    current_online[pname] = pdata
            setattr(mc, "ONLINE_LLM_MODEL", current_online)
            setattr(configs_pkg, "ONLINE_LLM_MODEL", current_online)
    except Exception:
        pass


def load_model_settings_on_startup():
    """Called once at startup to apply any saved JSON overrides."""
    if os.path.exists(_CONFIG_PATH):
        config = get_model_settings_config(masked=False)
        _apply_to_globals(config)
