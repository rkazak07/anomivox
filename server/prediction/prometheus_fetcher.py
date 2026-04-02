"""
Prometheus Fetcher
══════════════════
Prometheus HTTP API'dan zaman serisi metriklerini çeker.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger("server.prediction.prometheus_fetcher")

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")

METRIC_QUERIES = {
    "cpu_usage": '100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
    "connection_count": 'pg_stat_activity_count',
    "query_time_ms": 'pg_stat_statements_mean_time_seconds * 1000',
    "disk_usage_pct": '(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100',
    "memory_usage_pct": '(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100',
}

METRIC_THRESHOLDS = {
    "cpu_usage": 85.0,
    "connection_count": 80.0,   # DB'ye göre değişir; burada % değil mutlak sayı
    "query_time_ms": 1000.0,
    "disk_usage_pct": 85.0,
    "memory_usage_pct": 90.0,
}


async def fetch_metric(metric_name: str, lookback_hours: int = 24, step: str = "5m") -> List[Dict]:
    """
    Prometheus'tan belirtilen metriğin son `lookback_hours` saatlik verisini çek.

    Returns:
        [{'timestamp': float, 'value': float}, ...]
    """
    import aiohttp
    query = METRIC_QUERIES.get(metric_name)
    if not query:
        raise ValueError(f"Bilinmeyen metrik: {metric_name}")

    end = datetime.utcnow()
    start = end - timedelta(hours=lookback_hours)
    params = {
        "query": query,
        "start": start.timestamp(),
        "end": end.timestamp(),
        "step": step,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await resp.json()

    results = data.get("data", {}).get("result", [])
    if not results:
        return []

    # İlk series'i kullan (avg)
    series = results[0].get("values", [])
    return [{"timestamp": float(ts), "value": float(val)} for ts, val in series]


def get_supported_metrics() -> List[Dict]:
    return [
        {"name": k, "threshold": METRIC_THRESHOLDS.get(k)}
        for k in METRIC_QUERIES
    ]
