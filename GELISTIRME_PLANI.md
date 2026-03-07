# Anomivox — Proje Analizi & Geliştirme Planı

> Oluşturulma: 2026-03-07
> Versiyon: v0.2.0 üzerine analiz

---

## 1. Projenin Çalışma Mimarisi

### 1.1 Servis Katmanları

```
[Kullanici]
    |
    +-- Streamlit WebUI (18501)  <-- webui.py + webui_pages/
    |
    +-- FastAPI REST API (7861)  <-- server/api.py
    |       |
    |       +-- Auth / Kullanici Yonetimi
    |       +-- Chat (LLM, RAG, KB)
    |       +-- Knowledge Base (KB)
    |       +-- Diagnose (Tani)
    |       +-- Dashboard
    |       +-- Mail / Telegram Alert
    |       +-- DBA Agent proxy
    |
    +-- DBA Agent (8100)         <-- dba_agent/main.py
    |
    +-- LiteLLM Gateway (4000)   <-- ai-agent-gateway
    |       |
    |       +-- Ollama (yerel LLM)
    |       +-- OpenAI / Gemini / Groq / Anthropic / DeepSeek
    |
[Altyapi]
    +-- PostgreSQL (5432)        <-- pg_data volume
    +-- ChromaDB (embedded)      <-- chroma_db/ volume (container icinde)
    +-- Prometheus (9090)
    +-- Alertmanager (9093)
    +-- Node Exporter (9100)
    +-- PG Exporter (9187)
    +-- Notify Worker (8023)     <-- prometheus_service_docker/app.py
```

### 1.2 Baslatma Akisi

```
docker compose up
    |
    +--> entrypoint.sh
            |
            1. configs/*.py yoksa .example'dan kopyala
            2. OPENAI_API_KEY varsa model_config.py'e yaz
            3. WEBUI_API_URL varsa server_config.py'e yaz
            4. APP_MODE'a gore startup.py --<mode> calistir
                |
                +-- api   : FastAPI (uvicorn, 7861)
                +-- webui : Streamlit (pnpm dev, 18501)
```

### 1.3 Tani (Diagnose) Akisi

```
Prometheus Alert
    |
    v
Notify Worker (app.py)
    |-- Alert JSON'u parse eder
    |-- anomaly_trigger/ altina kaydeder
    |-- DBA Agent'a bildirim gonder (HTTP)
    |-- Telegram'a bildirim gonder
    |
    v
MultiAgents.from_task()  <-- multiagents/multiagents.py
    |
    +-- Reporter Agent (ChiefDBA)
    +-- RoleAssigner Agent  --> KB'den uzman isimleri ceker
    +-- Solver Agents (her uzman icin)
            |
            +-- ChromaDB RAG sorgusu
            +-- Prometheus metrik cekme
            +-- Kok neden analizi
            +-- Cozum onerisi
    |
    v
UCT Tree-of-Thought  <-- multiagents/reasoning_algorithms/tree_of_thought/
    |
    v
Tani Raporu (JSON/JSONL)
    |
    +-- WebUI'a gosterilir
    +-- Telegram'a iletilir
```

### 1.4 DBA Agent Akisi

```
DBA Agent (dba_agent/)
    |
    +-- /health          : Saglik durumu
    +-- Telegram Bot     : 7/24 komut arayuzu
    +-- Tool Registry    : Kayitli araclar
            |
            +-- db_diagnostic.py  : get_health, get_connections, get_slow_queries...
            +-- metric_tools.py   : Prometheus metrik sorgu
            +-- os_tools.py       : SSH ile OS analizi
            +-- db_action_tools.py: Aksiyon araclari (RISK: LOW/MEDIUM/HIGH)
            +-- ssh_executor.py   : Sunucuya SSH baglantisi
    |
    +-- LiteLLM Gateway uzerinden model routing:
            Triage  --> llama3.2:1b  (< 1 sn)
            SQL     --> sqlcoder     (3-8 sn)
            DBA/Planlama --> llama3.1:8b (3-8 sn)
```

### 1.5 Knowledge Base (KB) Akisi

