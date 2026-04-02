# Anomivox — Geliştirme Planı

> Güncelleme: 2026-04-01
> Versiyon: v0.2.0 → v0.3.0

---

## Proje Özeti

**Anomivox**, yapay zeka destekli özerk veritabanı izleme ve anomali tespit platformudur.
Prometheus metrikleri, çok-ajanlı LLM tanı sistemi ve otonom aksiyon yeteneğini bir araya getirir.

### Servis Mimarisi

```
[Kullanici]
    |
    +-- Vue.js WebUI (18501)         <-- webui/
    |
    +-- FastAPI REST API (7861)      <-- server/api.py
    |       +-- Auth / Kullanici
    |       +-- Chat (LLM, RAG, KB)
    |       +-- Knowledge Base
    |       +-- Diagnose (Tani)
    |       +-- Dashboard
    |       +-- Mail / Telegram Alert
    |
    +-- DBA Agent (8100)             <-- dba_agent/main.py
    |       +-- Telegram Bot (7/24)
    |       +-- Tool Registry (diagnostic, action, metric, ssh)
    |       +-- Multi-DB Adapters (PG, MySQL, Oracle, MSSQL)
    |       +-- Incident Memory (JSONL + ChromaDB RAG)
    |
    +-- LiteLLM Gateway (4000)       <-- ai-agent-gateway
    |       +-- Ollama (yerel LLM)
    |       +-- OpenAI / Gemini / Groq / Anthropic / DeepSeek
    |
    +-- Notify Worker (8023)         <-- prometheus_service_docker/app.py
    |       +-- Alert parse & depolama
    |       +-- DBA Agent bildirim
    |
[Altyapi]
    +-- PostgreSQL (5432)
    +-- Redis (6379)                 <-- Token cache (LRU, sifreli)
    +-- ChromaDB (embedded)          <-- ./chroma_db bind mount
    +-- Prometheus (9090)
    +-- Alertmanager (9093)
    +-- Node Exporter (9100)
    +-- PG Exporter (9187)
```

---

## Tamamlanan Çalışmalar (v0.2.0)

| # | Başlık | Commit |
|---|--------|--------|
| 3.1 | `.gitignore` eklendi | mevcut |
| 3.2 | Auth token'ları Redis + PostgreSQL'e kalıcı hale getirildi | `6e76b4d` |
| 3.3 | ChromaDB volume mount düzeltildi | `1abc4f7` |
| 3.4 | DBA Agent Phase 5 — Aksiyon yürütme (A1-A5, B1-B8, C1-C4) | `7897b17` |
| 3.5 | JSONL format desteği düzeltildi | `8e266a5` |
| 3.6 | Desteklenmeyen dosya formatı için kullanıcı dostu hata | `6dab696` |
| 3.7 | Notify Worker hata yönetimi güçlendirildi | `dd91963` |
| 3.8 | API tutarlılığı — KB endpoint'leri (409/404 düzeltmesi) | `3c66abb` |
| 3.9 | Grafik Dashboard — Prometheus metrik görselleştirme | `9863661` |
| 3.10 | Dashboard'a Redis entegrasyonu | `dc83979` |
| 3.11 | Oracle / MSSQL adapter desteği | `b4e4715` |

---

## Bekleyen Çalışmalar

---

### ÖNCELİK 1 — Kritik / Güvenlik

#### 4.1 LangChain Sürümünü Güncelle
**Sorun:** `langchain==0.0.344` (Aralık 2023), güvenlik ve uyumluluk riski taşıyor.
**Etki:** Tüm KB, chat ve agent zincirleri.

**Yapılacak:**
- `requirements.txt`: `langchain>=0.2.0`, `langchain-community>=0.2.0`, `langchain-core>=0.2.0`
- Import yollarını güncelle:
  - `from langchain.vectorstores` → `from langchain_community.vectorstores`
  - `from langchain.docstore.document` → `from langchain_core.documents`
  - `from langchain.embeddings` → `from langchain_community.embeddings`
  - `from langchain.chat_models` → `from langchain_community.chat_models`
