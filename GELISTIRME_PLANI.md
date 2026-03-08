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

**Mevcut durum (2026-03-08 detayli analiz):**

Phase 5 yaklasik **%40 tamamlanmis** durumda:

| Bilesен | Durum | Dosya | Aciklama |
|---|---|---|---|
| Approval mekanizmasi | ✅ Calisiyor | `approval.py` | Inline keyboard, onay/red, timeout |
| SQL/SSH aksiyon yurutme | ✅ Calisiyor | `approval.py`, `db_action_tools.py` | `adapter.execute_action()` + `SSHExecutor` |
| Guvenlik kontrolleri | ✅ Calisiyor | `db_action_tools.py` | `_check_sql_forbidden()`, risk level validation |
| Audit logging | ✅ Calisiyor | `audit.py`, `approval.py` | Aksiyonlar kaydediliyor |
| Verifier | ⚠️ Yazilmis ama baglanmamis | `verifier.py` | Orphaned code — hicbir yerden cagrilmiyor |
| Orchestrator → Approval | ❌ Eksik | `orchestrator.py` | Tani bitince aksiyonlar approval'a iletilmiyor |
| Before/After snapshot | ❌ Eksik | `approval.py` | Aksiyon oncesi/sonrasi metrik karsilastirmasi yok |
| Rollback | ❌ Eksik | — | Hicbir rollback mekanizmasi yok |
| Kendi kendine ogrenme | ❌ Tamamen eksik | `memory/__init__.py` | 3 satirlik placeholder: "Faz 4'te implement edilecek" |

**Kod kaniti — orphaned verifier:**
```python
# orchestrator.py:95 — olusturuluyor ama HICBIR YERDE kullanilmiyor
self.verifier = Verifier()

# orchestrator.py:305-312 — gecmis kayit placeholder
"Henuz gecmis kayit yok (Faz 4'te eklenecek)"
```

**Kod kaniti — fire-and-forget sorunu:**
```python
# approval.py:141 — aksiyon ateslenip unutuluyor
asyncio.create_task(_execute_approved_actions(...))  # bot cokerse sonuc kaybolur
```

**Gercek eksikler:**

| Eksik | Nerede | Etki |
|---|---|---|
| Orchestrator → Approval baglantisi yok | `orchestrator.py` tani bitince approval'a iletmiyor | Aksiyonlar hic Telegram'a gelmiyor |
| Risk bazli otomatik yurutme yok | `SAFE` aksiyonlar onay beklemeden calismali | Her sey manuel onay bekliyor |
| Verifier entegrasyonu yok | Aksiyon sonrasi `verifier.py` calismiyor | Before/after karsilastirmasi yapilmiyor |
| Aksiyon tipi tespiti zayif | `action.get("type", "")` ama executor SQL'i `action.get("sql")` ile koyuyor | SQL'ler calismayabilir |
| `detail` callback implement edilmemis | `bot.py`'de `detail:{alert_id}` callback handler yok | Buton gosterilip tiklaninca hata |
| Async fire-and-forget | `approval.py:141` `asyncio.create_task()` | Bot cokerse kullanici sonucu ogrenemez |
| Approval timeout yetersiz | Default 3600s (1 saat) | VACUUM FULL buyuk tabloda 2+ saat surebilir |
| Multi-DB target eksik | `approval.py:226` `get_adapter()` hedef DB belirtmiyor | Hangi DB'ye aksiyon uygulandigi belirsiz |

**Yapilacak (oncelik sirasina gore):**

##### A — Kritik Baglanti Eksikleri (bunlar olmadan Phase 5 calismaz)

**A1. Aksiyon eslestirme duzelt** (~30dk)
- `approval.py:202` — `action.get("type", "")` yerine `action.get("sql", "")` kontrolu zaten var ama ust kosulda `type` kontrol ediliyor
- Executor'un dondugu `{"action": "...", "sql": "...", "risk": "..."}` formatina uyumlu hale getir
- **Dosyalar:** `dba_agent/telegram/approval.py`

