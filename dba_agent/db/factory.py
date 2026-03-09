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
    "oracle": "dba_agent.db.oracle.OracleAdapter",
    "mssql": "dba_agent.db.mssql.MSSQLAdapter",
    "sqlserver": "dba_agent.db.mssql.MSSQLAdapter",
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
    fallback_to_primary: bool = True,
) -> DatabaseAdapter:
    """
    İsme göre veya varsayılan DB adapter'ı döndürür.

    Args:
        name: DB target adı (None → primary/ilk target)
        config: DatabaseConfig (None → global config)
        fallback_to_primary: True ise name bulunamazsa primary'e düşer (uyarı loglar)
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
            if fallback_to_primary:
                logger.warning(
                    f"DB target '{name}' bulunamadı, primary'e fallback yapılıyor. "
                    f"Mevcut: {available}"
                )
                target = config.targets[0]
            else:
                raise ValueError(
                    f"DB target '{name}' bulunamadı. Mevcut: {available}"
                )

    return create_adapter(target)


def resolve_target_name(name: Optional[str]) -> str:
    """
    Aksiyon içindeki target_db adını doğrula ve normalize et.
    Bulunamazsa primary target adını döndürür.

    Args:
        name: action.get("target_db") değeri

    Returns:
        Geçerli DB target adı
    """
    config = get_config().database
    if not config.targets:
        return ""
    if not name:
        return config.targets[0].name
    match = next((t.name for t in config.targets if t.name == name), None)
    if match:
        return match
    logger.warning(f"target_db '{name}' config'de yok, primary kullanılacak.")
    return config.targets[0].name


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
