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
| 3 | Guvenlik | ~~Auth token'lari sadece bellekte, restart'ta siliniyor~~ **TAMAMLANDI** | Redis cache + PostgreSQL kalici token |
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

#### ~~3.2 Auth Token'larini Kalici Yap~~ — TAMAMLANDI (2026-03-07)
- Token'lar PostgreSQL `auth_token` tablosunda kalici
- Redis 7 (docker-compose) token cache katmani eklendi
- Her API istegi once Redis'ten okur (< 1ms), cache miss → PostgreSQL fallback
- Logout / sifre degisiklik / kullanici silme aninda Redis invalidate eder
- **Dosyalar:** `server/db/redis_client.py` (yeni), `server/db/repository/user_repository.py`, `docker-compose.yml`, `requirements.txt`

#### 3.3 ChromaDB Volume Mount Duzelt
**Sorun:** `docker-compose.yml`'de `chroma_data` volume tanimli ama `api` servisinde `./chroma_db:/app/chroma_db` seklinde bind mount var. Volume ve bind mount karisik.
**Yapilacak:**
- Tutarli bir yaklasim sec: ya hep bind mount (`./chroma_db`) ya da hep named volume
- `chroma_data` named volume'u gercekte kullanilmiyorsa kaldir

---

### ONCELIK 2 — Onemli Islevsel Eksikler

#### 3.4 DBA Agent Phase 5 — Aksiyon Yurutme

**Mevcut durum (2026-03-08 guncellendi — A1-A5, B1-B6, C1-C4 TAMAMLANDI):**

Phase 5 **~%90 tamamlanmis** durumda. Yalnizca B7 ve B8 kaldi.

| Bilesen | Durum | Dosya | Aciklama |
|---|---|---|---|
| Approval mekanizmasi | ✅ Tamamlandi | `approval.py` | Inline keyboard, onay/red, timeout; TR/EN dil destegi |
| SQL/SSH aksiyon yurutme | ✅ Tamamlandi | `approval.py`, `db_action_tools.py` | `adapter.execute_action()` + `SSHExecutor` |
| Guvenlik kontrolleri | ✅ Tamamlandi | `db_action_tools.py` | `_check_sql_forbidden()`, risk level validation |
| Audit logging | ✅ Tamamlandi | `audit.py` | Aksiyonlar + rollback bilgisi + gecmis sorgusu |
| Verifier entegrasyonu | ✅ Tamamlandi | `verifier.py`, `approval.py` | Before/after snapshot + LLM karsilastirma |
| Orchestrator → Approval | ✅ Tamamlandi | `orchestrator.py` | `_handle_actions()` — risk bazli yonlendirme |
| Rollback kaydi | ✅ Tamamlandi | `audit.py` | `log_rollback_info()` |
| Staged Execution | ✅ Tamamlandi | `approval.py` | `staged_stopped` flag — verifier basarisizsa dur |
| Cooldown | ✅ Tamamlandi | `approval.py` | `_cooldown_registry` + `DBA_COOLDOWN_MINUTES` |
| Dry-run modu | ✅ Tamamlandi | `config.py`, `approval.py` | `DBA_DRY_RUN=true` |
| Maintenance Window | ✅ Tamamlandi | `config.py`, `approval.py` | HIGH risk icin saat kisitlamasi |
| /history komutu | ✅ Tamamlandi | `bot.py`, `audit.py` | `get_recent_actions()` |
| Incident Memory Store | ✅ Tamamlandi | `memory/incident_store.py` | JSONL + ChromaDB (graceful fallback) |
| RAG Retrieval | ✅ Tamamlandi | `orchestrator.py` | `find_similar()` → LLM prompt'una enjekte |
| /stats komutu | ✅ Tamamlandi | `bot.py`, `incident_store.py` | Aksiyon basari oranlari |
| Feedback loop | ✅ Tamamlandi | `bot.py`, `approval.py` | 👍/👎/😐 butonlari + `update_feedback()` |
| TR/EN dil uyumu | ✅ Tamamlandi | `approval.py`, `orchestrator.py` | Tum Telegram mesajlari `DBA_AGENT_LANGUAGE`'a uygun |
| Fire-and-forget duzelt | ✅ Tamamlandi | `approval.py` | `_pending_tasks` set + `_on_action_task_done` |
| Multi-DB target | ✅ Tamamlandi | `approval.py`, `db/factory.py` | `resolve_target_name()` ile dogrulama + fallback; audit log'a `target_db` yaziliyor |
| Multi-approval | ✅ Tamamlandi | `approval.py`, `config.py` | `DBA_APPROVERS` + `DBA_REQUIRED_APPROVALS`; ilerleme "1/2 onay alindi" mesaji |

