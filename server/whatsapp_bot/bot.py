"""
Anomivox WhatsApp Bot — Otonom Veritabanı Yönetim Asistanı
WhatsApp Business Cloud API üzerinden çalışır.

Komutlar (mesaj olarak gönderilir):
  /status     — Sistem durumu özeti
  /health     — Veritabanı sağlık kontrolü
  /slow       — Yavaş sorgular
  /active     — Aktif sorgular
  /locks      — Lock bilgileri
  /db_size    — Veritabanı boyutu
  /tables     — Tablo istatistikleri
  /alerts     — Son alertler
  /diagnose   — Teşhis başlat
  /report     — Son rapor
  /help       — Komut listesi
"""

import os
import sys
import json
import asyncio
import logging
import signal
from datetime import datetime

import aiohttp

# Proje kökünü Python path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("anomivox.whatsapp")


# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────
def _load_config():
    """Load WhatsApp config from configs module."""
    try:
        from configs.whatsapp_config import (
            WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID,
            WHATSAPP_BUSINESS_ACCOUNT_ID, WHATSAPP_VERIFY_TOKEN,
            WHATSAPP_ALLOWED_NUMBERS, WHATSAPP_API_URL,
            WHATSAPP_PROMETHEUS_URL,
            WHATSAPP_PG_HOST, WHATSAPP_PG_PORT,
            WHATSAPP_PG_USER, WHATSAPP_PG_PASSWORD, WHATSAPP_PG_DB,
            WHATSAPP_NOTIFY_ON_ALERT, WHATSAPP_NOTIFY_ON_DIAGNOSIS,
            WHATSAPP_AUTO_DIAGNOSE, WHATSAPP_HEALTH_CHECK_INTERVAL,
            WHATSAPP_SLOW_QUERY_THRESHOLD,
        )
        return {
            "access_token": WHATSAPP_ACCESS_TOKEN,
            "phone_number_id": WHATSAPP_PHONE_NUMBER_ID,
            "business_account_id": WHATSAPP_BUSINESS_ACCOUNT_ID,
            "verify_token": WHATSAPP_VERIFY_TOKEN,
            "allowed_numbers": WHATSAPP_ALLOWED_NUMBERS,
            "api_url": WHATSAPP_API_URL,
            "prometheus_url": WHATSAPP_PROMETHEUS_URL,
            "pg_host": WHATSAPP_PG_HOST,
            "pg_port": WHATSAPP_PG_PORT,
            "pg_user": WHATSAPP_PG_USER,
            "pg_password": WHATSAPP_PG_PASSWORD,
            "pg_db": WHATSAPP_PG_DB,
            "notify_on_alert": WHATSAPP_NOTIFY_ON_ALERT,
            "notify_on_diagnosis": WHATSAPP_NOTIFY_ON_DIAGNOSIS,
            "auto_diagnose": WHATSAPP_AUTO_DIAGNOSE,
            "health_check_interval": WHATSAPP_HEALTH_CHECK_INTERVAL,
            "slow_query_threshold": WHATSAPP_SLOW_QUERY_THRESHOLD,
        }
    except ImportError as e:
        logger.error(f"Config import hatası: {e}")
        return None


CONFIG = _load_config()
GRAPH_API_URL = "https://graph.facebook.com/v21.0"


# ─────────────────────────────────────────
# WhatsApp Cloud API — Mesaj Gönderme
# ─────────────────────────────────────────
async def send_whatsapp_message(to: str, text: str, session: aiohttp.ClientSession = None):
    """WhatsApp Cloud API üzerinden mesaj gönder."""
    if not CONFIG or not CONFIG["access_token"] or not CONFIG["phone_number_id"]:
        logger.warning("WhatsApp API bilgileri eksik, mesaj gönderilemedi.")
        return False

    url = f"{GRAPH_API_URL}/{CONFIG['phone_number_id']}/messages"
    headers = {
        "Authorization": f"Bearer {CONFIG['access_token']}",
        "Content-Type": "application/json",
    }

    # WhatsApp mesaj limiti 4096 karakter
    MAX_LEN = 4000
    chunks = [text[i:i + MAX_LEN] for i in range(0, len(text), MAX_LEN)]

    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    try:
        for chunk in chunks:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"preview_url": False, "body": chunk},
            }
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    logger.error(f"WhatsApp mesaj gönderim hatası: {resp.status} — {err}")
                    return False
        return True
    except Exception as e:
        logger.error(f"WhatsApp mesaj gönderim exception: {e}")
        return False
    finally:
        if own_session:
            await session.close()


