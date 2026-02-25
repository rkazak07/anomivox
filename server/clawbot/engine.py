"""
Anomivox ClawBot Engine — Otonom DB Asistanı Beyni

Doğal dil mesajlarını anlayarak uygun DB skill'lerini çağırır,
sonuçları LLM ile yorumlayarak kullanıcıya anlaşılır yanıt üretir.

Akış:
  1. Kullanıcı mesajı → Intent Detection (LLM veya keyword match)
  2. Intent → Skill seçimi
  3. Skill çalıştırma → Ham veri
  4. Ham veri + kullanıcı sorusu → LLM ile doğal dil yanıtı
  5. Yanıt → Mesajlaşma kanalına gönderim

Desteklenen kanallar: Telegram, WhatsApp, Mail, Web UI
"""

import os
import sys
import json
import re
import logging
import asyncio
from datetime import datetime
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(
    format="%(asctime)s [ClawBot] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("anomivox.clawbot.engine")


# ── LLM Entegrasyonu ───────────────────────────────────────

def _get_llm_config():
    """ClawBot'un kendi LLM ayarlarını al (clawbot_config.py)."""
    try:
        from configs.clawbot_config import (
            get_llm_api_url, get_llm_model,
            CLAWBOT_LLM_API_KEY, CLAWBOT_AGENT_MODE,
            CLAWBOT_LLM_TEMPERATURE, CLAWBOT_LLM_MAX_TOKENS,
        )
        api_url = get_llm_api_url()
        model = get_llm_model()
        api_key = CLAWBOT_LLM_API_KEY
        temperature = CLAWBOT_LLM_TEMPERATURE
        max_tokens = CLAWBOT_LLM_MAX_TOKENS

        if api_url and model:
            return {
                "model_name": model,
                "api_base_url": api_url.rstrip("/"),
                "api_key": api_key,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
    except ImportError:
        pass

    # Fallback: model_config.py'den al
    try:
        from configs.model_config import ONLINE_LLM_MODEL, LLM_MODELS
        model_name = LLM_MODELS[0] if LLM_MODELS else "openai-api"
        config = ONLINE_LLM_MODEL.get(model_name, {})
        return {
            "model_name": config.get("model_name", "gpt-4"),
            "api_base_url": config.get("api_base_url", "https://api.openai.com/v1"),
            "api_key": config.get("api_key", os.environ.get("OPENAI_API_KEY", "")),
            "temperature": 0.3,
            "max_tokens": 1500,
        }
    except ImportError:
        return {
            "model_name": "gpt-4",
            "api_base_url": "https://api.openai.com/v1",
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
            "temperature": 0.3,
            "max_tokens": 1500,
        }


async def _llm_chat(system_prompt: str, user_message: str) -> str:
    """OpenAI-uyumlu API ile LLM yanıtı al."""
    import aiohttp

    config = _get_llm_config()

    if not config["api_key"]:
        return ""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
    }

    payload = {
        "model": config["model_name"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": config.get("temperature", 0.3),
        "max_tokens": config.get("max_tokens", 1500),
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{config['api_base_url']}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    err = await resp.text()
                    logger.error(f"LLM API error {resp.status}: {err[:200]}")
                    return ""
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  INTENT DETECTION — Mesajdan niyet çıkarma
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Komut → Skill eşlemesi
COMMAND_MAP = {
    "/status": "db_overview",
    "/overview": "db_overview",
    "/durum": "db_overview",
    "/health": "health_check",
    "/saglik": "health_check",
    "/sağlık": "health_check",
    "/slow": "slow_queries",
    "/slow_queries": "slow_queries",
    "/yavaş": "slow_queries",
    "/yavas": "slow_queries",
    "/active": "active_queries",
    "/active_queries": "active_queries",
    "/aktif": "active_queries",
    "/locks": "locks",
    "/kilit": "locks",
    "/tables": "table_stats",
    "/table_stats": "table_stats",
    "/tablolar": "table_stats",
    "/index": "index_recommendations",
    "/indexes": "index_recommendations",
    "/indeks": "index_recommendations",
    "/performance": "performance_summary",
    "/performans": "performance_summary",
    "/analiz": "performance_summary",
    "/analyze": "performance_summary",
}

# Aksiyon komutları
ACTION_COMMAND_MAP = {
    "/vacuum": "vacuum",
    "/reindex": "reindex",
    "/kill": "kill_query",
    "/kill_query": "kill_query",
}


def _keyword_intent(message: str) -> Optional[str]:
    """Anahtar kelimelerle intent tespiti."""
    from server.clawbot.skills import SKILL_REGISTRY

    msg_lower = message.lower().strip()

    # Önce komut eşlemesi
    first_word = msg_lower.split()[0] if msg_lower.split() else ""
    if first_word in COMMAND_MAP:
        return COMMAND_MAP[first_word]
    if first_word in ACTION_COMMAND_MAP:
        return f"action:{ACTION_COMMAND_MAP[first_word]}"

    # "veritabanı neden yavaş" gibi kapsamlı sorular → performance_summary
    comprehensive_patterns = [
        r"(neden|niçin|niye).*(yavaş|slow|sorun|problem)",
        r"(ne oluyor|what.*(happening|wrong))",
        r"(genel|full|komple|kapsamlı).*(analiz|analysis|rapor|report)",
        r"(problem|sorun).*(ne|what)",
    ]
    for pattern in comprehensive_patterns:
        if re.search(pattern, msg_lower):
            return "performance_summary"

    # Anahtar kelime eşlemesi — en iyi eşleşmeyi bul
    best_skill = None
    best_score = 0

    for skill_name, skill_info in SKILL_REGISTRY.items():
        score = 0
        for keyword in skill_info["keywords"]:
            kw_lower = keyword.lower()
            if kw_lower in msg_lower:
                # Uzun keyword'ler daha spesifik → daha yüksek puan
                score += len(kw_lower)

        if score > best_score:
            best_score = score
            best_skill = skill_name

    if best_score >= 3:  # En az 3 karakter eşleşmeli
        return best_skill

    return None


async def _llm_intent(message: str) -> Tuple[Optional[str], Optional[dict]]:
    """LLM ile intent tespiti — keyword match başarısız olursa kullanılır."""
    from server.clawbot.skills import SKILL_REGISTRY, ACTION_SKILLS

    skill_descriptions = "\n".join(
        f"- {name}: {info['description']}"
        for name, info in SKILL_REGISTRY.items()
    )
    action_descriptions = "\n".join(
        f"- action:{name}: {info['description']} (parametre: {info['requires_param']})"
        for name, info in ACTION_SKILLS.items()
    )

    system_prompt = f"""Sen Anomivox ClawBot'un intent detection modülüsün.
Kullanıcının veritabanı hakkındaki sorusunu analiz edip en uygun skill'i seç.

Mevcut skill'ler:
{skill_descriptions}

Aksiyon skill'leri (dikkatli kullan, DB değişikliği yapar):
{action_descriptions}

YANIT FORMATI (sadece JSON, başka bir şey yazma):
{{"intent": "skill_name", "params": {{}}}}

Eğer aksiyon ise:
{{"intent": "action:vacuum", "params": {{"table_name": "public.users"}}}}
{{"intent": "action:kill_query", "params": {{"pid": 12345, "force": false}}}}

Hiçbir skill uymuyorsa:
{{"intent": "general_chat", "params": {{}}}}

ÖNEMLİ: "veritabanı neden yavaş", "ne oluyor", "sorun ne" gibi genel sorularda → "performance_summary" kullan.
"""

    result = await _llm_chat(system_prompt, message)

    if not result:
        return None, None

    try:
        # JSON çıkar
        json_match = re.search(r'\{[^{}]+\}', result)
        if json_match:
            parsed = json.loads(json_match.group())
            return parsed.get("intent"), parsed.get("params", {})
    except (json.JSONDecodeError, AttributeError):
        pass

    return None, None


async def detect_intent(message: str) -> Tuple[str, dict]:
    """
    Mesajdan intent ve parametreleri tespit et.
    Önce keyword match, başarısız olursa LLM ile dener.
    Returns: (intent_name, params_dict)
    """
    msg_stripped = message.strip()

    # 1. Komut parse — aksiyon parametrelerini çıkar
    parts = msg_stripped.split(maxsplit=1)
    first_word = parts[0].lower() if parts else ""
    rest = parts[1].strip() if len(parts) > 1 else ""

    # Aksiyon komutları
    if first_word in ACTION_COMMAND_MAP:
        action = ACTION_COMMAND_MAP[first_word]
        params = {}

        if action == "vacuum" and rest:
            params["table_name"] = rest
        elif action == "reindex" and rest:
            params["table_name"] = rest
        elif action == "kill_query" and rest:
            try:
                pid_str = rest.split()[0]
                params["pid"] = int(pid_str)
                params["force"] = "force" in rest.lower() or "zorla" in rest.lower()
            except ValueError:
                pass

        return f"action:{action}", params

    # 2. Keyword match
    keyword_result = _keyword_intent(msg_stripped)
    if keyword_result:
        return keyword_result, {}

    # 3. LLM intent detection
    llm_intent, llm_params = await _llm_intent(msg_stripped)
    if llm_intent and llm_intent != "general_chat":
        return llm_intent, llm_params or {}

    # 4. Fallback → performance_summary (genel soru kabul et)
    return "general_chat", {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SKILL EXECUTOR — Beceri çalıştırma
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def execute_skill(intent: str, params: dict, db_id: str = None) -> dict:
    """Intent'e göre uygun skill'i çalıştır ve sonuç döndür."""
    from server.clawbot.skills import SKILL_REGISTRY, ACTION_SKILLS

    if intent.startswith("action:"):
        action_name = intent.replace("action:", "")
        if action_name not in ACTION_SKILLS:
            return {"error": f"Bilinmeyen aksiyon: {action_name}"}

        skill = ACTION_SKILLS[action_name]
        fn = skill["fn"]
        required_param = skill["requires_param"]

        if required_param not in params:
            return {
                "error": f"Aksiyon '{action_name}' için '{required_param}' parametresi gerekli",
                "usage": f"/{action_name} <{required_param}>",
            }

        try:
            return fn(**params, db_id=db_id)
        except Exception as e:
            return {"error": str(e)[:300]}

    if intent in SKILL_REGISTRY:
        skill = SKILL_REGISTRY[intent]
        fn = skill["fn"]
        # Varsayılan parametreleri kullan, override'ları uygula
        call_params = {**skill.get("params", {}), **params}

        try:
            return fn(**call_params, db_id=db_id)
        except Exception as e:
            return {"error": str(e)[:300]}

    return {"error": f"Bilinmeyen intent: {intent}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RESPONSE FORMATTER — Yanıt formatlama
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _format_overview(data: dict) -> str:
    """Genel durum yanıtını formatla."""
    if "error" in data:
        return f"❌ Hata: {data['error']}"

    lines = ["🤖 *ClawBot — Veritabanı Genel Durumu*\n"]
    lines.append(f"🐘 {data.get('version', '?')}")
    lines.append(f"⏱ Uptime: {data.get('uptime', '?')}")

    conn = data.get("connections", {})
    lines.append(f"🔗 Bağlantılar: {conn.get('active', '?')}/{conn.get('max', '?')} (%{conn.get('usage_pct', 0)})")

    lines.append(f"\n💾 Toplam Boyut: {data.get('total_size', '?')}")
    lines.append(f"📁 Veritabanı Sayısı: {data.get('database_count', 0)}")

    for db in data.get("databases", []):
        lines.append(f"  • {db['name']}: {db['size']}")

    return "\n".join(lines)


def _format_health(data: dict) -> str:
    """Sağlık raporu yanıtını formatla."""
    if "error" in data:
        return f"❌ Hata: {data['error']}"

    status = data.get("status", "unknown")
    status_icon = {"healthy": "✅", "warning": "⚠️", "critical": "🔴"}.get(status, "❓")

    lines = [f"🤖 *ClawBot — Sağlık Raporu* {status_icon}\n"]

    metrics = data.get("metrics", {})
    lines.append(f"📊 Cache Hit: %{metrics.get('cache_hit_ratio', '?')}")
    lines.append(f"📊 Commit Ratio: %{metrics.get('commit_ratio', '?')}")
    lines.append(f"🔗 Bağlantı Kullanımı: %{metrics.get('connection_usage_pct', '?')}")
    lines.append(f"🐌 30s+ Sorgu: {metrics.get('long_running_queries', 0)}")
    lines.append(f"🔒 Kilit Bekleyen: {metrics.get('waiting_locks', 0)}")

    dead_tables = metrics.get("dead_tuple_tables", [])
    if dead_tables:
        lines.append("\n🗑 *Yüksek Dead Tuple:*")
        for t in dead_tables[:3]:
            lines.append(f"  • {t['table']}: {t['dead_tuples']:,} dead (%{t['dead_pct']})")

    issues = data.get("issues", [])
    if issues:
        lines.append("\n⚡ *Tespit Edilen Sorunlar:*")
        for issue in issues:
            icon = "🔴" if issue["severity"] == "critical" else "⚠️"
            lines.append(f"  {icon} {issue['msg']}")
    else:
        lines.append("\n✅ Sorun tespit edilmedi.")

    return "\n".join(lines)


def _format_slow_queries(data: dict) -> str:
    """Yavaş sorgular yanıtını formatla."""
    if "error" in data:
        return f"❌ Hata: {data['error']}"

    if not data.get("extension_available", True):
        return "⚠️ pg_stat_statements eklentisi yüklü değil.\n\nETKİNLEŞTİRME:\n`CREATE EXTENSION IF NOT EXISTS pg_stat_statements;`"

    queries = data.get("queries", [])
    if not queries:
        return "✅ Belirtilen eşiğin üzerinde yavaş sorgu bulunamadı."

    lines = [f"🤖 *ClawBot — En Yavaş {len(queries)} Sorgu*\n"]
    for i, q in enumerate(queries, 1):
        short = q["query"][:120].replace("\n", " ")
        lines.append(
            f"*{i}.* ⏱ Avg: `{q['avg_ms']}ms` | Çağrı: `{q['calls']}` | Satır: `{q['rows']}`\n"
            f"  `{short}...`\n"
        )

    return "\n".join(lines)


def _format_active(data: dict) -> str:
    """Aktif sorgular yanıtını formatla."""
    queries = data.get("queries", [])
    if not queries:
        return "✅ Şu an çalışan aktif sorgu yok."

    lines = [f"🤖 *ClawBot — Aktif Sorgular ({len(queries)})*\n"]
    for q in queries:
        short = q["query"][:100].replace("\n", " ")
        lines.append(
            f"🔹 PID `{q['pid']}` | `{q['user']}@{q['database']}` | ⏱ `{q['duration']}`\n"
            f"  `{short}...`\n"
        )

    return "\n".join(lines)


def _format_locks(data: dict) -> str:
    """Kilitler yanıtını formatla."""
    locks = data.get("locks", [])
    if not locks:
        return "✅ Kilit bekleyen sorgu yok."

    lines = [f"🤖 *ClawBot — Kilit Bekleyen Sorgular ({len(locks)})*\n"]
    for lk in locks:
        lines.append(
            f"🚫 PID `{lk['blocked_pid']}` (`{lk['blocked_user']}`) bekliyor ⏱ `{lk['wait_duration']}`\n"
            f"  → Kilitleyen: PID `{lk['blocking_pid']}` (`{lk['blocking_user']}`)\n"
        )

    return "\n".join(lines)


def _format_tables(data: dict) -> str:
    """Tablo istatistikleri yanıtını formatla."""
    tables = data.get("tables", [])
    if not tables:
        return "ℹ️ Kullanıcı tablosu bulunamadı."

    lines = [f"🤖 *ClawBot — Tablo İstatistikleri ({len(tables)})*\n"]
    for t in tables:
        lines.append(
            f"📋 `{t['name']}`\n"
            f"   Boyut: `{t['size']}` | Satır: `{t['live_rows']:,}` | Dead: `{t['dead_rows']:,}`\n"
            f"   Index Kullanımı: %{t['index_usage_pct']} | Son VACUUM: `{t['last_vacuum']}`\n"
        )

    return "\n".join(lines)


def _format_index_recs(data: dict) -> str:
    """Index önerileri yanıtını formatla."""
    recs = data.get("recommendations", [])
    unused = data.get("analysis", {}).get("unused_indexes", [])

    if not recs and not unused:
        return "✅ Index yapısı iyi durumda."

    lines = ["🤖 *ClawBot — Index Analizi*\n"]

    if recs:
        lines.append("📊 *Index İyileştirme Önerileri:*")
        for r in recs:
            sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(r["severity"], "⚪")
            lines.append(
                f"  {sev_icon} `{r['table']}` — Seq: {r['seq_scan']:,} | Idx: {r['idx_scan']:,} | Index: %{r['index_usage_pct']}"
            )
            if r.get("suggestion"):
                lines.append(f"     {r['suggestion']}")
            lines.append("")

    if unused:
        lines.append("🗑 *Kullanılmayan Index'ler (silinebilir):*")
        for u in unused:
            lines.append(f"  • `{u['index']}` on `{u['table']}` ({u['size']})")

    return "\n".join(lines)


def _format_performance(data: dict) -> str:
    """Performans özeti yanıtını formatla."""
    if "error" in data:
        return f"❌ Hata: {data['error']}"

    lines = ["🤖 *ClawBot — Performans Analiz Raporu*\n"]
    lines.append(f"📅 {data.get('timestamp', '')[:19]}\n")

    # Health summary
    health = data.get("health", {})
    status = health.get("status", "unknown")
    status_icon = {"healthy": "✅", "warning": "⚠️", "critical": "🔴"}.get(status, "❓")
    lines.append(f"🏥 Genel Durum: {status_icon} *{status.upper()}*\n")

    # Overview
    overview = data.get("overview", {})
    if overview:
        lines.append(f"🐘 {overview.get('version', '?')}")
        lines.append(f"⏱ Uptime: {overview.get('uptime', '?')}")
        conn = overview.get("connections", {})
        lines.append(f"🔗 Bağlantılar: {conn.get('active', '?')}/{conn.get('max', '?')}")
        lines.append(f"💾 DB Boyutu: {overview.get('current_db_size', '?')}")

    # Issues
    issues = health.get("issues", [])
    if issues:
        lines.append(f"\n⚡ *Tespit Edilen Sorunlar ({len(issues)}):*")
        for issue in issues[:5]:
            icon = "🔴" if issue["severity"] == "critical" else "⚠️"
            lines.append(f"  {icon} {issue['msg']}")

    # Slow queries
    slow = data.get("slow_queries", [])
    if slow:
        lines.append(f"\n🐌 *En Yavaş {len(slow)} Sorgu:*")
        for i, sq in enumerate(slow[:3], 1):
            lines.append(f"  {i}. Avg: `{sq['avg_ms']}ms` — `{sq['query'][:80]}...`")

    # Locks
    locks = data.get("locks", [])
    if locks:
        lines.append(f"\n🔒 *Kilit Bekleyen: {len(locks)} sorgu*")

    # Actions suggested
    actions = data.get("actions_suggested", [])
    if actions:
        lines.append(f"\n💡 *Önerilen Aksiyonlar:*")
        for a in actions[:5]:
            action_name = a.get("action", "?")
            reason = a.get("reason", "")
            if action_name == "vacuum":
                lines.append(f"  🗑 VACUUM → `{a.get('table', '?')}` — {reason}")
            elif action_name == "create_index":
                lines.append(f"  📑 INDEX → `{a.get('table', '?')}` — {reason}")
            elif action_name == "optimize_query":
                lines.append(f"  ⚡ OPTIMIZE → `{a.get('query', '?')[:60]}...`")
            elif action_name == "investigate_locks":
                lines.append(f"  🔒 LOCK INVESTIGATION — {reason}")
    else:
        if not issues:
            lines.append("\n✅ Herhangi bir aksiyon gerekmemektedir.")

    return "\n".join(lines)


def _format_action(intent: str, data: dict) -> str:
    """Aksiyon sonucunu formatla."""
    if "error" in data:
        return f"❌ Hata: {data['error']}"

    action_name = intent.replace("action:", "")

    if action_name == "vacuum":
        if data.get("success"):
            return (
                f"✅ *VACUUM ANALYZE tamamlandı*\n\n"
                f"📋 Tablo: `{data.get('table', '?')}`\n"
                f"🗑 Dead tuple: {data.get('dead_before', 0):,} → {data.get('dead_after', 0):,}\n"
                f"🧹 Temizlenen: {data.get('cleaned', 0):,}"
            )
        return f"❌ VACUUM başarısız: {data.get('error', 'Bilinmeyen hata')}"

    if action_name == "reindex":
        if data.get("success"):
            return f"✅ *REINDEX tamamlandı*\n\n📋 Tablo: `{data.get('table', '?')}`"
        return f"❌ REINDEX başarısız: {data.get('error', 'Bilinmeyen hata')}"

    if action_name == "kill_query":
        if data.get("success"):
            action_type = data.get("action", "cancel")
            target = data.get("target", {})
            return (
                f"✅ *Sorgu {'sonlandırıldı' if action_type == 'terminate' else 'iptal edildi'}*\n\n"
                f"👤 Kullanıcı: `{target.get('user', '?')}`\n"
                f"📝 Sorgu: `{target.get('query', '?')[:100]}...`"
            )
        return f"❌ Sorgu durdurulamadı: {data.get('error', 'Bilinmeyen hata')}"

    return json.dumps(data, ensure_ascii=False, indent=2)


# Formatter registry
_FORMATTERS = {
    "db_overview": _format_overview,
    "health_check": _format_health,
    "slow_queries": _format_slow_queries,
    "active_queries": _format_active,
    "locks": _format_locks,
    "table_stats": _format_tables,
    "index_recommendations": _format_index_recs,
    "performance_summary": _format_performance,
}


def format_response(intent: str, data: dict) -> str:
    """Intent'e göre uygun formatlayıcı ile yanıt üret."""
    if intent.startswith("action:"):
        return _format_action(intent, data)

    formatter = _FORMATTERS.get(intent)
    if formatter:
        return formatter(data)

    # Bilinmeyen intent — JSON döndür
    return f"🤖 *ClawBot Yanıtı:*\n\n```\n{json.dumps(data, ensure_ascii=False, indent=2)[:2000]}\n```"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LLM ENRICHMENT — Yanıtı zenginleştirme
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _enrich_with_llm(user_message: str, raw_data: dict, formatted: str, intent: str) -> str:
    """
    Ham veri + formatlı yanıt + kullanıcı sorusunu LLM'e gönderip
    daha detaylı, konuşma dilinde yanıt üret.
    """
    system_prompt = """Sen Anomivox ClawBot — otonom PostgreSQL veritabanı asistanısın.
Kullanıcının veritabanı sorusuna veritabanından toplanan gerçek verilerle yanıt ver.

Kurallar:
1. Kısa ve net yanıtlar ver
2. Emoji kullan ama aşırıya kaçma
3. Kritik sorunları vurgula
4. Somut aksiyon önerileri sun
5. Türkçe ve İngilizce soru anlayabilirsin, soruldugu dilde yanıt ver
6. Markdown formatı kullan (* bold, ` code)
7. Veriyi olduğu gibi rapor et, uydurma

Aşağıda veritabanından toplanan gerçek zamanlı veriler var. Bu verileri kullanarak kullanıcının sorusunu yanıtla."""

    user_msg = f"""Kullanıcı Sorusu: {user_message}

Tespit Edilen Intent: {intent}

Veritabanından Toplanan Ham Veri:
{json.dumps(raw_data, ensure_ascii=False, default=str)[:3000]}

Formatlı Rapor:
{formatted[:2000]}

Lütfen yukarıdaki verilere dayanarak kullanıcının sorusunu yanıtla. 
Eğer soruya veritabanı verileriyle cevaplanamıyorsa, elindeki verilerden en yakın sonucu sun."""

    enriched = await _llm_chat(system_prompt, user_msg)

    if enriched and len(enriched) > 20:
        return enriched

    # LLM çağrısı başarısız olursa formatlı yanıtı döndür
    return formatted


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GENERAL CHAT — LLM ile serbest sohbet (DB konulu)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _handle_general_chat(message: str, db_id: str = None) -> str:
    """
    Hiçbir skill'e uymayan sorularda — önce performans özetini topla,
    sonra LLM ile yanıt ver.
    """
    # DB verisini topla
    try:
        from server.clawbot.skills import skill_performance_summary
        raw_data = skill_performance_summary(db_id=db_id)
    except Exception:
        raw_data = {}

    system_prompt = """Sen Anomivox ClawBot — otonom PostgreSQL veritabanı asistanısın.
Kullanıcıyla doğal dilde sohbet ederek veritabanı sorunlarını çözersin.

Yeteneklerin:
- Veritabanı durumu sorgulama
- Sağlık kontrolü ve performans analizi
- Yavaş sorgu tespiti
- Index önerisi
- VACUUM, REINDEX, Kill Query gibi müdahaleler

Aşağıda veritabanının güncel durumu var. Bu bilgileri kullanarak yanıt ver.
Soruldugu dilde yanıt ver (Türkçe veya İngilizce)."""

    user_msg = f"""Kullanıcı: {message}

Veritabanı Güncel Durumu:
{json.dumps(raw_data, ensure_ascii=False, default=str)[:3000]}"""

    result = await _llm_chat(system_prompt, user_msg)

    if result:
        return result

    # LLM yoksa fallback
    return (
        "🤖 *ClawBot*\n\n"
        "Sorunuzu anladım ancak şu an LLM modeli yapılandırılmamış.\n\n"
        "Kullanabileceğiniz komutlar:\n"
        "• `/status` — Genel durum\n"
        "• `/health` — Sağlık raporu\n"
        "• `/slow` — Yavaş sorgular\n"
        "• `/active` — Aktif sorgular\n"
        "• `/locks` — Kilitler\n"
        "• `/tables` — Tablo istatistikleri\n"
        "• `/index` — Index önerileri\n"
        "• `/performance` — Kapsamlı analiz\n"
        "• `/vacuum <tablo>` — VACUUM çalıştır\n"
        "• `/reindex <tablo>` — REINDEX çalıştır\n"
        "• `/kill <pid>` — Sorgu durdur"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ANA FONKSİYON — process_message
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def process_message(
    message: str,
    channel: str = "api",
    user_id: str = None,
    use_llm_enrichment: bool = True,
    db_id: str = None,
) -> dict:
    """
    Ana ClawBot mesaj işleme fonksiyonu.
    
    Args:
        message: Kullanıcı mesajı (doğal dil veya komut)
        channel: Kaynak kanal ("telegram", "whatsapp", "mail", "api", "webui")
        user_id: Kullanıcı kimliği (kanal bazlı)
        use_llm_enrichment: LLM ile yanıtı zenginleştir
        db_id: Hangi veritabanı bağlantısını kullanacağı (Multi-DB)
    
    Returns:
        {
            "intent": str,
            "response": str,       # Formatlı metin yanıtı
            "raw_data": dict,      # Ham skill verisi
            "channel": str,
            "timestamp": str,
            "db_id": str,
        }
    """
    start_time = datetime.now()
    logger.info(f"[{channel}] Message from {user_id}: {message[:100]}")

    # 1. Intent Detection
    intent, params = await detect_intent(message)
    logger.info(f"[{channel}] Intent: {intent}, Params: {params}")

    # 2. General chat — LLM destekli serbest sohbet
    if intent == "general_chat":
        response = await _handle_general_chat(message, db_id=db_id)
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"[{channel}] General chat response in {elapsed:.1f}s")
        return {
            "intent": intent,
            "response": response,
            "raw_data": {},
            "channel": channel,
            "timestamp": start_time.isoformat(),
            "elapsed_sec": elapsed,
            "db_id": db_id or "default",
        }

    # 3. Skill Execution
    try:
        raw_data = execute_skill(intent, params, db_id=db_id)
    except Exception as e:
        logger.error(f"Skill execution error: {e}")
        raw_data = {"error": str(e)[:300]}

    # 4. Formatlı yanıt
    formatted = format_response(intent, raw_data)

    # 5. LLM Enrichment (isteğe bağlı)
    if use_llm_enrichment and "error" not in raw_data:
        try:
            enriched = await _enrich_with_llm(message, raw_data, formatted, intent)
            response = enriched
        except Exception as e:
            logger.warning(f"LLM enrichment failed: {e}")
            response = formatted
    else:
        response = formatted

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"[{channel}] Response for '{intent}' in {elapsed:.1f}s")

    return {
        "intent": intent,
        "response": response,
        "raw_data": raw_data,
        "channel": channel,
        "timestamp": start_time.isoformat(),
        "elapsed_sec": elapsed,
        "db_id": db_id or "default",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PROACTIVE — Periyodik otonom analiz
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def proactive_analysis() -> Optional[str]:
    """
    Otonom proaktif analiz — sorun tespit ederse yanıt döndürür.
    Cron/scheduler ile periyodik çağrılır.
    Tüm kanallara (Telegram, WhatsApp, Mail) bildirim göndermek için kullanılır.
    """
    try:
        from server.clawbot.skills import skill_health_check, skill_slow_queries

        health = skill_health_check()
        slow = skill_slow_queries(threshold_ms=5000, limit=3)

        problems = []

        # Kritik sağlık sorunları
        for issue in health.get("issues", []):
            if issue["severity"] == "critical":
                problems.append(f"🔴 {issue['msg']}")
            elif issue["severity"] == "warning":
                problems.append(f"⚠️ {issue['msg']}")

        # Çok yavaş sorgular
        for sq in slow.get("queries", []):
            if sq["avg_ms"] > 10000:
                problems.append(f"🐌 Aşırı yavaş sorgu: avg {sq['avg_ms']}ms — `{sq['query'][:80]}...`")

        if not problems:
            return None  # Sorun yok, bildirim gönderme

        report = "🤖 *ClawBot — Proaktif Uyarı*\n\n"
        report += "\n".join(problems)
        report += f"\n\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        report += "\n\nDetay için: `/performance` veya `/health` komutunu kullanın."

        return report

    except Exception as e:
        logger.error(f"Proactive analysis error: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  YARDIMCI — Komut listesi
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_help_text() -> str:
    """ClawBot yardım metni."""
    return (
        "🤖 *Anomivox ClawBot — Otonom DB Asistanı*\n\n"
        "Doğal dilde soru sorabilir veya komut kullanabilirsiniz:\n\n"
        "📊 *Sorgulama:*\n"
        "  `/status` — Genel durum özeti\n"
        "  `/health` — Kapsamlı sağlık raporu\n"
        "  `/slow` — Yavaş sorgular\n"
        "  `/active` — Aktif sorgular\n"
        "  `/locks` — Kilit bekleyen sorgular\n"
        "  `/tables` — Tablo istatistikleri\n"
        "  `/index` — Index analizi ve önerileri\n"
        "  `/performance` — Komple performans analizi\n\n"
        "⚡ *Müdahale:*\n"
        "  `/vacuum <tablo>` — VACUUM ANALYZE\n"
        "  `/reindex <tablo>` — REINDEX\n"
        "  `/kill <pid>` — Sorguyu durdur\n\n"
        "💬 *Doğal Dil:*\n"
        '  "Veritabanı neden yavaş?"\n'
        '  "Kaç veritabanı var?"\n'
        '  "Doluluğu nedir?"\n'
        '  "Index önerisi ver"\n'
        '  "Slow query bul"\n\n'
        "🔔 Proaktif izleme ile sorun tespit edildiğinde\n"
        "   otomatik bildirim gönderilir."
    )
