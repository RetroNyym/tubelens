"""HTML rapor uretimi - tek dosya, harici bağımlılık yok."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import REPORT_DIR, ensure_dirs
from .shopping import action_recipe, channel_leak_summary, revenue_leak

CSS = """
:root{--bg:#0f1115;--card:#181b22;--line:#2a2f3a;--txt:#e6e8ee;--mut:#9aa3b2;
--ok:#2ecc71;--warn:#f1c40f;--bad:#e74c3c;--acc:#5b8cff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.6 "Segoe UI",Roboto,system-ui,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:26px;margin:0 0 6px} h2{font-size:19px;margin:34px 0 12px;
border-bottom:1px solid var(--line);padding-bottom:8px}
h3{font-size:16px;margin:18px 0 8px}
.sub{color:var(--mut);margin-bottom:24px;font-size:13px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.card .label{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.card .value{font-size:30px;font-weight:700;margin-top:6px}
.card .hint{font-size:12px;color:var(--mut);margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--card);
border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:14px}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line)}
th{background:#1e222b;color:var(--mut);font-weight:600;font-size:12px;
text-transform:uppercase;letter-spacing:.05em}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.b-ok{background:rgba(46,204,113,.15);color:var(--ok)}
.b-warn{background:rgba(241,196,15,.15);color:var(--warn)}
.b-bad{background:rgba(231,76,60,.15);color:var(--bad)}
.b-acc{background:rgba(91,140,255,.15);color:var(--acc)}
.bar{height:9px;background:#22262f;border-radius:6px;overflow:hidden;min-width:90px}
.bar>i{display:block;height:100%;border-radius:6px}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:13px}
.list{margin:0;padding-left:18px} .list li{margin:5px 0}
.note{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--acc);
border-radius:8px;padding:12px 14px;margin:12px 0;font-size:14px}
code{background:#22262f;padding:1px 6px;border-radius:5px;font-size:13px}
a{color:var(--acc)}
"""


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _bar(score: float, width: int = 120) -> str:
    score = max(0.0, min(100.0, float(score)))
    color = "var(--ok)" if score >= 70 else "var(--warn)" if score >= 40 else "var(--bad)"
    return (
        f'<div class="bar" style="width:{width}px">'
        f'<i style="width:{score}%;background:{color}"></i></div>'
    )


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge b-{kind}">{_esc(text)}</span>'


def build_report(data: dict[str, Any]) -> Path:
    """data: {channel, videos:[...shopping analyses...], ai:[...search checks...],
    summary:{...}, generated_at}"""
    ensure_dirs()
    s = data.get("summary", {})
    leak = data.get("leak") or channel_leak_summary(data.get("videos", []))
    rows_video = []
    for a in data.get("videos", []):
        aff = len(a.get("affiliate_links", []))
        miss = a.get("misses", [])
        vleak = revenue_leak({}, a)["leak"]
        rows_video.append(
            "<tr>"
            f'<td><a href="https://www.youtube.com/watch?v={_esc(a.get("video_id",""))}" target="_blank">'
            f'{_esc(a.get("title",""))[:70]}</a><br>'
            f'<span class="sub">{_esc(a.get("views",0))} izlenme</span></td>'
            f"<td>{_bar(a.get('opportunity_score',0))} "
            f"<b>{_esc(a.get('opportunity_score',0))}</b></td>"
            f"<td><b style=\"color:var(--bad)\">${_esc(vleak)}</b></td>"
            f"<td>{aff}</td>"
            f"<td>{_badge('var','ok') if a.get('disclosures') else _badge('yok','bad') if aff else _badge('-','warn')}</td>"
            f"<td>{len(a.get('shopping_tags') or [])}</td>"
            f'<td><ul class="list">' + "".join(f"<li>{_esc(m)}</li>" for m in miss[:3]) + "</ul></td>"
            "</tr>"
        )

    rows_ai = []
    for check in data.get("ai", []):
        eng_cells = []
        for e in check.get("engines", []):
            if not e.get("ok"):
                eng_cells.append(f"<td>{_badge('hata','bad')}</td>")
            elif e.get("found"):
                rank = e.get("rank", "?")
                ai = " +AI" if e.get("in_ai") else ""
                eng_cells.append(f"<td>{_badge(f'#{rank}{ai}', 'ok')}</td>")
            else:
                eng_cells.append(f"<td>{_badge('yok','warn')}</td>")
        rows_ai.append(
            "<tr>"
            f'<td class="mono">{_esc(check.get("query",""))}</td>'
            + "".join(eng_cells)
            + f"<td>{_bar(check.get('score',0),90)} <b>{_esc(check.get('score',0))}</b></td>"
            "</tr>"
        )

    ai_ok = sum(
        1 for c in data.get("ai", []) for e in c.get("engines", []) if e.get("ok") and e.get("found")
    )
    ai_total = sum(1 for c in data.get("ai", []) for e in c.get("engines", []) if e.get("ok"))
    in_ai = sum(
        1 for c in data.get("ai", []) for e in c.get("engines", []) if e.get("in_ai")
    )

    opportunities = []
    for a in data.get("videos", []):
        for m in a.get("misses", []):
            opportunities.append(f'<li><b>{_esc(a.get("title","")[:50])}</b> — {_esc(m)}</li>')

    recipe_blocks: list[str] = []
    for a in data.get("videos", []):
        recs = action_recipe({}, a)
        if not recs:
            continue
        items = []
        for r in recs:
            copy_html = ""
            if r.get("copy"):
                copy_html = (
                    '<pre class="mono" style="white-space:pre-wrap;background:#22262f;'
                    f'padding:8px;border-radius:6px">{_esc(r["copy"])}</pre>'
                )
            items.append(f'<li><b>{_esc(r["title"])}</b> — {_esc(r["text"])}{copy_html}</li>')
        recipe_blocks.append(
            f'<div class="note"><b>{_esc(a.get("title","")[:60])}</b>'
            f'<ul class="list">{"".join(items)}</ul></div>'
        )
    recipes_section = (
        "".join(recipe_blocks)[:6000]
        if recipe_blocks
        else '<div class="sub">Bütün eksikler kapatılmış — reçete yok.</div>'
    )

    generated = data.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M")

    html_doc = f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TubeLens Rapor — {_esc(data.get("channel",""))}</title>
<style>{CSS}</style></head><body><div class="wrap">

<h1>TubeLens Analiz Raporu</h1>
<div class="sub">Kanal: <b>{_esc(data.get("channel",""))}</b> · Üretilme: {_esc(generated)} ·
Videolar: {_esc(s.get("videos",0))}</div>

<h2>Özet</h2>
<div class="cards">
  <div class="card" style="border-color:var(--bad)"><div class="label">Tahmini Aylık Kaçak</div>
    <div class="value" style="color:var(--bad)">${_esc(leak.get("total_leak",0))}</div>
    <div class="hint">${_esc(leak.get("total_potential",0))} $ potansiyel · ${_esc(leak.get("videos_at_risk",0))} riskli video</div></div>
  <div class="card"><div class="label">Gelir Fırsat Skoru</div>
    <div class="value">{_esc(s.get("avg_score",0))}</div>
    <div class="hint">0-100 · affiliate + disclosure + shopping</div></div>
  <div class="card"><div class="label">Affiliate Link</div>
    <div class="value">{_esc(s.get("total_affiliate_links",0))}</div>
    <div class="hint">tüm videolarda toplam</div></div>
  <div class="card"><div class="label">Linki Olmayan</div>
    <div class="value">{_esc(s.get("videos_without_links",0))}</div>
    <div class="hint">hiç link içermeyen videolar</div></div>
  <div class="card"><div class="label">AI Görünürlük</div>
    <div class="value">{ai_ok}/{ai_total}</div>
    <div class="hint">{in_ai} sonuç AI özetinde yer alıyor</div></div>
</div>

<h2>Gelir Fırsatları (öncelikli)</h2>
<div class="note">Aşağıdaki maddeler para kaybına doğrudan bağlıdır. Her madde bir
gecelik düzeltme ile kapatılabilir; toplam etki aylık gelirde ölçülebilir artış sağlar.</div>
<ul class="list">{''.join(opportunities[:25]) or '<li>Büyük açık bulunamadı.</li>'}</ul>

<h2>Hazır Düzeltme Reçeteleri</h2>
<div class="note">Aşağıdaki metinler doğrudan panoya kopyalanabilir. Her reçete bir eksiği
kapatır; kapandıkça yukarıdaki $ kaçak azalır.</div>
{recipes_section}

<h2>Video Bazlı Affiliate / Shopping Analizi</h2>
<table><thead><tr>
<th>Video</th><th>Fırsat Skoru</th><th>$ Kaçak</th><th>Affiliate</th><th>Disclosure</th>
<th>Shopping</th><th>Eksikler</th>
</tr></thead><tbody>
{''.join(rows_video) or '<tr><td colspan="7">Veri yok</td></tr>'}
</tbody></table>

<h2>AI Arama Görünürlüğü</h2>
<div class="note">Video, hedef anahtar kelimelerde Google / YouTube / Bing / DuckDuckGo
sonuçlarında kaçıncı sırada? <b>+AI</b> işareti, sonucun AI özet kutusunda da
göründüğünü gösterir (2026'da trafik büyümesinin büyük kısmı buradan geliyor).</div>
<table><thead><tr>
<th>Anahtar Kelime</th><th>Google</th><th>YouTube</th><th>Bing</th><th>DDG</th><th>Skor</th>
</tr></thead><tbody>
{''.join(rows_ai) or '<tr><td colspan="6">Veri yok — <code>scan</code> komutunu çalıştırın</td></tr>'}
</tbody></table>

<h2>Sonraki Adımlar</h2>
<ul class="list">
<li>Affiliate linki olmayan videolara konuya uygun ortaklık linki + disclosure metni ekle.</li>
<li>Ürün geçen videolara YouTube Shopping etiketi ekle (Studio → Video → Shopping).</li>
<li>AI özetinde görünmeyen kelimeler için video açıklamasına 3-5 soru/cevap formatlı blok ekle.</li>
<li>Bu raporu haftalık <code>python -m tubelens scan</code> ile yenileyip skor takibi yap.</li>
</ul>

<div class="sub" style="margin-top:36px">TubeLens v0.1 · yerel analiz aracı</div>
</div></body></html>"""

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"report_{stamp}.html"
    out.write_text(html_doc, encoding="utf-8")
    latest = REPORT_DIR / "latest.html"
    latest.write_text(html_doc, encoding="utf-8")
    return out
