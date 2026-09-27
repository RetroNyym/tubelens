# TubeLens

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](requirements.txt)
[![Free queries](https://img.shields.io/badge/ücretsiz%20sorgu-5-brightgreen.svg)](#ücretsiz-plan-ve-lisans)

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
| `panel.py` | Standart kütüphane HTTP paneli (harici framework yok) |
| `cli.py` | `scan` / `report` / `panel` / `status` / `activate` / `deactivate` / `keygen` |
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

- [x] Ödeme entegrasyonu: LemonSqueezy License API ile uzaktan lisans doğrulama
- [ ] Webhook → GitHub Action ile satış kaydı (opsiyonel)
- [ ] Zaman serisi: skor takibi (`runs` geçmişinden trend grafiği)
- [ ] Rakip AI görünürlüğü karşılaştırma (aynı sorguda kim önde?)
- [ ] Toplu CSV dışa/içe aktarma ve planlı tarama (`cron`)
- [ ] Kanal bazlı affiliate boşluk raporu (hangi videoda hangi program eksik)

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
