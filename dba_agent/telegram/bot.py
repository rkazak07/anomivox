"""
Telegram Bot — İnteraktif DBA Agent Bot
═══════════════════════════════════════
Telegram üzerinden komut alma, tanı çalıştırma ve rapor gönderme.

Komutlar:
  /start   — Hoş geldin mesajı
  /help    — Kullanım kılavuzu
  /status  — Sistem sağlık durumu
  /diagnose <açıklama> — Manuel tanı başlat
  /tools   — Kayıtlı araçları listele
  /db      — Veritabanı bağlantı durumu
  /cancel  — Devam eden tanıyı iptal et

Faz 3 implementasyonu — python-telegram-bot >= 21.0
"""

import asyncio
import logging
import html
from datetime import datetime
from typing import Optional, Dict, Any

from telegram import (
    Update,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from dba_agent.config import get_config, TelegramConfig

logger = logging.getLogger("dba_agent.telegram.bot")

# ── Aktif tanı takibi ────────────────────────
_active_diagnoses: Dict[str, asyncio.Task] = {}


class DBABot:
    """
    İnteraktif Telegram Bot — DBA Agent ile entegre.

    Lifecycle:
        bot = DBABot()
        await bot.start()   # polling başlar (arka plan)
        ...
        await bot.stop()
    """

    def __init__(self):
        self.config: TelegramConfig = get_config().telegram
        self.app: Optional[Application] = None
        self._running = False

    @property
    def is_configured(self) -> bool:
        """Bot token tanımlı mı?"""
        return bool(self.config.bot_token and self.config.bot_token.strip())

    def _is_authorized(self, chat_id: int) -> bool:
        """Sadece izinli chat_id'lerden komut kabul et."""
        allowed = self.config.all_chat_ids
        if not allowed:
            # chat_id listesi boşsa admin_chat_id kontrolü
            return str(chat_id) == self.config.admin_chat_id
        return str(chat_id) in allowed

    async def start(self):
        """Bot'u başlat — polling modunda."""
        if not self.is_configured:
            logger.warning("Telegram bot token tanımlı değil, bot başlatılmadı.")
            return

        logger.info("Telegram bot başlatılıyor...")

        self.app = (
            ApplicationBuilder()
            .token(self.config.bot_token)
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .build()
        )

        # ── Komut handler'ları ─────────────────
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("diagnose", self._cmd_diagnose))
        self.app.add_handler(CommandHandler("tools", self._cmd_tools))
        self.app.add_handler(CommandHandler("db", self._cmd_db))
        self.app.add_handler(CommandHandler("sql", self._cmd_sql))
        self.app.add_handler(CommandHandler("query", self._cmd_sql))  # alias
        self.app.add_handler(CommandHandler("run", self._cmd_run))
        self.app.add_handler(CommandHandler("cancel", self._cmd_cancel))
        self.app.add_handler(CommandHandler("service", self._cmd_service))
        self.app.add_handler(CommandHandler("kill", self._cmd_kill))
        self.app.add_handler(CommandHandler("vacuum", self._cmd_vacuum))
        self.app.add_handler(CommandHandler("ssh", self._cmd_ssh))
        self.app.add_handler(CommandHandler("monitor", self._cmd_monitor))
        self.app.add_handler(CommandHandler("history", self._cmd_history))
        self.app.add_handler(CommandHandler("stats", self._cmd_stats))

        # ── Callback handler (inline keyboard) ─
        self.app.add_handler(CallbackQueryHandler(self._callback_handler))

        # ── Serbest metin handler ──────────────
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        # ── Bot komutlarını ayarla ─────────────
        commands = [
            BotCommand("start", "Hoş geldin mesajı"),
            BotCommand("help", "Kullanım kılavuzu"),
            BotCommand("status", "Sistem sağlık durumu"),
            BotCommand("diagnose", "Manuel tanı başlat"),
            BotCommand("tools", "Kayıtlı araçları listele"),
            BotCommand("db", "Veritabanı durumu"),
            BotCommand("sql", "SQL sorgusu çalıştır"),
            BotCommand("run", "DBA aracı çalıştır"),
            BotCommand("service", "Servis durumu kontrol (SSH)"),
            BotCommand("kill", "Oturum/sorgu öldür"),
            BotCommand("vacuum", "Tablo VACUUM"),
            BotCommand("ssh", "SSH sistem bilgisi"),
            BotCommand("monitor", "Proaktif izleme durumu / kontrol"),
            BotCommand("cancel", "Tanıyı iptal et"),
            BotCommand("history", "Son uygulanan aksiyonlar"),
            BotCommand("stats", "Aksiyon başarı istatistikleri"),
        ]

        # ── Initialize + Start ─────────────────
        await self.app.initialize()
        await self.app.bot.set_my_commands(commands)
        await self.app.start()
        await self.app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )

        self._running = True
        logger.info("✅ Telegram bot başlatıldı (polling aktif)")

    async def stop(self):
        """Bot'u durdur."""
        if self.app and self._running:
            logger.info("Telegram bot durduruluyor...")
            # Aktif tanıları iptal et
            for task_id, task in _active_diagnoses.items():
                task.cancel()
            _active_diagnoses.clear()

            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self._running = False
            logger.info("Telegram bot durduruldu.")

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = ParseMode.MARKDOWN,
        reply_markup=None,
    ):
        """Belirli bir chat'e mesaj gönder."""
        if not self.app or not self._running:
            logger.warning("Bot çalışmıyor, mesaj gönderilemedi.")
            return

        try:
            # Telegram mesaj limiti 4096 karakter
            if len(text) <= 4096:
                await self.app.bot.send_message(
                    chat_id=int(chat_id),
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
            else:
                # Uzun mesajları parçala
                chunks = _split_message(text, 4096)
                for chunk in chunks:
                    await self.app.bot.send_message(
                        chat_id=int(chat_id),
                        text=chunk,
                        parse_mode=parse_mode,
                    )
        except Exception as e:
            logger.error(f"Telegram mesaj gönderme hatası: {e}")
            # Markdown parse hatası olabilir, plain text dene
            try:
                await self.app.bot.send_message(
                    chat_id=int(chat_id),
                    text=text,
                    parse_mode=None,
                )
            except Exception as e2:
                logger.error(f"Plain text gönderme de başarısız: {e2}")

    async def broadcast(self, text: str, parse_mode: str = ParseMode.MARKDOWN):
        """Tüm izinli chat'lere mesaj gönder."""
        for chat_id in self.config.all_chat_ids:
            await self.send_message(chat_id, text, parse_mode)

    # ─────────────────────────────────────────────
    # Komut Handler'ları
    # ─────────────────────────────────────────────

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Hoş geldin mesajı."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        text = (
            "🤖 *Anomivox DBA Agent*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Merhaba! Ben veritabanı tanı ve yönetim asistanınız.\n\n"
            "📋 *Kullanılabilir komutlar:*\n"
            "  /status — Sistem sağlık durumu\n"
            "  /diagnose — Manuel tanı başlat\n"
            "  /tools — Kayıtlı araçlar\n"
            "  /db — Veritabanı durumu\n"
            "  /help — Detaylı yardım\n\n"
            "💡 Doğrudan mesaj yazarak da soru sorabilirsiniz.\n\n"
            f"🕐 Çalışma zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Detaylı yardım."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        text = (
            "📖 *DBA Agent — Kullanım Kılavuzu*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "*Temel Komutlar:*\n"
            "  /start — Hoş geldin mesajı\n"
            "  /help — Bu mesajı gösterir\n\n"
            "*Tanı & Analiz:*\n"
            "  /diagnose CPU yüksek — CPU anomalisi tanısı\n"
            "  /diagnose Slow queries — Yavaş sorgu analizi\n"
            "  /cancel — Devam eden tanıyı iptal et\n\n"
            "*Veritabanı Komutları:*\n"
            "  /db — Tüm DB bağlantı durumu\n"
            "  /sql SELECT version() — SQL çalıştır\n"
            "  /run get\\_health — DBA aracı çalıştır\n"
            "  /run get\\_slow\\_queries limit=5\n"
            "  /tools — Kullanılabilir araçlar\n\n"
            "*DB Aksiyon Komutları:*\n"
            "  /kill 12345 — Oturumu sonlandır\n"
            "  /kill 12345 cancel — Sorguyu iptal et\n"
            "  /vacuum users — VACUUM ANALYZE\n"
            "  /vacuum users full — VACUUM FULL ⚠️\n\n"
            "*OS / SSH Komutları:*\n"
            "  /service postgresql — Servis durumu\n"
            "  /ssh info — Sistem bilgisi\n"
            "  /ssh disk — Disk durumu\n"
            "  /ssh ps — Process listesi\n"
            "  /ssh port 5432 — Port kontrolü\n\n"
            "*Sunucu Metrikleri:*\n"
            "  /status — Genel sistem durumu\n\n"
            "*Proaktif İzleme:*\n"
            "  /monitor — İzleme durumu\n"
            "  /monitor start — Başlat\n"
            "  /monitor stop — Durdur\n"
            "  /monitor interval 120 — Aralık ayarla\n\n"
            "*Junior DBA — Doğal Dil (komut gerekmez):*\n"
            "  Sunucu/DB adı ile birlikte yazabilirsiniz:\n"
            '  _"prod sunucusundaki postgresql uzun sorgu var mı?"_\n'
            '  _"analytics db\'sinde yavaş sorguları göster"_\n'
            '  _"mysql\'deki kilitli bağlantıları listele"_\n'
            '  _"users tablosunu vacuum yap"_\n'
            '  _"CPU ve disk durumu nedir?"_\n'
            '  _"PostgreSQL servisi çalışıyor mu?"_\n'
            '  _"SELECT count(*) FROM orders"_\n\n'
            "💡 Sistem; sunucu adı, DB tipi ve işlem niyetini\n"
            "  otomatik tespit eder — komut yazmanıza gerek yok.\n"
            "  Proaktif izleme anormal durumlarda sizi bildirir."
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sistem sağlık durumu."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        await update.message.reply_text("🔄 Sistem durumu kontrol ediliyor...")

        try:
            from dba_agent.inference import get_llm_client
            from dba_agent.tools import get_tool_registry
            config = get_config()

            # LLM durumu
            llm = get_llm_client()
            llm_health = llm.health_check()
            llm_ok = llm_health.get("status") == "ok" or llm_health.get("litellm", {}).get("reachable", False)
            llm_emoji = "✅" if llm_ok else "❌"

            # DB durumu
            db_status_lines = []
            try:
                from dba_agent.db import get_all_adapters
                for name, adapter in get_all_adapters().items():
                    try:
                        adapter.connect()
                        health = adapter.get_health()
                        db_status_lines.append(
                            f"  ✅ {name}: v{health.version} | "
                            f"Conn: {health.active_connections}/{health.max_connections} | "
                            f"Cache: {health.cache_hit_ratio:.1%}"
                        )
                    except Exception as e:
                        db_status_lines.append(f"  ❌ {name}: {str(e)[:50]}")
                    finally:
                        adapter.disconnect()
            except Exception:
                db_status_lines.append("  ⚠️ DB bilgisi alınamadı")

            # Tools
            registry = get_tool_registry()
            tool_count = len(registry.list_tools())

            # LLM istatistikleri
            stats = llm.stats
            total_calls = stats.get("total_calls", 0)
            success = stats.get("success", 0)
            avg_dur = stats.get("avg_duration_sec", 0)

            # Monitoring durumu
            mon_line = "  ❓ Bilinmiyor"
            try:
                from dba_agent.monitoring import get_health_monitor
                mon = get_health_monitor()
                mon_stats = mon.stats
                mon_emoji = "✅" if mon_stats["running"] else "⏸️"
                mon_line = (
                    f"  {mon_emoji} {'Aktif' if mon_stats['running'] else 'Pasif'} — "
                    f"Kontrol: {mon_stats['check_count']} | "
                    f"Alert: {mon_stats['alert_count']} | "
                    f"Aralık: {mon_stats['check_interval_sec']}s"
                )
            except Exception:
                pass

            text = (
                "📊 *Anomivox DBA Agent — Durum*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🤖 Agent: ✅ Çalışıyor (v0.2.0)\n"
                f"🧠 LLM: {llm_emoji} {'Bağlı' if llm_ok else 'Bağlantı yok'}\n"
                f"🔧 Araçlar: {tool_count} kayıtlı\n\n"
                f"🖥️ *Veritabanları:*\n"
                f"{chr(10).join(db_status_lines) if db_status_lines else '  Hedef yok'}\n\n"
                f"👁️ *Proaktif İzleme:*\n"
                f"{mon_line}\n\n"
                f"📈 *LLM İstatistikleri:*\n"
                f"  Toplam çağrı: {total_calls}\n"
                f"  Başarılı: {success}\n"
                f"  Ort. süre: {avg_dur:.1f}s\n\n"
                f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Status hatası: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Durum alınamadı:\n{str(e)[:200]}")

    async def _cmd_diagnose(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manuel tanı başlat."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        chat_id = str(update.effective_chat.id)

        # Aktif tanı var mı kontrol et
        if chat_id in _active_diagnoses and not _active_diagnoses[chat_id].done():
            await update.message.reply_text(
                "⚠️ Zaten devam eden bir tanı var.\n"
                "/cancel ile iptal edebilirsiniz."
            )
            return

        # Açıklama al
        alert_text = " ".join(context.args) if context.args else ""
        if not alert_text:
            await update.message.reply_text(
                "❓ *Tanı açıklaması gerekli*\n\n"
                "Kullanım:\n"
                "  /diagnose CPU yüksek son 10 dakika\n"
                "  /diagnose Yavaş sorgular var\n"
                "  /diagnose Disk dolmak üzere",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Tanı başlat (arka plan görevi)
        await update.message.reply_text(
            f"🔍 *Tanı başlatılıyor...*\n\n"
            f"📋 Açıklama: _{alert_text}_\n\n"
            f"⏳ Bu işlem CPU-only LLM ile yapılır,\n"
            f"birkaç dakika sürebilir. Tamamlandığında\n"
            f"sonuç burada paylaşılacak.",
            parse_mode=ParseMode.MARKDOWN,
        )

        task = asyncio.create_task(
            self._run_diagnosis(chat_id, alert_text)
        )
        _active_diagnoses[chat_id] = task

    async def _run_diagnosis(self, chat_id: str, alert_text: str):
        """Tanı pipeline'ını çalıştır ve sonucu gönder."""
        try:
            from dba_agent.agent import get_orchestrator
            orchestrator = get_orchestrator()

            report = await orchestrator.diagnose(
                alert_text=alert_text,
                alert_id=f"tg-{int(datetime.now().timestamp())}",
            )

            # Rapor metnini gönder
            if report.report_text:
                await self.send_message(chat_id, report.report_text)
            elif report.error:
                await self.send_message(
                    chat_id,
                    f"❌ *Tanı Hatası*\n\n{report.error[:500]}",
                )
            else:
                # Fallback kısa rapor
                from dba_agent.telegram.formatter import format_diagnosis_report
                text = format_diagnosis_report(report)
                await self.send_message(chat_id, text)

            # MEDIUM/HIGH aksiyonlar varsa Telegram onay butonlarını göster
            # (Orchestrator zaten register_pending_approval yaptı)
            if report.recommended_actions:
                approval_needed = [
                    a for a in report.recommended_actions
                    if a.get("risk", "safe") in ("medium", "high")
                ]
                # LOW aksiyonlar auto_approve_low kapalıysa onay listesine girer
                from dba_agent.config import get_config as _get_cfg
                if not _get_cfg().security.auto_approve_low:
                    approval_needed += [
                        a for a in report.recommended_actions
                        if a.get("risk", "safe") == "low"
                    ]

                if approval_needed:
                    from dba_agent.telegram.approval import (
                        create_approval_keyboard,
                        get_pending_approval,
                    )
                    # Sadece gerçekten kuyruğa alındıysa buton göster
                    if get_pending_approval(report.alert_id):
                        keyboard = create_approval_keyboard(report.alert_id)
                        risk_levels = ", ".join(
                            sorted({a.get("risk", "safe") for a in approval_needed})
                        )
                        await self.send_message(
                            chat_id,
                            f"⚠️ *Onay Gerekiyor*\n\n"
                            f"Risk: `{risk_levels}` — {len(approval_needed)} aksiyon\n"
                            f"Uygulamak ister misiniz?",
                            reply_markup=keyboard,
                        )

        except asyncio.CancelledError:
            await self.send_message(chat_id, "🚫 Tanı iptal edildi.")
        except Exception as e:
            logger.error(f"Diagnosis hatası (Telegram): {e}", exc_info=True)
            await self.send_message(
                chat_id,
                f"❌ *Tanı başarısız*\n\n`{str(e)[:300]}`",
            )
        finally:
            _active_diagnoses.pop(chat_id, None)

    async def _cmd_tools(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kayıtlı araçları listele."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        try:
            from dba_agent.tools import get_tool_registry
            registry = get_tool_registry()
            tools = registry.list_tools()

            # Kategori bazlı gruplama
            categories: Dict[str, list] = {}
            for t in tools:
                cat = t.category or "other"
                categories.setdefault(cat, []).append(t)

            lines = ["🔧 *Kayıtlı Araçlar*\n━━━━━━━━━━━━━━━━━━\n"]
            for cat, cat_tools in sorted(categories.items()):
                lines.append(f"\n📂 *{cat.upper()}*")
                for t in cat_tools:
                    risk_emoji = {"safe": "🟢", "low": "🟡", "medium": "🟠", "high": "🔴"}.get(
                        t.risk_level, "⚪"
                    )
                    lines.append(f"  {risk_emoji} `{t.name}` — {t.description[:60]}")

            lines.append(f"\n📊 Toplam: {len(tools)} araç")
            await update.message.reply_text(
                "\n".join(lines), parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            await update.message.reply_text(f"❌ Araçlar listelenemedi:\n{str(e)[:200]}")

    async def _cmd_db(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Veritabanı bağlantı durumu."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        await update.message.reply_text("🔄 Veritabanları kontrol ediliyor...")

        try:
            from dba_agent.db import get_all_adapters

            lines = ["🖥️ *Veritabanı Durumu*\n━━━━━━━━━━━━━━━━━━\n"]

            for name, adapter in get_all_adapters().items():
                try:
                    adapter.connect()
                    health = adapter.get_health()
                    uptime_h = round(health.uptime_sec / 3600, 1)
                    lines.append(
                        f"\n✅ *{name}*\n"
                        f"  Versiyon: {health.version}\n"
                        f"  Bağlantı: {health.active_connections}/{health.max_connections}\n"
                        f"  Cache Hit: {health.cache_hit_ratio:.1%}\n"
                        f"  DB Boyut: {round(health.database_size_mb, 1)} MB\n"
                        f"  Uptime: {uptime_h} saat"
                    )
                except Exception as e:
                    lines.append(f"\n❌ *{name}*\n  Hata: {str(e)[:100]}")
                finally:
                    adapter.disconnect()

            await self.send_message(update.effective_chat.id, "\n".join(lines))

        except Exception as e:
            await update.message.reply_text(f"❌ DB durumu alınamadı:\n{str(e)[:200]}")

    async def _cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Son uygulanan aksiyonları listele."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        limit = 10
        if context.args:
            try:
                limit = min(int(context.args[0]), 50)
            except ValueError:
                pass

        try:
            from dba_agent.security.audit import AuditLogger
            audit = AuditLogger()
            records = audit.get_recent_actions(limit)

            if not records:
                await update.message.reply_text(
                    "📋 *Aksiyon Geçmişi*\n\nHenüz kayıtlı aksiyon yok.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            risk_emojis = {"safe": "🟢", "low": "🟡", "medium": "🟠", "high": "🔴"}
            lines = [f"📋 *Son {len(records)} Aksiyon*\n━━━━━━━━━━━━━━━━━━\n"]
            for rec in records:
                ts = rec.get("timestamp", "")[:16].replace("T", " ")
                risk = rec.get("risk_level", "safe")
                emoji = risk_emojis.get(risk, "⚪")
                result = rec.get("result", "?")
                result_emoji = "✅" if result == "success" else "❌"
                cmd = rec.get("command", "")[:60]
                target = rec.get("target", "")
                lines.append(
                    f"{result_emoji} {emoji} `{ts}`\n"
                    f"   📍 {target}\n"
                    f"   💬 `{cmd}`"
                )

            await self.send_message(
                update.effective_chat.id,
                "\n\n".join(lines),
            )

        except Exception as e:
            await update.message.reply_text(f"❌ Geçmiş alınamadı:\n{str(e)[:200]}")

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Aksiyon başarı istatistiklerini göster."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        try:
            from dba_agent.memory import get_incident_store
            store = get_incident_store()
            stats = store.get_action_stats()

            if stats["total"] == 0:
                await update.message.reply_text(
                    "📊 *Aksiyon İstatistikleri*\n\nHenüz kayıtlı incident yok.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            lines = [
                f"📊 *Aksiyon İstatistikleri*\n━━━━━━━━━━━━━━━━━━",
                f"📈 Toplam incident: *{stats['total']}*",
                f"✅ Başarı oranı: *{stats['success_rate']*100:.0f}%*",
                f"💊 Ort. sağlık iyileşmesi: *{stats['avg_health_delta']:+.1f}*",
                "",
                "🔧 *Aksiyon Bazlı:*",
            ]
            for action_name, s in stats["by_action"].items():
                bar = "█" * int(s["success_rate"] * 10) + "░" * (10 - int(s["success_rate"] * 10))
                lines.append(
                    f"  `{action_name[:25]}`\n"
                    f"  {bar} {s['success_rate']*100:.0f}% ({s['count']} kez)"
                )

            await self.send_message(
                update.effective_chat.id,
                "\n".join(lines),
            )

        except Exception as e:
            await update.message.reply_text(f"❌ İstatistikler alınamadı:\n{str(e)[:200]}")

    async def _cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Aktif tanıyı iptal et."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        chat_id = str(update.effective_chat.id)

        if chat_id in _active_diagnoses and not _active_diagnoses[chat_id].done():
            _active_diagnoses[chat_id].cancel()
            await update.message.reply_text("🚫 Tanı iptal ediliyor...")
        else:
            await update.message.reply_text("ℹ️ Aktif bir tanı işlemi yok.")

    async def _cmd_sql(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """SQL sorgusu çalıştır (read-only)."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        sql = " ".join(context.args) if context.args else ""
        if not sql:
            await update.message.reply_text(
                "❓ *SQL sorgusu gerekli*\n\n"
                "Kullanım:\n"
                "  /sql SELECT version()\n"
                "  /sql SELECT count(*) FROM pg\\_stat\\_activity\n"
                "  /sql SHOW max\\_connections\n\n"
                "⚠️ Sadece SELECT/SHOW/EXPLAIN/WITH izinli.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        await update.message.reply_text(f"🔄 SQL çalıştırılıyor...")

        try:
            from dba_agent.telegram.smart_handler import execute_tool, format_tool_result
            result = await execute_tool("execute_diagnostic_query", {"sql": sql})
            formatted = format_tool_result("execute_diagnostic_query", result)
            await self.send_message(update.effective_chat.id, formatted)
        except Exception as e:
            await update.message.reply_text(f"❌ SQL hatası: {str(e)[:300]}")

    async def _cmd_run(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """DBA aracını doğrudan çalıştır."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        args_list = context.args if context.args else []
        if not args_list:
            from dba_agent.tools import get_tool_registry
            registry = get_tool_registry()
            tools = registry.list_tools()
            tool_names = [f"`{t.name}`" for t in tools]
            await update.message.reply_text(
                "❓ *Araç adı gerekli*\n\n"
                "Kullanım:\n"
                "  /run get\\_health\n"
                "  /run get\\_active\\_connections\n"
                "  /run get\\_slow\\_queries limit=5\n"
                "  /run get\\_table\\_stats schema=public\n"
                "  /run get\\_cpu\\_usage\n\n"
                f"📋 Mevcut araçlar:\n{', '.join(tool_names)}",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        tool_name = args_list[0]
        # Args parse: key=value formatı
        tool_args = {}
        for a in args_list[1:]:
            if "=" in a:
                k, v = a.split("=", 1)
                # Tip dönüşümü
                try:
                    v = int(v)
                except ValueError:
                    try:
                        v = float(v)
                    except ValueError:
                        pass
                tool_args[k] = v

        await update.message.reply_text(f"🔧 `{tool_name}` çalıştırılıyor...", parse_mode=ParseMode.MARKDOWN)

        try:
            from dba_agent.telegram.smart_handler import execute_tool, format_tool_result
            result = await execute_tool(tool_name, tool_args)
            formatted = format_tool_result(tool_name, result)
            await self.send_message(update.effective_chat.id, formatted)
        except Exception as e:
            await update.message.reply_text(f"❌ Araç hatası: {str(e)[:300]}")

    async def _cmd_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Servis durumu kontrol et (SSH üzerinden)."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        service_name = context.args[0] if context.args else ""
        if not service_name:
            await update.message.reply_text(
                "❓ *Servis adı gerekli*\n\n"
                "Kullanım:\n"
                "  /service postgresql\n"
                "  /service mysql\n"
                "  /service nginx\n"
                "  /service docker\n\n"
                "📋 Servis durumunu SSH ile kontrol eder.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        ssh_target = context.args[1] if len(context.args) > 1 else None
        await update.message.reply_text(f"🔄 `{service_name}` kontrol ediliyor...", parse_mode=ParseMode.MARKDOWN)

        try:
            from dba_agent.telegram.smart_handler import execute_tool, format_tool_result
            result = await execute_tool("check_service_status", {
                "service_name": service_name,
                "ssh_target": ssh_target,
            })
            formatted = format_tool_result("check_service_status", result)
            await self.send_message(update.effective_chat.id, formatted)

            # Servis down ise logları da göster
            if result.get("success") and not result.get("result", {}).get("active"):
                log_result = await execute_tool("read_service_logs", {
                    "service_name": service_name,
                    "lines": 30,
                    "since": "30m",
                    "ssh_target": ssh_target,
                })
                log_formatted = format_tool_result("read_service_logs", log_result)
                await self.send_message(
                    update.effective_chat.id,
                    f"📋 *Son loglar ({service_name} down):*\n\n{log_formatted}",
                )

        except Exception as e:
            await update.message.reply_text(f"❌ SSH hatası: {str(e)[:300]}")

    async def _cmd_kill(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Oturum veya sorgu öldür."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        if not context.args:
            await update.message.reply_text(
                "❓ *PID gerekli*\n\n"
                "Kullanım:\n"
                "  /kill 12345 — Oturumu sonlandır\n"
                "  /kill 12345 cancel — Sadece sorguyu iptal et\n\n"
                "⚠️ `cancel` → nazik iptal (pg\\_cancel\\_backend)\n"
                "⚠️ PID alone → terminate (pg\\_terminate\\_backend)\n\n"
                "PID'leri görmek için: \"aktif bağlantılar\" yazın",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        try:
            pid = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ PID sayı olmalıdır.")
            return

        mode = context.args[1] if len(context.args) > 1 else "terminate"
        db_name = context.args[2] if len(context.args) > 2 else None

        if mode == "cancel":
            tool_name = "cancel_query"
            emoji = "🔄"
            label = "Sorgu iptal"
        else:
            tool_name = "kill_session"
            emoji = "💀"
            label = "Oturum sonlandırma"

        # Onay mekanizması — riskli işlem
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"✅ {label} (PID {pid})",
                    callback_data=f"dbaction:{tool_name}:{pid}:{db_name or ''}",
                ),
                InlineKeyboardButton("❌ İptal", callback_data="dbaction_cancel"),
            ]
        ])

        await update.message.reply_text(
            f"{emoji} *{label} — Onay Gerekli*\n\n"
            f"  PID: `{pid}`\n"
            f"  İşlem: `{tool_name}`\n\n"
            f"⚠️ Bu işlem geri alınamaz.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    async def _cmd_vacuum(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Tablo VACUUM."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        if not context.args:
            await update.message.reply_text(
                "❓ *Tablo adı gerekli*\n\n"
                "Kullanım:\n"
                "  /vacuum users — VACUUM ANALYZE\n"
                "  /vacuum public.orders — Schema ile\n"
                "  /vacuum users full — VACUUM FULL ⚠️\n\n"
                "⚠️ VACUUM FULL tablo kilitler, dikkatli kullanın.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        table_name = context.args[0]
        full_mode = len(context.args) > 1 and context.args[1].lower() == "full"
        db_name = None
        if len(context.args) > 2:
            db_name = context.args[2]

        tool_name = "vacuum_full_table" if full_mode else "vacuum_table"
        label = "VACUUM FULL" if full_mode else "VACUUM ANALYZE"

        await update.message.reply_text(
            f"🧹 `{label} {table_name}` çalıştırılıyor...",
            parse_mode=ParseMode.MARKDOWN,
        )

        try:
            from dba_agent.telegram.smart_handler import execute_tool, format_tool_result
            args = {"table_name": table_name}
            if db_name:
                args["db_name"] = db_name
            if not full_mode:
                args["analyze"] = True

            result = await execute_tool(tool_name, args)
            formatted = format_tool_result(tool_name, result)
            await self.send_message(update.effective_chat.id, formatted)
        except Exception as e:
            await update.message.reply_text(f"❌ VACUUM hatası: {str(e)[:300]}")

    async def _cmd_ssh(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """SSH üzerinden sistem bilgisi."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        sub_cmd = context.args[0] if context.args else "info"
        ssh_target = context.args[1] if len(context.args) > 1 else None

        tool_map = {
            "info": ("get_system_info", {}),
            "disk": ("check_disk_space", {}),
            "ps": ("check_process_list", {}),
            "process": ("check_process_list", {}),
            "port": ("check_port", {"port": int(context.args[1]) if len(context.args) > 1 else 5432}),
        }

        if sub_cmd not in tool_map:
            await update.message.reply_text(
                "❓ *SSH Alt Komutlar*\n\n"
                "  /ssh info — Sistem bilgisi\n"
                "  /ssh disk — Disk durumu\n"
                "  /ssh ps — Process listesi\n"
                "  /ssh port 5432 — Port kontrolü\n\n"
                "Alternatif:\n"
                "  /service postgresql — Servis durumu\n"
                "  /run read\\_service\\_logs service\\_name=postgresql",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        tool_name, default_args = tool_map[sub_cmd]
        if ssh_target and sub_cmd != "port":
            default_args["ssh_target"] = ssh_target

        await update.message.reply_text(f"🔄 SSH: `{sub_cmd}` çalıştırılıyor...", parse_mode=ParseMode.MARKDOWN)

        try:
            from dba_agent.telegram.smart_handler import execute_tool, format_tool_result
            result = await execute_tool(tool_name, default_args)
            formatted = format_tool_result(tool_name, result)
            await self.send_message(update.effective_chat.id, formatted)
        except Exception as e:
            await update.message.reply_text(f"❌ SSH hatası: {str(e)[:300]}")

    async def _cmd_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Proaktif izleme durumu ve kontrolü.

        Kullanım:
          /monitor           — Durum göster
          /monitor start     — İzlemeyi başlat
          /monitor stop      — İzlemeyi durdur
          /monitor interval 120 — Kontrol aralığını değiştir (saniye)
        """
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Yetkisiz erişim.")
            return

        from dba_agent.monitoring import get_health_monitor
        monitor = get_health_monitor()
        sub = context.args[0].lower() if context.args else "status"

        if sub == "start":
            if monitor.is_running:
                await update.message.reply_text("⚠️ İzleme zaten çalışıyor.")
            else:
                await monitor.start()
                await update.message.reply_text(
                    f"✅ Proaktif izleme başlatıldı\n"
                    f"  Aralık: {monitor.thresholds.check_interval_sec}s\n"
                    f"  Long query eşiği: {monitor.thresholds.long_query_sec}s\n"
                    f"  Cooldown: {monitor.thresholds.alert_cooldown_sec}s"
                )

        elif sub == "stop":
            await monitor.stop()
            await update.message.reply_text("⏸️ Proaktif izleme durduruldu.")

        elif sub == "interval" and len(context.args) > 1:
            try:
                secs = int(context.args[1])
                monitor.thresholds.check_interval_sec = secs
                await update.message.reply_text(f"✅ Kontrol aralığı {secs}s olarak ayarlandı.")
            except ValueError:
                await update.message.reply_text("❌ Geçersiz değer. Örnek: /monitor interval 120")

        else:
            # Durum göster
            stats = monitor.stats
            running_emoji = "✅" if stats["running"] else "⏸️"
            thr = monitor.thresholds
            text = (
                "👁️ *Proaktif İzleme Durumu*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"  {running_emoji} Durum: {'Aktif' if stats['running'] else 'Pasif'}\n"
                f"  🔁 Kontrol sayısı: {stats['check_count']}\n"
                f"  🚨 Alert sayısı: {stats['alert_count']}\n"
                f"  ⏱️ Aralık: {stats['check_interval_sec']}s\n"
                f"  🕒 Cooldown: {thr.alert_cooldown_sec}s\n\n"
                f"*Eşik Değerleri:*\n"
                f"  🐌 Uzun sorgu: >{thr.long_query_sec}s\n"
                f"  🔒 Kilitler: >={thr.blocked_lock_count}\n"
                f"  🔗 Bağlantı: >%{thr.connection_usage_pct}\n"
                f"  💾 Cache hit min: %{thr.cache_hit_min_pct}\n"
                f"  🔄 Rep. lag: >{thr.replication_lag_sec}s\n"
                f"  🏥 Min. skor: {thr.health_score_min}/100\n\n"
                f"*Kontrol:*\n"
                f"  /monitor start — Başlat\n"
                f"  /monitor stop — Durdur\n"
                f"  /monitor interval 60 — Aralık ayarla"
            )
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Serbest metin — Akıllı DBA Agent mesaj işleyici."""
        if not self._is_authorized(update.effective_chat.id):
            return

        user_text = update.message.text.strip()
        if not user_text:
            return

        chat_id = str(update.effective_chat.id)

        # Tanı tetikleyici — uzun açıklamalı mesajlarda tanı öner
        diag_keywords = [
            "tanı yap", "diagnose", "teşhis et", "tam analiz",
            "neden çöktü", "sorun tespit", "root cause",
        ]
        is_full_diag = any(kw in user_text.lower() for kw in diag_keywords)

        if is_full_diag:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Tanı Başlat", callback_data=f"diag_confirm:{user_text[:100]}"),
                    InlineKeyboardButton("❌ İptal", callback_data="diag_cancel"),
                ]
            ])
            await update.message.reply_text(
                f"🔍 *Tam tanı pipeline başlatılsın mı?*\n\n"
                f"📋 _{user_text[:200]}_\n\n"
                f"Bu işlem birkaç dakika sürebilir.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        else:
            # ── Akıllı DBA handler — intent → tool → sonuç ──
            try:
                from dba_agent.telegram.smart_handler import handle_smart_message
                await handle_smart_message(
                    user_text=user_text,
                    chat_id=chat_id,
                    send_func=self.send_message,
                )
            except Exception as e:
                logger.error(f"Smart handler hatası: {e}", exc_info=True)
                await update.message.reply_text(
                    "❌ İşlem sırasında hata oluştu.\n"
                    "Komutları deneyebilirsiniz:\n"
                    "  /status — Sistem durumu\n"
                    "  /db — DB bağlantıları\n"
                    "  /sql SELECT version()\n"
                    "  /diagnose — Tam tanı"
                )

    async def _callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inline keyboard callback handler."""
        query = update.callback_query
        await query.answer()

        if not self._is_authorized(query.message.chat.id):
            await query.edit_message_text("⛔ Yetkisiz erişim.")
            return

        data = query.data
        chat_id = str(query.message.chat.id)

        if data.startswith("diag_confirm:"):
            alert_text = data[len("diag_confirm:"):]
            await query.edit_message_text(
                f"🔍 *Tanı başlatıldı*\n📋 _{alert_text}_\n\n⏳ Lütfen bekleyin...",
                parse_mode=ParseMode.MARKDOWN,
            )
            task = asyncio.create_task(
                self._run_diagnosis(chat_id, alert_text)
            )
            _active_diagnoses[chat_id] = task

        elif data == "diag_cancel":
            await query.edit_message_text("❌ Tanı iptal edildi.")

        elif data.startswith("approve:"):
            from dba_agent.telegram.approval import handle_approval
            await handle_approval(query, data, approved=True)

        elif data.startswith("reject:"):
            from dba_agent.telegram.approval import handle_approval
            await handle_approval(query, data, approved=False)

        elif data.startswith("detail:"):
            alert_id = data[len("detail:"):]
            from dba_agent.telegram.approval import get_pending_approval
            approval = get_pending_approval(alert_id)
            if not approval:
                await query.answer("⏰ Onay süresi doldu veya bulunamadı.", show_alert=True)
                return
            actions = approval.get("actions", [])
            lines = [f"📋 *Aksiyon Detayları*\n🏷️ Alert: `{alert_id}`\n"]
            risk_emojis = {"safe": "🟢", "low": "🟡", "medium": "🟠", "high": "🔴"}
            for i, a in enumerate(actions, 1):
                risk = a.get("risk", "safe")
                emoji = risk_emojis.get(risk, "⚪")
                lines.append(
                    f"{i}. {emoji} *{a.get('action', 'Bilinmeyen')}*\n"
                    f"   Risk: `{risk}`\n"
                    f"   SQL: `{a.get('sql', '-')[:120]}`\n"
                    f"   Sebep: _{a.get('reason', '-')[:100]}_"
                )
            await query.answer()
            await bot.send_message(
                chat_id,
                "\n\n".join(lines),
                parse_mode=ParseMode.MARKDOWN,
            )

        elif data.startswith("dbaction:"):
            # DB action onay — format: dbaction:tool_name:pid:db_name
            parts = data.split(":")
            if len(parts) >= 3:
                tool_name = parts[1]
                pid = int(parts[2])
                db_name = parts[3] if len(parts) > 3 and parts[3] else None

                await query.edit_message_text(
                    f"⏳ `{tool_name}` çalıştırılıyor (PID {pid})...",
                    parse_mode=ParseMode.MARKDOWN,
                )

                try:
                    from dba_agent.telegram.smart_handler import execute_tool, format_tool_result
                    result = await execute_tool(tool_name, {"pid": pid, "db_name": db_name})
                    formatted = format_tool_result(tool_name, result)
                    await self.send_message(chat_id, formatted)
                except Exception as e:
                    await self.send_message(chat_id, f"❌ Hata: {str(e)[:300]}")

        elif data == "dbaction_cancel":
            await query.edit_message_text("❌ İşlem iptal edildi.")

        elif data.startswith("smartact_ok:"):
            # Doğal dil ile istenen aksiyon onaylandı
            token = data[len("smartact_ok:"):]
            await query.edit_message_text(
                "✅ *Onaylandı* — aksiyon uygulanıyor...",
                parse_mode=ParseMode.MARKDOWN,
            )
            from dba_agent.telegram.smart_handler import execute_pending_smart_action
            await execute_pending_smart_action(
                token=token,
                chat_id=chat_id,
                send_func=self.send_message,
            )

        elif data.startswith("smartact_cancel:"):
            token = data[len("smartact_cancel:"):]
            # Bekleyen aksiyonu temizle
            from dba_agent.telegram.smart_handler import _PENDING_SMART_ACTIONS
            _PENDING_SMART_ACTIONS.pop(token, None)
            await query.edit_message_text("❌ Aksiyon iptal edildi.")

        elif data.startswith("feedback_"):
            # feedback_good:incident_id | feedback_bad:incident_id | feedback_partial:incident_id
            parts = data.split(":", 1)
            if len(parts) == 2:
                sentiment, incident_id = parts[0].replace("feedback_", ""), parts[1]
                score_map = {"good": 1.0, "partial": 0.5, "bad": 0.0}
                score = score_map.get(sentiment, 0.5)
                emoji_map = {"good": "👍", "partial": "😐", "bad": "👎"}
                emoji = emoji_map.get(sentiment, "💬")
                try:
                    from dba_agent.memory import get_incident_store
                    store = get_incident_store()
                    updated = store.update_feedback(incident_id, score)
                    msg = (
                        f"{emoji} *Geri bildirim kaydedildi*\n"
                        f"Incident: `{incident_id}`\n"
                        f"Skor: {score}"
                    ) if updated else f"⚠️ Incident bulunamadı: `{incident_id}`"
                    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    await query.edit_message_text(f"❌ Geri bildirim kaydedilemedi:\n{str(e)[:200]}")


# ─────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ─────────────────────────────────────────────

def _split_message(text: str, max_length: int = 4096) -> list:
    """Uzun mesajı Telegram limiti içinde parçala."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Satır sonuna göre böl
        split_pos = text.rfind("\n", 0, max_length)
        if split_pos == -1:
            split_pos = max_length

        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")

    return chunks


# ─── Singleton ────────────────────────────────
_bot: Optional[DBABot] = None


def get_bot() -> DBABot:
    """Bot singleton'ı döndürür."""
    global _bot
    if _bot is None:
        _bot = DBABot()
    return _bot
