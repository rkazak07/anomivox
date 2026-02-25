"""
Anomivox Telegram Bot — Otonom DB Yönetim ve Bildirim Sistemi

Özellikler:
  - Prometheus alert → Telegram bildirim
  - Otomatik anomali teşhisi tetikleme
  - WhatsApp-tarzı komut arayüzü: /status, /health, /slow_queries, /diagnose
  - Proaktif DB sağlık izleme
  - Doğrudan DB müdahalesi: VACUUM, REINDEX, kill query
"""

import asyncio
import json
import logging
import os
import sys
import signal
import traceback
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
import psycopg2
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

# ── Config ──────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configs.telegram_config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_ALLOWED_USERS,
    ANOMIVOX_API_URL,
    PROMETHEUS_URL,
    TELEGRAM_PG_HOST,
    TELEGRAM_PG_PORT,
    TELEGRAM_PG_USER,
    TELEGRAM_PG_PASSWORD,
    TELEGRAM_PG_DB,
    TELEGRAM_NOTIFY_ON_ALERT,
    TELEGRAM_HEALTH_CHECK_INTERVAL,
    TELEGRAM_SLOW_QUERY_THRESHOLD,
)

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [TelegramBot] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Yardımcılar ────────────────────────────────────────────

def is_authorized(user_id: int) -> bool:
    """Kullanıcı yetkili mi kontrol et."""
    if not TELEGRAM_ALLOWED_USERS:
        return True
    return user_id in TELEGRAM_ALLOWED_USERS


def get_db_connection():
    """PostgreSQL bağlantısı oluştur."""
    return psycopg2.connect(
        host=TELEGRAM_PG_HOST,
        port=TELEGRAM_PG_PORT,
        user=TELEGRAM_PG_USER,
        password=TELEGRAM_PG_PASSWORD,
        dbname=TELEGRAM_PG_DB,
        connect_timeout=5,
    )


def escape_md(text: str) -> str:
    """MarkdownV2 için özel karakterleri escape et."""
    chars = r"_*[]()~`>#+-=|{}.!\\"
    for c in chars:
        text = text.replace(c, f"\\{c}")
    return text


