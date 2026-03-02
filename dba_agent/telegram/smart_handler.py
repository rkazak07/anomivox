"""
Telegram Akıllı Mesaj İşleyici — DBA Agent Entegrasyonu
═══════════════════════════════════════════════════════
Kullanıcı mesajlarını anlayıp doğrudan DBA araçlarını
çalıştıran, gerçek DB verileriyle yanıt veren sistem.

Serbest metin yazıldığında:
  1. Intent analizi (hangi tool çalışmalı?)
  2. Tool çalıştır (gerçek DB/metrik verisi)
  3. Sonucu LLM ile özetle
  4. Telegram'a gönder
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from dba_agent.config import get_config

logger = logging.getLogger("dba_agent.telegram.smart_handler")


# ─────────────────────────────────────────────
# Intent → Tool mapping
# ─────────────────────────────────────────────

INTENT_PATTERNS: List[Tuple[str, List[str], Dict[str, Any]]] = [
    # (tool_name, keyword_patterns, default_args)
    
    # ── DB Sağlık ─────────────────────────────
    ("get_health", [
        r"sağlık|health|durum|genel\s*durum|nasıl|iyi\s*mi|db\s*durumu",
        r"score|puan|skor",
    ], {}),
    
    # ── Bağlantılar ──────────────────────────
    ("get_active_connections", [
        r"bağlantı|connection|conn|aktif\s*bağlantı|kaç\s*bağlantı",
        r"oturum|session|client|who",
    ], {}),
    
    # ── Uzun süren sorgular ──────────────────
    ("get_long_running_queries", [
        r"uzun.*sorgu|long.*quer|yavaş.*sorgu|slow.*quer|çalışan.*sorgu",
        r"running.*quer|sorgu.*sürü|ne\s*kadar\s*sürüyor",
    ], {"threshold_sec": 1.0}),
    
    # ── Kilitler ─────────────────────────────
    ("get_blocked_locks", [
        r"kilit|lock|blok|engel|deadlock|kilitlen",
        r"wait|bekle|block",
    ], {}),
    
    # ── Yavaş sorgular (istatistik) ─────────
    ("get_slow_queries", [
        r"en\s*yavaş|slowest|top.*slow|sorgu.*istatist|query.*stat",
        r"pg_stat|performance|perform",
    ], {"limit": 10}),
    
    # ── Tablo istatistikleri ─────────────────
    ("get_table_stats", [
        r"tablo|table|boyut|size|dead.*row|bloat",
        r"satır\s*sayı|row\s*count|kaç\s*satır|tablo.*bilgi",
    ], {"schema": "public"}),
    
    # ── Index ─────────────────────────────────
    ("get_index_stats", [
        r"index|indeks|kullanılmayan.*index|unused.*index",
        r"idx|index.*stat|index.*bilgi|index.*durum",
    ], {"schema": "public"}),
    
    # ── CPU ───────────────────────────────────
    ("get_cpu_usage", [
        r"cpu|işlemci|processor|yük|load",
    ], {"duration": "5m"}),
    
    # ── Bellek ────────────────────────────────
    ("get_memory_usage", [
        r"memory|bellek|ram|hafıza|mem",
    ], {}),
    
    # ── Disk ──────────────────────────────────
    ("get_disk_usage", [
        r"disk|depolama|storage|alan|yer|doluluk",
    ], {}),
    
    # ── I/O ───────────────────────────────────
    ("get_io_stats", [
        r"io|i/o|disk.*io|read.*write|yazma.*okuma",
    ], {"duration": "5m"}),
    
    # ── PostgreSQL metrikleri ─────────────────
    ("get_pg_metrics", [
        r"pg.*metric|tps|transaction|cache\s*hit|replic|dead\s*tuple",
    ], {}),
    
    # ── Alert'ler ─────────────────────────────
    ("get_active_alerts", [
        r"alert|alarm|uyarı|aktif.*alert|firing",
    ], {}),

    # ═══════════════════════════════════════════
    # OS Tools (SSH) — Faz 5
    # ═══════════════════════════════════════════

    # ── Servis Durumu ─────────────────────────
    ("check_service_status", [
        r"servis.*durum|service.*status|systemctl|servis.*çalışıyor",
        r"postgresql.*servis|mysql.*servis|nginx.*servis|servis.*kontrol",
        r"servis.*durdu|service.*down|servis.*aktif",
    ], {"service_name": "postgresql"}),

    # ── Servis Logları ────────────────────────
    ("read_service_logs", [
        r"servis.*log|service.*log|journalctl|servis.*hata",
        r"postgresql.*log|mysql.*log|log.*oku|log.*göster",
    ], {"service_name": "postgresql", "lines": 50}),

    # ── Sistem Bilgisi ────────────────────────
    ("get_system_info", [
        r"sistem.*bilgi|system.*info|sunucu.*bilgi|server.*info",
        r"hostname|kernel|uptime|os.*bilgi|makine",
    ], {}),

    # ── Disk Alanı (SSH) ─────────────────────
    ("check_disk_space", [
        r"disk.*alan|disk.*space|df|doluluk.*ssh|sunucu.*disk",
    ], {}),

    # ── Process Listesi ──────────────────────
    ("check_process_list", [
        r"process|proses|ps\s*aux|çalışan.*program|top\s*process",
        r"pid.*liste|hangi.*çalışıyor",
    ], {}),

    # ── OS Log Okuma ─────────────────────────
    ("read_os_log", [
        r"os.*log|sistem.*log|var.*log|syslog|dmesg",
        r"hata.*log|error.*log|log.*dosya",
    ], {"log_path": "/var/log/syslog", "lines": 50}),

    # ── Port Kontrolü ────────────────────────
    ("check_port", [
        r"port.*kontrol|port.*açık|port.*dinle|port.*listen",
        r"port\s*\d+|hangi.*port",
    ], {"port": 5432}),

    # ═══════════════════════════════════════════
    # DB Action Tools — Faz 5
    # ═══════════════════════════════════════════

    # ── Sorgu İptal ──────────────────────────
    ("cancel_query", [
        r"sorgu.*iptal|cancel.*query|sorgu.*durdur|query.*cancel",
        r"pg_cancel|iptal.*et",
    ], {}),

    # ── Oturum Öldürme ───────────────────────
    ("kill_session", [
        r"oturum.*öldür|kill.*session|session.*kill|bağlantı.*kes",
        r"terminate|sonlandır|pid.*öldür|kill.*pid",
    ], {}),

    # ── VACUUM ───────────────────────────────
    ("vacuum_table", [
        r"vacuum|vakum|dead.*temizle|dead.*tuple.*temizle",
        r"tablo.*temizle|temizlik.*yap",
    ], {}),

    # ── REINDEX ──────────────────────────────
    ("reindex_table", [
        r"reindex|index.*yeniden|index.*oluştur|index.*rebuild",
        r"bozuk.*index|şişmiş.*index|optimize.*table",
    ], {}),

    # ── ANALYZE ──────────────────────────────
    ("analyze_table", [
        r"analyze|analiz.*tablo|istatistik.*güncelle|planner",
    ], {}),

    # ── Config ───────────────────────────────
    ("set_db_config", [
        r"config.*değiştir|parametre.*ayarla|set.*config|alter.*system",
        r"work_mem|shared_buffer|effective_cache",
    ], {}),

    # ── Config Reload ────────────────────────
    ("reload_db_config", [
        r"config.*reload|reload.*config|pg_reload|yeniden.*yükle.*config",
    ], {}),

    # ── Uzun Sorguları Toplu Öldürme ─────────
    ("kill_long_running_queries", [
        r"uzun.*sorgu.*öldür|kill.*long.*running|hepsini.*öldür",
        r"toplu.*öldür|tümünü.*sonlandır",
    ], {"threshold_sec": 300}),
]

# SQL sorgusu tespiti
SQL_PATTERN = re.compile(
    r"^\s*(SELECT|SHOW|EXPLAIN|WITH)\s+",
    re.IGNORECASE | re.MULTILINE,
)

# DB adı tespiti — "db_adı'nda", "db_adı için", "db_adı DB'de" vs.
DB_NAME_PATTERN = re.compile(
    r"(?:db[:\s]+|database[:\s]+|veritabanı[:\s]+|"
    r"(\w+)[\s'](?:da|de|nda|nde|için|üzerinde|db|veritabanı))",
    re.IGNORECASE,
)


def detect_intent(text: str) -> Tuple[Optional[str], Dict[str, Any], float]:
    """
    Kullanıcı metninden intent tespit et.
    
    Returns:
        (tool_name, args, confidence)
        tool_name=None ise intent tespit edilemedi
    """
    text_lower = text.lower().strip()
    
    # SQL sorgusu mu?
    if SQL_PATTERN.match(text):
        return "execute_diagnostic_query", {"sql": text.strip()}, 0.95
    
    # DB adı tespiti
    db_name = _extract_db_name(text_lower)
    
    best_tool = None
    best_score = 0.0
    best_args = {}
    
    for tool_name, patterns, default_args in INTENT_PATTERNS:
        score = 0.0
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                score += len(matches) * 0.3
        
        if score > best_score:
            best_score = score
            best_tool = tool_name
            best_args = dict(default_args)
    
    if best_tool and best_score >= 0.3:
        if db_name:
            best_args["db_name"] = db_name
        
        # Threshold parametresi metinden çıkar
        time_match = re.search(r"(\d+)\s*(saniye|sn|sec|s)\b", text_lower)
        if time_match and "threshold_sec" in best_args:
            best_args["threshold_sec"] = float(time_match.group(1))
        
        # Limit parametresi
        limit_match = re.search(r"(?:ilk|top|en\s*fazla|limit)\s*(\d+)", text_lower)
        if limit_match and "limit" in best_args:
            best_args["limit"] = int(limit_match.group(1))
        
        return best_tool, best_args, min(best_score, 1.0)
    
    return None, {}, 0.0


def _extract_db_name(text: str) -> Optional[str]:
    """Metinden DB adını çıkarmaya çalış."""
    config = get_config()
    known_names = [t.name.lower() for t in config.database.targets]
    
    # Bilinen DB adlarını ara
    for name in known_names:
        if name in text:
            # Orijinal case'ini bul
            for t in config.database.targets:
                if t.name.lower() == name:
                    return t.name
    
    return None


async def execute_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool'u çalıştır ve sonucu döndür.
    
    Returns:
        {"success": bool, "result": Any, "error": str|None, "tool": str}
    """
    from dba_agent.tools import get_tool_registry
    registry = get_tool_registry()
    
    result = await registry.execute(tool_name, **args)
    result["tool"] = tool_name
    return result