**A2. Orchestrator → Approval pipeline kur** (~2-3 saat)
- `orchestrator.diagnose()` tamamlaninca onerilen aksiyonlari risk bazinda yonlendir:
  ```
  SAFE aksiyonlar     → otomatik yurut → Verifier
  LOW aksiyonlar      → otomatik yurut (config toggle: DBA_AUTO_APPROVE_LOW)
  MEDIUM/HIGH         → Telegram approval mesaji gonder → onay/red → yurut/logla
  ```
- `orchestrator.py`'ye `_handle_actions()` metodu ekle
- **Dosyalar:** `dba_agent/agent/orchestrator.py`, `dba_agent/telegram/approval.py`

**A3. Verifier entegrasyonu + Before/After Snapshot** (~2-3 saat)
- `approval.py`'de aksiyon oncesi `verifier.take_snapshot()` cagir
- Aksiyon sonrasi tekrar snapshot al ve `verifier.verify()` ile karsilastir
- Verifier sonucunu Telegram'a gonder (health_score, cache_hit_ratio, active_connections degisimi)
- Rollback gerektiriyorsa uyar
- **Dosyalar:** `dba_agent/agent/orchestrator.py`, `dba_agent/agent/verifier.py`, `dba_agent/telegram/approval.py`

**A4. `detail` callback handler** (~30dk)
- `bot.py`'ye `detail:{alert_id}` icin callback handler ekle
- Tiklaninca aksiyonlarin detaylarini (SQL, risk, reason) gostersin
- **Dosyalar:** `dba_agent/telegram/bot.py`

**A5. Async fire-and-forget duzelt** (~1 saat)
- `approval.py:141`'deki `asyncio.create_task()` yerine task tracking ekle
- Aksiyon tamamlaninca veya hata olunca Telegram'a bildirim gonder
- Task referanslarini `_pending_tasks` dict'inde tut (GC icin)
- **Dosyalar:** `dba_agent/telegram/approval.py`

##### B — Kalite Gelistirmeleri

**B1. Dry-run modu** (~1 saat)
- `DBA_DRY_RUN=true` env ile aksiyonlar yurutulmuyor, sadece ne yapilacagi loglanir
- Test ve demo icin kritik
- **Dosyalar:** `dba_agent/config.py`, `dba_agent/telegram/approval.py`

**B2. Bakim zaman penceresi (Maintenance Window)** (~1 saat)
- HIGH riskli aksiyonlar icin `DBA_MAINTENANCE_START=02:00` / `DBA_MAINTENANCE_END=05:00` config
- Pencere disinda: "Bu aksiyon sadece bakim saatlerinde uygulanabilir" uyarisi
- SAFE/LOW aksiyonlar pencereden bagimsiz calisir
- **Dosyalar:** `dba_agent/config.py`, `dba_agent/telegram/approval.py`

**B3. Rollback kaydi** (~1 saat)
- Her yurutulen aksiyonun geri alinabilir versiyonu audit log'a yazilir
- Ornek: `{"action": "set_db_config", "param": "work_mem", "old_value": "4MB", "new_value": "64MB", "rollback_sql": "ALTER SYSTEM SET work_mem = '4MB'"}`
- **Dosyalar:** `dba_agent/security/audit.py`, `dba_agent/telegram/approval.py`

**B4. Aksiyon gecmisi komutu (/history)** (~1 saat)
- Telegram'da `/history` komutu: son 10 uygulanan aksiyonu listele
- Audit log'dan okur
- **Dosyalar:** `dba_agent/telegram/bot.py`, `dba_agent/security/audit.py`

**B5. Kademeli yurutme (Staged Execution)** (~2 saat)
- Birden fazla aksiyon onerildiginde hepsini birden degil, sirayla calistir
- Her adim sonrasi verifier kontrol etsin, iyilesme yoksa dursun
- Gereksiz HIGH risk aksiyonlardan kacin
- **Dosyalar:** `dba_agent/telegram/approval.py`, `dba_agent/agent/verifier.py`

**B6. Cooldown mekanizmasi** (~1 saat)
- Ayni anomali icin kisa surede tekrar aksiyon tetiklenmesini engelle
- Ornek: `VACUUM ANALYZE` calistiktan sonra 30 dk ayni tablo icin tekrar tetiklenmesin
- `_cooldown_registry` dict: `{action_key: last_executed_at}`
- **Dosyalar:** `dba_agent/telegram/approval.py`, `dba_agent/config.py`

