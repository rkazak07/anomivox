"""
Agent Araçları (Faz 2 + Faz 5)
═══════════════════════════════
DB diagnostic, metric, OS tools (SSH), DB action tools.
"""

from dba_agent.tools.registry import ToolRegistry, get_tool_registry
from dba_agent.tools.db_diagnostic import register_db_diagnostic_tools
from dba_agent.tools.metric_tools import register_metric_tools
from dba_agent.tools.os_tools import register_os_tools
from dba_agent.tools.db_action_tools import register_db_action_tools


def register_all_tools() -> ToolRegistry:
    """Tüm araçları kaydet ve registry döndür."""
    registry = get_tool_registry()
    register_db_diagnostic_tools()
    register_metric_tools()
    register_os_tools()
    register_db_action_tools()
    return registry


__all__ = [
    "ToolRegistry",
    "get_tool_registry",
    "register_all_tools",
    "register_db_diagnostic_tools",
    "register_metric_tools",
    "register_os_tools",
    "register_db_action_tools",
]
