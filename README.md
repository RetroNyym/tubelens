# TubeLens

**YouTube AI arama görünürlüğü + affiliate gelir denetçisi.**
Tek komutla bir videonun ya da kanalın: yapay zekâ özetlerinde görünüp görünmediğini,
4 arama motorundaki sırasını, affiliate link / disclosure / YouTube Shopping eksiklerini
ve kaçırılan gelir fırsatlarını gösterir.

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
fırsat listesi üretilir.

---

## Kurulum

```bash
git clone https://github.com/RetroNyym/tubelens.git
cd tubelens
python -m venv .venv
.venv\Scripts\activate        # Windows — Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Gereksinim: **Python 3.11+**, internet erişimi. YouTube Data API anahtarı **gerekmez**.

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

# Yerel panel (tarayıcıda açılır)
python -m tubelens panel
```

- **CLI:** çıktı `reports/report_*.html` dosyasına yazılır.
- **Panel:** `http://127.0.0.1:8787` — formdan tarama başlatır, sonuçları tablo
  olarak gösterir, son HTML raporu `/report` adresinde açılır.
  Headless ortam için: `python -m tubelens panel --no-browser`.

---

## Ücretsiz plan ve lisans (Freemium)

| | Ücretsiz | Pro |
|---|---|---|
| Video / kanal tarama | ✅ sınırsız | ✅ sınırsız |
| Affiliate & shopping analizi | ✅ sınırsız | ✅ sınırsız |
| AI görünürlük sorgusu | **5 sorgu** | sınırsız |
| Rapor + panel | ✅ | ✅ |

- **1 sorgu = 1 anahtar kelime.** `--keywords a,b,c` 3 sorgu harcar.
  Kaç video taradığınız hak yakmaz.
- Kalan hak az ise sistem ilk N kelimeyle çalışır ve uyarır; hak bittiyse
  AI adımı kilitlenir, video/affiliate analizi çalışmaya devam eder.
- Durum ve kota: `python -m tubelens status`

```bash
# Pro'ya geçiş (anahtar satılır / ödemeden sonra verilir)
python -m tubelens activate TL1-xxxx-yyyy

# Satıcı için anahtar üretme (satın alma akışı entegre edilecek)
python -m tubelens keygen --days 365
```

Lisans anahtarı **HMAC-SHA256 imzalıdır ve çevrimdışı doğrulanır**; sunucu gerekmez.
Anahtar biçimi: `TL1-<base64 payload>-<imza>` (payload içinde süre sınırı taşır).
Kota sayaçları `data/quota.json` içinde tutulur ve kullanıcı tarafından sıfırlanabilir —
bu, hobi ölçeğinde caydırıcılık içindir; ödeme entegrasyonu (LemonSqueezy/Paddle
webhook doğrulaması) yol haritasındadır.

---

## Nasıl çalışıyor?

YouTube Data API kotası ve anahtarı olmadan çalışır. HTML'deki gömülü JSON
(`ytInitialPlayerResponse`, `ytInitialData`) ayrıştırılır:

| Modül | Görev |
|---|---|
| `youtube.py` | Video/kanal/arama scraping, AI özeti sinyalleri, `lockupViewModel` & `videoRenderer` desteği |
| `search.py` | Google / YouTube / Bing / DDG kontrolü + ağırlıklı skor |
| `shopping.py` | Affiliate, disclosure, shopping etiketi analizi + fırsat skoru |
| `quota.py` | Freemium kota + imzalı lisans anahtarı |
| `report.py` | Tek dosya HTML rapor (`reports/latest.html`) |
| `panel.py` | Standart kütüphane HTTP paneli (harici framework yok) |
| `cli.py` | `scan` / `report` / `panel` / `status` / `activate` / `keygen` |
| `storage.py` | `data/store.json` kayıt deposu (tarama geçmişi) |

İstekler kibar gecikmeli (`POLITE_DELAY = 0.8s`), tek bir User-Agent ile atılır.

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

- [ ] Ödeme entegrasyonu (LemonSqueezy / Paddle) + webhook ile lisans doğrulama
- [ ] Zaman serisi: skor takibi (`runs` geçmişinden trend grafiği)
- [ ] Rakip AI görünürlüğü karşılaştırma (aynı sorguda kim önde?)
- [ ] Toplu CSV dışa/içe aktarma ve planlı tarama (`cron`)
- [ ] Kanal bazlı affiliate boşluk raporu (hangi videoda hangi program eksik)

---

## Katkı

Issue ve PR açmak serbest. Kurulum sonrası `python -m tubelens status` ile
ortamın çalıştığını doğrulayın.

## Lisans

[MIT](LICENSE) — kod MIT, **lisans anahtarı üretimi ve dağıtımımı satıcıya aittir**.