```
Dokuman Yukleme
    |
    +-- upload_docs()  --> fiziksel dosya knowledge_base/<kb>/ altina
    +-- KnowledgeFile  --> document loader (PDF, DOCX, TXT, MD...)
    +-- text_splitter  --> chunk'lara bol
    +-- EmbeddingsFunAdapter --> vektorlestir
    +-- ChromaDB.add_texts() --> chroma_db/ altina kaydet
    +-- add_file_to_db()     --> PostgreSQL'e metadata kaydet
```

---

## 2. Mevcut Eksikler & Bilinen Sorunlar

| # | Alan | Sorun | Etki |
|---|------|-------|------|
| 1 | DBA Agent | Phase 5 (aksiyon yurutme) implement edilmemis | Oneriler var ama calistirilmiyor |
| 2 | Guvenlik | `.env` ve `configs/*.py` dosyalarinda hardcoded API key'ler | Repo'ya sizdiysa kritik |
| 3 | Guvenlik | Auth token'lari sadece bellekte, restart'ta siliniyor | Kullanicilar her restart'ta cikiyor |
| 4 | KB | ChromaDB silme: source path uyumsuzlugu (duzeltildi) | Dosyalar silinmiyordu |
| 5 | KB | Desteklenmeyen format 500 donuyordu (duzeltildi) | UI cokuyordu |
| 6 | Bagimlılık | LangChain 0.0.344 (cok eski) | Guvenlik/uyumluluk riski |
| 7 | Yapilandirma | `.gitignore` yok | Gizli dosyalar repoya girebilir |
| 8 | ChromaDB | Embedded mod, container icinde, volume mount eksik | Restart'ta veri kaybi riski |
| 9 | KB | `.jsonl` format hatali parse ediliyor | JSONL dokumanlari yuklenemiyor |
| 10 | DBA Agent | Ollama URL `localhost` hardcoded | Docker aginda calismiyor |

---

## 3. Gelistirme Plani — Oncelik Sirasina Gore

---

### ONCELIK 1 — Kritik / Guvenlik

#### 3.1 `.gitignore` Ekle
**Sorun:** `configs/*.py`, `.env`, `chroma_db/`, `knowledge_base/` gibi hassas dosyalar commit edilebilir.
**Yapilacak:**
- Root `.gitignore` olustur
- `configs/*.py` (sadece `.example` dosyalari commit edilmeli)
- `.env`, `*.jsonl` (veri dosyalari), `chroma_db/`, `knowledge_base/`, `logs/` ekle

#### 3.2 Auth Token'larini Kalici Yap
**Sorun:** `server/auth/` session token'lari sadece Python `dict` bellekte tutuluyor. API restart edildiginde tum kullanicilar cikmis oluyor.
**Yapilacak:**
- Token'lari PostgreSQL'deki `app_user` tablosuna veya ayri bir `session` tablosuna yaz
- Alternatif: Redis (yeni servis) veya mevcut PostgreSQL

**Dosyalar:** `server/auth/auth_api.py`, `server/db/repository/user_repository.py`

#### 3.3 ChromaDB Volume Mount Duzelt
**Sorun:** `docker-compose.yml`'de `chroma_data` volume tanimli ama `api` servisinde `./chroma_db:/app/chroma_db` seklinde bind mount var. Volume ve bind mount karisik.
**Yapilacak:**
- Tutarli bir yaklasim sec: ya hep bind mount (`./chroma_db`) ya da hep named volume
- `chroma_data` named volume'u gercekte kullanilmiyorsa kaldir

---

### ONCELIK 2 — Onemli Islevsel Eksikler

#### 3.4 DBA Agent Phase 5 — Aksiyon Yurutme
**Sorun:** `dba_agent/tools/db_action_tools.py` araclar tanimli ama agent bunlari planlama asamasinda onerip durduruyor; gercekte yurutmuyor.
**Yapilacak:**
- `dba_agent/agent/` altinda aksiyon yurutme dongusu yaz
- Onay mekanizmasiyla entegre et: `LOW` → otomatik, `MEDIUM/HIGH` → Telegram onay
- Audit log yaz: `logs/dba_agent_audit.jsonl`

