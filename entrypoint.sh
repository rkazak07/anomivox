#!/bin/bash
set -e

# ── 1. Config dosyaları yoksa .example'dan kopyala ──────────
CONFIG_FILES=(
    "model_config.py"
    "server_config.py"
    "kb_config.py"
    "basic_config.py"
    "prompt_config.py"
    "diagnose_config.py"
    "mail_config.py"
)

for f in "${CONFIG_FILES[@]}"; do
    if [ ! -f "configs/$f" ]; then
        echo "[entrypoint] configs/$f bulunamadı, .example'dan kopyalanıyor..."
        cp "configs/$f.example" "configs/$f"
    fi
done

# ── 2. OPENAI_API_KEY → model_config.py ─────────────────────
if [ -n "$OPENAI_API_KEY" ]; then
    echo "[entrypoint] OPENAI_API_KEY model_config.py'ye yazılıyor..."
    python3 - <<PYEOF
import re

with open("configs/model_config.py", "r") as f:
    content = f.read()

# openai-api bloğundaki api_key değerini doldur
content = re.sub(
    r'("openai-api".*?"api_key":\s*)"[^"]*"',
    lambda m: m.group(0).replace(m.group(0), m.group(0).rsplit('"', 2)[0] + '"${OPENAI_API_KEY}"'),
    content,
    flags=re.DOTALL
)

# text-embedding-ada-002 için placeholder'ı doldur
content = content.replace('"your OPENAI_API_KEY"', '"${OPENAI_API_KEY}"')

with open("configs/model_config.py", "w") as f:
    f.write(content)
PYEOF
fi

# ── 3. WEBUI_API_URL → server_config.py (Docker iç ağ adresi) ──
# Docker'da WebUI konteyneri API'ye "localhost" yerine servis adıyla ulaşır.
# Örnek: WEBUI_API_URL=api:7861
# startup.py bu değeri okuyup webui/.env.serve-dev dosyasına yazar.
if [ -n "$WEBUI_API_URL" ]; then
    echo "[entrypoint] WEBUI_API_URL server_config.py'ye yazılıyor: $WEBUI_API_URL"
    sed -i "s|\"api_base_url\": \"[^\"]*\"|\"api_base_url\": \"${WEBUI_API_URL}\"|g" configs/server_config.py
fi

# ── 4. Uygulamayı başlat ─────────────────────────────────────
# APP_MODE değerleri: api | webui | all-webui | all-api | lite | python_app
MODE=${APP_MODE:-all-webui}

if [ "$MODE" = "python_app" ]; then
    echo "[entrypoint] Başlatılıyor: python3 prometheus_service_docker/app.py"
    exec python3 prometheus_service_docker/app.py
else
    echo "[entrypoint] Başlatılıyor: python startup.py --${MODE}"
    exec python startup.py --${MODE}
fi