**3.4 Phase 5 — %100 TAMAMLANDI** (2026-03-08)

#### ~~3.5 JSONL Format Destegi Duzelt~~ — TAMAMLANDI (2026-03-08)
**Yapilan:**
- `LOADER_DICT` ve `DIAGNOSE_FILE_DICT`: `.jsonl` artik `JSONLinesLoader`'a, `.json` ise `JSONLoader`'a ayrı ayrı yonlendiriliyor
- `JSONLinesLoader.__init__`: `json_lines=True` + `jq_schema="."` + `text_content=False` + `_jsonl_metadata_func` ile satır satır yukle; her satır dict veya str olabilir
- `_jsonl_metadata_func`: dict satırlarının tüm alanlarını metadata'ya ekler
- `get_loader`: `JSONLoader` artik `jq_schema="."` (tek obje veya array); `JSONLinesLoader` kendi varsayilanlarını kullanir
- `file2docs`: metrics standardizasyonu `JSONLinesLoader`'i da kapsiyor

**Dosyalar:** `server/knowledge_base/utils.py`

#### ~~3.6 Desteklenmeyen Dosya Formatlari Icin Kullanici Dostu Hata~~ — TAMAMLANDI (2026-03-08)
**Yapilan:**
- `upload_docs()` icinde format kontrolu eklendi: yuklenmeden once uzanti kontrolu, desteklenmeyen dosyalar `failed_files`'a eklenir, kaydedilmez
- UI'da (knowledge_base.py): `failed_files` varsa her dosya icin `st.warning()`, desteklenen formatlar `st.info()` ile gosterilir
- `LOADER_DICT` import'u `kb_doc_api.py`'ye eklendi

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
| Ozellik | Dashboard | Zamanlama | DBA Phase 5 (A1-A4 kritik, B1-B4 kalite) | JSONL yukle |

---

## 5. Onerildigimiz Calisma Sirasi

```
Hafta 1-2:
  [x] .gitignore ekle
  [x] ChromaDB volume mount duzelt
  [ ] Auth token'lari PostgreSQL'e tasi
  [x] JSONL format hatasi duzelt

Hafta 3-4:
  [ ] LangChain surumu guncelle
  [ ] Notify Worker hata yonetimi guclendir
  [x] Desteklenmeyen format UI uyarisi

Ay 2:
  [x] DBA Agent Phase 5 — A1: Aksiyon eslestirme duzelt
  [x] DBA Agent Phase 5 — A2: Orchestrator → Approval pipeline
  [x] DBA Agent Phase 5 — A3: Verifier entegrasyonu + Before/After snapshot
  [x] DBA Agent Phase 5 — A4: detail callback handler
  [x] DBA Agent Phase 5 — A5: Fire-and-forget duzelt
  [x] DBA Agent Phase 5 — B1: Dry-run modu
  [x] DBA Agent Phase 5 — B2: Maintenance Window
  [x] DBA Agent Phase 5 — B3: Rollback kaydi
  [x] DBA Agent Phase 5 — B4: /history komutu
  [x] DBA Agent Phase 5 — B5: Staged Execution
  [x] DBA Agent Phase 5 — B6: Cooldown mekanizmasi
  [x] DBA Agent Phase 5 — C1: Incident Memory Store
  [x] DBA Agent Phase 5 — C2: RAG Retrieval
  [x] DBA Agent Phase 5 — C3: /stats komutu
  [x] DBA Agent Phase 5 — C4: Feedback loop
  [x] DBA Agent Phase 5 — B7: Multi-DB target
  [x] DBA Agent Phase 5 — B8: Multi-approval
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


7. Tanı ve KB  Mimarisi

KB ekranıdna Create Knowledge Base diyince ingilizce oluşuyor Türkçe diline ihtiyaç var. ayrıca oluşturulan KB'de ayarlar sekmesi güncellenecek.
Tanı ekranı dosyaları Türkçe olarak ve İNgilizce Olarak Eklenecek..
Tanı ve KB yapısın hem türkçe, hem ingilizce dosyalar oluşturmalı ve çalışmalı

8. Configs klasör yapısı Ayarlar sekmesine taşınacak
