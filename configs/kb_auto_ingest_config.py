"""
Knowledge Base Auto-Ingest Configuration
=========================================
Controls automatic ingestion of diagnosis results into Knowledge Base.
"""

import os
import json

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "kb_auto_ingest_config.json")

_DEFAULT_CONFIG = {
    "enabled": False,
    "target_kb_name": "dba_diagnosis_history",
    "embed_model": "m3e-base",
    "auto_create_kb": True,
    "include_metrics": True,
    "include_root_cause": True,
    "include_solution": True,
    "min_severity": "low",         # low, medium, high, critical
    "chunk_size": 500,
    "chunk_overlap": 50,
    "max_history_docs": 1000,      # Max docs to keep (0 = unlimited)
}


def get_kb_auto_ingest_config() -> dict:
    """Load auto-ingest config from JSON file, falling back to defaults."""
    config = dict(_DEFAULT_CONFIG)
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            config.update(saved)
        except Exception:
            pass
    return config


def save_kb_auto_ingest_config(config: dict) -> dict:
    """Persist auto-ingest config to JSON file."""
    current = get_kb_auto_ingest_config()
    current.update(config)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    return current