async def send_to_default(text: str, session: aiohttp.ClientSession = None):
    """Config'deki varsayılan numaraya bildirim gönder (ilk allowed number veya env)."""
    # Varsayılan alıcı: env'den gelen WHATSAPP_DEFAULT_RECIPIENT ya da ilk allowed number
    recipient = os.getenv("WHATSAPP_DEFAULT_RECIPIENT", "")
    if not recipient and CONFIG and CONFIG.get("allowed_numbers"):
        recipient = CONFIG["allowed_numbers"][0]
    if not recipient:
        logger.warning("Varsayılan WhatsApp alıcısı yok.")
        return False
    return await send_whatsapp_message(recipient, text, session)


# ─────────────────────────────────────────
# PostgreSQL Sorguları
# ─────────────────────────────────────────
def _pg_query(query: str, params=None) -> list:
    """PostgreSQL'e bağlan, sorgu çalıştır, sonuç döndür."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=CONFIG["pg_host"],
            port=CONFIG["pg_port"],
            user=CONFIG["pg_user"],
            password=CONFIG["pg_password"],
            dbname=CONFIG["pg_db"],
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(query, params)
        if cur.description:
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            result = [dict(zip(cols, r)) for r in rows]
        else:
            result = []
        cur.close()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"PG query hatası: {e}")
        return []


# ─────────────────────────────────────────
# Komut İşleyiciler
# ─────────────────────────────────────────
async def cmd_help(sender: str, session: aiohttp.ClientSession):
    text = (
        "🤖 *Anomivox WhatsApp Bot*\n\n"
        "📋 *Komutlar:*\n"
        "/status — Sistem durumu\n"
        "/health — DB sağlık kontrolü\n"
        "/slow — Yavaş sorgular\n"
        "/active — Aktif sorgular\n"
        "/locks — Lock bilgileri\n"
        "/db_size — Veritabanı boyutu\n"
        "/tables — Tablo istatistikleri\n"
        "/alerts — Son Prometheus alertleri\n"
        "/diagnose — Teşhis başlat\n"
        "/report — Son rapor\n"
        "/help — Bu mesaj"
    )
    await send_whatsapp_message(sender, text, session)


async def cmd_status(sender: str, session: aiohttp.ClientSession):
    lines = ["📊 *Sistem Durumu*\n"]

    # DB bağlantısı
    try:
        rows = _pg_query("SELECT version() as ver")
        if rows:
            lines.append(f"✅ PostgreSQL: Bağlı")
            lines.append(f"📌 {rows[0]['ver'][:60]}")
        else:
            lines.append("❌ PostgreSQL: Bağlantı yok")
    except Exception:
        lines.append("❌ PostgreSQL: Bağlantı hatası")

    # DB boyutu
    rows = _pg_query("SELECT pg_size_pretty(pg_database_size(current_database())) as size")
    if rows:
        lines.append(f"💾 DB Boyutu: {rows[0]['size']}")

    # Aktif bağlantılar
    rows = _pg_query("SELECT count(*) as cnt FROM pg_stat_activity WHERE state = 'active'")
    if rows:
        lines.append(f"🔗 Aktif Bağlantılar: {rows[0]['cnt']}")

    # Prometheus
    try:
        async with session.get(f"{CONFIG['prometheus_url']}/-/healthy", timeout=aiohttp.ClientTimeout(total=5)) as resp:
            lines.append(f"✅ Prometheus: {'Sağlıklı' if resp.status == 200 else 'Hata'}")
    except Exception:
        lines.append("⚠️ Prometheus: Erişilemiyor")

    await send_whatsapp_message(sender, "\n".join(lines), session)


async def cmd_health(sender: str, session: aiohttp.ClientSession):
    lines = ["🏥 *Sağlık Kontrolü*\n"]
    issues = 0

    # Aktif bağlantı sayısı
    rows = _pg_query("SELECT count(*) as cnt FROM pg_stat_activity")
    rows_max = _pg_query("SHOW max_connections")
    if rows and rows_max:
        cnt = rows[0]["cnt"]
        mx = int(rows_max[0]["max_connections"])
        pct = round(cnt / mx * 100, 1)
        status = "🟢" if pct < 70 else ("🟡" if pct < 90 else "🔴")
        lines.append(f"{status} Bağlantılar: {cnt}/{mx} ({pct}%)")
        if pct >= 80:
            issues += 1

    # Yavaş sorgular
    threshold = CONFIG.get("slow_query_threshold", 5.0)
    rows = _pg_query(
        "SELECT count(*) as cnt FROM pg_stat_activity WHERE state='active' AND now()-query_start > interval '%s seconds'",
        (threshold,)
    )
    if rows:
        cnt = rows[0]["cnt"]
        status = "🟢" if cnt == 0 else "🔴"
        lines.append(f"{status} Yavaş Sorgular (>{threshold}s): {cnt}")
        if cnt > 0:
            issues += 1

    # Lock'lar
    rows = _pg_query("SELECT count(*) as cnt FROM pg_locks WHERE NOT granted")
    if rows:
        cnt = rows[0]["cnt"]
        status = "🟢" if cnt == 0 else "🟡"
        lines.append(f"{status} Bekleyen Lock: {cnt}")
        if cnt > 0:
            issues += 1

    # Dead tuples (bloat)
    rows = _pg_query(
        "SELECT schemaname||'.'||relname as tbl, n_dead_tup FROM pg_stat_user_tables "
        "WHERE n_dead_tup > 10000 ORDER BY n_dead_tup DESC LIMIT 3"
    )
    if rows:
        lines.append(f"🟡 Yüksek Dead Tuple:")
        for r in rows:
            lines.append(f"   {r['tbl']}: {r['n_dead_tup']:,}")
        issues += 1
    else:
        lines.append("🟢 Dead Tuples: Normal")

    lines.append(f"\n{'⚠️ ' + str(issues) + ' sorun tespit edildi' if issues else '✅ Sistem sağlıklı'}")
    await send_whatsapp_message(sender, "\n".join(lines), session)


async def cmd_slow_queries(sender: str, session: aiohttp.ClientSession):
    threshold = CONFIG.get("slow_query_threshold", 5.0)
    rows = _pg_query(
        "SELECT pid, usename, now()-query_start as duration, left(query, 150) as query "
        "FROM pg_stat_activity WHERE state='active' AND now()-query_start > interval '%s seconds' "
        "ORDER BY query_start LIMIT 10",
        (threshold,)
    )
    if not rows:
        await send_whatsapp_message(sender, f"✅ Yavaş sorgu yok (>{threshold}s)", session)
        return

    lines = [f"🐌 *Yavaş Sorgular (>{threshold}s)*\n"]
    for r in rows:
        lines.append(f"PID: {r['pid']} | {r['usename']} | {r['duration']}")
        lines.append(f"```{r['query']}```\n")
    await send_whatsapp_message(sender, "\n".join(lines), session)


async def cmd_active_queries(sender: str, session: aiohttp.ClientSession):
    rows = _pg_query(
        "SELECT pid, usename, state, now()-query_start as duration, left(query, 120) as query "
        "FROM pg_stat_activity WHERE state != 'idle' AND pid != pg_backend_pid() "
        "ORDER BY query_start LIMIT 10"
    )
    if not rows:
        await send_whatsapp_message(sender, "✅ Aktif sorgu yok", session)
        return

    lines = [f"⚡ *Aktif Sorgular ({len(rows)})*\n"]
    for r in rows:
        lines.append(f"PID {r['pid']} | {r['usename']} | {r['state']} | {r['duration']}")
        lines.append(f"```{r['query']}```\n")
    await send_whatsapp_message(sender, "\n".join(lines), session)


async def cmd_locks(sender: str, session: aiohttp.ClientSession):
    rows = _pg_query(
        "SELECT bl.pid AS blocked_pid, a.usename AS blocked_user, "
        "kl.pid AS blocking_pid, ka.usename AS blocking_user, "
        "a.query AS blocked_query "
        "FROM pg_catalog.pg_locks bl "
        "JOIN pg_catalog.pg_stat_activity a ON a.pid = bl.pid "
        "JOIN pg_catalog.pg_locks kl ON kl.transactionid = bl.transactionid AND kl.pid != bl.pid "
        "JOIN pg_catalog.pg_stat_activity ka ON ka.pid = kl.pid "
        "WHERE NOT bl.granted LIMIT 10"
    )
    if not rows:
        await send_whatsapp_message(sender, "✅ Bekleyen lock yok", session)
        return

    lines = ["🔒 *Bekleyen Lock'lar*\n"]
    for r in rows:
        lines.append(
            f"Blocked PID {r['blocked_pid']} ({r['blocked_user']}) ← "
            f"Blocking PID {r['blocking_pid']} ({r['blocking_user']})"
        )
        lines.append(f"```{r['blocked_query'][:120]}```\n")
    await send_whatsapp_message(sender, "\n".join(lines), session)


async def cmd_db_size(sender: str, session: aiohttp.ClientSession):
    rows = _pg_query(
        "SELECT current_database() as db, pg_size_pretty(pg_database_size(current_database())) as size"
    )
    lines = ["💾 *Veritabanı Boyutu*\n"]
    if rows:
        lines.append(f"DB: {rows[0]['db']} → {rows[0]['size']}")

    rows2 = _pg_query(
        "SELECT schemaname||'.'||tablename as tbl, "
        "pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size "
        "FROM pg_tables WHERE schemaname='public' "
        "ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10"
    )
    if rows2:
        lines.append("\n📊 *En Büyük Tablolar:*")
        for r in rows2:
            lines.append(f"  {r['tbl']}: {r['size']}")

    await send_whatsapp_message(sender, "\n".join(lines), session)


async def cmd_tables(sender: str, session: aiohttp.ClientSession):
    rows = _pg_query(
        "SELECT schemaname||'.'||relname as tbl, n_live_tup, n_dead_tup, "
        "last_vacuum, last_autovacuum, last_analyze "
        "FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 10"
    )
    if not rows:
        await send_whatsapp_message(sender, "ℹ️ Kullanıcı tablosu bulunamadı", session)
        return

    lines = ["📋 *Tablo İstatistikleri*\n"]
    for r in rows:
        lines.append(f"*{r['tbl']}*")
        lines.append(f"  Live: {r['n_live_tup']:,} | Dead: {r['n_dead_tup']:,}")
        lv = str(r.get('last_autovacuum') or r.get('last_vacuum') or '-')[:16]
        lines.append(f"  Son Vacuum: {lv}\n")
    await send_whatsapp_message(sender, "\n".join(lines), session)


async def cmd_alerts(sender: str, session: aiohttp.ClientSession):
    try:
        async with session.get(
            f"{CONFIG['prometheus_url']}/api/v1/alerts",
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            data = await resp.json()
    except Exception as e:
        await send_whatsapp_message(sender, f"❌ Prometheus'a erişilemedi: {e}", session)
        return

    alerts = data.get("data", {}).get("alerts", [])
    firing = [a for a in alerts if a.get("state") == "firing"]

    if not firing:
        await send_whatsapp_message(sender, "✅ Aktif alert yok", session)
        return

    lines = [f"🚨 *Aktif Alertler ({len(firing)})*\n"]
    for a in firing[:10]:
        name = a.get("labels", {}).get("alertname", "?")
        sev = a.get("labels", {}).get("severity", "?")
        desc = a.get("annotations", {}).get("description", "")[:120]
        lines.append(f"⚠️ *{name}* [{sev}]")
        if desc:
            lines.append(f"   {desc}\n")
    await send_whatsapp_message(sender, "\n".join(lines), session)


async def cmd_diagnose(sender: str, session: aiohttp.ClientSession):
    await send_whatsapp_message(sender, "🔍 Teşhis başlatılıyor...", session)
    try:
        async with session.post(
            f"{CONFIG['api_url']}/diagnose/start",
            json={},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            data = await resp.json()
            if data.get("code") == 200:
                await send_whatsapp_message(sender, "✅ Teşhis başlatıldı! Tamamlandığında bildirim alacaksınız.", session)
            else:
                await send_whatsapp_message(sender, f"❌ Teşhis başlatılamadı: {data.get('msg', '')}", session)
    except Exception as e:
        await send_whatsapp_message(sender, f"❌ Teşhis API hatası: {e}", session)


async def cmd_report(sender: str, session: aiohttp.ClientSession):
    try:
        async with session.get(
            f"{CONFIG['api_url']}/diagnose/status",
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            data = await resp.json()
            if data.get("code") == 200:
                d = data.get("data", {})
                status = d.get("status", "unknown")
                lines = [f"📄 *Son Teşhis Raporu*\n", f"Durum: {status}"]
                if d.get("report"):
                    lines.append(f"\n{d['report'][:3000]}")
                await send_whatsapp_message(sender, "\n".join(lines), session)
            else:
                await send_whatsapp_message(sender, "ℹ️ Henüz teşhis raporu yok", session)
    except Exception as e:
        await send_whatsapp_message(sender, f"❌ Rapor alınamadı: {e}", session)


# Komut haritası
COMMANDS = {
    "/help": cmd_help,
    "/start": cmd_help,
    "/status": cmd_status,
    "/health": cmd_health,
    "/slow": cmd_slow_queries,
    "/active": cmd_active_queries,
    "/locks": cmd_locks,
    "/db_size": cmd_db_size,
    "/tables": cmd_tables,
    "/alerts": cmd_alerts,
    "/diagnose": cmd_diagnose,
    "/report": cmd_report,
}


# ─────────────────────────────────────────
# Incoming Message Handler
# ─────────────────────────────────────────
async def handle_incoming_message(body: dict, session: aiohttp.ClientSession):
    """Meta webhook'tan gelen mesajı işle."""
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        for msg in messages:
            sender = msg.get("from", "")
            msg_type = msg.get("type", "")

            # Yetki kontrolü
            if CONFIG.get("allowed_numbers") and sender not in CONFIG["allowed_numbers"]:
                await send_whatsapp_message(sender, "⛔ Bu botu kullanma yetkiniz yok.", session)
                continue

            if msg_type == "text":
                text = msg["text"]["body"].strip().lower()
                cmd = text.split()[0] if text else ""

                handler = COMMANDS.get(cmd)
                if handler:
                    await handler(sender, session)
                else:
                    await send_whatsapp_message(
                        sender,
                        "❓ Bilinmeyen komut. Komut listesi için /help yazın.",
                        session
                    )
    except Exception as e:
        logger.error(f"Mesaj işleme hatası: {e}", exc_info=True)


