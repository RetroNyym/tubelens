# Changelog

TubeLens depoya itilen her önemli değişikliğin kaydı. Yeni bir değişiklik
her push ile buraya eklenir. Biçim: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/).

## [Unreleased] — 2026-10-08

### Eklendi
- **Klip modu:** yeni `klip.py` — metinden anlatımsız 3–15 sn klip; sağlayıcı
  sırası `ltx` (HF Spaces, anahtarsız) → `pollinations` (`POLLINATIONS_API_KEY`)
  → `viggle`/`higgsfield` (env anahtarlı). CLI `python -m tubelens klip <FİKİR>`,
  panel 3. sekmede "Klip Üret" formu. Yeni `viggle.py` / `higgsfield.py`.
  Testler: `tests/test_klip.py`, `tests/test_viggle.py`.
- **Avatar modu:** yeni `avatar.py` — görsel + ses (yoksa metinden Edge TTS)
  ile dudak senkron video; sıra LatentSync (HF Spaces) → Hedra
  (`HEDRA_API_KEY`) → Viggle (`VIGGLE_API_KEY`). CLI `avatar --image …`,
  panelde "Avatar Üret" formu. Test: `tests/test_avatar.py`.
- **ai-video-studio portu (panel):** 5 sekmeli yeni arayüz —
  *Klip & Avatar*, *Galeri & Kuyruk* sekmeleri; gruplu Video Üret formu
  (Konu & Format · Görsel Kaynakları · Ses & Altyazı).
- **İş kuyruğu:** `/api/video|klip|/avatar` → `_enqueue` (aynı anda en fazla
  2 farklı mod, geçmiş 60 iş, `state.jobs`), 2 daemon worker;
  `/api/gallery` + `/api/gallery/<ad>/<dosya>` (Range/streaming),
  `POST /api/gallery/delete`.
- **Ses & müzik yükleme:** `AUDIO_DIR`/`BGMDIR` + `GET/POST /api/audio`,
  `/api/bgm` (mp3 vb., 20 dosya sınırı) + silme uçları; panelde "Müzik yükle"
  ve ses seçimi; `POST /api/video` gövdesine `bgm`, `bgm_volume`.
- **Stil preset'leri:** yeni `presets.py` — `sinematik|anime|2d|3d|minimal|
  belgesel`; CLI `--preset`, panelde "Stil" seçici; senaryo + görsel ekine
  birleşik uygulanır. Test: `tests/test_presets.py`.
- **4:3 / 3:4 formatları:** `assemble.SIZES` + AI görsel boyutları
  (1344×1008 / 1008×1344) + Pexels/Pixabay dikeylik tercihleri; clone ve
  video `--aspect` choices'ına eklendi. Testler: `test_assemble.py`,
  `test_footage.py`.
- **HF FLUX görsel:** yeni `hf.py` — 4 uçlu router (`FLUX.1-schnell`, krea,
  SD3 …), token yoksa hata; `footage.from_ai_images` HF-first → Pollinations
  fallback. Test: `tests/test_hf.py`.
- **hfspace genişletmesi:** `available()` (asla fırlatmaz, cache'li),
  `upload()`, `image_to_video()` (görüntüden LTX klip), `lipsync()`
  (LatentSync Space), `LATENTSYNC_SPACE`. Test: `tests/test_hfspace.py`.
- **Durum & Lisans aksiyonları:** `POST /api/deactivate` + `/api/report`
  (`_run_action`, `state.action_log`), lisans detayı + sağlayıcı rozetleri
  (`state.providers`), "Kaldır (deactivate)" / "Raporu yeniden oluştur".
- **Tarama sekmesi klon ayarları:** `cllang`/`claspect`/`cldur` — klon
  dili, formatı ve süresi (`POST /api/clone {url, lang, aspect, duration}`).

### Değiştirildi
- Panel arayüzü baştan tasarlandı (gruplu kart CSS'i, 5 sekme, alanların
  tamamı kuyruk/Galeri/Durum uçlarıyla eşleşiyor); ekran görüntüleri
  `docs/screenshots/` altında 5 sekme olarak yenilendi.
- `POST /api/video` artık **kuyruğa** alır (`{ok, job}` döner, tekil
  `video_busy` reddi kalktı); panelde üretim logu job nesnesinden okunur.
- `footage.gather` docstring + kodda kaynak sırası: web görsel araması
  LTX'ten **önce** (dokümanla aynı).
- `pyproject.toml` package-data: `tubelens/data/*.json` (kurulumla gelir);
  README `pip install -e ".[dev]"`.

### Düzeltildi
- **Kuyruk `params` kayboluyordu:** `_enqueue` iş nesnesine yazmıyordu →
  CLI `topic`'siz çalışıp "topic veya --script-file gerekli" ile bitiyordu
  (regresyon testi `test_video_enqueue_goes_through_queue`).
- **Galeri video yükleme patlaması:** `renderGallery` her kartta
  `preload="metadata"` ile tüm dosyaları çekiordu (60 MB'lik videolar +
  her Range isteğinde tam dosya okuma) → headless Edge sayfada asılı
  kalıyordu; `preload="none"` + `_send_path` streaming (Range'de sadece
  istenen bayt). Panelde açılış süresi ~500 MB indirmeden kurtuldu.
- **State'e anahtar sızıntısı:** `state.jobs` içindeki `params`
  (hf/openai/elevenlabs anahtarları) `/api/state` yanıtından çıkarıldı.

Testler: suite **163/163** geçiyor.

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
