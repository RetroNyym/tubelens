# TubeLens

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](requirements.txt)
[![CI](https://github.com/RetroNyym/tubelens/actions/workflows/ci.yml/badge.svg)](https://github.com/RetroNyym/tubelens/actions/workflows/ci.yml)
[![Free queries](https://img.shields.io/badge/ücretsiz%20sorgu-5-brightgreen.svg)](#ücretsiz-plan-ve-lisans)
[![Video kit](https://img.shields.io/badge/video-MP4%20üretimi-brightgreen.svg)](#3-tubelens-video-kit--para-basan-video-hattı)

**YouTube AI arama görünürlüğü + affiliate gelir denetçisi.**
Tek komutla bir videonun ya da kanalın: yapay zekâ özetlerinde görüp görünmediğini,
4 arama motorundaki sırasını, affiliate link / disclosure / YouTube Shopping eksiklerini
ve kaçırılan gelir fırsatlarını gösterir.

**Ayrıca** anahtarsız **video üretim kiti** ile konudan bitmiş MP4 üretir
(senaryo → stok görüntü → seslendirme → altyazı → montaj), panelden tek tuşla.

> **Neden bu araç?** 2026'da YouTube trafiğinin büyük kısmı Google AI Overviews,
> YouTube'un kendi AI özeti, Bing Copilot ve DuckDuckGo AI Chat üzerinden geliyor.
> "Video kaçırıyor mu?" sorusuna yanıt veren, bunu API anahtarı olmadan yapan ve
> affiliate tarafını da kontrol eden bir araç pazarda neredeyse yok.

---

## Özellikler

### 1) AI arama görünürlüğü takibi
Anahtar kelimeyi 4 motor üzerinden sorgular ve videonun nerede göründüğünü puanlar:

| Motor | Ağırlık | Ne ölçülür |
|---|---|---|
| Google | 0.35 | Organik sıralama + AI Overview içinde var mı |
| YouTube  | 0.30 | Sıralama + **sonucun kendi AI özeti** + başka videonun AI özeti metninde geçme |
| Bing | 0.20 | Sıralama + Copilot/AI kutusu |
| DuckDuckGo | 0.15 | Sıralama + AI Chat sonucu |

- `+AI` rozeti: sonucun AI özet kutusunda da göründüğünü gösterir.
- `in_ai_text`: videonun başlığı *başka* bir videonun AI özeti metninde geçiyor mu
  (yani rakip videonun AI kaynağı olup olmadığınız).
- Bot koruması / JS zorunluluğu olan motorlar **"bulundu" yerine dürüstçe `hata` döner**
  ve ağırlık çalışan motorlara kayar — yanıltıcı "0 sonuç" vermez.

### 2) Affiliate & YouTube Shopping denetçisi
Her video için:
- Açıklamadaki linkler → affiliate tespiti (Amazon, Trendyol, Havuz, Impact, cdiscount …)
- Reklam/sponsor **disclosure** var mı (YouTube politika riski)
- YouTube Shopping ürün etiketi var mı
- Açıklama uzunluğu, spam sinyalleri, konuya uygun program önerileri

Sonuçta **0-100 gelir fırsat skoru** ve "şu videoya şunu ekle" şeklinde öncelikli
fırsat listesi üretilir. Yanında **$ kaçak tahmini** da var (aşağıda bkz. özellik 5).

### 3) TubeLens Video Kit — para basan video hattı

MoneyPrinterTurbo tarzı, **kendi kitimiz** olarak doğrudan CLI'ye gömülü tam video
üretim hattı. Tek komutla konudan bitmiş MP4'e:

- **Senaryo** → anahtarsız Pollinations LLM (hook, anlatım, SEO başlık/açıklama/etiket + İngilizce stok görüntü kelimeleri)
- **Görüntü** → dört kademeli kaynak zinciri (ilk elenen geçer, **hiçbirinde anahtar yoksa bile üretilir**):

  | Sıra | Kaynak | Anahtar |
  |---|---|---|
  | 1 | `--footage-dir` kendi görüntüleriniz | gerekmez |
  | 2 | Pexels API | ücretsiz |
  | 3 | Pixabay API | ücretsiz |
  | 4 | **Pollinations AI görsel + Ken Burns** (anahtarsız) | **yok** |

- **Seslendirme** → 4 motor (`--tts-engine`):

  | Motor | Anahtar | Kelime zamanlaması |
  |---|---|---|
  | `edge` (varsayılan) | **yok** | gerçek (WordBoundary) |
  | `gtts` | **yok** | tahmini (orantılı) |
  | `openai` | OpenAI API | tahmini (orantılı) |
  | `elevenlabs` | ElevenLabs API | **gerçek** (karakter bazlı) |

- **Altyazı** → kelime bazlı zamanlamadan SRT + videoya yakma (libass)
- **Montaj** → FFmpeg: hedef çözünürlüğe indirme (cover-crop), klip birleştirme, ses kalibrasyonu, opsiyonel arka plan müziği, `+faststart`

Çıktı klasöründe: `video.mp4`, `script.json` / `script.txt`, `audio.mp3`,
`subtitles.srt` ve YouTube'a yükleme için hazır `meta.json` (başlık/açıklama/etiketler).

> **Marka imzası:** her video sağ üst köşede yarı saydam **TubeLens filigranı** taşır
> ve `meta.json` açıklamasının sonuna "— TubeLens ile üretildi" satırı eklenir
> (`--no-logo` ile kapatılır; panelde Video Üret sekmesindeki onay kutusu).

> **Ücretsiz ve anahtarsız:** senaryo + TTS (edge/gtts) + altyazı + montaj + AI görsel
> tamamen anahtarsız çalışır. Pexels/Pixabay anahtarları isteğe bağlı hız/kalite artışıdır;
> OpenAI/ElevenLabs yalnızca daha iyi ses isteyenler içindir.

### 4) Kazananı Klonla — Tarama → Üretim hattı (rakiplerde yok)

Tarama tablosundaki her videonun yanındaki **`▶ Klonla`** butonu:

1. Kaynak videonun **transkriptini** (kapalıysa başlık+açıklamayı) çeker,
2. LLM ile videonun **yapısını** (hook, akış, tempo) analiz edip **aynı yapıda
   özgün senaryo** üretir — birebir kopya prompt'ta yasaklanmıştır (%30 farklı açı),
3. Senaryo `data/clone_draft.json`'a yazılır, panel Video formunu **otomatik doldurur**,
4. `Video Üret`e bastığında senaryo **dosyadan okunur** (LLM tekrar çalışmaz).

```bash
# CLI karşılığı
python -m tubelens clone "https://www.youtube.com/watch?v=VIDEO_ID"
python -m tubelens video --script-file data/clone_draft.json
```

> "Rakibin en çok izlenen videosunu bul → 3 dakikada kendi versiyonunu üret" hattı.
> Kota harcamaz (Pollinations anahtarsız); YouTube API anahtarı gerekmez.

### 5) Gelir Kaçak $ Paneli — skor değil, para

Skorlar ikna etmez; **para rakamı** eder. Tarama sonrası:

- **"Tahmini aylık kaçak: $X"** kartı — izlenme × affiliate tıklama oranı × konu/komisyon endeksi;
  affiliate/shopping/eksik açıklama payları ayrı ayrı $ olarak kırılır
  (affiliate %60, shopping etiketi %25, kısa açıklama %10),
- Tabloda video bazlı **$ Kaçak** sütunu,
- Her videoda **`Düzelt ▾`** → eksik için hazır reçete: disclosure metni, program önerisi,
  Studio etiketleme adımları, açıklama iskeleti — hepsi **`Panoya kopyala`** ile tek tık,
- HTML raporda aynı kart + "Hazır Düzeltme Reçeteleri" bölümü.

> Hesaplama deterministiktir, **kota harcamaz**. Endeksler `shopping.py`'de
> (`_EARN_PER_CLICK`, `_AFFILIATE_CTR`) düzenlenebilir.

---

## Kurulum

```bash
git clone https://github.com/RetroNyym/tubelens.git
cd tubelens
python -m venv .venv
.venv\Scripts\activate        # Windows — Linux/macOS: source .venv/bin/activate
pip install -e .              # `tubelens` komutunu da kurar (alternatif: -r requirements.txt)

# doğrulama + testler (offline, ~5 sn)
tubelens --version
python -m pytest
```

Gereksinim: **Python 3.11+**, internet erişimi. YouTube Data API anahtarı **gerekmez**.
Video kiti için de anahtar gerekmez (ffmpeg `imageio-ffmpeg` ile otomatik gelir).

---

## Kullanım

```bash
# Tek video: affiliate + shopping denetimi
python -m tubelens scan "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Kanalın son videolarını tara
python -m tubelens scan "@mkbhd" --limit 10

# AI görünürlük kontrolü (her anahtar kelime 1 sorgu harcar)
python -m tubelens scan "@mkbhd" --limit 5 --keywords "en iyi bütçe laptop 2026, iphone 18 inceleme"

# Kayıtlı veriden HTML rapor üret
python -m tubelens report

# KAZANANI KLONLA: rakip videonun yapısını özgün senaryoya çevir
python -m tubelens clone "https://www.youtube.com/watch?v=VIDEO_ID"
python -m tubelens video --script-file data/clone_draft.json   # senaryo dosyadan (LLM atlanır)

# Yerel panel (tarayıcıda açılır) — 3 sekmeli: Tarama & Rapor | Video Üret | Durum & Lisans
python -m tubelens panel

# Video Kit: konudan bitmiş videoya (senaryo + görüntü + ses + altyazı)
python -m tubelens video "Sabah koşusunun 7 faydası"

# Sadece senaryo üret (YouTube başlık/açıklama/etiketler dahil)
python -m tubelens video "Yapay zeka nedir" --script-only

# Anahtarsız tam üretim: AI görsel (Ken Burns) + Google gTTS seslendirme
python -m tubelens video "Gülümsemenin enerji veren etkisi" --tts-engine gtts

# ElevenLabs ile profesyonel ses + gerçek kelime zamanlaması
python -m tubelens video "Kahve demleme sırları" --tts-engine elevenlabs --elevenlabs-key ANAHTAR

# Pixabay + Pexels anahtarlarıyla stok görüntüler, yatay 720p
python -m tubelens video "Kahve demleme" --aspect 16:9 --resolution 720 \
  --footage-dir "C:\footage" --pixabay-key PIX_KEY --bgm music.mp3

# Pexels/Pixabay anahtarını bir kez kaydet (ücretsiz: pexels.com/api · pixabay.com/api/docs)
python -m tubelens video "konu" --pexels-key PTL_ANAHTAR --pixabay-key PBX_ANAHTAR
```

- **CLI:** çıktı `reports/report_*.html` dosyasına yazılır.
- **Panel:** `http://127.0.0.1:8787` — **3 sekme**: *Tarama & Rapor* (analiz tabloları),
  *Video Üret* (kaynak/ses motoru seçimli üretim formu + oynatıcı; **klon taslağı
  geldiğinde form otomatik dolar**), *Durum & Lisans*
  (kota, lisans aktivasyon formu). Tarama sekmesinde **`▶ Klonla`** butonu ve
  **$ kaçak** sütunu + satır açılır **`Düzelt ▾`** reçeteleri (Panoya kopyala) vardır.
  Üretilen video panelde oynatılır ve
  `/api/video/latest` adresinden indirilir (HTTP Range destekli, cache-bust'lu).
  Headless ortam için: `python -m tubelens panel --no-browser`.
- **Panel video API'si:** `POST /api/video` gövdesi:
  `{topic, lang, duration, aspect, resolution, style, footage_dir, pexels_key, pixabay_key,
  ai_visuals, tts_engine, voice, openai_key, elevenlabs_key, script_only, script_file}`;
  ilerleme `/api/state` → `video` alanında, son üretim `/api/video/latest` + `/api/video/srt`;
  klon: `POST /api/clone` `{url}` → `state.clone.draft`;
  lisans: `POST /api/activate` `{key}`. Üretim ≈1–3 dk sürer.
- **Video Kit:** çıktı `videos/<zaman>-<slug>/` klasörüne yazılır; en son üretim
  `videos/` altında kalır, depoya girmez. `video --help` tüm seçenekleri listeler
  (`--lang`, `--duration`, `--aspect 9:16|16:9|1:1`, `--voice`, `--clips`,
  `--no-subs`, `--bgm-volume`, `--out` …).

### Örnek çıktı (gerçek üretim)

```bash
python -m tubelens video "Gülüşü güzelleştiren 3 alışkanlık" --duration 15 --resolution 720
```

```
videos/panel-20260928-104745/
├── video.mp4        ← 19.3 sn, 9:16 @720p, H.264 + AAC, altyazılar videoya yakılmış
├── script.txt       ← seslendirme metni (konuşma dili)
├── script.json      ← sahne/kare yapısı + hook + CTA
├── audio.mp3        ← Edge TTS (tr-TR-ahmetNeural)
├── subtitles.srt    ← kelime bazlı zamanlanmış altyazı (6 cue)
└── meta.json        ← YouTube başlık/açıklama/etiketler + stok görüntü terimleri
```

- **Önizleme videosu (360p):** [examples/ornek-video/video-onizleme-360p.mp4](examples/ornek-video/video-onizleme-360p.mp4)
- **Metin örnekleri:** [examples/ornek-video/](examples/ornek-video/) — `meta.json`,
  `script.txt`, `subtitles.srt` gerçek çıktıdan alınmıştır.
- **Panel HTTP API örneği:** [examples/video-api.sh](examples/video-api.sh)

Örnek senaryo ve altyazı (üretimden, olduğu gibi):

> İlk 3 saniyede gülümsemeye hazır olun! Yeni 3 alışkanlıkla yüzünüzü aydınlatın.
>
> 1️⃣ Güneş ışığıyla dolu bir duş alın, 2️⃣ Çiçekli minik aksesuarlar takın,
> 3️⃣ Saçlarınızı doğal bir dokuya kavuşturun. Gülüşünüzü şimdi yükseltin!

```srt
1
00:00:00,050 --> 00:00:02,775
İlk 3 saniyede gülümsemeye hazır olun

2
00:00:03,650 --> 00:00:06,388
Yeni 3 alışkanlıkla yüzünüzü aydınlatın
```

Video hattının akışı:

```
konu ─▶ llm.py (Pollinations, anahtarsız) ─▶ senaryo + YouTube SEO meta
          ├─▶ footage.py  (Pexels / --footage-dir) ─▶ klip .mp4'ler
          ├─▶ voice.py    (Edge TTS, anahtarsız)   ─▶ audio.mp3 + kelime zamanları
          └─▶ assemble.py (FFmpeg: scale/crop, concat, tpad, SRT yakma, mix)
                                    └─▶ video.mp4 + meta.json + subtitles.srt
```

---

## Ücretsiz plan ve lisans (Freemium)

| | Ücretsiz | Pro |
|---|---|---|
| Video / kanal tarama | ✅ sınırsız | ✅ sınırsız |
| Affiliate & shopping analizi | ✅ sınırsız | ✅ sınırsız |
| AI görünürlük sorgusu | **5 sorgu** | sınırsız |
| Rapor + panel | ✅ | ✅ |
| Video üretim kiti (senaryo + MP4) | ✅ sınırsız | ✅ sınırsız |

- **1 sorgu = 1 anahtar kelime.** `--keywords a,b,c` 3 sorgu harcar.
  Kaç video taradığınız hak yakmaz.
- Kalan hak az ise sistem ilk N kelimeyle çalışır ve uyarır; hak bittiyse
  AI adımı kilitlenir, video/affiliate analizi çalışmaya devam eder.
- Durum ve kota: `python -m tubelens status`

```bash
# Pro'ya geçiş — iki tür anahtar kabul edilir:
#  1) Ödeme sonrası verilen ürün anahtarı (LemonSqueezy, çevrimiçi doğrulanır)
python -m tubelens activate 38b1460a-5104-4067-a91d-77b872934d51
#  2) Yerel/dağıtım anahtarı (TL1-..., çevrimdışı, imza ile)
python -m tubelens activate TL1-xxxx-yyyy

python -m tubelens deactivate     # lisansı bu bilgisayardan kaldırır
python -m tubelens status         # kalan hak / lisans detayı
```

### Lisans nasıl doğrulanıyor?

| | Yerel anahtar (`TL1-…`) | Ürün anahtarı (LemonSqueezy) |
|---|---|---|
| Doğrulama | Çevrimdışı, HMAC-SHA256 imzası | Çevrimiçi License API (`activate` / `validate`) |
| Süre sınırı | Anahtarın içinde taşır | Paneldeki anahtar bitiş tarihi |
| Yeniden kontrol | Yok (imza yeterli) | En fazla **7 günde bir** tek istek |
| İnternet yoksa | Sorun yok | **30 günlük tolerans**; sonrası ücrete düşer |
| Kullanım hakkı | Sınırsız | Sınırsız (activation limiti varsa o kadar cihaz) |

- Doğrulama `tubelens/license.py` içindedir; `activate` yanıtı ve
  `activation_id` `data/quota.json`'a yazılır.
- API `expired` / `disabled` dönerse lisans otomatik düşer ve kullanıcı
  ücretsiz plana döner (sayaç yerinde kaldığı için 5 hakkı yeniden başlar).
- Kota dosyası elle silinirse sayaç sıfırlanır; **LemonSqueezy anahtarında bu
  işe yaramaz**, çünkü lisans sunucuda durur — asıl caydırıcılık ödeme
  entegrasyonundan gelir.

### Satıcı kurulumu (LemonSqueezy)

1. [LemonSqueezy](https://lemonsqueezy.com) hesabı aç → mağaza oluştur.
2. **Products → New product** → *Software license* tipini seç,
   *License key generation* açık olsun (limit/bitiş ayarlayabilirsin).
3. Müşteri ödeme yaptığında anahtar otomatik üretilir ve e-posta ile gider.
4. Anahtarı alan müşteri `python -m tubelens activate <ANAHTAR>` der —
   ek API anahtarı ya da webhook **gerekmez** (License API anahtarsız çalışır).
5. Panel/kota: `python -m tubelens keygen` ile dağıtım (yerel) anahtarı da
   üretebilirsin; ürün anahtarlarının tek avantajı sunucu tarafında iptal
   edilebilmesidir (`deactivate`, anahtar durumu *disabled*).

İsteğe bağlı: LemonSqueezy **webhook**'unu bir GitHub Action'a bağlayıp
satışları `data/` dışındaki bir kayıt defterine yazabilirsin; müşteri tarafında
zaten License API doğrulaması yapıldığı için bu zorunlu değildir.

### Toplu anahtar üretimi — müşteriye gönderim (satıcı)

```bash
# 100 adet 1 yıllık anahtar -> data/keys/satis-365gun.csv
python -m tubelens keygen --days 365 --count 100 --csv data/keys/satis-365gun.csv

# 20 adet sınırsız anahtar -> data/keys/satis-sinirsiz.csv
python -m tubelens keygen --days 0 --count 20 --csv data/keys/satis-sinirsiz.csv

# Tek anahtar (konsola basar)
python -m tubelens keygen --days 365
```

- **Akış:** satışta müşteriye CSV'den bir `TL1-…` anahtarı olduğu gibi gönderirsin;
  müşteri kendi makinesinde `python -m tubelens activate <ANAHTAR>` der.
  Anahtar **HMAC-SHA256 imzalıdır** — aktivasyon internet *istemz*, çevrimdışı
  doğrulanır; her anahtar tek cihazda aktifleşir (`deactivate` ile serbest kalır).
- **CSV sütunları:** `key, days, generated_at, status` — gönderdiğin anahtarın
  `status`'unu *sent/active* olarak güncelleyip satış takibi yapabilirsin.
- **Güvenlik:** `/data/keys/` `.gitignore`'dadır, anahtarlar depoya girmez.
  Sınırsız sayıda üretebilirsin; her üretim anında kendini doğrular.

---

## Nasıl çalışıyor?

YouTube Data API kotası ve anahtarı olmadan çalışır. HTML'deki gömülü JSON
(`ytInitialPlayerResponse`, `ytInitialData`) ayrıştırılır:

| Modül | Görev |
|---|---|
| `youtube.py` | Video/kanal/arama scraping, AI özeti sinyalleri, `lockupViewModel` & `videoRenderer` desteği |
| `search.py` | Google / YouTube / Bing / DDG kontrolü + ağırlıklı skor |
| `shopping.py` | Affiliate, disclosure, shopping etiketi analizi + fırsat skoru |
| `quota.py` | Freemium kota (5 sorgu) + lisans durumu |
| `license.py` | LemonSqueezy License API: activate / validate / deactivate, 7 gün yenileme, 30 gün tolerans |
| `report.py` | Tek dosya HTML rapor (`reports/latest.html`) |
| `panel.py` | Sekmeli HTTP paneli: tarama + video üretim API'si + lisans aktivasyon, oynatıcı/indirme (Range) |
| `cli.py` | `scan` / `report` / `panel` / `video` / `status` / `activate` / `deactivate` / `keygen` (`--version`) |
| `storage.py` | `data/store.json` kayıt deposu (tarama geçmişi) |
| `llm.py` | Anahtarsız Pollinations LLM istemcisi + MPT tarzı senaryo üretici (JSON şema, cache-kırma retry) |
| `footage.py` | Görüntü kaynak zinciri: lokal → Pexels → Pixabay → **Pollinations AI görsel + Ken Burns (anahtarsız)** |
| `voice.py` | 4 TTS motoru: Edge / gTTS (anahtarsız), OpenAI / ElevenLabs (anahtarlı) + kelime zamanlamaları |
| `assemble.py` | FFmpeg montaj: scale/crop, concat, tpad, SRT yakma, ses mix |

Kurulum/test altyapısı: `pyproject.toml` (`pip install -e .` → `tubelens` komutu),
`tests/` (33 birim/smoke test, tamamı offline), GitHub Actions CI (Ubuntu + Windows).

İstekler kibar gecikmeli (`POLITE_DELAY = 0.8s`), tek bir User-Agent ile atılır.
Video kiti ağ istekleri: Pollinations (senaryo + AI görsel), Pexels/Pixabay (stok,
opsiyonel), Edge TTS / gTTS (ses, anahtarsız), OpenAI/ElevenLabs (ses, anahtarlı).

---

## Sınırlar ve yasal not

- Google bu araç için sonuç sayfası yerine JS/consent sayfası, Bing bot koruması
  nedeniyle alakasız sonuç döndürebilir; bu durumlar `hata` olarak işaretlenir.
- Araç yalnızca **herkese açık** sayfaları okur, istek atım hızını düşük tutar.
- YouTube/Google hizmet şartlarına uyumdan **kullanıcı sorumludur**; ticari kullanımda
  resmi API'ye geçiş önerilir.
- Rapor ve skorlar tahmini değerdir, kesin gelir garantisi vermez.

---

## Yol haritası

- [x] Ödeme entegrasyonu: LemonSqueezy License API ile uzaktan lisans doğrulama
- [x] Video üretim kiti: MoneyPrinterTurbo tarzı anahtarsız senaryo → MP4 hattı
- [ ] Webhook → GitHub Action ile satış kaydı (opsiyonel)
- [ ] Zaman serisi: skor takibi (`runs` geçmişinden trend grafiği)
- [ ] Rakip AI görünürlüğü karşılaştırma (aynı sorguda kim önde?)
- [ ] Toplu CSV dışa/içe aktarma ve planlı tarama (`cron`)
- [ ] Kanal bazlı affiliate boşluk raporu (hangi videoda hangi program eksik)
- [x] Görüntü: Pixabay + anahtarsız AI görsel/Ken Burns kaynak zinciri
- [x] Panel üzerinden video üretimi (Video Üret formu + oynatıcı/indirme)
- [x] Panel sekmeleri: Tarama & Rapor | Video Üret | Durum & Lisans (+ aktivasyon)
- [x] TTS motorları: Edge + gTTS (anahtarsız), OpenAI + ElevenLabs (anahtarlı)
- [x] Altyapı: pyproject kurulumu, 33 test, GitHub Actions CI

---

## Lisans

Anahtarlar bu depo üzerinden dağıtılır:

1. İletişim: [Issues](https://github.com/RetroNyym/tubelens/issues) (anahtar talebi / ödeme)
2. Ödeme sonrası **Pro anahtarınız** iletilir (LemonSqueezy mağazası).
3. Aktivasyon:

```bash
python -m tubelens activate <ÜRÜN ANAHTARI>   # LemonSqueezy (çevrimiçi)
python -m tubelens activate TL1-xxxx-yyyy      # yerel/dağıtım anahtarı (çevrimdışı)
python -m tubelens deactivate                  # cihazdan kaldır
```

Ücretsiz planda kalan hakkınızı `python -m tubelens status` ile görürsünüz.
Satıcı tarafında yerel anahtar üretimi: `python -m tubelens keygen --days 365`.

Kodun kendisi [MIT](LICENSE) ile lisanslıdır; **anahtar üretimi ve satışı**
lisans sahibine aittir. Kota sayacı `data/quota.json` içinde tutulur; ürün
anahtarlarında doğrulama LemonSqueezy üzerinde olduğu için dosya elle
değiştirilse bile Pro erişim açılmaz.

## Katkı

Issue ve PR açmak serbest. Kurulum sonrası `python -m tubelens status` ile
ortamın çalıştığını doğrulayın.