def format_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  KOMUT İŞLEYİCİLERİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot başlangıç mesajı."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Yetkiniz yok.")
        return

    welcome = (
        "🤖 *Anomivox DB Bot*\n\n"
        "Veritabanı izleme ve otonom müdahale sistemi\\.\n\n"
        "📋 *Komutlar:*\n"
        "/status — DB bağlantı durumu\n"
        "/health — Kapsamlı sağlık raporu\n"
        "/slow\\_queries — Yavaş sorguları listele\n"
        "/active\\_queries — Aktif sorguları göster\n"
        "/locks — Kilit bekleyen sorguları göster\n"
        "/db\\_size — Veritabanı boyutları\n"
        "/table\\_stats — Tablo istatistikleri\n"
        "/diagnose — Anomali teşhisi başlat\n"
        "/kill\\_query — Sorunlu sorguyu durdur\n"
        "/vacuum — VACUUM ANALYZE çalıştır\n"
        "/reindex — Tablo reindex\n"
        "/alerts — Son Prometheus alertleri\n"
        "/report — Son teşhis raporları\n"
        "/help — Bu mesajı göster"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yardım komutu."""
    await cmd_start(update, context)


# ── /status ─────────────────────────────────────────────────

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hızlı DB bağlantı durumu."""
    if not is_authorized(update.effective_user.id):
        return

    msg = await update.message.reply_text("🔄 Kontrol ediliyor...")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Versiyon
        cur.execute("SELECT version();")
        version = cur.fetchone()[0].split(",")[0]

        # Uptime
        cur.execute("SELECT current_timestamp - pg_postmaster_start_time();")
        uptime = cur.fetchone()[0]

        # Bağlantı sayısı
        cur.execute("SELECT count(*) FROM pg_stat_activity;")
        connections = cur.fetchone()[0]

        cur.execute("SHOW max_connections;")
        max_conn = cur.fetchone()[0]

        # DB boyutu
        cur.execute(f"SELECT pg_size_pretty(pg_database_size('{TELEGRAM_PG_DB}'));")
        db_size = cur.fetchone()[0]

        cur.close()
        conn.close()

        text = (
            f"✅ *Veritabanı Aktif*\n\n"
            f"🐘 `{version}`\n"
            f"⏱ Uptime: `{str(uptime).split('.')[0]}`\n"
            f"🔗 Bağlantılar: `{connections}/{max_conn}`\n"
            f"💾 DB Boyutu: `{db_size}`"
        )
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN_V2.replace("_", "\\_") if False else ParseMode.MARKDOWN)

    except Exception as e:
        await msg.edit_text(f"❌ *DB Bağlantı Hatası*\n\n`{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)


# ── /health ─────────────────────────────────────────────────

async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kapsamlı sağlık raporu."""
    if not is_authorized(update.effective_user.id):
        return

    msg = await update.message.reply_text("🔄 Sağlık raporu hazırlanıyor...")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        report_lines = ["📊 *DB Sağlık Raporu*\n"]

        # 1. Cache Hit Ratio
        cur.execute("""
            SELECT round(
                sum(blks_hit) * 100.0 / NULLIF(sum(blks_hit) + sum(blks_read), 0), 2
            ) FROM pg_stat_database;
        """)
        cache_hit = cur.fetchone()[0] or 0
        icon = "✅" if cache_hit > 95 else ("⚠️" if cache_hit > 85 else "🔴")
        report_lines.append(f"{icon} Cache Hit Ratio: `{cache_hit}%`")

        # 2. Transaction commit/rollback oranı
        cur.execute("""
            SELECT round(
                sum(xact_commit) * 100.0 / NULLIF(sum(xact_commit) + sum(xact_rollback), 0), 2
            ) FROM pg_stat_database;
        """)
        commit_ratio = cur.fetchone()[0] or 0
        icon = "✅" if commit_ratio > 95 else ("⚠️" if commit_ratio > 90 else "🔴")
        report_lines.append(f"{icon} Commit Ratio: `{commit_ratio}%`")

        # 3. Dead Tuples (VACUUM gereksinimi)
        cur.execute("""
            SELECT schemaname || '.' || relname as table,
                   n_dead_tup, n_live_tup,
                   round(n_dead_tup * 100.0 / NULLIF(n_live_tup + n_dead_tup, 0), 1) as dead_pct
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 1000
            ORDER BY n_dead_tup DESC LIMIT 3;
        """)
        dead_rows = cur.fetchall()
        if dead_rows:
            report_lines.append("\n🗑 *Yüksek Dead Tuple Tabloları:*")
            for tbl, dead, live, pct in dead_rows:
                report_lines.append(f"  `{tbl}`: {dead:,} dead ({pct}%)")
        else:
            report_lines.append("✅ Dead tuple problemi yok")

        # 4. Index kullanımı
        cur.execute("""
            SELECT schemaname || '.' || relname as table,
                   seq_scan, idx_scan,
                   round(idx_scan * 100.0 / NULLIF(seq_scan + idx_scan, 0), 1) as idx_pct
            FROM pg_stat_user_tables
            WHERE seq_scan + idx_scan > 100
            ORDER BY seq_scan DESC LIMIT 3;
        """)
        seq_tables = cur.fetchall()
        if seq_tables:
            report_lines.append("\n🔍 *Yüksek Sequential Scan Tabloları:*")
            for tbl, seq, idx, pct in seq_tables:
                icon = "✅" if (pct or 0) > 80 else "⚠️"
                report_lines.append(f"  {icon} `{tbl}`: seq={seq:,}, idx={idx:,} ({pct or 0}% index)")

        # 5. Bağlantı durumu
        cur.execute("""
            SELECT state, count(*)
            FROM pg_stat_activity
            GROUP BY state ORDER BY count(*) DESC;
        """)
        conn_states = cur.fetchall()
        report_lines.append("\n🔗 *Bağlantı Durumları:*")
        for state, cnt in conn_states:
            state_name = state or "null"
            report_lines.append(f"  `{state_name}`: {cnt}")

        # 6. Long-running queries
        cur.execute("""
            SELECT count(*) FROM pg_stat_activity
            WHERE state = 'active'
            AND query NOT ILIKE '%pg_stat%'
            AND now() - query_start > interval '30 seconds';
        """)
        long_running = cur.fetchone()[0]
        icon = "✅" if long_running == 0 else "🔴"
        report_lines.append(f"\n{icon} 30s+ çalışan sorgu: `{long_running}`")

        # 7. Replikasyon lag (varsa)
        cur.execute("""
            SELECT count(*) FROM pg_stat_replication;
        """)
        repl_count = cur.fetchone()[0]
        if repl_count > 0:
            cur.execute("""
                SELECT client_addr, state,
                       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) as lag_bytes
                FROM pg_stat_replication;
            """)
            for addr, state, lag in cur.fetchall():
                report_lines.append(f"📡 Replica `{addr}`: {state}, lag: `{format_bytes(lag or 0)}`")
        else:
            report_lines.append("📡 Replikasyon: yok")

        cur.close()
        conn.close()

        await msg.edit_text("\n".join(report_lines), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await msg.edit_text(f"❌ Hata: `{str(e)[:300]}`", parse_mode=ParseMode.MARKDOWN)


# ── /slow_queries ───────────────────────────────────────────

async def cmd_slow_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """En yavaş sorguları listele."""
    if not is_authorized(update.effective_user.id):
        return

    msg = await update.message.reply_text("🔄 Yavaş sorgular kontrol ediliyor...")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT query, calls, round(mean_exec_time::numeric, 2) as avg_ms,
                   round(total_exec_time::numeric, 2) as total_ms,
                   rows
            FROM pg_stat_statements
            WHERE query NOT LIKE '%pg_stat%'
            ORDER BY mean_exec_time DESC
            LIMIT 5;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            await msg.edit_text("ℹ️ pg_stat_statements boş veya eklenti yüklü değil.\n\n"
                                "Etkinleştirmek için:\n`ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';`",
                                parse_mode=ParseMode.MARKDOWN)
            return

        lines = ["🐌 *En Yavaş 5 Sorgu*\n"]
        for i, (query, calls, avg_ms, total_ms, row_count) in enumerate(rows, 1):
            short_q = query[:120].replace("`", "'").replace("\n", " ")
            lines.append(
                f"*{i}.* Avg: `{avg_ms}ms` | Calls: `{calls}` | Rows: `{row_count}`\n"
                f"`{short_q}...`\n"
            )

        await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        error_msg = str(e)
        if "pg_stat_statements" in error_msg:
            await msg.edit_text(
                "⚠️ `pg_stat_statements` eklentisi yüklü değil.\n\n"
                "Etkinleştirmek için:\n"
                "`CREATE EXTENSION IF NOT EXISTS pg_stat_statements;`\n"
                "ve PostgreSQL'i yeniden başlatın.",
                parse_mode=ParseMode.MARKDOWN)
        else:
            await msg.edit_text(f"❌ Hata: `{error_msg[:300]}`", parse_mode=ParseMode.MARKDOWN)


# ── /active_queries ─────────────────────────────────────────

async def cmd_active_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Şu an çalışan aktif sorguları göster."""
    if not is_authorized(update.effective_user.id):
        return

    msg = await update.message.reply_text("🔄 Aktif sorgular...")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT pid, usename, datname,
                   now() - query_start as duration,
                   state, left(query, 150) as query
            FROM pg_stat_activity
            WHERE state = 'active'
            AND pid != pg_backend_pid()
            AND query NOT ILIKE '%pg_stat%'
            ORDER BY query_start ASC
            LIMIT 10;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            await msg.edit_text("✅ Şu an çalışan aktif sorgu yok.")
            return

        lines = [f"⚡ *Aktif Sorgular ({len(rows)})*\n"]
        for pid, user, db, duration, state, query in rows:
            dur_str = str(duration).split(".")[0]
            short_q = query.replace("`", "'").replace("\n", " ")[:100]
            lines.append(
                f"🔹 PID `{pid}` | `{user}@{db}` | ⏱ `{dur_str}`\n"
                f"  `{short_q}...`\n"
            )

        await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await msg.edit_text(f"❌ Hata: `{str(e)[:300]}`", parse_mode=ParseMode.MARKDOWN)


