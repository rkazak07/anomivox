"""
Anomivox Mail Bildirim Servisi
SMTP üzerinden alert, teşhis ve sağlık kontrolü bildirimleri gönderir.

Standalone çalışmaz — API servisi içinden import edilir veya
alert webhook olarak kullanılır.
"""

import os
import sys
import ssl
import smtplib
import logging
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("anomivox.mail")


# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────
def _load_config():
    """Load Mail config from configs module."""
    try:
        from configs.mail_config import (
            MAIL_SMTP_HOST, MAIL_SMTP_PORT,
            MAIL_SMTP_USE_TLS, MAIL_SMTP_USE_SSL,
            MAIL_USERNAME, MAIL_PASSWORD,
            MAIL_FROM_NAME, MAIL_FROM_ADDRESS,
            MAIL_RECIPIENTS,
            MAIL_NOTIFY_ON_ALERT, MAIL_NOTIFY_ON_DIAGNOSIS,
            MAIL_NOTIFY_ON_HEALTH,
            MAIL_HEALTH_CHECK_INTERVAL, MAIL_SLOW_QUERY_THRESHOLD,
        )
        return {
            "smtp_host": MAIL_SMTP_HOST,
            "smtp_port": MAIL_SMTP_PORT,
            "use_tls": MAIL_SMTP_USE_TLS,
            "use_ssl": MAIL_SMTP_USE_SSL,
            "username": MAIL_USERNAME,
            "password": MAIL_PASSWORD,
            "from_name": MAIL_FROM_NAME,
            "from_address": MAIL_FROM_ADDRESS,
            "recipients": MAIL_RECIPIENTS,
            "notify_on_alert": MAIL_NOTIFY_ON_ALERT,
            "notify_on_diagnosis": MAIL_NOTIFY_ON_DIAGNOSIS,
            "notify_on_health": MAIL_NOTIFY_ON_HEALTH,
            "health_check_interval": MAIL_HEALTH_CHECK_INTERVAL,
            "slow_query_threshold": MAIL_SLOW_QUERY_THRESHOLD,
        }
    except ImportError as e:
        logger.error(f"Mail config import hatası: {e}")
        return None


CONFIG = _load_config()


# ─────────────────────────────────────────
# Mail Gönderme
# ─────────────────────────────────────────
def send_mail(subject: str, body_html: str, body_text: str = None, recipients: list = None) -> bool:
    """SMTP üzerinden mail gönder."""
    if not CONFIG:
        logger.warning("Mail config yüklenemedi.")
        return False

    smtp_host = CONFIG["smtp_host"]
    smtp_port = CONFIG["smtp_port"]
    username = CONFIG["username"]
    password = CONFIG["password"]
    from_addr = CONFIG["from_address"] or username
    from_name = CONFIG["from_name"] or "Anomivox"

    if not smtp_host or not username:
        logger.warning("SMTP host veya kullanıcı adı eksik, mail gönderilemedi.")
        return False

    to_list = recipients or CONFIG.get("recipients", [])
    if not to_list:
        logger.warning("Alıcı adresi yok, mail gönderilemedi.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_addr}>"
        msg["To"] = ", ".join(to_list)

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        if CONFIG["use_ssl"]:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, context=context)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            if CONFIG["use_tls"]:
                server.starttls()

        if username and password:
            server.login(username, password)

        server.sendmail(from_addr, to_list, msg.as_string())
        server.quit()

        logger.info(f"Mail gönderildi: {subject} → {', '.join(to_list)}")
        return True

    except Exception as e:
        logger.error(f"Mail gönderim hatası: {e}")
        return False


async def send_mail_async(subject: str, body_html: str, body_text: str = None, recipients: list = None) -> bool:
    """Mail'i thread pool'da gönder (async uyumlu)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, send_mail, subject, body_html, body_text, recipients)


# ─────────────────────────────────────────
# Template Fonksiyonları
# ─────────────────────────────────────────
def _html_template(title: str, content: str) -> str:
    """Anomivox markalı HTML mail template."""
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
    .container {{ max-width: 600px; margin: 20px auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
    .header {{ background: linear-gradient(135deg, #667eea, #764ba2); padding: 24px 32px; color: #fff; }}
    .header h1 {{ margin: 0; font-size: 20px; font-weight: 600; }}
    .header .subtitle {{ margin: 4px 0 0; font-size: 13px; opacity: 0.85; }}
    .body {{ padding: 24px 32px; color: #333; line-height: 1.6; }}
    .body h2 {{ font-size: 16px; color: #333; margin: 0 0 12px; }}
    .metric {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }}
    .metric:last-child {{ border-bottom: none; }}
    .metric .label {{ color: #666; font-size: 14px; }}
    .metric .value {{ font-weight: 600; font-size: 14px; }}
    .status-ok {{ color: #52c41a; }}
    .status-warn {{ color: #faad14; }}
    .status-error {{ color: #f5222d; }}
    .alert-card {{ background: #fff2f0; border: 1px solid #ffa39e; border-radius: 8px; padding: 16px; margin: 12px 0; }}
    .alert-card.resolved {{ background: #f6ffed; border-color: #b7eb8f; }}
    .code {{ background: #f5f5f5; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 13px; overflow-x: auto; margin: 8px 0; }}
    .footer {{ padding: 16px 32px; background: #fafafa; color: #999; font-size: 12px; text-align: center; border-top: 1px solid #eee; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🔮 Anomivox</h1>
      <div class="subtitle">{title}</div>
    </div>
    <div class="body">
      {content}
    </div>
    <div class="footer">
      Anomivox Autonomous Database Management System &bull; {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
  </div>
</body>
</html>
"""