- KB servis dosyalarını, chat zincirlerini ve agent modüllerini test et

**Dosyalar:**
- `requirements.txt`
- `server/knowledge_base/kb_service/*.py`
- `server/chat/*.py`
- `multiagents/agents/*.py`
- `multiagents/tools/*.py`

---

### ÖNCELİK 2 — Kullanıcı Arayüzü & Yerelleştirme

#### ~~4.2 KB Ekranı — Tam Türkçe Dil Desteği~~ ✅ TAMAMLANDI (2026-04-01)

**Yapılanlar:**
- `webui/src/lang/tr.js` ve `en.js`: 24 yeni KB i18n anahtarı eklendi
  - `kbDataset`, `kbSearchTest`, `kbDetailSettings`, `kbSelectFile`, `kbUploadBtn`
  - `kbFileName`, `kbDataCount`, `kbOperations`, `kbReview`
  - `kbDetailName`, `kbDetailBriefIntro`, `kbDetailEmbeddingModel`
  - `kbDeleteKbConfirm`, `kbDeleteFileConfirm`, `kbDeleteCompleted`, `kbUpdateCompleted`, `kbUploadCompleted`
  - `kbSearchPlaceholder`, `kbSearchBtn`, `kbPageContent`, `kbSource`, `kbFiles`, `kbFileUploadTip`, `kbChat`
- `webui/src/views/knowledge/detail.vue`: tüm hardcoded İngilizce metinler `$t()` ile değiştirildi
  - Menü öğeleri (Dataset, Search Test, Settings)
  - Upload/UPLOAD butonları, dosya upload ipucu metni
  - Tablo sütun başlıkları (File Name, Data Count, Operations)
  - Tablo aksiyon butonları (Review, Delete)
  - Ayarlar sekmesi (Name, Brief Introduction, Embedding Model, Save)
  - Tüm onay dialogları (delete KB, delete file) ve mesajları
  - Script'e `useI18n` import'u ve `t()` destructure eklendi
- `webui/src/views/knowledge/index.vue`: `files` hardcoded metni `$t('kbFiles')` yapıldı

#### 4.3 Tanı Ekranı — İki Dilli Dosya Desteği ✅ TAMAMLANDI

**Yapılan Değişiklikler:**
- `multiagents/prompt_templates/report_prompts.py`: `ANOMALY_DESC_PROMPT_tr` ve `ANOMALY_TITLE_PROMPT_tr` eklendi
- `multiagents/prompt_templates/roundtable_prompts.py`: `ROUND_TABLE_PROMPT_tr` eklendi
- `multiagents/prompt_templates/diagnosis_summary_prompts.py`: `DIAGNOSIS_SUMMARY_PROMPT_tr` eklendi
- `multiagents/agents/reporter.py`: `initialize_report()`, `update_diagnosis()`, `add_diagnosis_labels()`, `update_solutions()` metodlarına `elif self.language == 'tr':` dalları eklendi
- `multiagents/agents/solver.py`: kök neden ve çözüm promptları + `review_step()` için TR dalları eklendi; `ROUND_TABLE_PROMPT_tr` import edildi
- `multiagents/agents/role_assigner.py`: `user_select_experts()` içindeki kullanıcı mesajlarına TR dalları eklendi
- `multiagents/environments/dba.py`: `DIAGNOSIS_SUMMARY_PROMPT_tr` import edildi; uzman seçim açıklaması, kök neden/çözüm/tanı süreci başlıkları ve rapor tablosu sütun/bölüm başlıkları Türkçeleştirildi
- `multiagents/initialization.py`: `LANGUAGE = os.environ.get("DBA_AGENT_LANGUAGE", "en")` olarak güncellendi

---

### ÖNCELİK 3 — Kalite & Yapısal İyileştirme

#### ~~4.4 Configs — Ayarlar Ekranına Taşıma~~ ✅ TAMAMLANDI (2026-04-01)

