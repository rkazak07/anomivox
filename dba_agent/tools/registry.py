"""
Tool Registry — Agent Araç Kayıt Sistemi
═════════════════════════════════════════
Tüm agent araçlarını merkezi olarak yönetir.
Semantic tool matching (Faz 4) için genişletilebilir.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("dba_agent.tools.registry")


@dataclass
class ToolDef:
    """Araç tanımı."""
    name: str
    description: str
    category: str  # db_diagnostic, metric, index, query, os
    func: Callable
    args_schema: Dict[str, str] = field(default_factory=dict)
    risk_level: str = "safe"  # safe, low, medium, high, forbidden
    requires_db: bool = False
    requires_ssh: bool = False

    @property
    def summary(self) -> str:
        """Tek satır özet (prompt'a eklenecek)."""
        args_str = ", ".join(f"{k}: {v}" for k, v in self.args_schema.items())
        return f"- {self.name}({args_str}): {self.description} [risk: {self.risk_level}]"


class ToolRegistry:
    """
    Merkezi araç kayıt defteri.
    
    Kullanım:
        registry = ToolRegistry()
        registry.register(ToolDef(name="get_health", ...))
        tool = registry.get("get_health")
        result = await registry.execute("get_health", db_name="anomivox")
    """

    def __init__(self):
        self._tools: Dict[str, ToolDef] = {}

    def register(self, tool: ToolDef) -> None:
        """Araç kaydet."""
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' zaten kayıtlı, üzerine yazılıyor")
        self._tools[tool.name] = tool
        logger.debug(f"Tool registered: {tool.name} [{tool.category}]")

    def get(self, name: str) -> Optional[ToolDef]:
        """İsme göre araç getir."""
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[ToolDef]:
        """Araçları listele (opsiyonel kategori filtresi)."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def get_tool_descriptions(self, category: Optional[str] = None,
                               max_risk: str = "high") -> str:
        """
        LLM prompt'una eklenecek araç açıklamaları.
        
        Args:
            category: Filtre (None = hepsi)
            max_risk: Maksimum risk seviyesi (forbidden hariç)
        """
        risk_order = ["safe", "low", "medium", "high", "forbidden"]
        max_idx = risk_order.index(max_risk)
        
        tools = self.list_tools(category)
        tools = [t for t in tools if risk_order.index(t.risk_level) <= max_idx]
        
        if not tools:
            return "Kullanılabilir araç yok."
        
        by_category: Dict[str, List[ToolDef]] = {}
        for t in tools:
            by_category.setdefault(t.category, []).append(t)
        
        lines = []
        for cat, cat_tools in sorted(by_category.items()):
            lines.append(f"\n[{cat}]")
            for t in cat_tools:
                lines.append(t.summary)
        
        return "\n".join(lines)

    async def execute(self, name: str, **kwargs) -> Dict[str, Any]:
        """
        Aracı çalıştır.
        
        Returns:
            {"success": bool, "result": Any, "error": str|None}
        """
        tool = self.get(name)
        if not tool:
            return {"success": False, "result": None, "error": f"Tool '{name}' bulunamadı"}
        
        try:
            import asyncio
            import inspect
            
            if inspect.iscoroutinefunction(tool.func):
                result = await tool.func(**kwargs)
            else:
                # Sync fonksiyonu thread pool'da çalıştır
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: tool.func(**kwargs))
            
            logger.info(f"Tool executed: {name} → success")
            return {"success": True, "result": result, "error": None}
            
        except Exception as e:
            logger.error(f"Tool execution failed: {name} → {e}")
            return {"success": False, "result": None, "error": str(e)}

    @property
    def count(self) -> int:
        return len(self._tools)


# ─── Global Registry Singleton ────────────────
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Global tool registry singleton."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
