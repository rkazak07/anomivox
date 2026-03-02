"""
Agent Araçları (Faz 2)
══════════════════════
DB diagnostic, metric, index advisor, query advisor, OS tools.
"""

from dba_agent.tools.registry import ToolRegistry, get_tool_registry
from dba_agent.tools.db_diagnostic import register_db_diagnostic_tools
from dba_agent.tools.metric_tools import register_metric_tools


def register_all_tools() -> ToolRegistry:
    """Tüm araçları kaydet ve registry döndür."""
    registry = get_tool_registry()
    register_db_diagnostic_tools()
    register_metric_tools()
    # Faz 5: register_os_tools()
    return registry


__all__ = [
    "ToolRegistry",
    "get_tool_registry",
    "register_all_tools",
    "register_db_diagnostic_tools",
    "register_metric_tools",
]