async def execute_multiple_tools(
    tool_calls: List[Tuple[str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Birden fazla tool'u paralel çalıştır."""
    tasks = [execute_tool(name, args) for name, args in tool_calls]
    return await asyncio.gather(*tasks, return_exceptions=True)


def format_tool_result(tool_name: str, result: Dict[str, Any]) -> str:
    """Tool sonucunu okunabilir metin formatına çevir."""
    if not result.get("success"):
        return f"❌ `{tool_name}` hatası: {result.get('error', 'Bilinmeyen hata')}"
    
    data = result.get("result", {})
    
    # Tool bazlı formatlama
    formatters = {
        "get_health": _fmt_health,
        "get_active_connections": _fmt_connections,
        "get_long_running_queries": _fmt_long_queries,
        "get_blocked_locks": _fmt_locks,
        "get_slow_queries": _fmt_slow_queries,
        "get_table_stats": _fmt_table_stats,
        "get_index_stats": _fmt_index_stats,
        "get_cpu_usage": _fmt_cpu,
        "get_memory_usage": _fmt_memory,
        "get_disk_usage": _fmt_disk,
        "get_io_stats": _fmt_io,
        "get_pg_metrics": _fmt_pg_metrics,
        "get_active_alerts": _fmt_alerts,
        "execute_diagnostic_query": _fmt_query_result,
        # OS Tools
        "check_service_status": _fmt_service_status,
        "read_service_logs": _fmt_service_logs,
        "get_system_info": _fmt_system_info,
        "check_disk_space": _fmt_disk_space,
        "check_process_list": _fmt_process_list,
        "read_os_log": _fmt_os_log,
        "restart_service": _fmt_restart_service,
        "check_port": _fmt_check_port,
        # DB Action Tools
        "cancel_query": _fmt_action_result,
        "kill_session": _fmt_action_result,
        "vacuum_table": _fmt_vacuum_result,
        "vacuum_full_table": _fmt_vacuum_result,
        "reindex_table": _fmt_action_result,
        "analyze_table": _fmt_action_result,
        "set_db_config": _fmt_config_result,
        "reload_db_config": _fmt_action_result,
        "kill_long_running_queries": _fmt_bulk_kill_result,
    }
    
    formatter = formatters.get(tool_name)
    if formatter:
        try:
            return formatter(data)
        except Exception as e:
            logger.error(f"Format hatası ({tool_name}): {e}")
    
    # Fallback: JSON
    return f"```\n{json.dumps(data, indent=2, ensure_ascii=False)[:3000]}\n```"


# ─────────────────────────────────────────────
# Tool-specific formatters
# ─────────────────────────────────────────────

def _fmt_health(data: Dict) -> str:
    score = data.get("health_score", 0)
    emoji = "🟢" if score >= 80 else "🟡" if score >= 50 else "🔴"
    return (
        f"🏥 *Veritabanı Sağlık Raporu*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{emoji} Sağlık Skoru: *{score}/100*\n"
        f"📦 Tip: {data.get('db_type', '?')}\n"
        f"🔢 Versiyon: {data.get('version', '?')}\n"
        f"⏱️ Uptime: {data.get('uptime_hours', '?')} saat\n"
        f"🔗 Bağlantı: {data.get('connections', '?')} ({data.get('connection_usage_pct', '?')}%)\n"
        f"💾 DB Boyut: {data.get('database_size_mb', '?')} MB\n"
        f"📊 Cache Hit: {data.get('cache_hit_ratio', '?')}\n"
        f"🐌 Uzun Sorgu: {data.get('long_running_queries', 0)}\n"
        f"🔒 Kilitli: {data.get('blocked_locks', 0)}"
    )


def _fmt_connections(data: Dict) -> str:
    total = data.get("total", 0)
    by_state = data.get("by_state", {})
    
    lines = [
        f"🔗 *Aktif Bağlantılar: {total}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    for state, count in sorted(by_state.items(), key=lambda x: -x[1]):
        emoji = {"active": "🟢", "idle": "⚪", "idle in transaction": "🟡"}.get(state, "🔵")
        lines.append(f"  {emoji} {state}: {count}")
    
    conns = data.get("connections", [])
    if conns:
        lines.append(f"\n📋 *İlk {min(len(conns), 10)} bağlantı:*")
        for c in conns[:10]:
            dur = c.get("duration_sec", 0)
            q = c.get("query", "")[:80]
            lines.append(
                f"  • PID {c.get('pid')} | {c.get('user', '?')} | "
                f"{c.get('state', '?')} | {dur}s"
            )
            if q:
                lines.append(f"    `{q}`")
    
    return "\n".join(lines)


def _fmt_long_queries(data: Dict) -> str:
    count = data.get("count", 0)
    queries = data.get("queries", [])
    
    if count == 0:
        return "✅ Uzun süren sorgu yok!"
    
    lines = [
        f"🐌 *Uzun Süren Sorgular: {count}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    for q in queries[:5]:
        lines.append(
            f"\n⏱️ *{q.get('duration_sec', '?')}s* | PID: {q.get('pid')} | {q.get('user', '?')}\n"
            f"  State: {q.get('state', '?')}\n"
            f"  `{q.get('query', '?')[:150]}`"
        )
    
    return "\n".join(lines)


def _fmt_locks(data: Dict) -> str:
    count = data.get("count", 0)
    
    if count == 0:
        return "✅ Engellenmiş kilit yok!"
    
    lines = [
        f"🔒 *Engellenmiş Kilitler: {count}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    for l in data.get("locks", [])[:5]:
        lines.append(
            f"\n🔴 PID {l.get('pid')} → Bekleyen: {l.get('waiting_pid')}\n"
            f"  Tablo: {l.get('table', '?')}\n"
            f"  Tip: {l.get('lock_type', '?')} / {l.get('mode', '?')}\n"
            f"  Süre: {l.get('duration_sec', '?')}s\n"
            f"  `{l.get('query', '')[:120]}`"
        )
    
    return "\n".join(lines)


def _fmt_slow_queries(data: Dict) -> str:
    queries = data.get("queries", [])
    
    if not queries:
        return "✅ pg_stat_statements'ta yavaş sorgu kaydı yok."
    
    lines = [
        f"📊 *En Yavaş {len(queries)} Sorgu*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    for i, q in enumerate(queries[:7], 1):
        lines.append(
            f"\n*{i}.* Ort: {q.get('mean_time_ms', '?')}ms | "
            f"Çağrı: {q.get('calls', '?')} | "
            f"Hit: {q.get('hit_ratio', '?')}\n"
            f"  `{q.get('query', '?')[:150]}`"
        )
    
    return "\n".join(lines)


def _fmt_table_stats(data: Dict) -> str:
    tables = data.get("tables", [])
    
    if not tables:
        return "📋 Tablo bulunamadı."
    
    lines = [
        f"📋 *Tablo İstatistikleri ({len(tables)} tablo)*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    for t in tables[:15]:
        vacuum_emoji = "🔴" if t.get("needs_vacuum") else "🟢"
        lines.append(
            f"\n📦 *{t.get('table', '?')}*\n"
            f"  Satır: {t.get('rows', '?')} | Boyut: {t.get('size_mb', '?')} MB\n"
            f"  Dead: {t.get('dead_rows', 0)} {vacuum_emoji} | "
            f"Seq: {t.get('seq_scan', 0)} | Idx: {t.get('idx_scan', 0)}\n"
            f"  Son Vacuum: {t.get('last_vacuum', 'hiç')}"
        )
    
    return "\n".join(lines)


def _fmt_index_stats(data: Dict) -> str:
    total = data.get("total", 0)
    unused = data.get("unused_count", 0)
    unused_list = data.get("unused_indexes", [])
    
    lines = [
        f"📑 *Index İstatistikleri*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  Toplam: {total}\n"
        f"  Kullanılmayan: {'🔴 ' if unused > 0 else '🟢 '}{unused}"
    ]
    
    if unused_list:
        lines.append(f"\n⚠️ *Kullanılmayan Index'ler:*")
        for idx in unused_list[:10]:
            lines.append(
                f"  • `{idx.get('index', '?')}` ({idx.get('table', '?')}) — "
                f"{idx.get('size_mb', '?')} MB"
            )
    
    return "\n".join(lines)


def _fmt_cpu(data: Dict) -> str:
    usage = data.get("cpu_usage_pct", -1)
    status = data.get("status", "unknown")
    emoji = {"critical": "🔴", "warning": "🟡", "normal": "🟢"}.get(status, "⚪")
    return (
        f"🔥 *CPU Kullanımı*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  {emoji} {usage}% ({data.get('duration', '5m')} ortalama)\n"
        f"  Durum: {status.upper()}"
    )


def _fmt_memory(data: Dict) -> str:
    used = data.get("used_pct", -1)
    status = data.get("status", "unknown")
    emoji = {"critical": "🔴", "warning": "🟡", "normal": "🟢"}.get(status, "⚪")
    return (
        f"🧠 *Bellek Kullanımı*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  {emoji} %{used} kullanımda\n"
        f"  Toplam: {data.get('total_gb', '?')} GB\n"
        f"  Boş: {data.get('available_gb', '?')} GB\n"
        f"  Durum: {status.upper()}"
    )


def _fmt_disk(data: Dict) -> str:
    usage = data.get("disk_usage_pct", -1)
    status = data.get("status", "unknown")
    emoji = {"critical": "🔴", "warning": "🟡", "normal": "🟢"}.get(status, "⚪")
    return (
        f"💾 *Disk Kullanımı*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  {emoji} %{usage} dolu\n"
        f"  Durum: {status.upper()}"
    )


def _fmt_io(data: Dict) -> str:
    return (
        f"💿 *Disk I/O*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  📖 Okuma: {data.get('read_mb_per_sec', '?')} MB/s\n"
        f"  ✏️ Yazma: {data.get('write_mb_per_sec', '?')} MB/s\n"
        f"  Periyot: {data.get('duration', '5m')}"
    )


def _fmt_pg_metrics(data: Dict) -> str:
    return (
        f"🐘 *PostgreSQL Metrikleri*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  ⚡ TPS: {data.get('tps', '?')}\n"
        f"  📊 Cache Hit: %{data.get('cache_hit_ratio', '?')}\n"
        f"  🔄 Rep. Lag: {data.get('replication_lag_sec', 0)}s\n"
        f"  💀 Dead Tuples: {data.get('total_dead_tuples', '?')}"
    )


def _fmt_alerts(data: Dict) -> str:
    count = data.get("count", 0)
    
    if count == 0:
        return "✅ Aktif alert yok!"
    
    lines = [
        f"🚨 *Aktif Alert'ler: {count}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    for a in data.get("alerts", [])[:10]:
        sev = a.get("severity", "?")
        sev_e = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(sev, "⚪")
        lines.append(
            f"\n{sev_e} *{a.get('name', '?')}* [{sev}]\n"
            f"  {a.get('summary', '?')[:100]}"
        )
    
    return "\n".join(lines)


def _fmt_query_result(data: Dict) -> str:
    if not data.get("success"):
        return f"❌ Sorgu hatası: {data.get('error', 'Bilinmeyen')}"
    
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    exec_ms = data.get("execution_time_ms", 0)
    
    lines = [
        f"📊 *Sorgu Sonucu*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"  Satır: {data.get('row_count', 0)} | Süre: {exec_ms}ms\n"
    ]
    
    if rows:
        # Tablo formatı (max 15 satır)
        for i, row in enumerate(rows[:15], 1):
            row_parts = []
            for col in columns[:6]:  # Max 6 kolon
                val = row.get(col, "")
                if isinstance(val, str) and len(val) > 40:
                    val = val[:37] + "..."
                row_parts.append(f"{col}: {val}")
            lines.append(f"  {i}. {' | '.join(row_parts)}")
    
    return "\n".join(lines)


# ─────────────────────────────────────────────
# OS Tool Formatters
# ─────────────────────────────────────────────

def _fmt_service_status(data: Dict) -> str:
    active = data.get("active")
    emoji = "✅" if active else "❌" if active is False else "❓"
    return (
        f"🖥️ *Servis Durumu*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  Servis: `{data.get('service', '?')}`\n"
        f"  Sunucu: {data.get('host', '?')}\n"
        f"  {emoji} Durum: {data.get('status', '?')}\n\n"
        f"```\n{data.get('details', '')[:1500]}\n```"
    )


def _fmt_service_logs(data: Dict) -> str:
    log_lines = data.get("log_lines", [])
    err = data.get("error_count", 0)
    warn = data.get("warning_count", 0)
    
    err_emoji = "🔴" if err > 0 else "🟢"
    warn_emoji = "🟡" if warn > 0 else ""
    
    lines = [
        f"📋 *Servis Logları*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  Servis: `{data.get('service', '?')}`\n"
        f"  Sunucu: {data.get('host', '?')}\n"
        f"  Periyot: son {data.get('since', '?')}\n"
        f"  {err_emoji} Hata: {err} | {warn_emoji}Uyarı: {warn}\n"
        f"  Toplam: {data.get('total_lines', 0)} satır\n"
    ]
    
    if log_lines:
        # Son 20 satırı göster
        shown = log_lines[-20:]
        lines.append(f"\n```")
        for l in shown:
            lines.append(l[:120])
        lines.append("```")
    
    return "\n".join(lines)


def _fmt_system_info(data: Dict) -> str:
    mem = data.get("memory", {})
    disk = data.get("disk", {})
    load = data.get("load_avg", {})
    
    mem_pct = mem.get("usage_pct", 0)
    mem_emoji = "🔴" if mem_pct > 90 else "🟡" if mem_pct > 70 else "🟢"
    
    return (
        f"🖥️ *Sistem Bilgisi*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  🏷️ Hostname: {data.get('hostname', '?')}\n"
        f"  🐧 OS: {data.get('os', '?')}\n"
        f"  🔧 Kernel: {data.get('kernel', '?')[:80]}\n"
        f"  ⏱️ Uptime: {data.get('uptime', '?')}\n"
        f"  💻 CPU: {data.get('cpu_count', '?')} çekirdek\n"
        f"  📊 Load: {load.get('1min', '?')} / {load.get('5min', '?')} / {load.get('15min', '?')}\n\n"
        f"  {mem_emoji} Bellek: {mem.get('used_mb', '?')}MB / {mem.get('total_mb', '?')}MB ({mem_pct}%)\n"
        f"  💾 Disk: {disk.get('used', '?')} / {disk.get('size', '?')} ({disk.get('usage_pct', '?')})"
    )


def _fmt_disk_space(data: Dict) -> str:
    critical = data.get("critical", [])
    warnings = data.get("warnings", [])
    
    lines = [
        f"💾 *Disk Kullanımı*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  Sunucu: {data.get('host', '?')}\n"
    ]
    
    if critical:
        lines.append(f"  🔴 *KRİTİK:* {', '.join(critical)}")
    if warnings:
        lines.append(f"  🟡 *Uyarı:* {', '.join(warnings)}")
    if not critical and not warnings:
        lines.append(f"  🟢 Tüm diskler normal")
    
    for fs in data.get("filesystems", [])[:10]:
        pct = fs.get("usage_pct", 0)
        emoji = "🔴" if pct >= 95 else "🟡" if pct >= 85 else "🟢"
        lines.append(
            f"\n  {emoji} `{fs.get('mount', '?')}` — "
            f"{fs.get('used', '?')}/{fs.get('size', '?')} ({pct}%)"
        )
    
    return "\n".join(lines)


def _fmt_process_list(data: Dict) -> str:
    processes = data.get("processes", [])
    
    lines = [
        f"⚙️ *Process Listesi*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  Sunucu: {data.get('host', '?')}\n"
        f"  Filtre: {data.get('filter', '?')}\n"
        f"  Toplam: {data.get('total', 0)}\n"
    ]
    
    for p in processes[:15]:
        lines.append(
            f"\n  PID: {p.get('pid', '?')} | CPU: {p.get('cpu_pct', '?')}% | "
            f"MEM: {p.get('mem_pct', '?')}%\n"
            f"  User: {p.get('user', '?')} | `{p.get('command', '?')[:80]}`"
        )
    
    return "\n".join(lines)


def _fmt_os_log(data: Dict) -> str:
    log_lines = data.get("log_lines", [])
    
    lines = [
        f"📄 *OS Log*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  Dosya: `{data.get('log_path', '?')}`\n"
        f"  Sunucu: {data.get('host', '?')}\n"
        f"  Hata: {data.get('error_count', 0)} satır\n"
    ]
    
    if data.get("grep_pattern"):
        lines.append(f"  Filtre: `{data['grep_pattern']}`")
    
    if log_lines:
        shown = log_lines[-15:]
        lines.append(f"\n```")
        for l in shown:
            lines.append(l[:120])
        lines.append("```")
    
    return "\n".join(lines)


def _fmt_restart_service(data: Dict) -> str:
    restarted = data.get("restarted", False)
    emoji = "✅" if restarted else "❌"
    return (
        f"🔄 *Servis Yeniden Başlatma*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  Servis: `{data.get('service', '?')}`\n"
        f"  Sunucu: {data.get('host', '?')}\n"
        f"  Önceki: {data.get('pre_status', '?')}\n"
        f"  Sonraki: {data.get('post_status', '?')}\n"
        f"  {emoji} {data.get('message', '?')}"
    )


def _fmt_check_port(data: Dict) -> str:
    listening = data.get("listening", False)
    emoji = "✅" if listening else "❌"
    return (
        f"🔌 *Port Kontrolü*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  Sunucu: {data.get('host', '?')}\n"
        f"  Port: {data.get('port', '?')}\n"
        f"  {emoji} {'Dinleniyor' if listening else 'Dinlenmiyor'}\n"
        f"  `{data.get('details', '')[:300]}`"
    )


# ─────────────────────────────────────────────
# DB Action Formatters
# ─────────────────────────────────────────────

def _fmt_action_result(data: Dict) -> str:
    # Generic action formatter — cancel_query, kill_session, reindex, analyze, reload
    success_keys = ["cancelled", "killed", "reindexed", "analyzed", "reloaded"]
    success = any(data.get(k) for k in success_keys) or data.get("success", False)
    emoji = "✅" if success else "❌"
    
    lines = [
        f"⚡ *DB Aksiyon Sonucu*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  {emoji} {data.get('message', '?')}\n"
    ]
    
    if data.get("pid"):
        lines.append(f"  PID: {data['pid']}")
    if data.get("table"):
        lines.append(f"  Tablo: `{data['table']}`")
    if data.get("db_type"):
        lines.append(f"  DB: {data['db_type']}")
    if data.get("execution_time_ms"):
        lines.append(f"  Süre: {data['execution_time_ms']:.0f}ms")
    
    qi = data.get("query_info", {})
    if qi:
        lines.append(f"\n  📋 Bilgi: {qi.get('user', '?')} | {qi.get('state', '?')}")
        if qi.get("query"):
            lines.append(f"  `{qi['query'][:150]}`")
    
    return "\n".join(lines)


def _fmt_vacuum_result(data: Dict) -> str:
    vacuumed = data.get("vacuumed", False)
    emoji = "✅" if vacuumed else "❌"
    full = "FULL " if data.get("full") else ""
    
    lines = [
        f"🧹 *VACUUM {full}Sonucu*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"  Tablo: `{data.get('table', '?')}`\n"
        f"  {emoji} {data.get('message', '?')}\n"
        f"  Süre: {data.get('execution_time_ms', 0):.0f}ms\n"
    ]
    
    before = data.get("before", {})
    after = data.get("after", {})
    
    if before and after:
        lines.append(f"\n  📊 *Öncesi → Sonrası:*")
        lines.append(f"  Dead rows: {before.get('dead_rows', '?')} → {after.get('dead_rows', '?')}")
        lines.append(
            f"  Boyut: {before.get('total_size_mb', '?')}MB → {after.get('total_size_mb', '?')}MB"
        )
    
    return "\n".join(lines)


def _fmt_config_result(data: Dict) -> str:
    applied = data.get("applied", False)
    emoji = "✅" if applied else "❌"
    return (
        f"⚙️ *Config Değişikliği*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  Parametre: `{data.get('param', '?')}`\n"
        f"  Eski: {data.get('old_value', '?')}\n"
        f"  Yeni: {data.get('new_value', '?')}\n"
        f"  {emoji} {data.get('message', '?')}\n"
        f"  📌 {data.get('note', '')}"
    )


def _fmt_bulk_kill_result(data: Dict) -> str:
    count = data.get("killed_count", 0)
    emoji = "✅" if count > 0 else "ℹ️"
    
    lines = [
        f"💀 *Toplu Sorgu Sonlandırma*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  Eşik: {data.get('threshold_sec', '?')}s\n"
        f"  {emoji} {data.get('message', '?')}\n"
    ]
    
    for k in data.get("killed", [])[:10]:
        lines.append(
            f"\n  💀 PID {k.get('pid')} | {k.get('user', '?')} | "
            f"{k.get('duration_sec', '?')}s\n"
            f"    `{k.get('query', '')[:100]}`"
        )
    
    failed = data.get("failed_pids", [])
    if failed:
        lines.append(f"\n  ❌ Başarısız PID'ler: {failed}")
    
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Ana akıllı mesaj işleme fonksiyonu
# ─────────────────────────────────────────────

async def handle_smart_message(
    user_text: str,
    chat_id: str,
    send_func,
) -> None:
    """
    Kullanıcı mesajını akıllıca işle:
    1. Intent tespit et → Tool çalıştır
    2. Sonucu formatla
    3. LLM ile zenginleştir (opsiyonel)
    4. Gönder
    
    Args:
        user_text: Kullanıcı mesajı
        chat_id: Telegram chat ID
        send_func: async send_message(chat_id, text, parse_mode) fonksiyonu
    """
    from telegram.constants import ParseMode
    
    # ── Intent tespiti ───────────────────────
    tool_name, args, confidence = detect_intent(user_text)
    
    if tool_name and confidence >= 0.3:
        # Tool çalıştır
        await send_func(
            chat_id,
            f"🔧 `{tool_name}` çalıştırılıyor..." +
            (f" (DB: {args['db_name']})" if args.get("db_name") else ""),
            ParseMode.MARKDOWN,
        )
        
        try:
            result = await execute_tool(tool_name, args)
            formatted = format_tool_result(tool_name, result)
            await send_func(chat_id, formatted, ParseMode.MARKDOWN)
            
            # Tool sonucunu LLM ile yorumla
            if result.get("success"):
                await _send_llm_interpretation(
                    user_text, tool_name, result.get("result", {}),
                    chat_id, send_func,
                )
            
        except Exception as e:
            logger.error(f"Smart handler tool hatası: {e}", exc_info=True)
            await send_func(
                chat_id,
                f"❌ Araç çalıştırma hatası: `{str(e)[:200]}`",
                ParseMode.MARKDOWN,
            )
    
    else:
        # ── Birden fazla tool olabilir mi? ───
        multi_tools = _detect_multi_intent(user_text)
        
        if multi_tools:
            await send_func(
                chat_id,
                f"🔧 {len(multi_tools)} araç çalıştırılıyor...",
                ParseMode.MARKDOWN,
            )
            
            results = await execute_multiple_tools(multi_tools)
            
            all_text = []
            for r in results:
                if isinstance(r, Exception):
                    all_text.append(f"❌ Hata: {str(r)[:100]}")
                else:
                    all_text.append(format_tool_result(r.get("tool", "?"), r))
            
            combined = "\n\n".join(all_text)
            await send_func(chat_id, combined, ParseMode.MARKDOWN)
        
        else:
            # ── DBA-context LLM chat ─────────
            await _send_dba_chat(user_text, chat_id, send_func)


def _detect_multi_intent(text: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Birden fazla araç gerektiren istekleri tespit et.
    Örn: "CPU ve disk durumu nasıl?" → [get_cpu_usage, get_disk_usage]
    """
    text_lower = text.lower()
    tools = []
    seen = set()
    
    # Çoklu keyword kontrolü
    combined_keywords = {
        "cpu": ("get_cpu_usage", {"duration": "5m"}),
        "memory|bellek|ram": ("get_memory_usage", {}),
        "disk|depolama": ("get_disk_usage", {}),
        "bağlantı|connection": ("get_active_connections", {}),
        "lock|kilit": ("get_blocked_locks", {}),
        "sorgu|query|slow": ("get_long_running_queries", {"threshold_sec": 1.0}),
        "servis|service": ("check_service_status", {"service_name": "postgresql"}),
        "process|proses": ("check_process_list", {}),
        "system|sistem|sunucu": ("get_system_info", {}),
    }
    
    for patterns, (tool, args) in combined_keywords.items():
        for pattern in patterns.split("|"):
            if pattern in text_lower and tool not in seen:
                tools.append((tool, dict(args)))
                seen.add(tool)
                break
    
    # 2+ tool bulunduysa multi-intent
    if len(tools) >= 2:
        return tools
    
    return []


async def _send_llm_interpretation(
    user_question: str,
    tool_name: str,
    tool_result: Dict[str, Any],
    chat_id: str,
    send_func,
) -> None:
    """Tool sonucunu LLM ile kısa yorumla."""
    try:
        from dba_agent.inference import get_llm_client, ModelRouter, TaskType
        client = get_llm_client()
        router = ModelRouter()
        params = router.get_params(TaskType.CHAT)
        
        # Sonucu kısalt
        result_str = json.dumps(tool_result, ensure_ascii=False, default=str)[:1500]
        
        prompt = (
            f"Kullanıcı sorusu: {user_question}\n\n"
            f"Araç: {tool_name}\n"
            f"Sonuç:\n{result_str}\n\n"
            f"Bu verilere göre kısa (2-3 cümle) bir DBA yorumu yap. "
            f"Sorun varsa çözüm öner. Türkçe yanıtla."
        )
        
        response = await client.achat(
            prompt=prompt,
            model=params["model"],
            system_prompt=(
                "Sen deneyimli bir PostgreSQL/MySQL DBA'sın. "
                "Gerçek veritabanı verilerine dayanarak kısa ve net yorum yap. "
                "Emoji kullanma. Sadece profesyonel DBA yorumu."
            ),
            temperature=0.3,
            max_tokens=256,
        )
        
        if response and response.strip():
            from telegram.constants import ParseMode
            await send_func(
                chat_id,
                f"💡 *DBA Yorumu:*\n{response.strip()}",
                ParseMode.MARKDOWN,
            )
    
    except Exception as e:
        # LLM yorumu opsiyonel — hata olursa sessizce geç
        logger.debug(f"LLM interpretation hatası (opsiyonel): {e}")


async def _send_dba_chat(user_text: str, chat_id: str, send_func) -> None:
    """DBA context'li LLM sohbet — genel sorularda."""
    from telegram.constants import ParseMode
    
    await send_func(chat_id, "🤔 Düşünüyorum...", None)
    
    try:
        from dba_agent.inference import get_llm_client, ModelRouter, TaskType
        from dba_agent.tools import get_tool_registry
        
        client = get_llm_client()
        router = ModelRouter()
        params = router.get_params(TaskType.CHAT)
        
        # Mevcut DB bilgisini al
        db_context = ""
        try:
            from dba_agent.db import get_all_adapters
            for name, adapter in get_all_adapters().items():
                try:
                    adapter.connect()
                    h = adapter.get_health()
                    db_context += (
                        f"- {name}: {h.db_type} v{h.version}, "
                        f"conn: {h.active_connections}/{h.max_connections}, "
                        f"cache: {h.cache_hit_ratio:.1%}, "
                        f"score: {h.health_score}/100\n"
                    )
                except Exception:
                    db_context += f"- {name}: bağlantı hatası\n"
                finally:
                    adapter.disconnect()
        except Exception:
            db_context = "DB bilgisi alınamadı\n"
        
        # Tool listesi
        registry = get_tool_registry()
        tool_list = ", ".join(t.name for t in registry.list_tools())
        
        system_prompt = (
            "Sen Anomivox DBA Agent'sın — deneyimli bir veritabanı uzmanı asistanı.\n"
            "Telegram üzerinden DBA yardımı veriyorsun.\n\n"
            f"Bağlı veritabanları:\n{db_context}\n"
            f"Kullanılabilir araçlar: {tool_list}\n\n"
            "Kurallar:\n"
            "- Kısa ve net cevap ver (Telegram formatında)\n"
            "- Gerçek veri gerekiyorsa hangi komutu kullanması gerektiğini söyle\n"
            "- /diagnose ile tanı başlatmasını öner\n"
            "- Bilinmeyen konularda tahminde bulunma\n"
            "- Türkçe yanıtla"
        )
        
        response = await client.achat(
            prompt=user_text,
            model=params["model"],
            system_prompt=system_prompt,
            temperature=params["temperature"],
            max_tokens=params["max_tokens"],
        )
        
        await send_func(chat_id, response.strip() if response else "Yanıt alınamadı.", None)
    
    except Exception as e:
        logger.error(f"DBA chat hatası: {e}", exc_info=True)
        await send_func(
            chat_id,
            "❌ Yanıt oluşturulamadı.\n\n"
            "Kullanılabilir komutlar:\n"
            "  /status — Sistem durumu\n"
            "  /db — DB bağlantıları\n"
            "  /diagnose — Tanı başlat\n"
            "  /tools — Araç listesi",
            None,
        )