# ─────────────────────────────────────────
# Proaktif Sağlık Kontrolü
# ─────────────────────────────────────────
async def proactive_health_check(session: aiohttp.ClientSession):
    """Periyodik sağlık kontrolü — sorun varsa bildirim gönder."""
    while True:
        interval = CONFIG.get("health_check_interval", 300)
        await asyncio.sleep(interval)

        try:
            issues = []
            threshold = CONFIG.get("slow_query_threshold", 5.0)

            # Yavaş sorgu kontrolü
            rows = _pg_query(
                "SELECT count(*) as cnt FROM pg_stat_activity "
                "WHERE state='active' AND now()-query_start > interval '%s seconds'",
                (threshold,)
            )
            if rows and rows[0]["cnt"] > 0:
                issues.append(f"🐌 {rows[0]['cnt']} yavaş sorgu (>{threshold}s)")

            # Bağlantı kontrolü
            rows = _pg_query("SELECT count(*) as cnt FROM pg_stat_activity")
            rows_max = _pg_query("SHOW max_connections")
            if rows and rows_max:
                pct = rows[0]["cnt"] / int(rows_max[0]["max_connections"]) * 100
                if pct > 80:
                    issues.append(f"🔗 Yüksek bağlantı oranı: {pct:.0f}%")

            # Bekleyen lock
            rows = _pg_query("SELECT count(*) as cnt FROM pg_locks WHERE NOT granted")
            if rows and rows[0]["cnt"] > 3:
                issues.append(f"🔒 {rows[0]['cnt']} bekleyen lock")

            if issues:
                text = "⚠️ *Anomivox Proaktif Uyarı*\n\n" + "\n".join(issues)
                text += "\n\n_Detay için /health yazın._"
                await send_to_default(text, session)

        except Exception as e:
            logger.error(f"Proaktif kontrol hatası: {e}")