**Yapılanlar:**
- `webui/src/lang/tr.js` ve `en.js`: ~35 yeni i18n anahtarı eklendi
  - Genel: `id`, `admin`, `userRole`, `error`, `email`
  - Settings sayfası: `litellmModelTimeout`, `litellmModelContextWindow`, `litellmModelMaxOutput`, `litellmTokens`, `ssl`, `ssh`, `sshTest`, `dbTestVersion`, `dbTestDatabase`, `dbTestUser`, `dbTestSize`, `autoIngestOn`, `autoIngestOff`, `errorSavingSettings`
  - LLM Provider: `llmProviderSettings`, `llmActiveModel`, `llmGlobalSettings`, `llmProviderConfig`, `llmModelName`, `llmApiBaseUrl`, `llmApiKey`, `llmOpenAIProxy`, `llmTemperature`, `llmMaxTokens`, `llmHistoryLen`, `llmProviderGroq`, `llmProviderOpenAI`, `llmProviderGemini`, `llmProviderCustom`, `llmSaveSuccess`, `llmSaveFail`
- `webui/src/views/settings/index.vue`:
  - ~20 hardcoded string `$t()` çağrısına dönüştürüldü (ID label, Admin/User rolleri, tablo başlıkları, SSL/SSH sütunları, SSH Test butonu, DB test sonuç etiketleri, Auto-Ingest ON/OFF, E-posta label, hata mesajları)
  - Yeni **LLM Sağlayıcı Ayarları** collapsible bölümü eklendi:
    - Aktif model dropdown (groq-api / openai-api / gemini-api / qwen1.5-vllm)
    - Global Ayarlar: Temperature (slider 0-1), Max Tokens, Geçmiş Uzunluğu
    - Sağlayıcı Yapılandırması: her sağlayıcı için model_name, api_base_url, api_key (göster/gizle toggle), OpenAI için proxy alanı
    - Kaydet butonu + API entegrasyonu
- `configs/model_settings_config.py` (YENİ): JSON-backed LLM config (`configs/model_settings.json`), API key maskeleme, hot-reload desteği
- `server/model_config_api.py` (YENİ): `GET /config/llm` (maskelenmiş), `POST /config/llm` (kaydet + hot-reload)
- `server/api.py`: `mount_llm_config_routes()` eklendi, startup'ta `load_model_settings_on_startup()` çağrısı
- `webui/src/api/modelConfig.js` (YENİ): `getLlmConfigReq`, `saveLlmConfigReq` fonksiyonları

#### ~~4.6 Zamanlanmış Bakım Otomasyonu~~ ✅ TAMAMLANDI (2026-04-01)