**Dosyalar:** `dba_agent/agent/`, `dba_agent/tools/db_action_tools.py`, `dba_agent/telegram/bot.py`

#### 3.5 JSONL Format Destegi Duzelt
**Sorun:** `diagnose_run_data_copy.jsonl` yuklediginde `JSONLoader` her satirin `dict` olmasi bekliyor ama satirlar `str` olabilir.
**Yapilacak:**
- `server/knowledge_base/utils.py` icerisinde `JSONLoader` konfigurasyonunu gozden gecir
- `jq_schema` parametresini guncelle veya her satir icin farkli bir loader kullan
- `.jsonl` dosyalarinin satir satir yuklenmesini sagla

**Dosyalar:** `server/knowledge_base/utils.py`

#### 3.6 Desteklenmeyen Dosya Formatlari Icin Kullanici Dostu Hata
**Sorun:** `.log`, `.jsonl` gibi desteklenmeyen formatlar yukleniyor ama hic bir uyari verilmiyor.
**Yapilacak:**
- `upload_docs()` icinde format kontrolu ekle
- Desteklenmeyen formatlarda anlik kullaniciya bilgi ver (UI'da)
- `LOADER_DICT` sabiti ekranda goster

**Dosyalar:** `server/knowledge_base/kb_doc_api.py`, `webui_pages/knowledge_base/knowledge_base.py`

---

### ONCELIK 3 — Kalite & Istikrar

#### 3.7 LangChain Surumunu Guncelle
**Sorun:** `langchain==0.0.344` Aralik 2023'ten eski, guvenlik ve uyumluluk riskleri var.
**Yapilacak:**
- `requirements.txt` guncelle: `langchain>=0.1.0`
- `from langchain.vectorstores import Chroma` → `from langchain_community.vectorstores import Chroma`
- `from langchain.docstore.document import Document` → `from langchain_core.documents import Document`
- Tum import'lari tarayip guncelle

**Dosyalar:** `requirements.txt`, `server/knowledge_base/kb_service/chroma_kb_service.py`, diger KB dosyalari

#### 3.8 Notify Worker — Hata Yonetimi
**Sorun:** `prometheus_service_docker/app.py` Telegram ve DBA Agent cagrilarini try/except olmadan yapiyor; bir servis dustu mu hep birlikte cokuyor.
**Yapilacak:**
- Her dis cagriyi ayri try/except ile sar
- Timeout degerleri ekle (requests timeout=10)
- Retry mekanizmasi ekle (en az 3 deneme)

**Dosyalar:** `prometheus_service_docker/app.py`

#### 3.9 API Tutarliligi — KB Endpoint'leri
**Sorun:** Bazi endpoint'ler `code=404` donup `msg` ile hata bildiriyor, bazi endpoint'ler 200 donup icinde `failed_files` donuyor. Tutarsiz.
**Yapilacak:**
- HTTP status kodlarini standartlastir
- `BaseResponse` sinifinı gozden gecir
- Hata durumunda her zaman anlamli `msg` don

#### 3.10 Test Altyapisi
**Sorun:** `tests/` dizini var ama kapsamli testler yok.
**Yapilacak:**
- KB islemleri icin birim testler: yukle, sorgula, sil
- Auth akisi icin entegrasyon testi
- `pytest` + `httpx.AsyncClient` ile FastAPI test suite
- CI: GitHub Actions workflow ekle

---

### ONCELIK 4 — Yeni Ozellikler

#### 3.11 Grafik Dashboard (Metrik Gorselleştirme)
**Mevcut durum:** Dashboard sadece ozet veri donuyor, gorsellestirme yok.
**Yapilacak:**
- Prometheus sorgularini cekip Streamlit `st.line_chart` ile goster
- CPU, bellek, sorgu suresi zaman serisi grafikleri
- Anomali noktalari isaretlendi goster

**Dosyalar:** `webui_pages/` altina yeni `dashboard.py` sayfasi, `server/dashboard_api.py`

#### 3.12 Zamanlanmis Bakim Otomasyonu
**Mevcut durum:** VACUUM, REINDEX gibi bakim isleri sadece manuel tetiklenebiliyor.
**Yapilacak:**
- `APScheduler` ile zamanlanmis gorev altyapisi
- Bakimlarin bakim penceresi disinda calismasini zorunlu kil
- Sonuclari audit log'a yaz

#### 3.13 Oracle / MSSQL Destegi
**Mevcut durum:** Sadece PostgreSQL ve MySQL destekleniyor.
**Yapilacak:**
- `dba_agent/tools/db_diagnostic.py` soyutlama katmani olustur
- Oracle icin `cx_Oracle` / `oracledb` adapter
- MSSQL icin `pyodbc` adapter
- Her adapter icin `get_health`, `get_slow_queries` vs. implement et

#### 3.14 Multi-Tenant Kullanici Yonetimi
**Mevcut durum:** Tek admin + kullanici modeli var, KB ve tani sonuclari herkese acik.
**Yapilacak:**
- `app_user` tablosuna `tenant_id` ekle
- KB ve tani sonuclarini tenant bazinda filtrele
- API endpoint'lerine tenant middleware ekle

#### 3.15 Prediktif Anomali Tespiti
**Mevcut durum:** Sadece reaktif tespit: alarm geldikten sonra tani.
**Yapilacak:**
- Prometheus metriklerinden trend analizi
- Prophet veya basit ARIMA ile 1-4 saatlik ongordum
- Kritik esligi geçmeden once uyari gonder

---

## 4. Teknik Borc Ozeti

| Kategori | Dusuk | Orta | Yuksek | Kritik |
|----------|-------|------|--------|--------|
| Guvenlik | | | Hardcoded key | .gitignore yok |
| Stabilite | Test eksik | Notify hata yonetimi | ChromaDB volume | Auth bellekte |
| Performans | | | | LangChain eski |
| Ozellik | Dashboard | Zamanlama | DBA Phase 5 | JSONL yukle |

---

## 5. Onerildigimiz Calisma Sirasi

```
Hafta 1-2:
  [x] .gitignore ekle
  [x] ChromaDB volume mount duzelt
  [ ] Auth token'lari PostgreSQL'e tasi
  [ ] JSONL format hatasi duzelt

Hafta 3-4:
  [ ] LangChain surumu guncelle
  [ ] Notify Worker hata yonetimi guclendir
  [ ] Desteklenmeyen format UI uyarisi

Ay 2:
  [ ] DBA Agent Phase 5 (aksiyon yurutme)
  [ ] Temel test altyapisi
  [ ] Dashboard grafikleri

Ay 3+:
  [ ] Oracle/MSSQL adapter
  [ ] Multi-tenant
  [ ] Prediktif anomali
  [ ] Zamanlanmis bakim
```

---

## 6. Mimari Notlar

### ChromaDB Embedding
ChromaDB tamamen `api` container icinde embedded olarak calisiyor. Ayri bir ChromaDB container yok. Veri `./chroma_db` bind mount ile kalici hale getirilmis.

### Model Routing
Tum LLM cagrilari `LiteLLM Gateway` (port 4000) uzerinden gidiyor. Bu sayede:
- Ollama (yerel) ve bulut modelleri tek noktadan yonetiliyor
- Retry, fallback, timeout merkezi olarak yapilandiriliyor
- Model degisikligi kod degistirmeden `litellm_config.yaml` ile yapiliyor

### Multi-Agent Mimari
`multiagents/reasoning_algorithms/tree_of_thought/` UCT (Upper Confidence Bound for Trees) algoritmasi uzerinde ToT (Tree of Thought) implementasyonu. Her solver agent kendi dal'ini acip LLM ile dusunce zinciri olusturuyor, en iyi dal seciliyor.

### Konfigürasyon Yonetimi
Tum konfigurasyonlar `configs/*.py` dosyalarinda. `entrypoint.sh` `.example` dosyalarindan otomatik olusturuyor. Docker env degiskenleri `entrypoint.sh` uzerinden `configs/` dosyalarina yaziliyor — bu yuzden `configs/` dizini container volume'unda tutulmali.
