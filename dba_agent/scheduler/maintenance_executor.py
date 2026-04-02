"""
Maintenance Executor
═════════════════════
Zamanlanmış bakım görevlerini DBA Agent tool registry üzerinden çalıştırır.
"""

import logging
from typing import Dict

logger = logging.getLogger("dba_agent.scheduler.maintenance_executor")

TASK_QUERIES = {
    'VACUUM': 'VACUUM ANALYZE;',
    'REINDEX': 'REINDEX DATABASE CONCURRENTLY {db_name};',
    'ANALYZE': 'ANALYZE VERBOSE;',
    'LOG_ROTATE': None,  # OS-level, ayrı işlenir
    'STATS_COLLECT': 'SELECT pg_stat_reset(); ANALYZE;',
}


async def run_maintenance(task_type: str, db_target_name: str) -> Dict:
    """
    Belirtilen görev tipini verilen DB hedefinde çalıştır.

    Returns:
        {'success': bool, 'output': str}
    """
    logger.info(f"Bakım görevi: {task_type} → {db_target_name}")

    try:
        from dba_agent.tools import register_all_tools
        registry = register_all_tools()

        if task_type == 'LOG_ROTATE':
            return await _rotate_logs(db_target_name)

        sql = TASK_QUERIES.get(task_type)
        if not sql:
            return {'success': False, 'output': f'Bilinmeyen görev tipi: {task_type}'}

        # DB bağlantısını kur
        from dba_agent.db import get_db_connection
        conn = get_db_connection(db_target_name)
        if conn is None:
            return {'success': False, 'output': f'DB bağlantısı kurulamadı: {db_target_name}'}

        output_lines = []
        for stmt in sql.split(';'):
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                result = conn.execute(stmt)
                output_lines.append(f"OK: {stmt[:80]}")
            except Exception as e:
                output_lines.append(f"ERR: {stmt[:80]} — {e}")

        conn.close()
        return {'success': True, 'output': '\n'.join(output_lines)}

    except Exception as e:
        logger.error(f"Bakım görevi hatası ({task_type}): {e}", exc_info=True)
        return {'success': False, 'output': str(e)}


async def _rotate_logs(db_target_name: str) -> Dict:
    """PostgreSQL log rotate: pg_rotate_logfile() çağrısı."""
    try:
        from dba_agent.db import get_db_connection
        conn = get_db_connection(db_target_name)
        if conn is None:
            return {'success': False, 'output': f'DB bağlantısı kurulamadı: {db_target_name}'}
        conn.execute('SELECT pg_rotate_logfile()')
        conn.close()
        return {'success': True, 'output': 'Log rotate tamamlandı.'}
    except Exception as e:
        return {'success': False, 'output': str(e)}
