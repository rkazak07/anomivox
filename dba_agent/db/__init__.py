"""
DB Soyutlama Katmanı
════════════════════
Multi-DB adapter'lar (PostgreSQL, MySQL, vb.)
Mevcut prometheus_service_docker/app.py'deki multi-DB kodundan türetildi.
"""

from dba_agent.db.adapter import DatabaseAdapter, QueryResult, ConnectionInfo
from dba_agent.db.factory import get_adapter, get_all_adapters

__all__ = [
    "DatabaseAdapter", "QueryResult", "ConnectionInfo",
    "get_adapter", "get_all_adapters",
]