# ── /locks ──────────────────────────────────────────────────

async def cmd_locks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kilit bekleyen sorguları göster."""
    if not is_authorized(update.effective_user.id):
        return

    msg = await update.message.reply_text("🔄 Kilitler kontrol ediliyor...")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT blocked.pid AS blocked_pid,
                   blocked.usename AS blocked_user,
                   left(blocked_activity.query, 100) AS blocked_query,
                   blocking.pid AS blocking_pid,
                   blocking.usename AS blocking_user,
                   left(blocking_activity.query, 100) AS blocking_query,
                   now() - blocked_activity.query_start AS blocked_duration
            FROM pg_catalog.pg_locks AS blocked
            JOIN pg_catalog.pg_stat_activity AS blocked_activity ON blocked.pid = blocked_activity.pid
            JOIN pg_catalog.pg_locks AS blocking
                ON blocked.locktype = blocking.locktype
                AND blocked.database IS NOT DISTINCT FROM blocking.database
                AND blocked.relation IS NOT DISTINCT FROM blocking.relation
                AND blocked.page IS NOT DISTINCT FROM blocking.page
                AND blocked.tuple IS NOT DISTINCT FROM blocking.tuple
                AND blocked.virtualxid IS NOT DISTINCT FROM blocking.virtualxid
                AND blocked.transactionid IS NOT DISTINCT FROM blocking.transactionid
                AND blocked.classid IS NOT DISTINCT FROM blocking.classid
                AND blocked.objid IS NOT DISTINCT FROM blocking.objid
                AND blocked.objsubid IS NOT DISTINCT FROM blocking.objsubid
                AND blocked.pid != blocking.pid
            JOIN pg_catalog.pg_stat_activity AS blocking_activity ON blocking.pid = blocking_activity.pid
            WHERE NOT blocked.granted
            LIMIT 10;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            await msg.edit_text("✅ Kilit bekleyen sorgu yok.")
            return

        lines = [f"🔒 *Kilit Bekleyen Sorgular ({len(rows)})*\n"]
        for bpid, buser, bquery, kpid, kuser, kquery, dur in rows:
            lines.append(
                f"🚫 PID `{bpid}` (`{buser}`) *bekliyor* ⏱ `{str(dur).split('.')[0]}`\n"
                f"  → Kilitleyen: PID `{kpid}` (`{kuser}`)\n"
            )

        keyboard = [[InlineKeyboardButton(
            f"⚡ PID {rows[0][3]} Durdur",
            callback_data=f"kill_{rows[0][3]}"
        )]] if rows else []

        await msg.edit_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )

    except Exception as e:
        await msg.edit_text(f"❌ Hata: `{str(e)[:300]}`", parse_mode=ParseMode.MARKDOWN)


# ── /db_size ────────────────────────────────────────────────

async def cmd_db_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Veritabanı boyutları."""
    if not is_authorized(update.effective_user.id):
        return

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT datname, pg_size_pretty(pg_database_size(datname))
            FROM pg_database
            WHERE datistemplate = false
            ORDER BY pg_database_size(datname) DESC;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        lines = ["💾 *Veritabanı Boyutları*\n"]
        for db, size in rows:
            lines.append(f"  📁 `{db}`: `{size}`")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await update.message.reply_text(f"❌ Hata: `{str(e)[:300]}`", parse_mode=ParseMode.MARKDOWN)


