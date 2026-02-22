FROM python:3.10-slim

WORKDIR /app

# ── Sistem bağımlılıkları + Node.js 18 ──────────────────────
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    g++ \
    build-essential \
    libpq-dev \
    curl \
    libmagic1 \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# pnpm (package.json'da belirtilen sürüm: pnpm@7.9.0)
RUN npm install -g pnpm@7.9.0

# ── Python bağımlılıkları (layer cache için önce) ────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# NLTK veri setlerini önceden indir
RUN python -m nltk.downloader punkt stopwords averaged_perceptron_tagger

# ── Node bağımlılıkları (layer cache için önce package.json + .npmrc) ──
# .npmrc: strict-peer-dependencies=false, shamefully-hoist=true
COPY webui/package.json webui/.npmrc ./webui/
RUN cd webui && pnpm install

# ── Uygulama kodunu kopyala ──────────────────────────────────
COPY . .

# ── reports_ui Vue bileşenini derle ──────────────────────────
RUN cd webui_pages/reports/reports_ui && \
    npm install && \
    NODE_OPTIONS=--openssl-legacy-provider npm run build

# entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 7861 18501

ENTRYPOINT ["/entrypoint.sh"]