**Yapılanlar:**
- `requirements_api.txt`, `requirements_dba_agent.txt`: `APScheduler>=3.10.0` eklendi
- `server/db/models/scheduler_model.py` (YENİ): `ScheduledTaskModel` — ad, tür, hedef, cron, risk seviyesi, bakım penceresi, son çalışma bilgileri
- `server/db/repository/scheduler_repository.py` (YENİ): CRUD operasyonları + `update_task_run_result()`
- `server/api.py`: `scheduled_task` tablosu migrasyonu + `mount_scheduler_routes()` + startup/shutdown event
- `server/scheduler/scheduler_service.py` (YENİ): APScheduler `AsyncIOScheduler` singleton, `start_scheduler()`, `_execute_task()` (HIGH risk bakım penceresi kontrolü + DBA Agent'a HTTP call + audit log)
- `server/scheduler/scheduler_api.py` (YENİ): `GET/POST/PUT /scheduler/tasks`, `/scheduler/tasks/delete`, `/scheduler/tasks/run`
- `dba_agent/scheduler/maintenance_executor.py` (YENİ): VACUUM/REINDEX/ANALYZE/LOG_ROTATE/STATS_COLLECT SQL executor
- `dba_agent/main.py`: `POST /api/maintenance/run` endpoint eklendi
- `webui/src/api/scheduler.js` (YENİ): `listScheduledTasksReq`, `createScheduledTaskReq`, `updateScheduledTaskReq`, `deleteScheduledTaskReq`, `runScheduledTaskNowReq`
- `webui/src/views/scheduler/index.vue` (YENİ): Görev tablosu + oluştur/düzenle dialog, cron ifadesi, risk seviyesi, bakım penceresi
- `webui/src/router/index.js`: `/scheduler` route eklendi (Clock ikonu)
- `webui/src/lang/tr.js`, `en.js`: scheduler i18n key'leri eklendi

#### ~~4.7 Multi-Tenant Kullanıcı Yönetimi~~ ✅ TAMAMLANDI (2026-04-01)

**Yapılanlar:**
- `server/api.py`: `tenant` tablosu + `app_user/knowledge_base/conversation`'a `tenant_id` kolon migrasyonları (default tenant UUID: `00000000-0000-0000-0000-000000000001`)
- `server/db/models/tenant_model.py` (YENİ): `TenantModel`
- `server/db/models/user_model.py`, `knowledge_base_model.py`, `conversation_model.py`: `tenant_id` kolonu eklendi
- `server/db/repository/tenant_repository.py` (YENİ): `create_tenant`, `list_tenants`, `delete_tenant` (default tenant korumalı), `assign_user_to_tenant`, `list_tenant_users`
- `server/db/repository/user_repository.py`: `authenticate_user()`, `save_token()`, `get_user_by_token()` dönen dict'lere `tenant_id` eklendi
- `server/auth/tenant_api.py` (YENİ): `GET/POST /auth/tenants`, `/auth/tenants/delete`, `/auth/tenants/assign`, `/auth/tenants/{id}/users`
- `server/auth/auth_api.py`: `current_user_info()` yanıtına `tenant_id` eklendi
- `server/api.py`: `mount_tenant_routes()` eklendi
- `webui/src/api/tenant.js` (YENİ): tenant CRUD API fonksiyonları
- `webui/src/views/settings/index.vue`: **Tenant Yönetimi** collapsible bölümü eklendi (liste, oluştur, sil, kullanıcı ata)
- `webui/src/lang/tr.js`, `en.js`: tenant i18n key'leri eklendi

#### ~~4.8 Prediktif Anomali Tespiti~~ ✅ TAMAMLANDI (2026-04-01)

**Yapılanlar:**
- `requirements_api.txt`: `statsmodels>=0.14.0` eklendi
- `server/prediction/prometheus_fetcher.py` (YENİ): Prometheus HTTP API wrapper, 5 metrik (CPU/bağlantı/sorgu süresi/disk/bellek), eşik tablosu
- `server/prediction/arima_predictor.py` (YENİ): ARIMA(1,1,1) + lineer trend fallback, `will_breach_threshold()`
- `server/prediction/alert_dispatcher.py` (YENİ): Telegram + mail birleşik gönderim, 1 saatlik cooldown mekanizması
- `server/prediction_api.py` (YENİ): `POST /prediction/forecast`, `GET /prediction/metrics`, `POST /prediction/alerts/check`
- `server/api.py`: `mount_prediction_routes()` eklendi
- `webui/src/api/prediction.js` (YENİ): `getSupportedMetricsReq`, `getForecastReq`, `runAlertCheckReq`
- `webui/src/views/dashboard/index.vue`: **Tahminler** bölümü eklendi (metrik seçici, horizon seçici, SVG sparkline chart, eşik aşımı uyarısı)

#### 4.5 Test Altyapısı
**Sorun:** `tests/` dizini var ama kapsamlı testler yok. CI/CD yok.

**Yapılacak:**
- `pytest` + `httpx.AsyncClient` ile FastAPI test suite kur
- **Birim testler:**
  - Auth: login, logout, token geçerliliği, süresi dolmuş token
  - KB: oluştur, dosya yükle, sorgula, sil
  - Chat: LLM yanıt akışı
  - DBA Agent: aksiyon onay akışı (mock)
- **Entegrasyon testleri:**
  - Tam diagnose akışı (Prometheus alert → tani raporu)
  - KB yükle → RAG sorgu
- **GitHub Actions workflow:**
  - `pytest` koş
  - Docker build doğrula
  - `flake8` / `ruff` linting

**Dosyalar:**
- `tests/` dizini
- `.github/workflows/ci.yml` (yeni)
- `pyproject.toml` (test konfigürasyonu)

---

### ÖNCELİK 4 — Yeni Özellikler

> 4.6, 4.7 ve 4.8 tamamlandı — bkz. yukarıdaki tamamlanan bölümler.

---

## Önerilen Çalışma Sırası

```
Sprint 1 (Nisan 2026 — 1. hafta):
  [ ] 4.1 LangChain sürümünü güncelle
  [x] 4.2 KB ekranı Türkçe dil desteği ✅

Sprint 2 (Nisan 2026 — 2. hafta):
  [x] 4.3 Tanı ekranı iki dilli dosya desteği ✅
  [x] 4.4 Ayarlar ekranı gözden geçirme + LLM Provider Config ✅

Sprint 3 (Nisan 2026 — 3-4. hafta):
  [ ] 4.5 Test altyapısı ve GitHub Actions CI

Ay 2 (Mayıs 2026):
  [x] 4.6 Zamanlanmış bakım otomasyonu ✅
  [x] 4.7 Multi-tenant kullanıcı yönetimi ✅

Ay 3+ (Haziran 2026+):
  [x] 4.8 Prediktif anomali tespiti ✅
```

---

## Teknoloji Yığını (Referans)

| Katman | Teknoloji | Versiyon |
|--------|-----------|---------|
| Backend Framework | FastAPI + Uvicorn | >=0.104 |
| LLM Zinciri | LangChain | **0.0.344 → GÜNCELLENECEK** |
| Veritabanı ORM | SQLAlchemy | 2.0.19 |
| Vektör Deposu | ChromaDB (embedded) | 0.4.20 |
| Embedding | sentence-transformers | 2.7.0 |
| Cache | Redis 7 Alpine | Docker |
| Frontend | Vue.js + Vite | Node 18 |
| LLM Gateway | LiteLLM | latest |
| Zamanlayıcı | APScheduler | >=3.10 |
| İzleme | Prometheus + Alertmanager | official |

---

## Bilinen Teknik Borçlar

| Kategori | Önem | Konu |
|----------|------|------|
| Güvenlik | Orta | `configs/*.py`'de hardcoded API key'ler (prod'da env var kullan) |
| Bağımlılık | **Yüksek** | LangChain 0.0.344 çok eski → 4.1 ile çözülüyor |
| Dil | Orta | KB ve Tanı ekranları tam Türkçe değil → 4.2/4.3 |
| Yönetim | ~~Yüksek~~ | ~~Ayarlar dosya düzenleyici gerektiriyor~~ → 4.4 ✅ |
| Test | Orta | CI/CD yok, kapsam düşük → 4.5 |
| Özellik | ~~Düşük~~ | ~~Multi-tenant yok~~ → 4.7 ✅ |
| Özellik | ~~Düşük~~ | ~~Prediktif anomali yok~~ → 4.8 ✅ |

---

## Mimari Notlar

### ChromaDB
Tamamen `api` container içinde embedded çalışıyor. Veri `./chroma_db` bind mount ile kalıcı.

### Model Routing
Tüm LLM çağrıları LiteLLM Gateway (port 4000) üzerinden:
- Triage: `llama3.2:1b` (< 1 sn)
- SQL üretimi: `sqlcoder`
- DBA/Planlama: `llama3.1:8b`
- Fallback zinciri: `llama3.1 → llama3 → llama3.2`

### Çok-Ajan Sistemi
`multiagents/reasoning_algorithms/tree_of_thought/` — UCT (Upper Confidence Bound for Trees) algoritması ile ToT (Tree of Thought). Her solver agent kendi dalını açıp LLM ile düşünce zinciri oluşturuyor; en iyi dal seçiliyor.

### DBA Agent Onay Akışı
Risk seviyelerine göre Telegram onay mekanizması:
- **LOW**: Otomatik yürütme
- **MEDIUM**: Tek onay gerekli
- **HIGH**: `DBA_REQUIRED_APPROVALS` kadar onay + bakım penceresi kontrolü
- **DRY_RUN**: Gerçek yürütme yok, simüle eder
