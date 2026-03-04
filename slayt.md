# Anomivox — Müşteri Sunum Slaytları
> **Sunum Formatı:** Her `---` bir sonraki slayta geçişi temsil eder.  
> **Araç Önerisi:** [Marp](https://marp.app/), [Slidev](https://sli.dev/) veya [Reveal.js](https://revealjs.com/) ile HTML/PDF'e aktarabilirsiniz.

---

<!-- Slayt 1 — Kapak -->
# 🧠 Anomivox
## Yapay Zeka Destekli Otonom Veritabanı İzleme & Tanı Platformu

> *"Veritabanı sorunlarını siz fark etmeden önce tespit eder, analiz eder ve çözer."*

---

<!-- Slayt 2 — Ajanda -->
# 📋 Sunum Akışı

1. Problem: Geleneksel Veritabanı Yönetiminin Zorlukları
2. Çözüm: Anomivox Nedir?
3. Mimariye Genel Bakış
4. Temel Özellikler & Yetenekler
5. AI Agent Katmanı
6. Güvenlik & Onay Mekanizması
7. Desteklenen Teknolojiler
8. Kurulum & Dağıtım
9. Kullanım Senaryoları
10. Neden Anomivox?

---

<!-- Slayt 3 — Problem -->
# ⚠️ Problem: Geleneksel DB Yönetiminin Sınırları

```
Mevcut Durum:
  ┌─────────────────────────────────────────┐
  │  🔴 Yavaş sorgular saatler sonra fark edilir   │
  │  🔴 DBA ekibi 7/24 nöbet tutmak zorunda        │
  │  🔴 Anomali tespiti elle yapılır                │
  │  🔴 Kök neden analizi saatler alır              │
  │  🔴 Bilgi silolarında uzman bağımlılığı         │
  │  🔴 Çoklu DB türleri için ayrı araçlar          │
  └─────────────────────────────────────────┘
```

**Sonuç:** Yüksek MTTR (Ortalama Kurtarma Süresi), Operasyonel Maliyet Artışı, SLA İhlalleri

---

<!-- Slayt 4 — Çözüm -->
# ✅ Çözüm: Anomivox

> **Anomivox**, Prometheus metrik izleme, çok-ajanlı LLM tabanlı tanı ve otonom aksiyon kabiliyetlerini birleştiren entegre bir veritabanı yönetim platformudur.

```
  ┌──────────────────────────────────────────────────┐
  │  ✅ Anomalileri saniyeler içinde tespit eder      │
  │  ✅ Kök neden analizini otomatik gerçekleştirir   │
  │  ✅ Çözüm önerilerini LLM ile üretir              │
  │  ✅ Riskli aksiyonlarda insan onayı alır           │
  │  ✅ Telegram üzerinden 7/24 bildirim & yönetim    │
  │  ✅ PostgreSQL ve MySQL'i destekler                │
  └──────────────────────────────────────────────────┘
```

---

<!-- Slayt 5 — Mimari Genel Bakış -->
# 🏗️ Platform Mimarisi

```
┌─────────────────────────────────────────────────────────────┐
│                        KULLANICI KATMANI                     │
│   ┌─────────────────┐          ┌────────────────────────┐   │
│   │  Streamlit WebUI│          │   Telegram Bot         │   │
│   │  (Port: 18501)  │          │   (7/24 Erişim)        │   │
│   └────────┬────────┘          └───────────┬────────────┘   │
├────────────┼───────────────────────────────┼────────────────┤
│                         API KATMANI                          │
│   ┌─────────────────────────────────────────────────────┐   │
│   │           FastAPI / REST API  (Port: 7861)          │   │
│   │     Auth │ Chat │ KB │ Diagnose │ Dashboard         │   │
│   └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                       AGENT KATMANI                          │
│   ┌───────────────┐   ┌──────────────┐   ┌──────────────┐  │
│   │  Multi-Agent  │   │  DBA Agent   │   │  LiteLLM GW  │  │
│   │  (Diagnose)   │   │  (Otonom)    │   │  (Port:4000) │  │
│   └───────────────┘   └──────────────┘   └──────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                      VERİ & İZLEME KATMANI                   │
│  Prometheus │ Alertmanager │ PostgreSQL │ Node/PG Exporter   │
└─────────────────────────────────────────────────────────────┘
```

---

<!-- Slayt 6 — Temel Özellikler -->
# 🚀 Temel Özellikler

## 📊 Gerçek Zamanlı İzleme
- Prometheus + Alertmanager entegrasyonu
- CPU, Bellek, Disk, Ağ metrikleri
- Veritabanı özel metrikler (cache hit ratio, bağlantı sayısı, kilit durumu)
- Node Exporter ve PG Exporter desteği

## 🔍 Akıllı Anomali Tespiti
- Kolmogorov-Smirnov (KS) test algoritması
- İstatistiksel sapma analizi
- Yavaş sorgu tespiti (pg_stat_statements)
- Kilit çakışması tespiti

## 📚 Bilgi Tabanı (RAG)
- Vektör tabanlı arama (ChromaDB)
- CPU, Memory, IO, Query, Index, Recovery domain bilgileri
- Doküman yükleme ve otomatik indeksleme

---

<!-- Slayt 7 — Çok-Ajanlı Tanı Sistemi -->
# 🤖 Çok-Ajanlı Tanı Sistemi (Multi-Agent RAG)

```
Alarm Tetiklendi
      │
      ▼
┌─────────────────────────────────────────┐
│           ChiefDBA (Reporter Agent)      │
│  • Anomali açıklaması üretir            │
│  • Tanı raporunu oluşturur              │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│         RoleAssigner Agent               │
│  • Anomali tipini sınıflandırır         │
│  • Uygun uzman agent'ları seçer         │
│  ─────────────────────────────────      │
│  Uzman Kategorileri:                    │
│    🔵 CPU Expert     🟢 Memory Expert   │
│    🟡 IO Expert      🔴 Query Expert    │
│    🟣 Index Expert   ⚫ Lock Expert     │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│         Solver Agents (Paralel)          │
│  • Bilgi tabanında RAG araması          │
│  • Metrik analizi                       │
│  • Kök neden belirleme                  │
│  • Çözüm önerisi üretme                 │
└──────────────────┬──────────────────────┘
                   │
                   ▼
          📄 Tanı Raporu
```

---

<!-- Slayt 8 — DBA Agent Yetenekleri -->
# 🤖 Otonom DBA Agent Yetenekleri

## 🔧 Veritabanı Diagnostik Araçları
| Araç | Açıklama | Risk |
|------|----------|------|
| `get_health` | Genel DB sağlık skoru | SAFE |
| `get_active_connections` | Bağlantı durumu & dağılımı | SAFE |
| `get_long_running_queries` | Uzun süren sorgular | SAFE |
| `get_blocked_locks` | Kilit çakışmaları | SAFE |
| `get_slow_queries` | En yavaş sorgular | SAFE |

## ⚡ Aksiyon Araçları (Onay Gerektiren)
| Araç | Risk Seviyesi |
|------|---------------|
| `cancel_query` (pg_cancel_backend) | LOW |
| `terminate_session` (pg_terminate_backend) | MEDIUM |
| `run_vacuum` | LOW–HIGH |
| `run_reindex` | MEDIUM |
| `alter_system_set` | HIGH |

---

<!-- Slayt 9 — OS & Sistem İzleme -->
# 🖥️ SSH Üzerinden OS İzleme

> DBA Agent, veritabanı sunucusuna **SSH üzerinden** bağlanarak işletim sistemi düzeyinde analiz yapar.

```
DBA Agent → SSH → Sunucu
                    │
          ┌─────────┴──────────┐
          │                    │
    systemctl status      journalctl logs
    uptime / memory       disk kullanımı
    process listesi       servis yönetimi
```

### SSH Araçları
- `check_service_status` — PostgreSQL, MySQL, Nginx servis durumu
- `get_service_logs` — Hata loglarını getir
- `get_system_info` — Uptime, bellek, disk
- `list_processes` — İşlem listesi
- `restart_service` — Servis yeniden başlatma (**Yüksek Risk, Onay Gerektirir**)

---

<!-- Slayt 10 — Güvenlik & Onay Mekanizması -->
# 🔐 Güvenlik & Onay Mekanizması

## Risk Seviyeleri
```
  SAFE    ──  Sadece okuma, onay gerekmez
  LOW     ──  Düşük etkili, otomatik onaylanabilir
  MEDIUM  ──  Orta etkili, Telegram onayı gerekir
  HIGH    ──  Yüksek etkili, zorunlu onay + audit log
  FORBIDDEN── SQL injection / DROP / TRUNCATE  →  ENGELLENİR
```

## Telegram Onay Akışı
```
  Agent Öneri Üretir
         │
         ▼
  📱 Telegram'a Bildirim
         │
    ┌────┴────┐
  ✅ Onayla  ❌ Reddet
    │              │
  Aksiyon       İptal
  Çalışır       Log'a Yaz
```

## Audit Logging
- Tüm aksiyonlar `logs/dba_agent_audit.jsonl`'a kaydedilir
- Zaman damgası, hedef, komut, risk seviyesi, onaylayan, sonuç

---

<!-- Slayt 11 — LLM Model Mimarisi -->
# 🧠 LLM Model Mimarisi

> **LiteLLM Proxy** üzerinden **Ollama** modellerine erişim sağlanır.

```
  Python Agent
      │
      ▼
  LiteLLM Gateway (:4000)
      │
  Model Router
  ┌───┼───────────────────┐
  │   │                   │
  ▼   ▼                   ▼
llama3.2:1b    sqlcoder:latest    llama3.1:8b
(Triage/Hızlı) (SQL Analizi)     (Reasoning/Tanı)
   <1 sn          3-8 sn            3-8 sn
```

### Görev Tabanlı Model Routing
| Görev Tipi | Model |
|-----------|-------|
| Hızlı sınıflandırma (Triage) | `llama3.2:1b` |
| SQL analizi & optimizasyon | `sqlcoder:latest` |
| DBA tanı & planlama | `llama3.1:8b` |
| Genel sohbet (Telegram) | `llama3.1:8b` |
| Fallback | `llama3:8b` |

### Desteklenen Harici LLM'ler
OpenAI GPT-4 · Gemini · Groq · Anthropic · DeepSeek · Ollama (Local)

---

<!-- Slayt 12 — WebUI & Chat -->
# 💬 Web Arayüzü Özellikleri

## Streamlit WebUI (Port: 18501)

| Sayfa | İşlev |
|-------|-------|
| 📚 **Bilgi Tabanı** | Doküman yükleme, KB yönetimi |
| 💬 **Chat** | LLM ile sohbet, RAG destekli sorgu |
| 🩺 **Tanı Paneli** | Anomali listesi, tanı başlatma, akış izleme |
| 📊 **Raporlar** | Geçmiş tanı raporları, detaylı görüntüleme |

## Çok Dil Desteği
- 🇺🇸 İngilizce
- 🇹🇷 Türkçe

## Chat Özellikleri
- RAG (Retrieval Augmented Generation) destekli sorgu
- Tanı raporlarından bağlamsal cevaplar
- Mesaj geçmişi yönetimi
- Streaming yanıt desteği

---

<!-- Slayt 13 — Telegram Bot -->
# 📱 Telegram Bot Entegrasyonu

> 7/24 cep telefonunuzdan veritabanı yönetimi

### Bot Komutları
```
/start    → Hoş geldin & genel bakış
/status   → Sistem sağlık durumu
/diagnose → Manuel tanı başlat
/tools    → Kayıtlı araç listesi
/db       → DB bağlantı durumu
/cancel   → Devam eden tanıyı iptal et
/help     → Kullanım kılavuzu
```

### Alert Bildirimleri
- Prometheus alarmları anında iletilir
- Tanı tamamlandığında rapor gönderilir
- Riskli aksiyonlar için inline onay butonları:
  - ✅ **Onayla** · ❌ **Reddet** · 📋 **Detay Göster**

### Güvenlik
- Chat ID bazlı yetkilendirme
- Admin ve operatör rolleri
- Onay timeout süresi yapılandırılabilir

---

<!-- Slayt 14 — Desteklenen Teknolojiler -->
# 🛠️ Desteklenen Teknolojiler

## Veritabanları
| Platform | Desteklenen Sürümler |
|----------|---------------------|
| **PostgreSQL** | 12+ |
| **MySQL** | 5.7, 8.x |
| **MariaDB** | 10.x |
| *(Yol Haritası)* Oracle, MSSQL | — |

## LLM Sağlayıcıları
```
Yerel (Privacy-First):  Ollama (llama3.1, sqlcoder, llama3.2, llama3)
Bulut:                  OpenAI · Gemini · Groq · Anthropic · DeepSeek
```

## Altyapı Stack
```
Python 3.10+  ·  FastAPI  ·  Streamlit  ·  LangChain
ChromaDB      ·  PostgreSQL  ·  Docker Compose
Prometheus    ·  Alertmanager  ·  Node/PG Exporter
LiteLLM       ·  Ollama  ·  python-telegram-bot
```

---

<!-- Slayt 15 — Kurulum & Dağıtım -->
# 🚀 Kurulum & Dağıtım

## Docker Compose ile Tek Komut Kurulum

```bash
# 1. Projeyi klonla
git clone https://github.com/rkazak07/anomivox.git

# 2. Ortam değişkenlerini ayarla
cp .env.example .env
# .env dosyasını düzenle (DB bağlantısı, API key'ler, Telegram token)

# 3. Tüm servisleri başlat
docker compose up -d

# 4. Hazır!
# WebUI  → http://localhost:18501
# API    → http://localhost:7861/docs
# DBA Agent → http://localhost:8100/docs
```

## Servis Portları
| Servis | Port | Açıklama |
|--------|------|----------|
| WebUI | 18501 | Streamlit Arayüzü |
| API | 7861 | REST API & Swagger |
| DBA Agent | 8100 | Otonom Agent API |
| LiteLLM | 4000 | LLM Gateway |
| Prometheus | 9090 | Metrik UI |
| Alertmanager | 9093 | Alert Yönetimi |
| PostgreSQL | 5432 | Dahili DB |

---

<!-- Slayt 16 — Tanı Akışı Süreci -->
# 🔄 Uçtan Uca Tanı Akışı

```
  [1] ALARM
  Prometheus → Alertmanager → Anomivox Notify Worker
       │
       ▼
  [2] ANOMALİ KAYIT
  Alert bilgisi JSON formatında ayrıştırılır
  (alert_name, severity, start_time, metrics)
       │
       ▼
  [3] UZMAN SEÇİMİ
  RoleAssigner → Bilgi tabanından uzman agent'lar seçilir
  (CPU/Memory/IO/Query/Index/Lock uzmanları)
       │
       ▼
  [4] PARALEL TANI
  Her uzman agent kendi alanında:
   • Prometheus'tan metrik çeker
   • ChromaDB'den bilgi tabanı sorgular
   • Kök neden analizi yapar
       │
       ▼
  [5] RAPOR OLUŞTURMA
  ChiefDBA tüm analizleri birleştirir
  → Başlık, Açıklama, Kök Neden, Çözüm Önerileri
       │
       ▼
  [6] BİLDİRİM
  WebUI'a & Telegram'a rapor iletilir
  Riskli çözümler için onay beklenir
```

---

<!-- Slayt 17 — Örnek Tanı Raporu -->
# 📄 Örnek Tanı Raporu Çıktısı

```json
{
  "title": "Yüksek CPU Kullanımı — Verimsiz Sorgu",
  "anomaly_date": "2025-03-04 14:32:00",
  "anomaly_description": "PostgreSQL CPU kullanımı %95'e ulaştı.
                          pg_stat_statements'ta sequential scan
                          tespit edildi.",
  "root_cause": "orders tablosundaki status sütununda eksik index
                 nedeniyle tam tablo taraması yapılıyor.
                 Günde 50.000 kez çalışan sorgu.",
  "labels": ["cpu", "query", "index"],
  "solutions": [
    "CREATE INDEX idx_orders_status ON orders(status);",
    "ANALYZE orders;",
    "Sorgu planını EXPLAIN ANALYZE ile doğrula"
  ]
}
```

---

<!-- Slayt 18 — Performans & Ölçeklenebilirlik -->
# 📈 Performans & Ölçeklenebilirlik

## Model Yanıt Süreleri (CPU-only Ollama)
```
  Triage (llama3.2:1b)    ━━━━━━━━━━━━━━━━  < 1 saniye
  SQL Analiz (sqlcoder)   ━━━━━━━━━━━━━━━━━━━━━━━━  3-8 saniye
  DBA Tanı (llama3.1:8b)  ━━━━━━━━━━━━━━━━━━━━━━━━  3-8 saniye
  Tam Tanı Döngüsü        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ~30-90 sn
```

## Ölçeklendirme Seçenekleri
- **Dikey:** GPU destekli sunucuda 10x hız artışı
- **Yatay:** Birden fazla DBA Agent instance
- **Cloud LLM:** Ollama yerine OpenAI/Groq ile <5sn yanıt

## Altyapı Gereksinimleri (Minimum)
```
CPU-only:  4 vCPU, 16 GB RAM, 50 GB Disk
GPU Mode:  + NVIDIA GPU 8 GB VRAM
```

---

<!-- Slayt 19 — Kullanım Senaryoları -->
# 💼 Kullanım Senaryoları

## Senaryo 1: E-Ticaret Platformu
> *Black Friday yoğunluğunda yavaş sorgu tespit edildi*
- ✅ Anomivox otomatik tespit etti (45 sn)
- ✅ RoleAssigner Query Expert seçti
- ✅ Eksik index önerisi üretildi
- ✅ DBA Telegram'dan onayladı, index oluşturuldu

## Senaryo 2: Fintech — Veri Tabanı Kilit Çakışması
> *Gece 3'te kilit zinciri oluştu, işlemler durdu*
- ✅ Alert → Anomivox Lock Expert devreye girdi
- ✅ Blocking PID tespit edildi
- ✅ `pg_terminate_backend` Telegram onayı ile çalıştırıldı
- ✅ Audit log'a kaydedildi

## Senaryo 3: Sağlık Sektörü — Kapasite Planlaması
> *Veritabanı boyutu kritik eşiği aştı*
- ✅ VACUUM FULL önerildi
- ✅ Yönetici onayı alındı
- ✅ Bakım penceresi dışında otomatik ertelendi

---

<!-- Slayt 20 — Rekabet Avantajı -->
# 🏆 Neden Anomivox?

| Özellik | Geleneksel İzleme | Anomivox |
|---------|-------------------|----------|
| Anomali tespiti | Manuel, reaktif | Otomatik, proaktif |
| Kök neden analizi | DBA uzmanlığı gerekir | LLM tabanlı, otomatik |
| Çözüm önerisi | Yoktur / Manuel | AI üretimi |
| Aksiyon alma | Manuel DBA müdahalesi | Otonom + onaylı |
| 7/24 kapsama | Nöbet zorunlu | Telegram bot |
| Veri gizliliği | Bulut'a veri gönderilir | Yerel LLM seçeneği |
| Çoklu DB desteği | Ayrı araçlar gerekir | Tek platform |
| Denetim izi | Zayıf / Yoktur | JSONL audit log |

---

<!-- Slayt 21 — Güvenlik & Uyumluluk -->
# 🔒 Güvenlik & Uyumluluk

## Veri Güvenliği
- 🔐 **Yerel LLM Desteği** — Hassas veriler dış servise gönderilmez
- 🔐 **Read-Only Diagnostik** — Tüm tanı araçları salt okunur
- 🔐 **Forbidden SQL Patterns** — DROP, TRUNCATE, DELETE, vb. engellenir
- 🔐 **Rol Tabanlı Erişim** — Admin, DBA, Operatör rolleri

## Denetim & İzlenebilirlik
- 📝 Tüm aksiyonlar `dba_agent_audit.jsonl`'a kaydedilir
- 📝 Kimin, ne zaman, hangi komutu onayladığı takip edilir
- 📝 Alert → Tanı → Aksiyon → Sonuç tam izlenebilirliği

## Ağ İzolasyonu
- Tüm servisler `agent_network` Docker bridge ağında izole çalışır
- Dış erişim sadece belirlenen portlar üzerinden

---

<!-- Slayt 22 — Yol Haritası -->
# 🗺️ Ürün Yol Haritası

## ✅ Mevcut (v0.2.0)
- Multi-Agent RAG Diagnostik Sistemi
- DBA Otonom Agent (PostgreSQL, MySQL)
- Telegram Bot (Bildirim + Onay + Chat)
- SSH üzerinden OS İzleme
- LiteLLM Gateway, Ollama desteği
- ChromaDB Vector KB
- Audit Logging

## 🔜 Yakın Dönem (v0.3.0)
- Oracle & MSSQL desteği
- Grafiksel Dashboard & Metrik Görselleştirme
- Scheduled Maintenance Automation
- Multi-tenant kullanıcı yönetimi
- REST API webhook entegrasyonu

## 🔮 Uzun Dönem
- Prediktif anomali tahmini (ML tabanlı)
- Kubernetes Operator desteği
- Çoklu bölge / çoklu veri merkezi izleme
- Özelleştirilebilir playbook sistemi

---

<!-- Slayt 23 — Lisanslama & Destek -->
# 📦 Lisanslama & Destek

## Dağıtım Seçenekleri
```
  On-Premise    →  Kendi sunucunuzda, tam kontrol
  Docker Cloud  →  AWS, Azure, GCP üzerinde
  Hybrid        →  Agent yerel, LLM bulut
```

## Teknik Destek
- 📖 Kapsamlı dokümantasyon
- 🐛 GitHub Issues üzerinden hata bildirimi
- 💬 Slack / Discord topluluk desteği
- 🏢 Kurumsal destek paketi (isteğe bağlı)

## Gereksinimler (Üretim)
```bash
# Minimum
docker, docker compose >= 2.0
4 vCPU, 16 GB RAM, 50 GB SSD

# Önerilen
GPU (NVIDIA 8 GB+) veya Cloud LLM API key
PostgreSQL 12+ veya MySQL 8+
```

---

<!-- Slayt 24 — Kapanış & İletişim -->
# 🎯 Anomivox ile Bir Sonraki Adım

## Sizi Neler Bekliyor?

1. **🎭 Canlı Demo** — Gerçek ortamda anomali tespiti izleyin
2. **🧪 POC (Proof of Concept)** — 2 haftalık pilot kurulum
3. **📋 Teknik Değerlendirme** — Mevcut altyapınıza uyum analizi
4. **🚀 Üretim Kurulumu** — Ekibimizle birlikte tam dağıtım

---

## 💡 Demo Ortamı
```
WebUI  →  http://localhost:18501
API    →  http://localhost:7861/docs
Agent  →  http://localhost:8100/docs
```

---

> **"Veritabanı sorunları artık sizi bekletmeyecek —**  
> **Anomivox, sorunları siz fark etmeden önce çözüyor."**

---

# ❓ Sorular & Tartışma

## Teşekkürler!

```
  GitHub  :  github.com/rkazak07/anomivox
  Proje   :  Anomivox — AI-Powered Database Operations Platform
  Versiyon:  v0.2.0
```

---
*Bu sunum dosyası Marp, Slidev veya herhangi bir Markdown sunum aracıyla kullanılabilir.*
