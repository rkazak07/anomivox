"""
Knowledge Base Auto-Ingest Service
====================================
Automatically ingests completed diagnosis results into a designated Knowledge Base
so that future diagnoses benefit from historical patterns.
"""

import json
import os
from datetime import datetime
from typing import Optional

from langchain.docstore.document import Document

from configs import logger, log_verbose, EMBEDDING_MODEL, DEFAULT_VS_TYPES
from configs.kb_auto_ingest_config import get_kb_auto_ingest_config
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.knowledge_base.utils import KnowledgeFile, get_doc_path


def _ensure_kb_exists(kb_name: str, embed_model: str):
    """Create KB if it doesn't exist yet."""
    for vs_type in DEFAULT_VS_TYPES:
        kb = KBServiceFactory.get_service_by_name(kb_name, vs_type)
        if kb is None:
            kb = KBServiceFactory.get_service(kb_name, vs_type, embed_model)
            kb.create_kb()


def ingest_diagnosis_to_kb(
    diagnosis_data: dict,
    source_file: str = "",
) -> dict:
    """
    Ingest a single diagnosis result into the configured Knowledge Base.

    Parameters
    ----------
    diagnosis_data : dict
        The full diagnosis JSON object (from diagnose_run_data.jsonl).
    source_file : str
        Original anomaly file name for provenance tracking.

    Returns
    -------
    dict  {"success": bool, "message": str}
    """
    config = get_kb_auto_ingest_config()

    if not config.get("enabled", False):
        return {"success": False, "message": "Auto-ingest is disabled"}

    kb_name = config.get("target_kb_name", "dba_diagnosis_history")
    embed_model = config.get("embed_model", EMBEDDING_MODEL)

    # Ensure KB exists
    if config.get("auto_create_kb", True):
        try:
            _ensure_kb_exists(kb_name, embed_model)
        except Exception as e:
            msg = f"Failed to create KB '{kb_name}': {e}"
            logger.error(msg, exc_info=e if log_verbose else None)
            return {"success": False, "message": msg}

    # Build document content
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    doc_content = _build_document_content(diagnosis_data, config)
    if not doc_content.strip():
        return {"success": False, "message": "No content to ingest"}

    # Build metadata
    metadata = {
        "source": f"diagnosis_{timestamp}.json",
        "original_file": source_file,
        "ingest_time": datetime.now().isoformat(),
        "auto_ingested": True,
    }

    # Extract severity if present
    for key in ("severity", "level", "alert_level"):
        if key in diagnosis_data:
            metadata["severity"] = str(diagnosis_data[key])
            break

    doc = Document(page_content=doc_content, metadata=metadata)

    # Save a physical file so KB file management works correctly
    doc_path = get_doc_path(kb_name)
    os.makedirs(doc_path, exist_ok=True)
    physical_file = os.path.join(doc_path, f"diagnosis_{timestamp}.json")
    with open(physical_file, "w", encoding="utf-8") as f:
        json.dump(diagnosis_data, f, ensure_ascii=False, indent=2)

    # Add to all configured vector stores
    try:
        for vs_type in DEFAULT_VS_TYPES:
            kb = KBServiceFactory.get_service(kb_name, vs_type, embed_model)
            if kb is None:
                continue
            kb_file = KnowledgeFile(
                filename=f"diagnosis_{timestamp}.json",
                knowledge_base_name=kb_name,
            )
            kb.add_doc(kb_file=kb_file, docs=[doc])

        logger.info(f"[KB Auto-Ingest] Successfully ingested diagnosis into '{kb_name}'")
        return {"success": True, "message": f"Diagnosis ingested into KB '{kb_name}'"}
    except Exception as e:
        msg = f"[KB Auto-Ingest] Error ingesting diagnosis: {e}"
        logger.error(msg, exc_info=e if log_verbose else None)
        return {"success": False, "message": msg}


def ingest_from_file(file_path: str) -> dict:
    """
    Read a diagnosis result file and ingest it into KB.
    Supports both .json and .jsonl formats.
    """
    if not os.path.exists(file_path):
        return {"success": False, "message": f"File not found: {file_path}"}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            if file_path.endswith(".jsonl"):
                # JSONL: each line is a JSON object, take the last complete one
                lines = [l.strip() for l in f.readlines() if l.strip()]
                if not lines:
                    return {"success": False, "message": "Empty file"}
                diagnosis_data = json.loads(lines[-1])
            else:
                diagnosis_data = json.load(f)
    except Exception as e:
        return {"success": False, "message": f"Failed to parse file: {e}"}

    return ingest_diagnosis_to_kb(
        diagnosis_data=diagnosis_data,
        source_file=os.path.basename(file_path),
    )


def get_ingest_stats(kb_name: Optional[str] = None) -> dict:
    """
    Return statistics about auto-ingested diagnosis documents.
    """
    config = get_kb_auto_ingest_config()
    kb_name = kb_name or config.get("target_kb_name", "dba_diagnosis_history")

    stats = {
        "kb_name": kb_name,
        "enabled": config.get("enabled", False),
        "doc_count": 0,
        "kb_exists": False,
    }

    for vs_type in DEFAULT_VS_TYPES:
        kb = KBServiceFactory.get_service_by_name(kb_name, vs_type)
        if kb is not None:
            stats["kb_exists"] = True
            stats["doc_count"] = kb.count_files()
            break

    return stats


def _build_document_content(diagnosis_data: dict, config: dict) -> str:
    """Build the text content for the KB document from diagnosis data."""
    parts = []

    # Title / anomaly description
    for key in ("title", "anomaly", "anomaly_description", "alert", "alert_info"):
        if key in diagnosis_data and diagnosis_data[key]:
            parts.append(f"Anomaly: {diagnosis_data[key]}")
            break

    # Root cause
    if config.get("include_root_cause", True):
        for key in ("root_cause", "rootCause", "diagnosis", "analysis"):
            if key in diagnosis_data and diagnosis_data[key]:
                parts.append(f"Root Cause: {diagnosis_data[key]}")
                break

    # Solution
    if config.get("include_solution", True):
        for key in ("solution", "recommendation", "fix", "action"):
            if key in diagnosis_data and diagnosis_data[key]:
                parts.append(f"Solution: {diagnosis_data[key]}")
                break

    # Metrics
    if config.get("include_metrics", True):
        for key in ("metrics", "key_metrics", "metric_data"):
            if key in diagnosis_data and diagnosis_data[key]:
                metrics_str = json.dumps(diagnosis_data[key], ensure_ascii=False)
                parts.append(f"Key Metrics: {metrics_str}")
                break

    # If structured keys not found, dump the whole object
    if not parts:
        parts.append(json.dumps(diagnosis_data, ensure_ascii=False, indent=2))

    return "\n\n".join(parts)