# ─────────────────────────────────────────
# aiohttp Web Sunucusu (Webhook + Alert)
# ─────────────────────────────────────────
async def webhook_handler(request: aiohttp.web.Request):
    """Meta WhatsApp webhook — gelen mesajlar."""
    if request.method == "GET":
        # Webhook doğrulama (Meta tarafından yapılır)
        mode = request.query.get("hub.mode", "")
        token = request.query.get("hub.verify_token", "")
        challenge = request.query.get("hub.challenge", "")

        if mode == "subscribe" and token == CONFIG.get("verify_token", ""):
            logger.info("Webhook doğrulandı")
            return aiohttp.web.Response(text=challenge)
        else:
            return aiohttp.web.Response(status=403, text="Forbidden")

    # POST — gelen mesaj
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.Response(status=400, text="Invalid JSON")

    session = request.app.get("http_session")
    if session:
        asyncio.create_task(handle_incoming_message(body, session))

    return aiohttp.web.Response(status=200, text="OK")


async def alert_handler(request: aiohttp.web.Request):
    """Alertmanager webhook — Prometheus alertleri."""
    if not CONFIG.get("notify_on_alert"):
        return aiohttp.web.Response(status=200, text="Alerts disabled")

    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.Response(status=400, text="Invalid JSON")

    alerts = body.get("alerts", [])
    session = request.app.get("http_session")

    for alert in alerts:
        status_emoji = "🔴" if alert.get("status") == "firing" else "🟢"
        name = alert.get("labels", {}).get("alertname", "Unknown")
        severity = alert.get("labels", {}).get("severity", "")
        desc = alert.get("annotations", {}).get("description", "")
        summary = alert.get("annotations", {}).get("summary", "")

        text = (
            f"{status_emoji} *Prometheus Alert*\n\n"
            f"*{name}* [{severity}]\n"
            f"Durum: {alert.get('status', '?')}\n"
        )
        if summary:
            text += f"Özet: {summary}\n"
        if desc:
            text += f"Detay: {desc[:500]}\n"

        if session:
            await send_to_default(text, session)

        # Otomatik teşhis
        if CONFIG.get("auto_diagnose") and alert.get("status") == "firing" and session:
            try:
                async with session.post(
                    f"{CONFIG['api_url']}/diagnose/start",
                    json={},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    data = await resp.json()
                    if data.get("code") == 200:
                        await send_to_default("🔍 Otomatik teşhis başlatıldı.", session)
            except Exception as e:
                logger.error(f"Otomatik teşhis hatası: {e}")

    return aiohttp.web.Response(status=200, text="OK")


async def health_endpoint(request: aiohttp.web.Request):
    """Basit health check endpoint."""
    return aiohttp.web.json_response({"status": "ok", "service": "anomivox-whatsapp-bot"})


# ─────────────────────────────────────────
# App lifecycle
# ─────────────────────────────────────────
async def on_startup(app: aiohttp.web.Application):
    app["http_session"] = aiohttp.ClientSession()
    if CONFIG and CONFIG.get("health_check_interval", 0) > 0:
        app["health_task"] = asyncio.create_task(proactive_health_check(app["http_session"]))
    logger.info("WhatsApp Bot başlatıldı")


async def on_cleanup(app: aiohttp.web.Application):
    if "health_task" in app:
        app["health_task"].cancel()
    if "http_session" in app:
        await app["http_session"].close()
    logger.info("WhatsApp Bot kapatıldı")


def main():
    if not CONFIG:
        logger.error("WhatsApp config yüklenemedi, çıkılıyor.")
        sys.exit(1)

    if not CONFIG["access_token"]:
        logger.warning("WHATSAPP_ACCESS_TOKEN ayarlanmamış. Bot webhook modunda başlatılıyor.")

    app = aiohttp.web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    app.router.add_route("*", "/webhook", webhook_handler)
    app.router.add_route("POST", "/alert", alert_handler)
    app.router.add_get("/health", health_endpoint)

    port = int(os.getenv("WHATSAPP_BOT_PORT", "8025"))
    logger.info(f"WhatsApp Bot dinleniyor: port {port}")
    aiohttp.web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