# ── /table_stats ────────────────────────────────────────────

async def cmd_table_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tablo istatistikleri."""
    if not is_authorized(update.effective_user.id):
        return

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT schemaname || '.' || relname as table_name,
                   pg_size_pretty(pg_total_relation_size(relid)) as total_size,
                   n_live_tup as live_rows,
                   n_dead_tup as dead_rows,
                   last_vacuum,
                   last_autovacuum
            FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(relid) DESC
            LIMIT 10;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        lines = ["📊 *En Büyük 10 Tablo*\n"]
        for tbl, size, live, dead, vac, auto_vac in rows:
            last_v = str(vac or auto_vac or "hiç")[:16]
            lines.append(
                f"📋 `{tbl}`\n"
                f"   Boyut: `{size}` | Satır: `{live:,}` | Dead: `{dead:,}`\n"
                f"   Son VACUUM: `{last_v}`\n"
            )

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await update.message.reply_text(f"❌ Hata: `{str(e)[:300]}`", parse_mode=ParseMode.MARKDOWN)


# ── /kill_query ─────────────────────────────────────────────

async def cmd_kill_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sorunlu sorguyu durdur. Kullanım: /kill_query <PID>"""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Kullanım: `/kill_query <PID>`\n\n"
            "Önce `/active_queries` veya `/locks` ile PID'yi bulun.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        pid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Geçersiz PID. Sayı olmalı.")
        return

    keyboard = [
        [
            InlineKeyboardButton("🟡 Cancel (nazik)", callback_data=f"cancel_{pid}"),
            InlineKeyboardButton("🔴 Terminate (zorla)", callback_data=f"kill_{pid}"),
        ],
        [InlineKeyboardButton("❌ İptal", callback_data="dismiss")]
    ]

    await update.message.reply_text(
        f"⚠️ PID `{pid}` durdurulsun mu?\n\n"
        f"• *Cancel*: Sorguyu nazikçe iptal eder\n"
        f"• *Terminate*: Bağlantıyı zorla kapatır",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def callback_kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline button callback'leri."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "dismiss":
        await query.edit_message_text("❌ İptal edildi.")
        return

    if data.startswith("cancel_") or data.startswith("kill_"):
        action = "cancel" if data.startswith("cancel_") else "terminate"
        pid = int(data.split("_")[1])

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            if action == "cancel":
                cur.execute(f"SELECT pg_cancel_backend({pid});")
            else:
                cur.execute(f"SELECT pg_terminate_backend({pid});")

            result = cur.fetchone()[0]
            cur.close()
            conn.close()

            if result:
                await query.edit_message_text(
                    f"✅ PID `{pid}` başarıyla {'iptal edildi' if action == 'cancel' else 'sonlandırıldı'}.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text(f"⚠️ PID `{pid}` bulunamadı veya zaten kapanmış.",
                                              parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await query.edit_message_text(f"❌ Hata: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("vacuum_"):
        table = data.replace("vacuum_", "")
        try:
            conn = get_db_connection()
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(f"VACUUM ANALYZE {table};")
            cur.close()
            conn.close()
            await query.edit_message_text(f"✅ `VACUUM ANALYZE {table}` tamamlandı.", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await query.edit_message_text(f"❌ Hata: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("reindex_"):
        table = data.replace("reindex_", "")
        try:
            conn = get_db_connection()
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(f"REINDEX TABLE {table};")
            cur.close()
            conn.close()
            await query.edit_message_text(f"✅ `REINDEX TABLE {table}` tamamlandı.", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await query.edit_message_text(f"❌ Hata: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)


# ── /vacuum ─────────────────────────────────────────────────

async def cmd_vacuum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """VACUUM ANALYZE çalıştır. /vacuum [tablo_adı]"""
    if not is_authorized(update.effective_user.id):
        return

    if context.args:
        table = context.args[0]
        keyboard = [
            [
                InlineKeyboardButton(f"✅ Onayla: VACUUM {table}", callback_data=f"vacuum_{table}"),
                InlineKeyboardButton("❌ İptal", callback_data="dismiss"),
            ]
        ]
        await update.message.reply_text(
            f"⚠️ `VACUUM ANALYZE {table}` çalıştırılsın mı?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Dead tuple'ı yüksek tabloları göster
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT schemaname || '.' || relname, n_dead_tup, n_live_tup
                FROM pg_stat_user_tables
                WHERE n_dead_tup > 100
                ORDER BY n_dead_tup DESC LIMIT 5;
            """)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            if not rows:
                await update.message.reply_text("✅ VACUUM gerektiren tablo yok.")
                return

            keyboard = [
                [InlineKeyboardButton(f"🗑 {tbl} ({dead:,} dead)", callback_data=f"vacuum_{tbl}")]
                for tbl, dead, live in rows
            ]
            await update.message.reply_text(
                "🗑 *VACUUM yapılacak tabloyu seçin:*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: `{str(e)[:300]}`", parse_mode=ParseMode.MARKDOWN)


# ── /reindex ────────────────────────────────────────────────

async def cmd_reindex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tablo reindex. /reindex [tablo_adı]"""
    if not is_authorized(update.effective_user.id):
        return

    if context.args:
        table = context.args[0]
        keyboard = [
            [
                InlineKeyboardButton(f"✅ Onayla: REINDEX {table}", callback_data=f"reindex_{table}"),
                InlineKeyboardButton("❌ İptal", callback_data="dismiss"),
            ]
        ]
        await update.message.reply_text(
            f"⚠️ `REINDEX TABLE {table}` çalıştırılsın mı?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT schemaname || '.' || relname,
                       pg_size_pretty(pg_indexes_size(relid))
                FROM pg_stat_user_tables
                WHERE idx_scan > 0
                ORDER BY pg_indexes_size(relid) DESC LIMIT 5;
            """)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            keyboard = [
                [InlineKeyboardButton(f"🔄 {tbl} ({size})", callback_data=f"reindex_{tbl}")]
                for tbl, size in rows
            ]
            await update.message.reply_text(
                "🔄 *REINDEX yapılacak tabloyu seçin:*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: `{str(e)[:300]}`", parse_mode=ParseMode.MARKDOWN)


# ── /alerts ─────────────────────────────────────────────────

async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prometheus'taki aktif alertleri göster."""
    if not is_authorized(update.effective_user.id):
        return

    msg = await update.message.reply_text("🔄 Prometheus alertleri kontrol ediliyor...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{PROMETHEUS_URL}/api/v1/alerts") as resp:
                data = await resp.json()

        alerts = data.get("data", {}).get("alerts", [])

        if not alerts:
            await msg.edit_text("✅ Aktif alert yok.")
            return

        lines = [f"🚨 *Aktif Alertler ({len(alerts)})*\n"]
        for alert in alerts[:10]:
            name = alert.get("labels", {}).get("alertname", "?")
            severity = alert.get("labels", {}).get("severity", "?")
            state = alert.get("state", "?")
            icon = "🔴" if severity in ("critical", "CRIT") else ("🟡" if severity in ("warning", "WARN") else "🔵")
            lines.append(f"{icon} *{name}* | `{severity}` | {state}")

            desc = alert.get("annotations", {}).get("summary", "")
            if desc:
                lines.append(f"   {desc[:100]}")
            lines.append("")

        await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await msg.edit_text(f"❌ Prometheus bağlantı hatası: `{str(e)[:300]}`", parse_mode=ParseMode.MARKDOWN)


# ── /diagnose ───────────────────────────────────────────────

async def cmd_diagnose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Anomivox teşhis raporlarını göster veya teşhis başlat."""
    if not is_authorized(update.effective_user.id):
        return

    msg = await update.message.reply_text("🔄 Son teşhis raporları getiriliyor...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{ANOMIVOX_API_URL}/report/histories") as resp:
                data = await resp.json()

        reports = data.get("data", [])
        if not reports:
            await msg.edit_text("ℹ️ Henüz teşhis raporu yok.")
            return

        lines = ["📋 *Son Teşhis Raporları*\n"]
        for r in reports[:5]:
            filename = r if isinstance(r, str) else r.get("filename", "?")
            lines.append(f"📄 `{filename}`")

        lines.append(f"\nToplam: {len(reports)} rapor")
        await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await msg.edit_text(f"❌ API hatası: `{str(e)[:300]}`", parse_mode=ParseMode.MARKDOWN)


# ── /report ─────────────────────────────────────────────────

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Son teşhis raporlarını listele."""
    await cmd_diagnose(update, context)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PROAKTİF İZLEME — Arka Plan Görevleri
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def proactive_health_check(context: ContextTypes.DEFAULT_TYPE):
    """Periyodik sağlık kontrolü — sorun tespit ederse bildirim gönderir."""
    if not TELEGRAM_CHAT_ID:
        return

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        problems = []

        # 1. Bağlantı sayısı kontrolü
        cur.execute("SELECT count(*) FROM pg_stat_activity;")
        active = cur.fetchone()[0]
        cur.execute("SHOW max_connections;")
        max_c = int(cur.fetchone()[0])
        if active > max_c * 0.8:
            problems.append(f"🔴 Bağlantı dolmak üzere: {active}/{max_c} ({int(active/max_c*100)}%)")

        # 2. Long-running queries (5 dakikadan uzun)
        cur.execute("""
            SELECT pid, usename, left(query, 80),
                   extract(epoch from now() - query_start)::int as secs
            FROM pg_stat_activity
            WHERE state = 'active'
            AND query NOT ILIKE '%pg_stat%'
            AND now() - query_start > interval '5 minutes'
            ORDER BY query_start ASC LIMIT 3;
        """)
        long_queries = cur.fetchall()
        for pid, user, q, secs in long_queries:
            problems.append(f"⚠️ Uzun sorgu (PID {pid}, {format_duration(secs)}): `{q}...`")

        # 3. Lock bekleme
        cur.execute("""
            SELECT count(*) FROM pg_locks WHERE NOT granted;
        """)
        waiting_locks = cur.fetchone()[0]
        if waiting_locks > 0:
            problems.append(f"🔒 {waiting_locks} sorgu kilit bekliyor")

        # 4. Dead tuples yüksek
        cur.execute("""
            SELECT schemaname || '.' || relname, n_dead_tup
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 10000
            ORDER BY n_dead_tup DESC LIMIT 1;
        """)
        dead = cur.fetchone()
        if dead:
            problems.append(f"🗑 `{dead[0]}` tablosunda {dead[1]:,} dead tuple — VACUUM önerilir")

        cur.close()
        conn.close()

        if problems:
            text = "🚨 *Proaktif DB Uyarısı*\n\n" + "\n".join(problems)
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=text,
                parse_mode=ParseMode.MARKDOWN
            )

    except Exception as e:
        logger.error(f"Proactive health check error: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ALERT WEBHOOK — Prometheus'tan gelen alertleri Telegram'a ilet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from aiohttp import web

async def alert_webhook_handler(request):
    """Alertmanager webhook → Telegram bildirim."""
    try:
        data = await request.json()
        status = data.get("status", "unknown")
        alerts = data.get("alerts", [])

        for alert in alerts:
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            alert_name = labels.get("alertname", "Unknown")
            severity = labels.get("severity", "info")
            instance = labels.get("instance", "")

            icon = "🔴" if severity in ("critical", "CRIT") else ("🟡" if severity in ("warning", "WARN") else "🟢")
            status_icon = "🚨 FIRING" if alert.get("status") == "firing" else "✅ RESOLVED"

            summary = annotations.get("summary", "Açıklama yok")
            description = annotations.get("description", "")[:200]

            text = (
                f"{icon} *{status_icon}*\n\n"
                f"📌 *Alert:* `{alert_name}`\n"
                f"⚡ *Severity:* `{severity}`\n"
                f"🖥 *Instance:* `{instance}`\n\n"
                f"📝 {summary}\n"
            )
            if description:
                text += f"\n_{description}_"

            if TELEGRAM_CHAT_ID and hasattr(alert_webhook_handler, '_bot'):
                try:
                    # Firing alertlerde müdahale butonları göster
                    keyboard = None
                    if alert.get("status") == "firing":
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("📊 Sağlık Raporu", callback_data="health_report")],
                        ])

                    await alert_webhook_handler._bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.error(f"Telegram send error: {e}")

        return web.json_response({"status": "ok"})

    except Exception as e:
        logger.error(f"Alert webhook error: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)


async def health_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alert'ten gelen sağlık raporu callback'i."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "health_report":
        # Fake update ile cmd_health çağıramayız, doğrudan rapor gönder
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active';")
            active = cur.fetchone()[0]

            cur.execute("""
                SELECT count(*) FROM pg_stat_activity
                WHERE state = 'active' AND now() - query_start > interval '30 seconds';
            """)
            long_running = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM pg_locks WHERE NOT granted;")
            locks = cur.fetchone()[0]

            cur.close()
            conn.close()

            text = (
                f"📊 *Hızlı Sağlık Raporu*\n\n"
                f"⚡ Aktif sorgu: `{active}`\n"
                f"🐌 30s+ sorgu: `{long_running}`\n"
                f"🔒 Kilit bekleyen: `{locks}`\n\n"
                f"Detay için: /health"
            )
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            await query.edit_message_text(f"❌ Hata: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ANA UYGULAMA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_webhook_server(bot):
    """Alertmanager webhook sunucusu."""
    alert_webhook_handler._bot = bot

    webapp = web.Application()
    webapp.router.add_post("/alert", alert_webhook_handler)
    webapp.router.add_get("/health", lambda r: web.json_response({"status": "ok"}))

    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8024)
    await site.start()
    logger.info("Alert webhook server started on :8024")


def main():
    """Bot başlat."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN ayarlanmamış! configs/telegram_config.py dosyasını kontrol edin.")
        sys.exit(1)

    logger.info("Anomivox Telegram Bot başlatılıyor...")

    # Application oluştur
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Komut handler'ları
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("slow_queries", cmd_slow_queries))
    app.add_handler(CommandHandler("active_queries", cmd_active_queries))
    app.add_handler(CommandHandler("locks", cmd_locks))
    app.add_handler(CommandHandler("db_size", cmd_db_size))
    app.add_handler(CommandHandler("table_stats", cmd_table_stats))
    app.add_handler(CommandHandler("kill_query", cmd_kill_query))
    app.add_handler(CommandHandler("vacuum", cmd_vacuum))
    app.add_handler(CommandHandler("reindex", cmd_reindex))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("diagnose", cmd_diagnose))
    app.add_handler(CommandHandler("report", cmd_report))

    # Callback handler'ları (inline butonlar)
    app.add_handler(CallbackQueryHandler(health_report_callback, pattern="^health_report$"))
    app.add_handler(CallbackQueryHandler(callback_kill, pattern="^(kill_|cancel_|vacuum_|reindex_|dismiss)"))

    # Proaktif sağlık kontrolü (periyodik)
    if TELEGRAM_CHAT_ID and TELEGRAM_HEALTH_CHECK_INTERVAL > 0:
        app.job_queue.run_repeating(
            proactive_health_check,
            interval=TELEGRAM_HEALTH_CHECK_INTERVAL,
            first=60,
            name="health_check"
        )
        logger.info(f"Proaktif sağlık kontrolü: her {TELEGRAM_HEALTH_CHECK_INTERVAL}s")

    # Bot menu komutlarını ayarla
    async def post_init(application):
        await application.bot.set_my_commands([
            BotCommand("start", "Bot'u başlat"),
            BotCommand("status", "DB bağlantı durumu"),
            BotCommand("health", "Kapsamlı sağlık raporu"),
            BotCommand("slow_queries", "Yavaş sorguları listele"),
            BotCommand("active_queries", "Aktif sorguları göster"),
            BotCommand("locks", "Kilit bekleyen sorgular"),
            BotCommand("db_size", "Veritabanı boyutları"),
            BotCommand("table_stats", "Tablo istatistikleri"),
            BotCommand("kill_query", "Sorgu durdur (PID)"),
            BotCommand("vacuum", "VACUUM ANALYZE çalıştır"),
            BotCommand("reindex", "Tablo reindex"),
            BotCommand("alerts", "Prometheus alertleri"),
            BotCommand("diagnose", "Teşhis raporları"),
            BotCommand("report", "Son raporlar"),
            BotCommand("help", "Yardım"),
        ])
        # Webhook sunucusunu başlat
        await run_webhook_server(application.bot)
        logger.info("Telegram Bot hazır!")

    app.post_init = post_init

    # Bot'u çalıştır (polling mode)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
