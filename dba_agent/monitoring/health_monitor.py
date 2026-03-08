"""
Proaktif Sağlık İzleyici
════════════════════════
Arka planda periyodik olarak tüm DB target'larını kontrol eder.
Anormal durum tespit edilince Telegram'a otomatik bildirim gönderir.

İzlenen metrikler:
- Uzun süren sorgular (>30s)
- Engellenmiş kilitler
- Bağlantı kullanım oranı (>85%)
- Cache hit ratio (<85%)
- Replikasyon gecikmesi (>30s)
- CPU kullanımı (>90%)
- Bellek kullanımı (>90%)
- Disk doluluk (>90%)
- Sağlık skoru (<60)
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("dba_agent.monitoring")


# ─────────────────────────────────────────────
# Eşik değerleri
# ─────────────────────────────────────────────

@dataclass
class MonitorThresholds:
    """İzleme eşik değerleri — ENV'den okunur."""
    long_query_sec: float = float(os.getenv("MON_LONG_QUERY_SEC", "30"))
    blocked_lock_count: int = int(os.getenv("MON_BLOCKED_LOCKS", "1"))
    connection_usage_pct: float = float(os.getenv("MON_CONN_USAGE_PCT", "85"))
    cache_hit_min_pct: float = float(os.getenv("MON_CACHE_HIT_MIN", "85"))
    replication_lag_sec: float = float(os.getenv("MON_REPL_LAG_SEC", "30"))
    cpu_usage_pct: float = float(os.getenv("MON_CPU_PCT", "90"))
    memory_usage_pct: float = float(os.getenv("MON_MEM_PCT", "90"))
    disk_usage_pct: float = float(os.getenv("MON_DISK_PCT", "90"))
    health_score_min: int = int(os.getenv("MON_HEALTH_SCORE_MIN", "60"))
    check_interval_sec: int = int(os.getenv("MON_CHECK_INTERVAL", "60"))
    # Aynı alarm için tekrar bildirim süresi (saniye)
    alert_cooldown_sec: int = int(os.getenv("MON_ALERT_COOLDOWN", "300"))


@dataclass
class MonitorAlert:
    """Tespit edilen anomali."""
    target_name: str
    alert_type: str         # "long_query", "blocked_lock", "high_conn", ...
    severity: str           # "critical", "warning"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def alert_key(self) -> str:
        """Cooldown kontrolü için benzersiz anahtar."""
        return f"{self.target_name}:{self.alert_type}"


# ─────────────────────────────────────────────
# Ana İzleyici
# ─────────────────────────────────────────────

