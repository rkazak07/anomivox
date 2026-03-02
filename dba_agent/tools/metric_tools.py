"""
Metric Tools — Prometheus Metrik Araçları
═════════════════════════════════════════
Prometheus'tan metrik sorgulama ve anomali tespiti.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from dba_agent.config import get_config
from dba_agent.tools.registry import ToolDef, get_tool_registry

logger = logging.getLogger("dba_agent.tools.metric_tools")


class PrometheusClient:
    """Prometheus sorgu client'ı."""

    def __init__(self, base_url: Optional[str] = None, timeout: int = 10):
        self.base_url = base_url or get_config().prometheus.url
        self.timeout = timeout

    def query(self, promql: str) -> List[Dict[str, Any]]:
        """Anlık metrik sorgusu."""
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/query",
                params={"query": promql},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "success":
                return []
            return data.get("data", {}).get("result", [])
        except Exception as e:
            logger.error(f"Prometheus query error: {e}")
            return []

    def query_range(
        self, promql: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        step: str = "60s",
    ) -> List[Dict[str, Any]]:
        """Zaman aralığı metrik sorgusu."""
        end = end or datetime.utcnow()
        start = start or (end - timedelta(hours=1))

        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/query_range",
                params={
                    "query": promql,
                    "start": start.isoformat() + "Z",
                    "end": end.isoformat() + "Z",
                    "step": step,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "success":
                return []
            return data.get("data", {}).get("result", [])
        except Exception as e:
            logger.error(f"Prometheus range query error: {e}")
            return []

    def get_alerts(self) -> List[Dict[str, Any]]:
        """Aktif alert'leri getir."""
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/alerts",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            alerts = data.get("data", {}).get("alerts", [])
            return [a for a in alerts if a.get("state") in ("firing", "pending")]
        except Exception as e:
            logger.error(f"Prometheus alerts error: {e}")
            return []


# ─── Prometheus Client Singleton ──────────────
_prom: Optional[PrometheusClient] = None


def _get_prom() -> PrometheusClient:
    global _prom
    if _prom is None:
        _prom = PrometheusClient()
    return _prom


# ─────────────────────────────────────────────
# Tool Fonksiyonları
# ─────────────────────────────────────────────

def get_cpu_usage(duration: str = "5m") -> Dict[str, Any]:
    """CPU kullanım oranı."""
    prom = _get_prom()
    result = prom.query(
        f'100 - (avg(rate(node_cpu_seconds_total{{mode="idle"}}[{duration}])) * 100)'
    )
    value = float(result[0]["value"][1]) if result else -1
    return {
        "cpu_usage_pct": round(value, 1),
        "duration": duration,
        "status": "critical" if value > 90 else "warning" if value > 70 else "normal",
    }


def get_memory_usage() -> Dict[str, Any]:
    """Bellek kullanımı."""
    prom = _get_prom()
    
    total = prom.query("node_memory_MemTotal_bytes")
    available = prom.query("node_memory_MemAvailable_bytes")
    
    total_bytes = float(total[0]["value"][1]) if total else 0
    avail_bytes = float(available[0]["value"][1]) if available else 0
    
    used_pct = ((total_bytes - avail_bytes) / total_bytes * 100) if total_bytes > 0 else -1
    
    return {
        "total_gb": round(total_bytes / (1024**3), 1),
        "available_gb": round(avail_bytes / (1024**3), 1),
        "used_pct": round(used_pct, 1),
        "status": "critical" if used_pct > 90 else "warning" if used_pct > 80 else "normal",
    }


def get_disk_usage() -> Dict[str, Any]:
    """Disk kullanımı."""
    prom = _get_prom()
    result = prom.query(
        '100 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100)'
    )
    value = float(result[0]["value"][1]) if result else -1
    return {
        "disk_usage_pct": round(value, 1),
        "status": "critical" if value > 90 else "warning" if value > 80 else "normal",
    }


def get_io_stats(duration: str = "5m") -> Dict[str, Any]:
    """Disk I/O istatistikleri."""
    prom = _get_prom()
    
    read_rate = prom.query(f'rate(node_disk_read_bytes_total[{duration}])')
    write_rate = prom.query(f'rate(node_disk_written_bytes_total[{duration}])')
    
    total_read = sum(float(r["value"][1]) for r in read_rate) if read_rate else 0
    total_write = sum(float(r["value"][1]) for r in write_rate) if write_rate else 0
    
    return {
        "read_mb_per_sec": round(total_read / (1024**2), 2),
        "write_mb_per_sec": round(total_write / (1024**2), 2),
        "duration": duration,
    }


def get_pg_metrics() -> Dict[str, Any]:
    """PostgreSQL özel metrikleri (pg_exporter üzerinden)."""
    prom = _get_prom()
    
    results: Dict[str, Any] = {}
    
    # Transaction rate
    tps = prom.query('rate(pg_db_xact_commit[5m]) + rate(pg_db_xact_rollback[5m])')
    results["tps"] = round(float(tps[0]["value"][1]), 1) if tps else 0
    
    # Cache hit ratio
    cache = prom.query('pg_db_blks_hit / (pg_db_blks_hit + pg_db_blks_read)')
    results["cache_hit_ratio"] = round(float(cache[0]["value"][1]) * 100, 1) if cache else 0
    
    # Replication lag
    lag = prom.query('pg_replication_lag')
    results["replication_lag_sec"] = round(float(lag[0]["value"][1]), 1) if lag else 0
    
    # Dead tuples
    dead = prom.query('sum(pg_table_n_dead_tup)')
    results["total_dead_tuples"] = int(float(dead[0]["value"][1])) if dead else 0
    
    return results


def get_active_alerts() -> Dict[str, Any]:
    """Aktif Prometheus alert'leri."""
    prom = _get_prom()
    alerts = prom.get_alerts()
    return {
        "count": len(alerts),
        "alerts": [
            {
                "name": a.get("labels", {}).get("alertname", "unknown"),
                "state": a.get("state", ""),
                "severity": a.get("labels", {}).get("severity", ""),
                "summary": a.get("annotations", {}).get("summary", ""),
                "started": a.get("activeAt", ""),
            }
            for a in alerts[:20]
        ],
    }


def get_metric_history(
    metric: str,
    duration: str = "1h",
    step: str = "60s",
) -> Dict[str, Any]:
    """Belirli bir metriğin zaman serisi geçmişi."""
    prom = _get_prom()
    
    # Duration parse
    hours = 1
    if duration.endswith("h"):
        hours = int(duration[:-1])
    elif duration.endswith("m"):
        hours = int(duration[:-1]) / 60
    
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    
    result = prom.query_range(metric, start, end, step)
    
    if not result:
        return {"metric": metric, "values": [], "count": 0}
    
    values = []
    for point in result[0].get("values", []):
        values.append({
            "timestamp": datetime.utcfromtimestamp(point[0]).isoformat(),
            "value": round(float(point[1]), 2),
        })
    
    return {
        "metric": metric,
        "duration": duration,
        "count": len(values),
        "values": values[-60:],  # Son 60 nokta
    }


# ─────────────────────────────────────────────
# Tüm Metric Tool'ları Kaydet
# ─────────────────────────────────────────────

def register_metric_tools() -> None:
    """Tüm metric araçlarını registry'ye ekle."""
    registry = get_tool_registry()

    tools = [
        ToolDef(
            name="get_cpu_usage",
            description="Sunucu CPU kullanım oranı (yüzde)",
            category="metric",
            func=get_cpu_usage,
            args_schema={"duration": "str (varsayılan: 5m)"},
        ),
        ToolDef(
            name="get_memory_usage",
            description="Sunucu bellek (RAM) kullanımı",
            category="metric",
            func=get_memory_usage,
            args_schema={},
        ),
        ToolDef(
            name="get_disk_usage",
            description="Sunucu disk kullanım oranı",
            category="metric",
            func=get_disk_usage,
            args_schema={},
        ),
        ToolDef(
            name="get_io_stats",
            description="Disk I/O okuma/yazma hızları",
            category="metric",
            func=get_io_stats,
            args_schema={"duration": "str (varsayılan: 5m)"},
        ),
        ToolDef(
            name="get_pg_metrics",
            description="PostgreSQL metrikleri (TPS, cache hit, replication lag, dead tuples)",
            category="metric",
            func=get_pg_metrics,
            args_schema={},
        ),
        ToolDef(
            name="get_active_alerts",
            description="Aktif Prometheus alert'leri listesi",
            category="metric",
            func=get_active_alerts,
            args_schema={},
        ),
        ToolDef(
            name="get_metric_history",
            description="Belirli metriğin zaman serisi geçmişi (grafik verisi)",
            category="metric",
            func=get_metric_history,
            args_schema={"metric": "str (PromQL)", "duration": "str (varsayılan: 1h)", "step": "str (varsayılan: 60s)"},
        ),
    ]

    for tool in tools:
        registry.register(tool)

    logger.info(f"Metric tools registered: {len(tools)} tools")
