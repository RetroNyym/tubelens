# Changelog

TubeLens depoya itilen her önemli değişikliğin kaydı. Yeni bir değişiklik
her push ile buraya eklenir. Biçim: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/).

## [Unreleased] — 2026-10-07

### Eklendi
- **Web görsel araması (anahtarsız):** yeni `webimg.py` — Bing → Openverse →
  Wikimedia Commons sayfa aramasıyla konuya alakalı gerçek fotoğraf indirir
  (anahtar gerekmez). Kaynak zincirine 4. kademe olarak girdi
  (`footage.from_web_images`, `gather(allow_web=…)`); kapatmak için CLI
  `--no-web-images`, panelde "Web görsel araması" onay kutusu (varsayılan açık).
  Test: `tests/test_webimg.py`.
- **LTX AI video (opsiyonel):** yeni `hfspace.py` — Hugging Face Spaces
  `Lightricks/ltx-video-distilled` ile metinden gerçek video klibi
  (`footage.from_ltx_video`, `gather(allow_ltx=…)`); CLI `--ltx-video`,
  panelde "AI video LTX" onay kutusu (varsayılan kapalı). Anonim kota dolduğunda
  `HfSpaceError` fırlatılır ve zincir sessizce sonraki kaynağa düşer.
  `--hf-token` / panel "Hugging Face token" alanı token'ı `vconf`'a kaydeder
  (kota genişletir + HF router LLM).
- **HF router LLM (opsiyonel):** `llm.py`'ye `HF_ROUTER`/`HF_MODEL`
  (`openai/gpt-oss-120b`) — `--hf-token` varsa senaryo üretimi (script/clone)
  ücretsiz HF kredisiyle (`$0.10/ay`) Pollinations yerine çalışır.
- **Panel Video Üret formu alanları:** `vwebimg` / `vltx` / `vhf` —
  `POST /api/video` gövdesine `web_images`, `ltx_video`, `hf_token`;
  `startVideo` + `opt_map` + `--no-web-images`/`--ltx-video` bayrakları.
- **Panelde URL ile sekme açma:** `initTab()` + `load` → `location.hash`
  (`#video` → Video Üret, `#durum` → Durum & Lisans) — ekran görüntüsü /
  derin bağlantı desteği.
- **README ekran görüntüleri:** üç sekmenin gerçek panelden görselleri
  `docs/screenshots/panel-tarama.png`, `panel-video-uret.png`, `panel-durum.png`
  + "Ekran Görüntüleri" bölümü.

### Değiştirildi
- Kaynak zinciri tablosu 4 → 6 kademe (web görsel araması + LTX eklendi);
  `footage.gather` imzası `allow_web=True, allow_ltx=False, hf_token=""` aldı.
- Testler `allow_web=False` ile ağdan bağımsızlaştırıldı
  (`tests/test_footage.py`); suite 79/79 geçiyor.

## [Unreleased] — 2026-09-29

### Eklendi
- **Çift indirme:** her üretim iki dosya üretir — `video.mp4` (altyazılı) +
  `video_no_subs.mp4` (altyazısız). Panelde "Son üretim" kartında iki ayrı
  belirgin buton (mavi/yeşil) + `altyazılı + altyazısız hazır` rozeti.
  Yeni uç: `GET /api/video/nosubs` (HTTP Range, seek destekli).
  (`c797a3c`, `4c45856`)
- **PC'den fotoğraf yükleme:** Video Üret sekmesinde "PC'den foto ekle"
  butonu; jpg/png/webp çoklu yükleme (40 dosya, 25 MB/dosya, yalnızca
  127.0.0.1). Uçlar: `POST /api/upload`, `POST /api/upload/delete`,
  `GET /api/uploads`. Yüklenen fotoğraflar üretimde **en öncelikli görüntü
  kaynağı** olarak kullanılır (elle yazılan "Görüntü klasörü" onu geçer);
  fotoğraflar Ken Burns ile klipe çevrilir ve klip önbelleklenir.
  (`dfcd7af`)