def send_alert_mail(alerts: list) -> bool:
    """Prometheus alert bildirimi maili gönder."""
    if not CONFIG or not CONFIG.get("notify_on_alert"):
        return False

    firing = [a for a in alerts if a.get("status") == "firing"]
    resolved = [a for a in alerts if a.get("status") == "resolved"]

    content_parts = []

    if firing:
        content_parts.append(f"<h2>🚨 {len(firing)} Aktif Alert</h2>")
        for a in firing:
            name = a.get("labels", {}).get("alertname", "Unknown")
            severity = a.get("labels", {}).get("severity", "?")
            desc = a.get("annotations", {}).get("description", "")
            summary = a.get("annotations", {}).get("summary", "")
            content_parts.append(f"""
            <div class="alert-card">
                <strong>{name}</strong> <span class="status-error">[{severity}]</span><br>
                {f'<p>{summary}</p>' if summary else ''}
                {f'<p style="color:#666;font-size:13px">{desc}</p>' if desc else ''}
            </div>
            """)

    if resolved:
        content_parts.append(f"<h2>✅ {len(resolved)} Çözülen Alert</h2>")
        for a in resolved:
            name = a.get("labels", {}).get("alertname", "Unknown")
            content_parts.append(f"""
            <div class="alert-card resolved">
                <strong>{name}</strong> <span class="status-ok">[çözüldü]</span>
            </div>
            """)

    subject = f"{'🚨' if firing else '✅'} Anomivox Alert — {len(firing)} aktif, {len(resolved)} çözülen"
    body_html = _html_template("Prometheus Alert Bildirimi", "\n".join(content_parts))
    body_text = f"Aktif: {len(firing)}, Çözülen: {len(resolved)}"

    return send_mail(subject, body_html, body_text)


def send_diagnosis_mail(report: str, status: str = "completed") -> bool:
    """Teşhis raporu maili gönder."""
    if not CONFIG or not CONFIG.get("notify_on_diagnosis"):
        return False

    content = f"""
    <h2>📋 Teşhis Raporu</h2>
    <div class="metric">
        <span class="label">Durum</span>
        <span class="value {'status-ok' if status == 'completed' else 'status-warn'}">{status}</span>
    </div>
    <div class="code">{report[:3000]}</div>
    """

    subject = f"📋 Anomivox Teşhis Raporu — {status}"
    body_html = _html_template("Veritabanı Teşhis Raporu", content)

    return send_mail(subject, body_html, report[:3000])


def send_password_reset_mail(email: str, username: str, reset_token: str, base_url: str) -> bool:
    """Parola sıfırlama linki maili gönder."""
    reset_url = f"{base_url.rstrip('/')}/#/reset-password?token={reset_token}"
    content = f"""
    <h2>🔑 Parola Sıfırlama</h2>
    <p>Merhaba <strong>{username}</strong>,</p>
    <p>Hesabınız için parola sıfırlama talebinde bulunuldu. Aşağıdaki butona tıklayarak yeni parolanızı belirleyebilirsiniz.</p>
    <p style="text-align:center; margin: 24px 0;">
        <a href="{reset_url}"
           style="background:#667eea; color:#fff; padding:12px 28px; border-radius:8px;
                  text-decoration:none; font-weight:600; display:inline-block;">
            Parolayı Sıfırla
        </a>
    </p>
    <p style="color:#888; font-size:13px;">Bu link <strong>30 dakika</strong> geçerlidir. Eğer bu talebi siz yapmadıysanız bu e-postayı görmezden gelin.</p>
    <div class="code" style="word-break:break-all;">{reset_url}</div>
    """
    subject = "🔑 Anomivox — Parola Sıfırlama"
    body_html = _html_template("Parola Sıfırlama Talebi", content)
    body_text = f"Parola sıfırlama linki: {reset_url}\n\nBu link 30 dakika geçerlidir."
    return send_mail(subject, body_html, body_text, recipients=[email])


def send_health_mail(issues: list) -> bool:
    """Sağlık kontrolü uyarı maili gönder."""
    if not CONFIG or not CONFIG.get("notify_on_health"):
        return False

    if not issues:
        return False

    content = f"<h2>⚠️ {len(issues)} Sorun Tespit Edildi</h2>"
    for issue in issues:
        content += f"""
        <div class="metric">
            <span class="label">{issue}</span>
            <span class="value status-warn">⚠️</span>
        </div>
        """

    subject = f"⚠️ Anomivox Sağlık Uyarısı — {len(issues)} sorun"
    body_html = _html_template("Proaktif Sağlık Kontrolü", content)
    body_text = "\n".join(issues)

    return send_mail(subject, body_html, body_text)
