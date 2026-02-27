#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════
# OpenClaw Gateway Entrypoint
# ═══════════════════════════════════════════════════════════
# Tüm konfigürasyon environment variable'lardan okunur.
# İlk çalıştırmada openclaw.json oluşturulur.
# Sonraki çalıştırmalarda mevcut config korunur.
# ═══════════════════════════════════════════════════════════

OPENCLAW_HOME="${OPENCLAW_HOME:-/home/node/.openclaw}"
CONFIG_FILE="${OPENCLAW_HOME}/openclaw.json"
GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
GATEWAY_BIND="${OPENCLAW_GATEWAY_BIND:-lan}"
GATEWAY_MODE="${OPENCLAW_GATEWAY_MODE:-local}"

# ── Volume permission fix (root olarak çalışır) ──────────
if [ "$(id -u)" = "0" ]; then
    mkdir -p "${OPENCLAW_HOME}/workspace/skills"
    chown -R node:node "${OPENCLAW_HOME}"
    # node kullanıcısına geçiş yap ve aynı script'i tekrar çalıştır
    exec gosu node "$0" "$@"
fi

# Buradan itibaren node kullanıcısı olarak çalışır
mkdir -p "${OPENCLAW_HOME}/workspace/skills" 2>/dev/null || true

# ── Config dosyası yoksa env'den oluştur ──────────────────
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "[ai-agent] İlk çalıştırma — config oluşturuluyor..."

    # Model ayarı
    MODEL="${OPENCLAW_MODEL:-anthropic/claude-opus-4-6}"

    # JSON config oluştur
    cat > "${CONFIG_FILE}" << EOF
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "${MODEL}",
        "fallbacks": []
      }
    }
  },
  "gateway": {
    "port": ${GATEWAY_PORT},
    "bind": "${GATEWAY_BIND}",
    "mode": "${GATEWAY_MODE}",
    "controlUi": {
      "dangerouslyAllowHostHeaderOriginFallback": true
    }
  },
  "channels": {},
  "browser": {
    "enabled": false
  }
}
EOF

    # Telegram konfigürasyonu (eğer token varsa)
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
        echo "[ai-agent] Telegram bot konfigürasyonu ekleniyor..."
        TMP=$(mktemp)
        jq --arg token "$TELEGRAM_BOT_TOKEN" \
           '.channels.telegram = {"botToken": $token}' \
           "${CONFIG_FILE}" > "$TMP" && mv "$TMP" "${CONFIG_FILE}"
    fi

    # Discord konfigürasyonu (eğer token varsa)
    if [ -n "${DISCORD_BOT_TOKEN:-}" ]; then
        echo "[ai-agent] Discord bot konfigürasyonu ekleniyor..."
        TMP=$(mktemp)
        jq --arg token "$DISCORD_BOT_TOKEN" \
           '.channels.discord = {"token": $token}' \
           "${CONFIG_FILE}" > "$TMP" && mv "$TMP" "${CONFIG_FILE}"
    fi

    # Slack konfigürasyonu (eğer token varsa)
    if [ -n "${SLACK_BOT_TOKEN:-}" ] && [ -n "${SLACK_APP_TOKEN:-}" ]; then
        echo "[ai-agent] Slack bot konfigürasyonu ekleniyor..."
        TMP=$(mktemp)
        jq --arg bot "$SLACK_BOT_TOKEN" --arg app "$SLACK_APP_TOKEN" \
           '.channels.slack = {"botToken": $bot, "appToken": $app}' \
           "${CONFIG_FILE}" > "$TMP" && mv "$TMP" "${CONFIG_FILE}"
    fi

    # Gateway auth token (eğer varsa)
    if [ -n "${OPENCLAW_GATEWAY_TOKEN:-}" ]; then
        echo "[ai-agent] Gateway auth token ekleniyor..."
        TMP=$(mktemp)
        jq --arg token "$OPENCLAW_GATEWAY_TOKEN" \
           '.gateway.auth = {"token": $token}' \
           "${CONFIG_FILE}" > "$TMP" && mv "$TMP" "${CONFIG_FILE}"
    fi

    echo "[ai-agent] Config oluşturuldu: ${CONFIG_FILE}"
else
    echo "[ai-agent] Mevcut config kullanılıyor: ${CONFIG_FILE}"
fi

echo "[ai-agent] ────────────────────────────────────────"
echo "[ai-agent] AI Agent Gateway başlatılıyor..."
echo "[ai-agent] Port: ${GATEWAY_PORT}"
echo "[ai-agent] Bind: ${GATEWAY_BIND}"
echo "[ai-agent] Mode: ${GATEWAY_MODE}"
echo "[ai-agent] Config: ${CONFIG_FILE}"
echo "[ai-agent] ────────────────────────────────────────"

# Gateway'i başlat
exec openclaw gateway --port "${GATEWAY_PORT}" --allow-unconfigured
