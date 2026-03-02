"""
Model Router — Görev Tipine Göre Model Seçimi
══════════════════════════════════════════════
Her görev tipi için en uygun modeli seçer.

Kullanım:
    router = ModelRouter()
    model = router.get_model(TaskType.TRIAGE)       # → llama3.2:1b
    model = router.get_model(TaskType.SQL_ANALYSIS)  # → sqlcoder:latest
    model = router.get_model(TaskType.REASONING)     # → llama3.1:8b
"""

import logging
from enum import Enum
from typing import Optional

from dba_agent.config import InferenceConfig, get_config

logger = logging.getLogger("dba_agent.inference.router")


class TaskType(Enum):
    """Agent görev tipleri."""

    # Hızlı sınıflandırma — llama3.2:1b (<1s)
    TRIAGE = "triage"
    CLASSIFICATION = "classification"

    # Genel DBA reasoning — llama3.1:8b (3-8s)
    REASONING = "reasoning"
    DIAGNOSIS = "diagnosis"
    PLANNING = "planning"
    VERIFICATION = "verification"
    REPORT = "report"

    # SQL-özel görevler — sqlcoder (3-8s)
    SQL_ANALYSIS = "sql_analysis"
    SQL_OPTIMIZATION = "sql_optimization"
    INDEX_RECOMMENDATION = "index_recommendation"

    # OS analizi — llama3.1:8b
    OS_ANALYSIS = "os_analysis"
    LOG_ANALYSIS = "log_analysis"

    # Genel sohbet (Telegram interaktif)
    CHAT = "chat"


# Görev → Model mapping
_TASK_MODEL_MAP = {
    # Triage — ultra hızlı, basit sınıflandırma
    TaskType.TRIAGE: "triage_model",
    TaskType.CLASSIFICATION: "triage_model",

    # Reasoning — ana model
    TaskType.REASONING: "reasoning_model",
    TaskType.DIAGNOSIS: "reasoning_model",
    TaskType.PLANNING: "reasoning_model",
    TaskType.VERIFICATION: "reasoning_model",
    TaskType.REPORT: "reasoning_model",
    TaskType.CHAT: "reasoning_model",
    TaskType.OS_ANALYSIS: "reasoning_model",
    TaskType.LOG_ANALYSIS: "reasoning_model",

    # SQL — özelleşmiş model
    TaskType.SQL_ANALYSIS: "sql_model",
    TaskType.SQL_OPTIMIZATION: "sql_model",
    TaskType.INDEX_RECOMMENDATION: "sql_model",
}

# Görev tipine göre max token limitleri
_TASK_TOKEN_LIMITS = {
    TaskType.TRIAGE: 128,
    TaskType.CLASSIFICATION: 128,
    TaskType.REASONING: 512,
    TaskType.DIAGNOSIS: 1024,
    TaskType.PLANNING: 512,
    TaskType.VERIFICATION: 256,
    TaskType.REPORT: 1024,
    TaskType.SQL_ANALYSIS: 512,
    TaskType.SQL_OPTIMIZATION: 512,
    TaskType.INDEX_RECOMMENDATION: 256,
    TaskType.OS_ANALYSIS: 512,
    TaskType.LOG_ANALYSIS: 512,
    TaskType.CHAT: 512,
}

# Görev tipine göre temperature
_TASK_TEMPERATURE = {
    TaskType.TRIAGE: 0.0,           # Deterministik sınıflandırma
    TaskType.CLASSIFICATION: 0.0,
    TaskType.SQL_ANALYSIS: 0.0,     # SQL doğruluğu önemli
    TaskType.SQL_OPTIMIZATION: 0.0,
    TaskType.INDEX_RECOMMENDATION: 0.0,
    TaskType.REASONING: 0.1,        # Hafif yaratıcılık
    TaskType.DIAGNOSIS: 0.1,
    TaskType.PLANNING: 0.1,
    TaskType.VERIFICATION: 0.0,
    TaskType.REPORT: 0.2,
    TaskType.OS_ANALYSIS: 0.1,
    TaskType.LOG_ANALYSIS: 0.1,
    TaskType.CHAT: 0.3,             # Sohbette biraz daha rahat
}


class ModelRouter:
    """
    Görev tipine göre en uygun modeli, token limitini ve
    temperature'ı belirler.
    """

    def __init__(self, config: Optional[InferenceConfig] = None):
        self.config = config or get_config().inference

    def get_model(self, task: TaskType) -> str:
        """Görev tipi için model adı döndürür."""
        attr_name = _TASK_MODEL_MAP.get(task, "reasoning_model")
        model = getattr(self.config, attr_name, self.config.reasoning_model)
        logger.debug(f"Router: task={task.value} → model={model}")
        return model

    def get_max_tokens(self, task: TaskType) -> int:
        """Görev tipi için max output token sayısı."""
        return _TASK_TOKEN_LIMITS.get(task, self.config.max_output_tokens)

    def get_temperature(self, task: TaskType) -> float:
        """Görev tipi için temperature değeri."""
        return _TASK_TEMPERATURE.get(task, self.config.temperature)

    def get_params(self, task: TaskType) -> dict:
        """Görev tipi için tüm LLM parametrelerini döndürür."""
        return {
            "model": self.get_model(task),
            "max_tokens": self.get_max_tokens(task),
            "temperature": self.get_temperature(task),
        }