**B7. Multi-DB target destegi** (~2 saat)
- `approval.py:226`'da `get_adapter()` hedef DB belirtmeden cagriliyor
- Aksiyon formatina `target_db` alani ekle
- Hangi DB'ye aksiyon uygulandigini audit log'a yaz
- **Dosyalar:** `dba_agent/telegram/approval.py`, `dba_agent/db/factory.py`

**B8. Multi-approval (coklu onay)** (~2 saat)
- Telegram'da birden fazla DBA tanimla (`DBA_APPROVERS` env)
- HIGH risk aksiyonlar icin 2/3 onay zorunlulugu
- Onay durumunu Telegram'da canli goster: "1/2 onay alindi"
- **Dosyalar:** `dba_agent/telegram/approval.py`, `dba_agent/config.py`

##### C — Kendi Kendine Ogrenme (Phase 4 Memory/RAG)

**C1. Incident Memory Store** (~3-4 saat)
- Her tani + aksiyon + sonucu ChromaDB'ye kaydet
- Schema: `{alert_type, root_cause, actions_taken, success_rate, health_before, health_after, timestamp}`
- `dba_agent/memory/incident_store.py` olustur
- **Dosyalar:** `dba_agent/memory/incident_store.py` (yeni), `dba_agent/agent/orchestrator.py`

**C2. Benzer vaka getirme (RAG Retrieval)** (~2-3 saat)
- Yeni anomalide ChromaDB'den benzer gecmis vakalari getir (top-3 similarity)
- LLM'e "gecmiste bu sorunda X cozumu %90 basarili oldu" baglamini ver
- Orchestrator planning asamasinda gecmis deneyimi kullan
- **Dosyalar:** `dba_agent/memory/incident_store.py`, `dba_agent/agent/orchestrator.py`, `dba_agent/agent/prompts.py`

**C3. Aksiyon basari skoru & trend** (~2 saat)
- Her aksiyon sonrasi `health_score` degisimini kaydet
- Zaman icinde hangi aksiyonlarin en etkili oldugunu raporla
- Dusuk basarili aksiyonlari otomatik deprioritize et
- Telegram'da `/stats` komutu ile basari oranlari goster
- **Dosyalar:** `dba_agent/memory/incident_store.py`, `dba_agent/telegram/bot.py`

**C4. Feedback loop** (~2 saat)
- DBA aksiyon sonrasi Telegram'da "Bu cozum ise yaradi mi?" butonlari goster
- Kullanici geri bildirimi incident_store'a kaydet
- Gelecek onerileri siralama sirasinda bu skora gore agirliklandir
- **Dosyalar:** `dba_agent/telegram/bot.py`, `dba_agent/telegram/approval.py`, `dba_agent/memory/incident_store.py`

**Uygulama sirasi:**
```
A1 → A2 → A3 → A4 → A5
→ B1 → B2 → B3 → B5 → B4 → B6
→ C1 → C2 → C3 → C4
→ B7 → B8
```

**Faz aciklamasi:**
- A1-A5: Phase 5'in calismasi icin zorunlu. Bunlar olmadan aksiyon pipeline'i calismaz.
- B1-B6: Guvenlik ve kalite katmanlari. Uretim ortaminda olmasi gereken ozellikler.
- C1-C4: Kendi kendine ogrenme. Sistem her anomaliden ders cikarir, zaman icinde daha iyi oneriler sunar.
- B7-B8: Ileri seviye ozellikler. Multi-DB ve multi-approval destegi.

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
| Ozellik | Dashboard | Zamanlama | DBA Phase 5 (A1-A4 kritik, B1-B4 kalite) | JSONL yukle |

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
  [ ] DBA Agent Phase 5 — A1: Aksiyon eslestirme duzelt
  [ ] DBA Agent Phase 5 — A2: Orchestrator → Approval pipeline
  [ ] DBA Agent Phase 5 — A3: Verifier entegrasyonu
  [ ] DBA Agent Phase 5 — A4: detail callback handler
  [ ] DBA Agent Phase 5 — B1-B4: Dry-run, Maintenance Window, Rollback, /history
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