- **Yerel görüntü klasiğine foto desteği:** `footage.from_local` artık
  `.jpg/.jpeg/.png/.webp` kabul eder → Ken Burns ile `local_*.mp4` klip'e
  çevrilir; video + foto karışık klasörler çalışır. (`dfcd7af`)
- **Panel üretim mod logu:** üretim başlarken satır hangi modla gittiğini
  yazar (`senaryo+video (tüm adımlar)` · `goruntu klasoru kullaniliyor` …). (`1f9379c`)

### Düzeltildi
- **Pollinations "duz metin HTTP 200" hatası (kök neden):** `openai-fast`
  reasoning modunda thinking alanını doldurup `content`'i boş bırakıyordu.
  Çözüm: `reasoning_effort: "low"` (thinking 966 → 193 karakter), token
  bütçesi 1600 → 2400, anonim çalışmayan `gen.pollinations.ai` ucu kaldırıldı
  (401), `{"role":…}` nesne yanıtlarından iç content çıkarımı eklendi,
  boş yanıt teşhisi (reasoning karakter sayısıyla). (`629ccdb`)
- **Panel üretiminde senaryoda kalma:** "Sadece senaryo" onay kutusu
  kaldırıldı — panelde "Video Üret" her zaman5 adımın tamamını çalıştırır
  (senaryo → görüntü → ses → altyazı → MP4). CLI `video --script-only`
  bilinçli kullanım için duruyor. `result.ok` alanı artık her zaman
  boolean. (`1f9379c`)
- **Panel JS:** template literal ternary + onclick tırnak çakışması;
  `node --check` syntax testi eklendi (sekmelere tıklanamama sorunu). (`68a17fe`)

## [Unreleased] — 2026-09-28

### Eklendi
- **Masaüstü dağıtımı:** `pyinstaller tubelens.spec` → `dist/TubeLens.exe`
  (tek dosya, ~84 MB). Argümansız açılış paneli başlatır; frozen modda veri
  `%LOCALAPPDATA%\TubeLens`, gömülü veriler `_MEIPASS`; port meşgul ise
  "Panel zaten calisiyor" + tarayıcı aç. (`1f59104`)
- **RETRO+ tam ekran watermark:** GitHub profil fotoğrafından üretilen
  gömülü PNG ile panel + raporda `position:fixed` arka plan watermark (%7/%6
  opaklık); eski sağ-alt lens watermark kaldırıldı. (`ad99cf3`)
- **Marka kimliği:** TubeLens SVG/PNG logo, favicon, footer imzası;
  videoya üst-sağ filigran (`--no-logo` ile kapatılır), YouTube meta'ya
  "— TubeLens ile üretildi" imza satırı, Pillow bağımlılığı. (`d2af15d`)
- **CI dayanıklılığı:** `pip install --retries 10 --timeout60` (PyPI
  zaman aşımı geçici hataları). (`d91a544`)

## [Unreleased] — 2026-09-28 (önceki)

### Eklendi
- **İki kilit USP:** **Kazananı Klonla** (rakip video URL → transcript →
  özgün senaryo taslağı → üretim hatti, panelde ▶ Klonla) + **Gelir Kaçak $
  Paneli** (izlenme × CTR × tıklama başı kazanç modeli, eksik kırılımı:
  affiliate %60 / shopping %25 / kısa açıklama %10). (`06d1b44`)
- **Senaryo üretimi güvenilirliği:** max_tokens bütçesi, kesik JSON
  onarımı (`_repair_json` + trailing comma temizleme), 429 kuyruk backoff,
  `openai-fast` model. (`37b5cc4`)

## Sürümler (özet)

| Tarih | Commit | Özet |
|---|---|---|
| 2026-09 | `5a4f06d` | Satıcı keygen: toplu üretim (`--count/--csv`) |
| 2026-09 | `845769e` | Sekmeli panel + görüntü kaynak zinciri + 4 TTS + CI |
| 2026-09 | `1f3339a` | Video kiti: MoneyPrinterTurbo tarzı anahtarsız hat |
| 2026-09 | `3737212` | LemonSqueezy ile uzaktan lisans doğrulama |
| 2026-09 | `4b97e8c` | İlk sürüm: YouTube AI görünürlük + affiliate denetçisi |
