"""
Database Adapter Factory
════════════════════════
Config'e göre doğru adapter'ı oluşturur.
"""

import logging
from typing import Dict, List, Optional

from dba_agent.config import DatabaseConfig, DatabaseTarget, get_config
from dba_agent.db.adapter import DatabaseAdapter

logger = logging.getLogger("dba_agent.db.factory")

# Desteklenen DB tipleri
_ADAPTER_MAP = {
    "postgresql": "dba_agent.db.postgresql.PostgreSQLAdapter",
    "postgres": "dba_agent.db.postgresql.PostgreSQLAdapter",
    "mysql": "dba_agent.db.mysql.MySQLAdapter",
    "mariadb": "dba_agent.db.mysql.MySQLAdapter",
}


def _import_adapter_class(class_path: str):
    """Dinamik import — lazy loading."""
    module_path, class_name = class_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def create_adapter(target: DatabaseTarget) -> DatabaseAdapter:
    """
    Tek bir DB target için adapter oluştur.
    
    Raises:
        ValueError: Desteklenmeyen DB tipi
    """
    class_path = _ADAPTER_MAP.get(target.db_type.lower())
    if not class_path:
        raise ValueError(
            f"Desteklenmeyen veritabanı tipi: {target.db_type}. "
            f"Desteklenenler: {list(_ADAPTER_MAP.keys())}"
        )

    adapter_class = _import_adapter_class(class_path)
    adapter = adapter_class(target)
    logger.info(f"Created adapter: {adapter}")
    return adapter


def get_adapter(
    name: Optional[str] = None,
    config: Optional[DatabaseConfig] = None,
) -> DatabaseAdapter:
    """
    İsme göre veya varsayılan DB adapter'ı döndürür.
    
    Args:
        name: DB target adı (None → ilk target)
        config: DatabaseConfig (None → global config)
    """
    config = config or get_config().database

    if not config.targets:
        raise ValueError("Hiçbir veritabanı hedefi yapılandırılmamış.")

    if name is None:
        target = config.targets[0]
    else:
        target = next(
            (t for t in config.targets if t.name == name),
            None,
        )
        if target is None:
            available = [t.name for t in config.targets]
            raise ValueError(
                f"DB target '{name}' bulunamadı. Mevcut: {available}"
            )

    return create_adapter(target)


def get_all_adapters(
    config: Optional[DatabaseConfig] = None,
) -> Dict[str, DatabaseAdapter]:
    """Tüm yapılandırılmış DB'ler için adapter döndürür."""
    config = config or get_config().database
    adapters = {}
    for target in config.targets:
        try:
            adapters[target.name] = create_adapter(target)
        except ValueError as e:
            logger.warning(f"Adapter oluşturulamadı ({target.name}): {e}")
    return adapters