class HealthMonitor:
    """
    Arka planda asyncio görevi olarak çalışır.
    Her check_interval_sec saniyede bir tüm DB target'larını kontrol eder.
    """

    def __init__(self):
        self.thresholds = MonitorThresholds()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        # alert_key → son bildirim timestamp
        self._alert_sent_at: Dict[str, float] = {}
        # Kaç kontrol yapıldı
        self._check_count = 0
        # Kaç alert gönderildi
        self._alert_count = 0

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """İzleme döngüsünü başlat."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(), name="health_monitor")
        logger.info(
            f"Proaktif izleme başlatıldı — interval: {self.thresholds.check_interval_sec}s"
        )

    async def stop(self) -> None:
        """İzleme döngüsünü durdur."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Proaktif izleme durduruldu")

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "check_count": self._check_count,
            "alert_count": self._alert_count,
            "check_interval_sec": self.thresholds.check_interval_sec,
            "active_cooldowns": len(self._alert_sent_at),
        }

    # ─── İzleme Döngüsü ──────────────────────

    async def _monitor_loop(self) -> None:
        """Ana döngü — her interval'da check_all_targets çağırır."""
        # İlk başlangıçta 10s bekle (sistem ayağa kalksın)
        await asyncio.sleep(10)

        while self._running:
            try:
                await self._check_all_targets()
            except Exception as e:
                logger.error(f"İzleme döngüsü hatası: {e}", exc_info=True)

            await asyncio.sleep(self.thresholds.check_interval_sec)

    async def _check_all_targets(self) -> None:
        """Tüm DB target'larını paralel kontrol et."""
        from dba_agent.config import get_config
        config = get_config()
        targets = config.database.targets

        if not targets:
            return

        self._check_count += 1
        tasks = [self._check_target(target) for target in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        alerts: List[MonitorAlert] = []
        for res in results:
            if isinstance(res, Exception):
                logger.debug(f"Target kontrol hatası: {res}")
            elif isinstance(res, list):
                alerts.extend(res)

        for alert in alerts:
            await self._maybe_send_alert(alert)

    async def _check_target(self, target) -> List[MonitorAlert]:
        """Tek bir DB target'ı kontrol et, anomali listesi döndür."""
        alerts: List[MonitorAlert] = []

        try:
            from dba_agent.db import get_adapter
            adapter = get_adapter(target)
            adapter.connect()

            try:
                # 1. Genel sağlık
                health = adapter.get_health()
                health_alerts = self._check_health(target.name, health)
                alerts.extend(health_alerts)

                # 2. Uzun süren sorgular
                long_q_alerts = await self._check_long_queries(target.name, adapter)
                alerts.extend(long_q_alerts)

                # 3. Kilitler
                lock_alerts = await self._check_locks(target.name, adapter)
                alerts.extend(lock_alerts)

            finally:
                adapter.disconnect()

        except Exception as e:
            logger.debug(f"Target bağlantı hatası ({target.name}): {e}")
            # Bağlantı hatası — eğer daha önce çalışıyorduysa uyar
            if self._check_count > 3:
                alerts.append(MonitorAlert(
                    target_name=target.name,
                    alert_type="connection_error",
                    severity="critical",
                    message=f"Veritabanına bağlanılamıyor: {str(e)[:100]}",
                ))

        return alerts

    def _check_health(self, target_name: str, health) -> List[MonitorAlert]:
        """DatabaseHealth nesnesinden anomali çıkar."""
        alerts = []
        thr = self.thresholds

        # Sağlık skoru
        if health.health_score < thr.health_score_min:
            severity = "critical" if health.health_score < 40 else "warning"
            alerts.append(MonitorAlert(
                target_name=target_name,
                alert_type="low_health_score",
                severity=severity,
                message=f"Sağlık skoru düşük: {health.health_score}/100",
                details={"score": health.health_score},
            ))

        # Bağlantı kullanımı
        if health.max_connections > 0:
            conn_pct = (health.active_connections / health.max_connections) * 100
            if conn_pct >= thr.connection_usage_pct:
                severity = "critical" if conn_pct >= 95 else "warning"
                alerts.append(MonitorAlert(
                    target_name=target_name,
                    alert_type="high_connections",
                    severity=severity,
                    message=(
                        f"Bağlantı kullanımı yüksek: "
                        f"{health.active_connections}/{health.max_connections} (%{conn_pct:.0f})"
                    ),
                    details={
                        "active": health.active_connections,
                        "max": health.max_connections,
                        "pct": round(conn_pct, 1),
                    },
                ))

        # Cache hit ratio
        if health.cache_hit_ratio > 0:
            cache_pct = health.cache_hit_ratio * 100
            if cache_pct < thr.cache_hit_min_pct:
                alerts.append(MonitorAlert(
                    target_name=target_name,
                    alert_type="low_cache_hit",
                    severity="warning",
                    message=f"Cache hit ratio düşük: %{cache_pct:.1f}",
                    details={"cache_hit_pct": round(cache_pct, 1)},
                ))

        # Replikasyon gecikmesi
        if hasattr(health, "replication_lag_sec") and health.replication_lag_sec > thr.replication_lag_sec:
            severity = "critical" if health.replication_lag_sec > 120 else "warning"
            alerts.append(MonitorAlert(
                target_name=target_name,
                alert_type="replication_lag",
                severity=severity,
                message=f"Replikasyon gecikmesi: {health.replication_lag_sec:.0f}s",
                details={"lag_sec": health.replication_lag_sec},
            ))

        # Uzun sorgu sayısı (health içinde varsa)
        if hasattr(health, "long_running_queries") and health.long_running_queries > 0:
            alerts.append(MonitorAlert(
                target_name=target_name,
                alert_type="long_queries_count",
                severity="warning",
                message=f"{health.long_running_queries} uzun süren sorgu var",
                details={"count": health.long_running_queries},
            ))

        # Kilitli işlem sayısı (health içinde varsa)
        if hasattr(health, "blocked_locks") and health.blocked_locks >= thr.blocked_lock_count:
            severity = "critical" if health.blocked_locks >= 5 else "warning"
            alerts.append(MonitorAlert(
                target_name=target_name,
                alert_type="blocked_locks",
                severity=severity,
                message=f"{health.blocked_locks} engellenmiş kilit",
                details={"count": health.blocked_locks},
            ))

        return alerts

    async def _check_long_queries(self, target_name: str, adapter) -> List[MonitorAlert]:
        """Uzun süren sorgu tespiti — DB adapter üzerinden."""
        alerts = []
        thr = self.thresholds

        try:
            from dba_agent.tools import get_tool_registry
            registry = get_tool_registry()
            result = await registry.execute(
                "get_long_running_queries",
                db_name=target_name,
                threshold_sec=thr.long_query_sec,
            )

            if result.get("success"):
                data = result.get("result", {})
                count = data.get("count", 0)
                if count > 0:
                    queries = data.get("queries", [])
                    max_dur = max((q.get("duration_sec", 0) for q in queries), default=0)
                    severity = "critical" if max_dur > 300 else "warning"
                    alerts.append(MonitorAlert(
                        target_name=target_name,
                        alert_type="long_running_queries",
                        severity=severity,
                        message=(
                            f"{count} uzun sorgu — "
                            f"en uzun: {max_dur:.0f}s"
                        ),
                        details={
                            "count": count,
                            "max_duration_sec": max_dur,
                            "queries": [
                                {
                                    "pid": q.get("pid"),
                                    "duration_sec": q.get("duration_sec"),
                                    "user": q.get("user"),
                                    "query": (q.get("query", "")[:100]),
                                }
                                for q in queries[:3]
                            ],
                        },
                    ))
        except Exception as e:
            logger.debug(f"Long query check hatası ({target_name}): {e}")

        return alerts

    async def _check_locks(self, target_name: str, adapter) -> List[MonitorAlert]:
        """Kilit bloğu tespiti."""
        alerts = []
        thr = self.thresholds

        try:
            from dba_agent.tools import get_tool_registry
            registry = get_tool_registry()
            result = await registry.execute(
                "get_blocked_locks",
                db_name=target_name,
            )

            if result.get("success"):
                data = result.get("result", {})
                count = data.get("count", 0)
                if count >= thr.blocked_lock_count:
                    severity = "critical" if count >= 5 else "warning"
                    alerts.append(MonitorAlert(
                        target_name=target_name,
                        alert_type="blocked_locks_detail",
                        severity=severity,
                        message=f"{count} bağlantı kilitlenmiş durumda",
                        details={
                            "count": count,
                            "locks": data.get("locks", [])[:3],
                        },
                    ))
        except Exception as e:
            logger.debug(f"Lock check hatası ({target_name}): {e}")

        return alerts

    # ─── Telegram Bildirim ────────────────────

    async def _maybe_send_alert(self, alert: MonitorAlert) -> None:
        """Cooldown kontrolü yaparak alert gönder."""
        key = alert.alert_key()
        now = time.time()
        last_sent = self._alert_sent_at.get(key, 0)

        if now - last_sent < self.thresholds.alert_cooldown_sec:
            logger.debug(f"Alert cooldown aktif: {key}")
            return

        self._alert_sent_at[key] = now
        self._alert_count += 1

        try:
            await self._send_telegram_alert(alert)
        except Exception as e:
            logger.error(f"Telegram alert gönderme hatası: {e}")

    async def _send_telegram_alert(self, alert: MonitorAlert) -> None:
        """Telegram'a proaktif anomali bildirimi gönder."""
        from dba_agent.telegram.bot import get_bot
        bot = get_bot()

        if not bot._running:
            logger.debug("Telegram bot çalışmıyor, alert gönderilemedi")
            return

        msg = _format_monitor_alert(alert)
        await bot.broadcast(msg)
        logger.info(
            f"Proaktif alert gönderildi: [{alert.severity.upper()}] "
            f"{alert.target_name} — {alert.alert_type}"
        )


# ─────────────────────────────────────────────
# Alert Mesaj Formatı
# ─────────────────────────────────────────────

def _format_monitor_alert(alert: MonitorAlert) -> str:
    """Telegram'a gönderilecek proaktif alert mesajını formatla."""
    sev_emoji = {
        "critical": "🔴",
        "warning": "🟡",
        "info": "🔵",
    }.get(alert.severity, "⚪")

    type_emoji = {
        "long_running_queries": "🐌",
        "long_queries_count": "🐌",
        "blocked_locks": "🔒",
        "blocked_locks_detail": "🔒",
        "high_connections": "🔗",
        "low_cache_hit": "💾",
        "replication_lag": "🔄",
        "low_health_score": "🏥",
        "connection_error": "❌",
    }.get(alert.alert_type, "⚠️")

    import time as _time
    ts = _time.strftime("%H:%M:%S", _time.localtime(alert.timestamp))

    lines = [
        f"{sev_emoji} *OTOMATİK UYARI* — {alert.severity.upper()}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"{type_emoji} *DB:* `{alert.target_name}`",
        f"📋 *Sorun:* {alert.message}",
        f"🕐 *Zaman:* {ts}",
    ]

    # Detaylar
    details = alert.details
    if details:
        if alert.alert_type in ("long_running_queries", "long_queries_count"):
            queries = details.get("queries", [])
            if queries:
                lines.append(f"\n*En uzun sorgular:*")
                for q in queries[:3]:
                    lines.append(
                        f"  • PID {q.get('pid')} | {q.get('user', '?')} | "
                        f"{q.get('duration_sec', '?')}s\n"
                        f"    `{q.get('query', '')[:80]}`"
                    )

        elif alert.alert_type in ("blocked_locks", "blocked_locks_detail"):
            locks = details.get("locks", [])
            if locks:
                lines.append(f"\n*Kilitli bağlantılar:*")
                for l in locks[:3]:
                    lines.append(
                        f"  • PID {l.get('pid')} → {l.get('waiting_pid', '?')} | "
                        f"{l.get('table', '?')}"
                    )

        elif alert.alert_type == "high_connections":
            lines.append(
                f"\n  Aktif: {details.get('active')} / Maks: {details.get('max')} "
                f"(%{details.get('pct')})"
            )

    lines.extend([
        f"",
        f"💡 Detay için: `/db` veya `/diagnose {alert.target_name}`",
    ])

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────

_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Global HealthMonitor instance döndürür."""
    global _monitor
    if _monitor is None:
        _monitor = HealthMonitor()
    return _monitor
