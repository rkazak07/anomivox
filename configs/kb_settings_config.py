"""
Knowledge Base General Settings (UI-configurable)
===================================================
Manages runtime-overridable KB settings stored as JSON.
Falls back to kb_config.py defaults when no JSON override exists.
"""

import os
import json

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "kb_settings.json")

# Defaults mirror kb_config.py / model_config.py — these are the overridable subset
_DEFAULT_CONFIG = {
    "chunk_size": 500,
    "overlap_size": 50,
    "vector_search_top_k": 3,
    "score_threshold": 2.0,
    "text_splitter_name": "RecursiveCharacterTextSplitter",
    "default_vs_type": "chromadb",
    "zh_title_enhance": False,
    "embedding_model": "all-MiniLM-L6-v2",
    "default_knowledge_base": "samples",
    "vs_type_prompt_total_byte_size": 3000,
}


def get_kb_settings_config() -> dict:
    """Load KB settings from JSON file, falling back to defaults."""
    config = dict(_DEFAULT_CONFIG)
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            config.update(saved)
        except Exception:
            pass
    return config


def save_kb_settings_config(config: dict) -> dict:
    """Persist KB settings to JSON file and hot-reload globals."""
    current = get_kb_settings_config()
    current.update(config)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    _apply_to_globals(current)
    return current


def _apply_to_globals(config: dict):
    """Hot-reload changed values into the running configs module."""
    import configs as configs_pkg
    import configs.kb_config as kb_mod
    import configs.model_config as model_mod
    _kb_map = {
        "chunk_size": "CHUNK_SIZE",
        "overlap_size": "OVERLAP_SIZE",
        "vector_search_top_k": "VECTOR_SEARCH_TOP_K",
        "score_threshold": "SCORE_THRESHOLD",
        "text_splitter_name": "TEXT_SPLITTER_NAME",
        "zh_title_enhance": "ZH_TITLE_ENHANCE",
        "default_knowledge_base": "DEFAULT_KNOWLEDGE_BASE",
        "vs_type_prompt_total_byte_size": "VS_TYPE_PROMPT_TOTAL_BYTE_SIZE",
    }
    for json_key, py_attr in _kb_map.items():
        if json_key in config:
            setattr(kb_mod, py_attr, config[json_key])
            # Also update the top-level configs package so that
            # `from configs import X` picks up the new value.
            setattr(configs_pkg, py_attr, config[json_key])
    # Embedding model lives in model_config
    if "embedding_model" in config:
        old_model = getattr(model_mod, "EMBEDDING_MODEL", None)
        new_model = config["embedding_model"]
        setattr(model_mod, "EMBEDDING_MODEL", new_model)
        setattr(configs_pkg, "EMBEDDING_MODEL", new_model)
        # If embedding model changed, clear the embeddings cache so the new
        # model is downloaded / loaded on the next request.
        if old_model and old_model != new_model:
            try:
                from server.knowledge_base.kb_cache.base import embeddings_pool
                # Remove the old cached embedding from the pool
                old_key = None
                for k in embeddings_pool.keys():
                    if isinstance(k, tuple) and k[0] == old_model:
                        old_key = k
                        break
                if old_key:
                    embeddings_pool.pop(old_key)
                import logging
                logging.getLogger().info(
                    "Embedding model changed: %s -> %s  (cache cleared, "
                    "new model will be downloaded/loaded on next use)",
                    old_model, new_model,
                )
            except Exception as exc:
                import logging
                logging.getLogger().warning(
                    "Could not clear embedding cache after model change: %s", exc
                )


def load_kb_settings_on_startup():
    """Called once at startup to apply any saved JSON overrides."""
    if os.path.exists(_CONFIG_PATH):
        config = get_kb_settings_config()
        _apply_to_globals(config)
