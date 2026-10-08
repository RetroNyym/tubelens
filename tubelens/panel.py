"""Yerel web paneli - standart kutuphane ile (127.0.0.1:8787).

Sekmeli arayuz: Tarama & Rapor | Video Uret | Durum & Lisans.
Sunucu kayitli veriyi gosterir, tarama/video uretimini arka planda tetikler.
"""

from __future__ import annotations

import base64
import json
import os
import re
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import brand, quota, shopping, storage
from .config import REPORT_DIR, ROOT, ensure_dirs

UPLOAD_DIR = ROOT / "uploads"
UPLOAD_MAX_FILES = 40
UPLOAD_MAX_BYTES = 25 * 1024 * 1024
UPLOAD_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_DIR = ROOT / "audio"
BGMDIR = ROOT / "bgm"
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
BG_MAX_FILES = 20
GALLERY_FILES = {"video.mp4", "video_no_subs.mp4", "subtitles.srt", "meta.json", "script.txt"}

CSS = """
:root{--bg:#0f1115;--card:#181b22;--line:#2a2f3a;--txt:#e6e8ee;--mut:#9aa3b2;
--ok:#2ecc71;--warn:#f1c40f;--bad:#e74c3c;--acc:#5b8cff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.6 "Segoe UI",system-ui,sans-serif}
header{border-bottom:1px solid var(--line);padding:16px 24px;display:flex;
justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
h1{font-size:19px;margin:0}
.wrap{max-width:1140px;margin:0 auto;padding:24px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.label{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.value{font-size:26px;font-weight:700;margin-top:6px}
.bar-row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;background:var(--card);
border:1px solid var(--line);border-radius:12px;padding:14px;margin:16px 0}
.fgroup{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:14px 16px 16px;margin:0 0 14px}
.fgroup.lime{border-left:3px solid var(--acc)}
.fgt{display:block;font-size:12px;font-weight:700;letter-spacing:.07em;
text-transform:uppercase;color:var(--acc);margin-bottom:10px}
.frow{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input,select,textarea{background:#11141a;border:1px solid var(--line);color:var(--txt);
border-radius:8px;padding:10px 12px;font-size:14px;min-width:200px;flex:1;font-family:inherit}
textarea{min-height:64px;resize:vertical}
input[type=checkbox]{min-width:0;flex:0;width:16px;height:16px;accent-color:var(--acc)}
.chk{display:inline-flex;gap:7px;align-items:center;background:#11141a;border:1px solid var(--line);
border-radius:8px;padding:9px 12px;font-size:13px;cursor:pointer;color:var(--txt)}
.chk input{width:15px;height:15px}
button{background:var(--acc);border:0;color:#fff;border-radius:8px;padding:11px 18px;
font-weight:600;cursor:pointer;font-size:14px}
button:hover{filter:brightness(1.1)}
button.sec{background:#232733;border:1px solid var(--line);color:var(--txt);padding:9px 13px}
button.danger{background:#7a2b22}
.pbtn{padding:7px 11px;font-size:13px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);
border-radius:12px;overflow:hidden;font-size:14px;margin-top:10px}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line)}
th{background:#1e222b;color:var(--mut);font-size:12px;text-transform:uppercase}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.ok{background:rgba(46,204,113,.15);color:var(--ok)}
.warn{background:rgba(241,196,15,.15);color:var(--warn)}
.bad{background:rgba(231,76,60,.15);color:var(--bad)}
.acc{background:rgba(91,140,255,.15);color:var(--acc)}
.bar{height:9px;background:#22262f;border-radius:6px;overflow:hidden;width:110px;display:inline-block;vertical-align:middle}
.bar>i{display:block;height:100%}
.sub{color:var(--mut);font-size:13px}
h2{font-size:17px;margin:24px 0 8px}
.log{background:#11141a;border:1px solid var(--line);border-radius:10px;padding:12px;
font-family:Consolas,monospace;font-size:13px;white-space:pre-wrap;max-height:260px;overflow:auto}
.empty{color:var(--mut);padding:24px;text-align:center;background:var(--card);
border:1px dashed var(--line);border-radius:12px}
a{color:var(--acc)}
.tabs{display:flex;gap:6px;margin:4px 0 0;border-bottom:1px solid var(--line);flex-wrap:wrap}
.tab{background:none;color:var(--mut);padding:12px 16px;border:1px solid transparent;
border-bottom:none;border-radius:10px 10px 0 0;cursor:pointer;font-weight:600;font-size:14px}
.tab.on{background:var(--card);color:var(--txt);border-color:var(--line);box-shadow:0 -2px 0 var(--acc) inset}
.tabpanel{display:none;padding-top:6px}
.tabpanel.on{display:block}
.hint{font-size:13px;color:var(--mut);margin:6px 0 0}
.brand{width:30px;height:30px;vertical-align:-7px;margin-right:10px;flex:none}
.provs{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.provs .badge{font-size:12.5px;padding:4px 10px}
.gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;margin-top:12px}
.gal .card{padding:12px}
.gal video{width:100%;border-radius:8px;background:#000;aspect-ratio:16/9}
.jobrow{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:9px 12px;
background:#1e222b;border:1px solid var(--line);border-radius:9px;margin-top:8px;font-size:13.5px}
body::after{content:"";position:fixed;inset:0;
background:RETRO_URI no-repeat center/contain;opacity:.07;pointer-events:none;z-index:0}
.wrap,header{position:relative;z-index:1}
footer{border-top:1px solid var(--line);margin-top:40px;padding:16px 24px;text-align:center;
color:var(--mut);font-size:13px;position:relative;z-index:1}
footer b{color:var(--txt)}
"""

PAGE = f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TubeLens Panel</title><link rel="icon" href="{brand.FAVICON}">
<style>{CSS.replace("RETRO_URI", brand.retro_css())}</style></head><body>
<header><h1>{brand.SVG.replace('<svg ', '<svg class="brand" ')}TubeLens — AI Görünürlük + Affiliate + Video Üretim Paneli</h1>
<span class="sub"><span id="kota" class="badge acc" style="margin-right:12px">kota: …</span><a href="/report" target="_blank">Son HTML rapor</a></span></header>
<div class="wrap">

<div class="tabs">
  <button class="tab on" data-tab="scan" onclick="switchTab('scan')">1 · Tarama &amp; Rapor</button>
  <button class="tab" data-tab="video" onclick="switchTab('video')">2 · Video Üret</button>
  <button class="tab" data-tab="modes" onclick="switchTab('modes')">3 · Klip &amp; Avatar</button>
  <button class="tab" data-tab="gallery" onclick="switchTab('gallery')">4 · Galeri &amp; Kuyruk</button>
  <button class="tab" data-tab="status" onclick="switchTab('status')">5 · Durum &amp; Lisans</button>
</div>

<section id="tab-scan" class="tabpanel on">
<form onsubmit="return startScan()">
  <div class="bar-row" style="margin-bottom:0">
    <input id="target" placeholder="Video URL, video ID veya @kanal" required>
    <input id="keywords" placeholder="Anahtar kelimeler (virgülle) — opsiyonel">
    <select id="limit"><option value="5">5 video</option><option value="10" selected>10 video</option>
    <option value="20">20 video</option></select>
    <button type="submit">Tarama Başlat</button>
  </div>
</form>
<div class="fgroup" style="margin-top:12px">
  <span class="fgt">Klon ayarları — ▶ Klonla bu ayarlarla çalışır</span>
  <div class="frow">
    <select id="cllang"><option value="tr" selected>Türkçe</option><option value="en">English</option>
      <option value="de">Deutsch</option><option value="fr">Français</option><option value="es">Español</option>
      <option value="ar">Arabic</option><option value="ru">Russian</option></select>
    <select id="claspect"><option value="9:16" selected>9:16 dikey</option>
      <option value="16:9">16:9 yatay</option><option value="1:1">1:1 kare</option>
      <option value="4:3">4:3</option><option value="3:4">3:4</option></select>
    <select id="cldur"><option value="0" selected>Süre: kaynaktan al</option>
      <option value="30">30 sn</option><option value="45">45 sn</option>
      <option value="60">60 sn</option><option value="90">90 sn</option></select>
  </div>
</div>
<div class="log" id="log">Tarama bekleniyor…</div>
<div class="empty" id="lock" style="display:none;margin-top:10px">
  <b>Ücretsiz sorgu hakkınız doldu.</b> AI görünürlük kontrolü kilitlendi —
  video/affiliate analizi çalışmaya devam eder.<br>
  <code>python -m tubelens status</code> ·
  <code>python -m tubelens activate &lt;ANAHTAR&gt;</code>
</div>
<h2>Özet</h2>
<div class="cards" id="cards"></div>
<h2>Videolar</h2>
<div id="videos"><div class="empty">Kayıtlı video yok. Yukarıdan bir hedef tarayın.</div></div>
<h2>AI Görünürlük Kontrolleri</h2>
<div id="ai"><div class="empty">Kayıtlı AI kontrolü yok.</div></div>
</section>

<section id="tab-video" class="tabpanel">
<h2>Video Üret <span class="sub">senaryo → görüntü → ses → altyazı → MP4</span></h2>
<p class="hint">Kaynak zinciri: lokal klasör → Pexels → Pixabay → <b>web görsel araması (anahtarsız, Bing/Openverse/Wikimedia)</b> →
AI video LTX (opsiyonel) → <b>anahtarsız AI görsel + Ken Burns</b>. HF token'lı görseller FLUX ile üretilir.
Ses: Edge TTS / gTTS anahtarsız; OpenAI / ElevenLabs API anahtarlı.</p>
<div id="clonecard"></div>
<form onsubmit="return startVideo()">
  <div class="fgroup lime">
    <span class="fgt">Konu &amp; Format</span>
    <div class="frow" style="margin-bottom:10px">
      <input id="vtopic" placeholder="Video konusu (örn. Sabah koşusunun 7 faydası)" required style="min-width:100%">
    </div>
    <div class="frow">
      <select id="vaspect"><option value="9:16" selected>9:16 dikey (Shorts/TikTok)</option>
        <option value="16:9">16:9 yatay (YouTube)</option><option value="1:1">1:1 kare</option>
        <option value="4:3">4:3</option><option value="3:4">3:4</option></select>
      <select id="vduration" onchange="toggleCustomDur()"><option value="30">30 sn</option>
        <option value="45" selected>45 sn</option><option value="60">60 sn</option>
        <option value="90">90 sn</option><option value="custom">Özel süre…</option></select>
      <input id="vdurcustom" type="number" min="10" max="600" value="45" placeholder="Özel süre (sn)"
        style="display:none;max-width:150px">
      <select id="vres"><option value="1080" selected>1080p</option><option value="720">720p</option></select>
      <select id="vlang"><option value="tr" selected>Türkçe</option><option value="en">English</option>
        <option value="de">Deutsch</option><option value="fr">Français</option><option value="es">Español</option>
        <option value="ar">Arabic</option><option value="ru">Russian</option></select>
      <select id="vpreset"><option value="" selected>Stil: —</option>
        <option value="sinematik">Sinematik</option><option value="anime">Anime</option>
        <option value="2d">2D Animasyon</option><option value="3d">3D Pixar</option>
        <option value="minimal">Minimal</option><option value="belgesel">Belgesel</option></select>
      <input id="vstyle" placeholder="Ton (ops.) — belgesel, hızlı, eğlenceli">
      <input id="vclips" type="number" min="0" max="20" value="0" placeholder="Klip sayısı (0=oto)" style="max-width:170px">
    </div>
  </div>
  <div class="fgroup">
    <span class="fgt">Görsel Kaynakları</span>
    <div class="frow" style="margin-bottom:10px">
      <input id="vfootage" placeholder="Görüntü klasörü (ops., en öncelikli)">
      <span class="sub" style="display:flex;gap:8px;align-items:center">
        <button type="button" id="vupbtn" class="sec" style="padding:9px 14px">PC'den foto ekle</button>
        <input type="file" id="vup" multiple accept="image/*,.jpg,.jpeg,.png,.webp" style="display:none">
      </span>
      <input id="vpexels" placeholder="Pexels API anahtarı (ops., ücretsiz)">
      <input id="vpixabay" placeholder="Pixabay API anahtarı (ops., ücretsiz)">
    </div>
    <div class="frow">
      <label class="chk"><input type="checkbox" id="vai" checked> AI görsel fallback (anahtarsız)</label>
      <label class="chk"><input type="checkbox" id="vwebimg" checked> Web görsel araması — alakalı fotoğraf (anahtarsız)</label>
      <label class="chk"><input type="checkbox" id="vltx"> AI video LTX — metinden gerçek video (anahtarsız, yavaş)</label>
      <input id="vhf" placeholder="Hugging Face token (ops., ücretsiz — senaryo + görsel + LTX kotası)" style="max-width:330px">
    </div>
    <div class="provs" id="provvideo"></div>
  </div>
  <div class="fgroup">
    <span class="fgt">Ses &amp; Altyazı</span>
    <div class="frow" style="margin-bottom:10px">
      <select id="vtts">
        <option value="edge" selected>Edge TTS — anahtarsız (öneri)</option>
        <option value="gtts">Google gTTS — anahtarsız</option>
        <option value="openai">OpenAI TTS — API anahtarı</option>
        <option value="elevenlabs">ElevenLabs — API anahtarı</option>
      </select>
      <input id="vvoice" placeholder="Ses adı (ops.) — Edge: tr-TR-EmelNeural · OpenAI: alloy">
      <input id="vttsmodel" placeholder="OpenAI TTS modeli (ops., gpt-4o-mini-tts)" style="max-width:260px">
      <input id="vopenai" placeholder="OpenAI API anahtarı (ops., kaydedilir)">
      <input id="veleven" placeholder="ElevenLabs API anahtarı (ops., kaydedilir)">
    </div>
    <div class="frow">
      <select id="vbgm" style="max-width:260px"><option value="">Arka plan müziği: yok</option></select>
      <button type="button" id="vbgmup" class="sec" style="padding:9px 14px">Müzik yükle (mp3)</button>
      <input type="file" id="vbgmin" accept="audio/*,.mp3,.wav,.m4a,.ogg" style="display:none">
      <input id="vbgmvol" type="number" min="0" max="1" step="0.01" value="0.12" placeholder="Müzik sesi 0–1" style="max-width:160px">
      <label class="chk"><input type="checkbox" id="vsubs" checked> Altyazı üret + videoya yak</label>
    </div>
  </div>
  <div class="frow">
    <label class="chk"><input type="checkbox" id="vlogo" checked> Videoya TubeLens filigranı + imza</label>
    <button type="submit">Video Üret</button>
    <span class="sub">Üretim kuyruğa girer — aynı anda 2 iş çalışır, durumu 4 · Galeri sekmesinde izle.</span>
  </div>
</form>
<div id="uplist" class="sub" style="margin:-4px 0 12px"></div>
<p class="hint" style="margin:-4px 0 10px">Altyazı açıkken her üretimde <b>iki dosya</b> üretilir:
  <b>video.mp4</b> (altyazılı) + <b>video_no_subs.mp4</b> (altyazısız) —
  üretim bitince “Son üretim” kartında iki ayrı indirme butonu belirir.</p>
<div class="log" id="vlog">Video üretimi bekleniyor…</div>
<div id="vresult"></div>
</section>

<section id="tab-modes" class="tabpanel">
<h2>Klip &amp; Avatar <span class="sub">hızlı üretim modları — senaryo yok, tek komut</span></h2>
<form onsubmit="return startKlip()">
  <div class="fgroup lime">
    <span class="fgt">Metinden Klip — 3–15 sn, anlatımsız</span>
    <div class="frow" style="margin-bottom:10px">
      <input id="kprompt" placeholder="Klip fikri (örn. drone ile gün doğumu, sinematik)" required style="min-width:100%">
    </div>
    <div class="frow">
      <select id="kaspect"><option value="16:9" selected>16:9</option><option value="9:16">9:16</option>
        <option value="1:1">1:1</option><option value="4:3">4:3</option><option value="3:4">3:4</option></select>
      <select id="kdur"><option value="3">3 sn</option><option value="4" selected>4 sn</option>
        <option value="6">6 sn</option><option value="8">8 sn</option><option value="12">12 sn</option></select>
      <select id="kprov"><option value="auto" selected>Sağlayıcı: otomatik</option>
        <option value="ltx">LTX (HF Spaces)</option><option value="pollinations">Pollinations video</option>
        <option value="viggle">Viggle (anahtar)</option><option value="higgsfield">Higgsfield (anahtar)</option></select>
      <input id="kstyle" placeholder="Stil eki (ops.) — sinematik, gece">
      <button type="submit">Klip Üret</button>
    </div>
    <div class="provs" id="provklip"></div>
  </div>
</form>
<div class="log" id="klog">Klip bekleniyor…</div>
<div id="kresult"></div>
<form onsubmit="return startAvatar()">
  <div class="fgroup lime">
    <span class="fgt">Konuşma Avatarı — görsel + ses → dudak senkron video</span>
    <div class="frow" style="margin-bottom:10px">
      <select id="aimg" style="max-width:300px"><option value="">Yüklü görsel seç…</option></select>
      <button type="button" id="aupbtn" class="sec" style="padding:9px 14px">Görsel yükle</button>
      <input type="file" id="aup" accept="image/*,.jpg,.jpeg,.png,.webp" style="display:none">
      <select id="aaudio" style="max-width:300px"><option value="">Ses dosyası seç… (ops.)</option></select>
      <button type="button" id="aaudioupbtn" class="sec" style="padding:9px 14px">Ses yükle</button>
      <input type="file" id="aaudioup" accept="audio/*,.mp3,.wav,.m4a,.ogg" style="display:none">
    </div>
    <div class="frow" style="margin-bottom:10px">
      <textarea id="atext" placeholder="Seslendirilecek metin — ses dosyası yoksa buradan Edge TTS ile üretilir" style="min-width:100%"></textarea>
    </div>
    <div class="frow">
      <select id="alang"><option value="tr" selected>Türkçe</option><option value="en">English</option>
        <option value="de">Deutsch</option><option value="fr">Français</option><option value="es">Español</option></select>
      <select id="atts"><option value="edge" selected>Edge TTS (anahtarsız)</option>
        <option value="gtts">gTTS (anahtarsız)</option><option value="openai">OpenAI TTS</option>
        <option value="elevenlabs">ElevenLabs</option></select>
      <input id="avoice" placeholder="Ses adı (ops.)">
      <select id="aprovider"><option value="auto" selected>Sağlayıcı: otomatik</option>
        <option value="latentsync">LatentSync (HF)</option><option value="hedra">Hedra (anahtar)</option>
        <option value="viggle">Viggle (anahtar)</option></select>
      <button type="submit">Avatar Üret</button>
    </div>
    <div class="provs" id="provavatar"></div>
  </div>
</form>
<div class="log" id="alog2">Avatar bekleniyor…</div>
<div id="aresult"></div>
<p class="hint">Sağlayıcı sırası (otomatik): <b>LatentSync</b> (HF, anahtarsız kota) → <b>Hedra</b> (HEDRA_API_KEY) →
<b>Viggle</b> (VIGGLE_API_KEY). HF token'ı Video Üret sekmesinden kaydedebilirsin.</p>
</section>

<section id="tab-gallery" class="tabpanel">
<h2>Galeri &amp; Kuyruk <span class="sub">üretilen her şey: video · klip · avatar</span></h2>
<div class="fgroup">
  <span class="fgt">İş kuyruğu <span class="sub" id="jobcount" style="text-transform:none;letter-spacing:0"></span></span>
  <div id="jobs"><div class="empty">Kuyruk boş.</div></div>
</div>
<div id="gallery"><div class="empty">Henüz üretim yok. Video / Klip / Avatar sekmelerinden başlat.</div></div>
</section>

<section id="tab-status" class="tabpanel">
<h2>Durum &amp; Lisans</h2>
<div class="cards" id="statuscards"></div>
<form onsubmit="return activate()">
  <div class="bar-row">
    <input id="akey" placeholder="Lisans anahtarı (TL1-… veya LemonSqueezy ürün anahtarı)" required>
    <button type="submit">Aktive Et</button>
    <button type="button" class="danger" onclick="deactivate()">Kaldır (deactivate)</button>
    <button type="button" class="sec" onclick="rebuildReport()">Raporu yeniden oluştur</button>
  </div>
</form>
<div class="fgroup">
  <span class="fgt">Lisans detayı</span>
  <div class="log" id="licdetail" style="max-height:170px">Yükleniyor…</div>
</div>
<div class="fgroup">
  <span class="fgt">İşlem günlüğü</span>
  <div class="log" id="actlog" style="max-height:130px">Aktivasyon bekleniyor…</div>
</div>
<div class="fgroup">
  <span class="fgt">Sağlayıcılar</span>
  <div class="provs" id="provstatus"></div>
  <p class="hint">Anahtarlar: Pexels/Pixabay/OpenAI/ElevenLabs/HF Video Üret sekmesinde kaydedilir;
  Viggle/Higgsfield/Hedra ortam değişkenleriyle (<code>VIGGLE_API_KEY</code> · <code>HIGGSFIELD_API_KEY</code> · <code>HEDRA_API_KEY</code>).</p>
</div>
<p class="hint">CLI: <code>python -m tubelens status</code> ·
<code>python -m tubelens activate &lt;ANAHTAR&gt;</code> ·
<code>python -m tubelens deactivate</code> ·
Video CLI: <code>python -m tubelens video &lt;KONU&gt; --tts-engine edge|gtts|openai|elevenlabs</code> ·
<code>klip</code> · <code>avatar</code></p>
</section>

</div>
<script>
let timer=null;
let vtimer=null;
let vticks=0;
let vCache=0;
let vKey='';
let ctimer=null;
let cloneApplied='';
let ktimer=null;
let atimer=null;
function switchTab(name){{
  document.querySelectorAll('.tab').forEach(function(b){{
    b.classList.toggle('on', b.dataset.tab===name);
  }});
  document.querySelectorAll('.tabpanel').forEach(function(s){{
    s.classList.toggle('on', s.id==='tab-'+name);
  }});
  history.replaceState(null,'','#'+name);
}}
function initTab(){{
  const h=(location.hash||'').replace('#','');
  if(h && document.getElementById('tab-'+h)) switchTab(h);
}}
window.addEventListener('load', initTab);
async function startScan(){{
  const target=document.getElementById('target').value.trim();
  const keywords=document.getElementById('keywords').value.trim();
  const limit=document.getElementById('limit').value;
  if(!target) return false;
  document.getElementById('log').textContent='Tarama başladı…';
  const r=await fetch('/api/scan',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{target,keywords,limit}})}});
  const j=await r.json();
  if(!j.ok){{document.getElementById('log').textContent='Hata: '+j.error;return false;}}
  if(timer) clearInterval(timer);
  timer=setInterval(poll,1200); poll();
  return false;
}}
async function cloneVideo(vid){{
  const lg=document.getElementById('log');
  lg.textContent='Klonlanıyor: '+vid+' (transkript + yapı analizi)…';
  const cs={{lang:document.getElementById('cllang').value,
    aspect:document.getElementById('claspect').value,
    duration:parseInt(document.getElementById('cldur').value,10)||0}};
  const r=await fetch('/api/clone',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{url:vid,lang:cs.lang,aspect:cs.aspect,duration:cs.duration}})}});
  const j=await r.json();
  if(!j.ok){{lg.textContent='Hata: '+j.error;return;}}
  switchTab('video'); poll();
}}
function renderClone(j){{
  const c=j.clone||{{}};
  const card=document.getElementById('clonecard');
  if(!card) return;
  if(c.busy){{
    card.innerHTML='<div class="card" style="border-left:3px solid var(--acc)"><b>Klonlanıyor…</b> '+
      '<span class="sub">'+((c.log||'').slice(-160))+'</span></div>';
    return;
  }}
  const d=c.draft;
  if(!d||!d.script||!d.script.script){{card.innerHTML=''; return;}}
  if(cloneApplied!==d.created_at){{
    cloneApplied=d.created_at;
    document.getElementById('vtopic').value=d.script.title||'';
    const asp=document.getElementById('vaspect');
    if(Array.from(asp.options).some(o=>o.value===(d.aspect||'9:16'))) asp.value=d.aspect||'9:16';
    const dur=document.getElementById('vduration');
    const dv=String(d.duration||45);
    if(Array.from(dur.options).some(o=>o.value===dv)){{
      dur.value=dv; document.getElementById('vdurcustom').style.display='none';
    }}else{{
      dur.value='custom';
      document.getElementById('vdurcustom').style.display='';
      document.getElementById('vdurcustom').value=dv;
    }}
    document.getElementById('vstyle').value='';
  }}
  const words=(d.script.script||'').split(/\\s+/).length;
  card.innerHTML='<div class="card" style="border-left:3px solid var(--ok);margin-bottom:12px">'+
    '<div class="label">Klon taslağı hazır — özgün açıyla</div>'+
    '<div style="margin-top:6px"><b>'+(d.script.title||'—')+'</b> <span class="sub">'+words+' kelime · '+
    (d.duration||45)+' sn · '+(d.aspect||'9:16')+'</span></div>'+
    '<div class="sub">Kaynak: '+((d.source&&d.source.title||'').slice(0,70))+' · '+
    ((d.source&&d.source.views)||0)+' izlenme</div>'+
    '<div class="sub">Form dolduruldu. <b>Video Üret</b>e bas — senaryo dosyadan okunur, LLM tekrar çalışmaz.</div>'+
    '</div>';
}}
async function copyText(id){{
  const el=document.getElementById(id);
  if(!el) return;
  try{{ await navigator.clipboard.writeText(el.value); }}catch(e){{ el.select(); document.execCommand('copy'); }}
  const btn=document.getElementById('btn-'+id);
  if(btn){{ const t=btn.textContent; btn.textContent='Kopyalandı ✓'; setTimeout(function(){{btn.textContent=t;}},1400); }}
}}
function toggleRecipe(i){{
  const row=document.getElementById('rec'+i);
  if(!row) return;
  row.style.display=(row.style.display==='none')?'':'none';
}}
function toggleCustomDur(){{
  const s=document.getElementById('vduration');
  const c=document.getElementById('vdurcustom');
  c.style.display=(s.value==='custom')?'':'none';
}}
function videoDuration(){{
  const s=document.getElementById('vduration');
  if(s.value==='custom'){{
    const v=parseInt(document.getElementById('vdurcustom').value,10);
    return (v>=10&&v<=600)?v:45;
  }}
  return parseInt(s.value,10);
}}
async function startVideo(){{
  const topic=document.getElementById('vtopic').value.trim();
  if(!topic) return false;
  const payload={{topic,
    lang:document.getElementById('vlang').value,
    duration:videoDuration(),
    aspect:document.getElementById('vaspect').value,
    resolution:parseInt(document.getElementById('vres').value,10),
    style:document.getElementById('vstyle').value.trim(),
    preset:document.getElementById('vpreset').value,
    clips:parseInt(document.getElementById('vclips').value,10)||0,
    footage_dir:document.getElementById('vfootage').value.trim(),
    pexels_key:document.getElementById('vpexels').value.trim(),
    pixabay_key:document.getElementById('vpixabay').value.trim(),
    ai_visuals:document.getElementById('vai').checked,
    web_images:document.getElementById('vwebimg').checked,
    ltx_video:document.getElementById('vltx').checked,
    hf_token:document.getElementById('vhf').value.trim(),
    tts_engine:document.getElementById('vtts').value,
    tts_model:document.getElementById('vttsmodel').value.trim(),
    voice:document.getElementById('vvoice').value.trim(),
    openai_key:document.getElementById('vopenai').value.trim(),
    elevenlabs_key:document.getElementById('veleven').value.trim(),
    bgm:document.getElementById('vbgm').value,
    bgm_volume:parseFloat(document.getElementById('vbgmvol').value),
    subs:document.getElementById('vsubs').checked,
    logo:document.getElementById('vlogo').checked,
    script_file:cloneApplied?'clone_draft.json':''}};
  document.getElementById('vlog').textContent='Video üretimi kuyruğa alındı…';
  document.getElementById('vresult').innerHTML='';
  const r=await fetch('/api/video',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify(payload)}});
  const j=await r.json();
  if(!j.ok){{document.getElementById('vlog').textContent='Hata: '+j.error;return false;}}
  if(vtimer) clearInterval(vtimer);
  vticks=0;
  vtimer=setInterval(poll,1500); poll();
  return false;
}}
async function startKlip(){{
  const prompt=document.getElementById('kprompt').value.trim();
  if(!prompt) return false;
  document.getElementById('klog').textContent='Klip kuyruğa alındı…';
  document.getElementById('kresult').innerHTML='';
  const r=await fetch('/api/klip',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{prompt,
      aspect:document.getElementById('kaspect').value,
      duration:parseFloat(document.getElementById('kdur').value),
      provider:document.getElementById('kprov').value,
      style:document.getElementById('kstyle').value.trim()}})}});
  const j=await r.json();
  if(!j.ok){{document.getElementById('klog').textContent='Hata: '+j.error;return false;}}
  if(!ktimer) ktimer=setInterval(poll,1500); poll();
  return false;
}}
async function startAvatar(){{
  const image=document.getElementById('aimg').value;
  const text=document.getElementById('atext').value.trim();
  const audio=document.getElementById('aaudio').value;
  if(!image){{document.getElementById('alog2').textContent='Önce görsel yükle veya seç.';return false;}}
  if(!text&&!audio){{document.getElementById('alog2').textContent='Ses dosyası seç veya metin yaz.';return false;}}
  document.getElementById('alog2').textContent='Avatar kuyruğa alındı…';
  document.getElementById('aresult').innerHTML='';
  const r=await fetch('/api/avatar',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{image,audio,text,
      lang:document.getElementById('alang').value,
      tts_engine:document.getElementById('atts').value,
      voice:document.getElementById('avoice').value.trim(),
      provider:document.getElementById('aprovider').value}})}});
  const j=await r.json();
  if(!j.ok){{document.getElementById('alog2').textContent='Hata: '+j.error;return false;}}
  if(!atimer) atimer=setInterval(poll,1500); poll();
  return false;
}}
async function deactivate(){{
  document.getElementById('actlog').textContent='Lisans kaldırılıyor…';
  const r=await fetch('/api/deactivate',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});
  const j=await r.json();
  document.getElementById('actlog').textContent=(j.ok?'OK: ':'Hata: ')+(j.message||j.error||'');
  poll();
}}
async function rebuildReport(){{
  document.getElementById('actlog').textContent='HTML rapor yeniden üretiliyor…';
  const r=await fetch('/api/report',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});
  const j=await r.json();
  document.getElementById('actlog').textContent=(j.ok?'OK: ':'Hata: ')+(j.message||j.error||'');
  poll();
}}
async function activate(){{
  const key=document.getElementById('akey').value.trim();
  if(!key) return false;
  document.getElementById('actlog').textContent='Aktivasyon denendi…';
  const r=await fetch('/api/activate',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{key}})}});
  const j=await r.json();
  document.getElementById('actlog').textContent=(j.ok?'OK: ':'Hata: ')+(j.message||j.error||'');
  poll();
  return false;
}}
async function poll(){{
  const r=await fetch('/api/state'); const j=await r.json();
  render(j);
}}
function renderVideo(j){{
  const v=j.video||{{}};
  const lg=document.getElementById('vlog');
  if(lg && v.log) lg.textContent=v.log;
  const box=document.getElementById('vresult');
  if(!box) return;
  const res=v.result;
  if(!res){{box.innerHTML=''; return;}}
  if(!res.ok){{
    box.innerHTML='<div class="empty" style="color:var(--bad);margin-top:10px"><b>Video üretilemedi:</b> '+
      ((res.error||'bilinmeyen hata').slice(-500))+'</div>';
    return;
  }}
  const key=res.key||res.dir||'';
  if(key!==vKey){{vKey=key; vCache=Date.now();}}
  const url='/api/video/latest'+(vCache?('?t='+vCache):'');
  const dlBlue='display:inline-block;padding:10px 16px;border-radius:8px;font-weight:700;text-decoration:none;color:#fff;background:var(--acc);margin:6px 6px 0 0';
  const dlGreen='display:inline-block;padding:10px 16px;border-radius:8px;font-weight:700;text-decoration:none;color:#fff;background:#1f9c58;margin:6px 6px 0 0';
  const media=res.video
    ? '<div><video controls preload="metadata" width="210" src="'+url+'"></video>'+
      '<div class="sub" style="margin-top:4px">Oynatıcıda ALTYAZILI kopya oynuyor</div></div>'
    : '<span class="badge ok">senaryo hazır</span>';
  box.innerHTML='<div class="card" style="margin-top:10px"><div class="label">Son üretim — '+
    (res.engine?((res.engine)+('' + (res.engine==='edge'||res.engine==='gtts'?' (anahtarsız)':' (API)'))):'')+'</div>'+
    '<div style="margin-top:6px"><b>'+(res.title||'—')+'</b> <span class="sub">'+(res.duration||0)+' sn</span>'+
    (res.video&&res.video_no_subs?' <span class="badge ok">altyazılı + altyazısız hazır</span>':'')+'</div>'+
    '<div style="margin-top:6px;display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap">'+media+
    '<div>'+(res.video?'<a href="'+url+'" download="video.mp4" style="'+dlBlue+'">⬇ video.mp4 — ALTYAZILI</a>':'')+
    (res.video_no_subs?'<a href="/api/video/nosubs" download="video_no_subs.mp4" style="'+dlGreen+'">⬇ video_no_subs.mp4 — ALTYAZISIZ</a>':'')+
    (res.video?'<a href="/api/video/srt" download="subtitles.srt" style="'+dlBlue+'">subtitles.srt</a>':'')+
    '<div style="margin-top:8px"><code>'+res.dir+'</code></div></div></div></div>';
}}
function bar(v){{
  const c=v>=70?'var(--ok)':v>=40?'var(--warn)':'var(--bad)';
  return `<span class="bar"><i style="width:${{v}}%;background:${{c}}"></i></span> <b>${{v}}</b>`;
}}
function render(j){{
  const s=j.summary||{{}};
  const k=document.getElementById('kota');
  if(k) k.textContent=j.quota||'kota: —';
  const lock=document.getElementById('lock');
  if(lock) lock.style.display=(!j.licensed && (j.quota||'').indexOf('0/')>-1)?'block':'none';
  const sc=document.getElementById('statuscards');
  if(sc){{
    const jobs=j.jobs||[];
    const pend=jobs.filter(x=>x.status==='pending'||x.status==='running').length;
    sc.innerHTML=`
     <div class="card"><div class="label">Kota</div><div class="value" style="font-size:18px">${{j.quota||'—'}}</div></div>
     <div class="card"><div class="label">Lisans</div><div class="value" style="font-size:18px">${{j.licensed?'PRO':'Ücretsiz'}}</div></div>
     <div class="card"><div class="label">Video üretimi</div><div class="value" style="font-size:18px">${{j.video&&j.video.busy?'çalışıyor':(j.video&&j.video.result&&j.video.result.ok?'son üretim hazır':'bekliyor')}}</div></div>
     <div class="card"><div class="label">Kuyruk</div><div class="value" style="font-size:18px">${{pend?pend+' iş':'boş'}}</div></div>
     <div class="card"><div class="label">Panel</div><div class="value" style="font-size:18px">127.0.0.1:8787</div></div>`;
  }}
  renderLic(j); renderProviders(j); renderJobs(j); renderGallery(j); renderModes(j);
  const lk=j.leak||{{}};
  document.getElementById('cards').innerHTML=`
   <div class="card" style="border-color:var(--bad)"><div class="label">Tahmini Aylık Kaçak</div>
    <div class="value" style="color:var(--bad)">${{lk.total_leak?('$'+lk.total_leak):'$0'}}</div>
    <div class="hint">${{lk.total_potential?('$'+lk.total_potential+' potansiyel · '):''}}${{lk.videos_at_risk||0}} riskli video</div></div>
   <div class="card"><div class="label">Fırsat Skoru</div><div class="value">${{s.avg_score??0}}</div></div>
   <div class="card"><div class="label">Video</div><div class="value">${{s.videos??0}}</div></div>
   <div class="card"><div class="label">Affiliate Link</div><div class="value">${{s.total_affiliate_links??0}}</div></div>
   <div class="card"><div class="label">Linki Olmayan</div><div class="value">${{s.videos_without_links??0}}</div></div>`;
  if(j.videos && j.videos.length){{
    document.getElementById('videos').innerHTML=`<table><tr><th>Video</th><th>Skor</th><th>$ Kaçak</th><th>Affil.</th>
     <th>Disclosure</th><th>Shopping</th><th></th></tr>`+
     j.videos.map((v,i)=>{{
       const rec=v.recipes||[];
       let recRow='';
       if(rec.length){{
         recRow='<tr id="rec'+i+'" style="display:none"><td colspan="7"><div style="padding:6px 0">'+
           rec.map(r=>'<div style="margin:8px 0;padding:10px;background:#1e222b;border-radius:8px">'+
             '<b>'+r.title+'</b><div class="sub" style="white-space:pre-line;margin-top:4px">'+r.text+'</div>'+
             (r.copy?'<div style="margin-top:8px"><textarea readonly id="copy'+i+'-'+r.id+'" style="width:100%;height:64px;font-size:12px;background:#14161c;color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:6px">'+r.copy+'</textarea>'+
               '<button id="btn-copy'+i+'-'+r.id+'" data-copy="copy'+i+'-'+r.id+'" onclick="copyText(this.dataset.copy)" style="margin-top:6px">Panoya kopyala</button></div>':'')+
           '</div>').join('')+'</div></td></tr>';
       }}
       const leak=v.leak>0?'<b style="color:var(--bad)">$'+v.leak+'</b>':'<span class="sub">$0</span>';
       return '<tr><td><a href="https://www.youtube.com/watch?v='+v.video_id+'" target="_blank">'+(v.title||'').slice(0,60)+'</a>'+
         '<div class="sub">'+(v.views||0)+' izlenme '+
         '<button data-vid="'+v.video_id+'" onclick="cloneVideo(this.dataset.vid)" title="Bu videonun yapısını klonla → özgün senaryo" style="margin-left:8px">▶ Klonla</button></div></td>'+
         '<td>'+bar(v.opportunity_score)+'</td>'+
         '<td>'+leak+'</td>'+
         '<td>'+(v.affili||[]).length+'</td>'+
         '<td>'+(v.disc?'<span class="badge ok">var</span>':(v.affili&&v.affili.length?'<span class="badge bad">yok</span>':'<span class="badge warn">-</span>'))+'</td>'+
         '<td>'+(v.shop||0)+'</td>'+
         '<td>'+(rec.length?'<button onclick="toggleRecipe('+i+')">Düzelt ▾</button>':'')+'</td></tr>'+recRow;
     }}).join('')+`</table>`;
  }}
  if(j.ai && j.ai.length){{
    document.getElementById('ai').innerHTML=`<table><tr><th>Sorgu</th><th>Google</th><th>YouTube</th>
      <th>Bing</th><th>DDG</th><th>Skor</th></tr>`+
      j.ai.map(c=>`<tr><td class="sub">${{(c.query||'').slice(0,50)}}</td>`+
        c.engines.map(e=>`<td>${{e.ok?(e.found?'<span class="badge ok">#'+e.rank+(e.in_ai?'+AI':'')+'</span>':'<span class="badge warn">yok</span>'):'<span class="badge bad">hata</span>'}}</td>`).join('')+
        `<td>${{bar(c.score)}}</td></tr>`).join('')+`</table>`;
  }}
  const lg=document.getElementById('log');
  if(lg && j.log) lg.textContent=j.log;
  const al=document.getElementById('actlog');
  if(al && j.activate_log) al.textContent=j.activate_log;
  renderVideo(j);
  renderClone(j);
  if(j.clone && !j.clone.busy && j.clone.draft && ctimer){{
    clearInterval(ctimer); ctimer=null;
  }}
  if(j.video&&j.video.result&&!j.video.busy&&vtimer){{
    clearInterval(vtimer); vtimer=null;
  }}
  if(vtimer){{
    vticks++;
    if(vticks>800){{clearInterval(vtimer); vtimer=null;}}
  }}
  const jobs=j.jobs||[];
  if(ktimer && !jobs.some(x=>x.kind==='klip'&&(x.status==='pending'||x.status==='running'))){{
    clearInterval(ktimer); ktimer=null;
  }}
  if(atimer && !jobs.some(x=>x.kind==='avatar'&&(x.status==='pending'||x.status==='running'))){{
    clearInterval(atimer); atimer=null;
  }}
  if(j.busy===false && timer && j.finished){{
    clearInterval(timer); timer=null;
  }}
}}
function renderLic(j){{
  const el=document.getElementById('licdetail');
  if(el) el.textContent=j.license_text||'—';
}}
function provBadge(label,ok,note){{
  const cls=ok?'ok':'warn';
  const t=label+(note?' · '+note:'');
  return '<span class="badge '+cls+'">'+(ok?'✓ ':'○ ')+t+'</span>';
}}
function renderProviders(j){{
  const p=j.providers||{{}};
  const items=[
    provBadge('Edge TTS',true,'anahtarsız'),
    provBadge('gTTS',true,'anahtarsız'),
    provBadge('Pollinations',true,'senaryo+görsel'),
    provBadge('Web görsel',true,'Bing/Openverse'),
    provBadge('Pexels',!!p.pexels,p.pexels?'kayıtlı':'anahtar yok'),
    provBadge('Pixabay',!!p.pixabay,p.pixabay?'kayıtlı':'anahtar yok'),
    provBadge('HF token',!!p.hf,p.hf?'kayıtlı':'opsiyonel'),
    provBadge('LTX video',p.ltx===true,p.ltx===true?'müsait':(p.ltx===false?'kota/düşer':'bilinmiyor')),
    provBadge('OpenAI',!!p.openai,p.openai?'kayıtlı':'anahtarlı'),
    provBadge('ElevenLabs',!!p.elevenlabs,p.elevenlabs?'kayıtlı':'anahtarlı'),
    provBadge('Viggle',!!p.viggle,p.viggle?'anahtar var':'env yok'),
    provBadge('Higgsfield',!!p.higgsfield,p.higgsfield?'anahtar var':'env yok'),
    provBadge('Hedra',!!p.hedra,p.hedra?'anahtar var':'env yok')
  ].join('');
  ['provvideo','provklip','provavatar','provstatus'].forEach(function(id){{
    const el=document.getElementById(id);
    if(el) el.innerHTML=items;
  }});
}}
function renderJobs(j){{
  const jobs=(j.jobs||[]).slice().reverse();
  const box=document.getElementById('jobs');
  const cnt=document.getElementById('jobcount');
  if(cnt) cnt.textContent=jobs.length?('· '+jobs.length+' kayıt'):'';
  if(!box) return;
  if(!jobs.length){{box.innerHTML='<div class="empty">Kuyruk boş.</div>'; return;}}
  box.innerHTML=jobs.slice(0,12).map(function(x){{
    const st=x.status==='running'?'<span class="badge acc">çalışıyor</span>':
      x.status==='pending'?'<span class="badge warn">bekliyor</span>':
      x.status==='done'?'<span class="badge ok">bitti</span>':'<span class="badge bad">hata</span>';
    const kind=x.kind==='video'?'Video':x.kind==='klip'?'Klip':'Avatar';
    const tail=(x.log||'').slice(-220).split('\\n').slice(-3).join('\\n');
    const link=(x.status==='done'&&x.dir_name)?
      ' <a href="/api/gallery/'+encodeURIComponent(x.dir_name)+'/video.mp4" target="_blank">▶ Oynat</a>'+
      ' · <a href="/api/gallery/'+encodeURIComponent(x.dir_name)+'/video.mp4" download="video.mp4">⬇ İndir</a>':'';
    return '<div class="jobrow"><span class="badge acc">'+kind+'</span>'+st+
      '<b style="flex:1;min-width:180px">'+(x.title||x.label||'')+'</b>'+link+
      (tail?'<div class="sub" style="flex-basis:100%;font-family:Consolas,monospace;white-space:pre-wrap;margin:0">'+tail+'</div>':'')+
      '</div>';
  }}).join('');
}}
function renderGallery(j){{
  const box=document.getElementById('gallery');
  if(!box) return;
  const items=j.gallery||[];
  if(!items.length){{box.innerHTML='<div class="empty">Henüz üretim yok. Video / Klip / Avatar sekmelerinden başlat.</div>'; return;}}
  box.innerHTML='<div class="gal">'+items.map(function(g){{
    const url='/api/gallery/'+encodeURIComponent(g.name)+'/video.mp4';
    const modeBadge=g.mode==='klip'?'<span class="badge acc">klip</span>':
      g.mode==='avatar'?'<span class="badge ok">avatar</span>':'<span class="badge warn">video</span>';
    return '<div class="card"><video controls preload="none" src="'+url+'"></video>'+
      '<div style="margin-top:8px">'+modeBadge+' <b>'+((g.title||g.name).slice(0,48))+'</b></div>'+
      '<div class="sub">'+(g.duration?g.duration+' sn · ':'')+g.created+
      (g.has_subs?' · altyazılı':'')+'</div>'+
      '<div style="margin-top:6px"><a href="'+url+'" download="'+g.name+'.mp4">⬇ indir</a>'+
      (g.has_subs?' · <a href="/api/gallery/'+encodeURIComponent(g.name)+'/subtitles.srt" download="subtitles.srt">srt</a>':'')+
      ' · <a href="#" class="gal-del" data-name="'+g.name+'" onclick="delGallery(this.dataset.name);return false">sil</a></div></div>';
  }}).join('')+'</div>';
}}
async function delGallery(name){{
  if(!confirm('Silinsin mi: '+name)) return;
  await fetch('/api/gallery/delete',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{name:name}})}});
  poll();
}}
function jobCard(x){{
  const url='/api/gallery/'+encodeURIComponent(x.dir_name)+'/video.mp4';
  const kind=(x.kind||'').toUpperCase();
  return '<div class="card" style="margin-top:10px"><div class="label">'+kind+' hazır</div>'+
    '<div style="margin-top:6px"><b>'+(x.title||'—')+'</b> <span class="sub">'+(x.duration?x.duration+' sn · ':'')+
    (x.provider||'')+'</span></div>'+
    '<div style="margin-top:8px"><a href="'+url+'" target="_blank">▶ Oynat</a> · '+
    '<a href="'+url+'" download="video.mp4">⬇ İndir</a> · '+
    '<a href="#" onclick="switchTab(\\'gallery\\');return false">Galeriye bak</a></div></div>';
}}
function renderModes(j){{
  const jobs=(j.jobs||[]).slice().reverse();
  ['klip','avatar'].forEach(function(kind){{
    const job=jobs.find(x=>x.kind===kind);
    if(!job) return;
    const lgId=kind==='klip'?'klog':'alog2';
    const resId=kind==='klip'?'kresult':'aresult';
    const lg=document.getElementById(lgId);
    if(lg&&job.log&&(job.status==='running'||job.status==='pending'||job.status==='error')) lg.textContent=job.log;
    if(job.status==='error'&&lg) lg.textContent='HATA: '+(job.log||'').slice(-500);
    const res=document.getElementById(resId);
    if(res&&job.status==='done') res.innerHTML=jobCard(job);
    if(res&&job.status==='error') res.innerHTML='<div class="empty" style="color:var(--bad);margin-top:10px"><b>'+kind+' üretilemedi:</b> '+
      ((job.log||'').slice(-400))+'</div>';
  }});
}}
async function refreshUploads(){{
  try{{
    const r=await fetch('/api/uploads');
    const j=await r.json();
    const box=document.getElementById('uplist');
    if(!box) return;
    if(!j.files||!j.files.length){{box.innerHTML=''; refreshImgSel(); return;}}
    box.innerHTML='<b>Yüklenen fotoğraflar ('+j.files.length+'): </b>'+
      j.files.map(f=>'<span style="display:inline-block;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:3px 8px;margin:3px 4px 0 0">'+
        f.name+' <a href="#" onclick="delUpload(\\''+f.name+'\\');return false" title="Sil">✕</a></span>').join('');
    refreshImgSel();
  }}catch(e){{}}
}}
async function delUpload(name){{
  try{{
    await fetch('/api/upload/delete',{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{name:name}})}});
    refreshUploads();
  }}catch(e){{}}
}}
async function uploadPics(ev){{
  const files=Array.from(ev.target.files||[]);
  const box=document.getElementById('uplist');
  if(!files.length||!box) return;
  box.textContent='Yükleniyor ('+files.length+' dosya)…';
  const payload={{files:[]}};
  for(const f of files){{
    const data=await new Promise((res,rej)=>{{
      const rd=new FileReader();
      rd.onload=()=>res(String(rd.result).split(',',2)[1]||'');
      rd.onerror=rej;
      rd.readAsDataURL(f);
    }});
    payload.files.push({{name:f.name,data:data}});
  }}
  try{{
    const r=await fetch('/api/upload',{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify(payload)}});
    const j=await r.json();
    if(j.ok) box.textContent='Yüklendi ('+(j.saved||0)+' fotoğraf) — üretimde kullanılacak';
    else box.textContent='Hata: '+(j.error||(j.errors||[]).join(', ')||'yüklenemedi');
    refreshUploads();
  }}catch(e){{ box.textContent='Hata: '+e; }}
  ev.target.value='';
}}
async function refreshAudio(){{
  try{{
    const r=await fetch('/api/audio'); const j=await r.json();
    const sel=document.getElementById('aaudio');
    if(!sel) return;
    const cur=sel.value;
    sel.innerHTML='<option value="">Ses dosyası seç… (ops.)</option>'+
      (j.files||[]).map(f=>'<option value="'+f.name+'">'+f.name+'</option>').join('');
    if(cur) sel.value=cur;
  }}catch(e){{}}
}}
async function refreshBgm(){{
  try{{
    const r=await fetch('/api/bgm'); const j=await r.json();
    const sel=document.getElementById('vbgm');
    if(!sel) return;
    const cur=sel.value;
    sel.innerHTML='<option value="">Arka plan müziği: yok</option>'+
      (j.files||[]).map(f=>'<option value="'+f.name+'">'+f.name+'</option>').join('');
    if(cur) sel.value=cur;
  }}catch(e){{}}
}}
async function uploadFileList(ev, endpoint, listRefresh){{
  const files=Array.from(ev.target.files||[]);
  if(!files.length) return;
  const payload={{files:[]}};
  for(const f of files){{
    const data=await new Promise((res,rej)=>{{
      const rd=new FileReader();
      rd.onload=()=>res(String(rd.result).split(',',2)[1]||'');
      rd.onerror=rej;
      rd.readAsDataURL(f);
    }});
    payload.files.push({{name:f.name,data:data}});
  }}
  try{{
    await fetch(endpoint,{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify(payload)}});
    listRefresh();
  }}catch(e){{}}
  ev.target.value='';
}}
(function init(){{
  const h=(location.hash||'').replace('#','');
  if(h==='video'||h==='status'||h==='scan'||h==='modes'||h==='gallery') switchTab(h);
  document.getElementById('vupbtn').onclick=()=>document.getElementById('vup').click();
  document.getElementById('vup').onchange=uploadPics;
  const aup=document.getElementById('aupbtn');
  if(aup){{
    aup.onclick=()=>document.getElementById('aup').click();
    document.getElementById('aup').onchange=async(ev)=>{{
      await uploadFileList(ev,'/api/upload',()=>{{refreshUploads(); refreshImgSel();}});
    }};
  }}
  const abtn=document.getElementById('aaudioupbtn');
  if(abtn){{
    abtn.onclick=()=>document.getElementById('aaudioup').click();
    document.getElementById('aaudioup').onchange=(ev)=>uploadFileList(ev,'/api/audio',refreshAudio);
  }}
  const bbtn=document.getElementById('vbgmup');
  if(bbtn){{
    bbtn.onclick=()=>document.getElementById('vbgmin').click();
    document.getElementById('vbgmin').onchange=(ev)=>uploadFileList(ev,'/api/bgm',refreshBgm);
  }}
  refreshUploads(); refreshImgSel(); refreshAudio(); refreshBgm();
  poll(); setInterval(poll,4000);
}})();
function refreshImgSel(){{
  const sel=document.getElementById('aimg');
  if(!sel) return;
  fetch('/api/uploads').then(r=>r.json()).then(j=>{{
    const cur=sel.value;
    sel.innerHTML='<option value="">Yüklü görsel seç…</option>'+
      (j.files||[]).map(f=>'<option value="'+f.name+'">'+f.name+'</option>').join('');
    if(cur) sel.value=cur;
  }}).catch(()=>{{}});
}}
</script>
<footer><b>{brand.SVG.replace('<svg ', '<svg style="width:16px;height:16px;vertical-align:-3px;margin-right:6px" ')}TubeLens</b> · RetroNyym — analiz · affiliate denetçisi · ücretsiz video üretim kiti</footer>
</body></html>"""


class _State:
    def __init__(self) -> None:
        self.log = "Hazır."
        self.busy = False
        self.finished = False
        self.last_analyses: list[dict] = []
        self.last_ai: list[dict] = []
        self.video_busy = False
        self.video_log = "Video üretimi bekleniyor…"
        self.video_result: dict | None = None
        self.activate_log = "Aktivasyon bekleniyor…"
        self.action_log = ""
        self.license_text: str | None = None
        self.clone_busy = False
        self.clone_log = "Klon bekleniyor…"
        self.clone_draft: dict | None = None
        self.jobs: list[dict] = []
        self.ltx_ok: object | None = None


STATE = _State()
JOBS_COND = threading.Condition()
JOBS_PENDING: list[dict] = []
JOBS_RUNNING: set[str] = set()
WORKERS_STARTED = False
JOB_SEQ = 0
PROBE_LOCK = threading.Lock()


def _safe_upload_name(name: str) -> str:
    """Yukleme dosya adini guvenli hale getirir (path traversal imkansiz)."""
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).lstrip(".")
    return name[:80]


def _video_row(record: dict) -> dict:
    a = record.get("analysis", {})
    return {
        "video_id": a.get("video_id", record.get("id", "")),
        "title": a.get("title", record.get("title", "")),
        "views": a.get("views", record.get("views", 0)),
        "opportunity_score": a.get("opportunity_score", 0),
        "affili": a.get("affiliate_links", []),
        "disc": bool(a.get("disclosures")),
        "shop": len(a.get("shopping_tags") or []),
        "leak": shopping.revenue_leak(record, a)["leak"],
        "recipes": shopping.action_recipe(record, a),
    }


def _state_payload() -> dict:
    store = storage.load()
    videos = [_video_row(v) for v in store.get("videos", {}).values()]
    videos.sort(key=lambda r: r["opportunity_score"], reverse=True)
    analyses = [v.get("analysis") for v in store.get("videos", {}).values() if v.get("analysis")]
    ai = store.get("ai_checks", [])[-20:]
    _start_probes()
    with JOBS_COND:
        # params anahtari kasitli disarda: hf/openai/elevenlabs anahtarlari
        # /api/state uzerinden asla istemciye donmemeli.
        jobs = [
            {k: v for k, v in j.items() if k != "params"}
            for j in STATE.jobs
        ]
    return {
        "log": STATE.log,
        "busy": STATE.busy,
        "finished": STATE.finished,
        "videos": STATE.last_analyses or videos,
        "ai": STATE.last_ai or ai,
        "summary": shopping.channel_summary(analyses),
        "leak": shopping.channel_leak_summary(analyses),
        "quota": quota.summary_line(),
        "licensed": quota.is_licensed(),
        "license_text": STATE.license_text or "Yükleniyor…",
        "activate_log": STATE.activate_log,
        "action_log": STATE.action_log,
        "providers": _providers_payload(),
        "jobs": jobs,
        "gallery": _gallery_items(),
        "clone": {
            "busy": STATE.clone_busy,
            "log": STATE.clone_log,
            "draft": STATE.clone_draft,
        },
        "video": {
            "busy": STATE.video_busy,
            "log": STATE.video_log,
            "result": STATE.video_result,
        },
    }


def _cli_cmd(*args: str) -> list[str]:
    """Alt surec CLI komutu. Frozen exe'de `-m tubelens` calismadigi icin
    argumanlar dogrudan exe'ye verilir."""
    import sys

    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "tubelens", *args]


def _enqueue(kind: str, label: str, params: dict) -> dict:
    """Uretim isini kuyruğa alir (ayni anda en fazla 2 farkli mod calisir)."""
    global JOB_SEQ
    with JOBS_COND:
        JOB_SEQ += 1
        job = {
            "id": JOB_SEQ,
            "kind": kind,
            "label": label,
            "title": str(params.get("topic") or params.get("prompt") or label),
            "params": params,
            "status": "pending",
            "log": f"Sırada: {label}",
            "created": datetime.now().strftime("%H:%M:%S"),
            "dir_name": "",
            "provider": "",
            "duration": 0,
        }
        STATE.jobs.append(job)
        if len(STATE.jobs) > 60:
            del STATE.jobs[: len(STATE.jobs) - 60]
        JOBS_PENDING.append(job)
        JOBS_COND.notify_all()
    _ensure_workers()
    return job


def _ensure_workers() -> None:
    global WORKERS_STARTED
    with JOBS_COND:
        if WORKERS_STARTED:
            return
        WORKERS_STARTED = True
    for _ in range(2):
        threading.Thread(target=_job_worker, daemon=True).start()


def _job_worker() -> None:
    while True:
        with JOBS_COND:
            while True:
                job = next(
                    (j for j in JOBS_PENDING if j["kind"] not in JOBS_RUNNING), None
                )
                if job is not None:
                    break
                JOBS_COND.wait(timeout=1.0)
            JOBS_PENDING.remove(job)
            JOBS_RUNNING.add(job["kind"])
            job["status"] = "running"
        try:
            _execute_job(job)
        except Exception as exc:  # noqa: BLE001
            job["status"] = "error"
            job["log"] = (job.get("log", "") + f"\nHATA: {exc}")[-4000:]
        finally:
            with JOBS_COND:
                JOBS_RUNNING.discard(job["kind"])
                JOBS_COND.notify_all()


def _execute_job(job: dict) -> None:
    params = job.get("params") or {}
    if job["kind"] == "video":
        _run_video(params, job)
    elif job["kind"] == "klip":
        _run_klip(params, job)
    elif job["kind"] == "avatar":
        _run_avatar(params, job)


def _saved_hf_token(params: dict) -> str:
    from . import config

    return str(
        params.get("hf_token") or config.load_video_config().get("hf_token") or ""
    ).strip()


def _run_klip(params: dict, job: dict) -> None:
    import subprocess

    from .config import ROOT, VIDEO_DIR

    prompt = str(params.get("prompt", "")).strip()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = VIDEO_DIR / f"panel-klip-{stamp}"
    cmd = _cli_cmd("klip", prompt, "--out", str(out_dir))
    for field, flag in (("aspect", "--aspect"), ("provider", "--provider"), ("style", "--style")):
        value = params.get(field)
        if value and not (field == "provider" and value == "auto"):
            cmd += [flag, str(value)]
    if params.get("duration"):
        cmd += ["--duration", str(params["duration"])]
    hf = _saved_hf_token(params)
    if hf:
        cmd += ["--hf-token", hf]
    job["log"] = f"Klip üretimi başladı: {prompt}"
    try:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=1500,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        job["log"] = out[-4000:] or "Klip tamamlandı."
        meta = _read_meta(out_dir)
        ok = proc.returncode == 0 and (out_dir / "video.mp4").exists()
        job["status"] = "done" if ok else "error"
        job["dir_name"] = out_dir.name
        job["title"] = str(meta.get("title") or prompt)
        job["duration"] = meta.get("duration_sec", 0)
        job["provider"] = str(meta.get("provider") or "")
    except subprocess.TimeoutExpired:
        job["status"] = "error"
        job["log"] = "Klip zaman aşımı (25 dk)"
    except Exception as exc:  # noqa: BLE001
        job["status"] = "error"
        job["log"] = f"Klip hatası: {exc}"


def _run_avatar(params: dict, job: dict) -> None:
    import subprocess

    from .config import ROOT, VIDEO_DIR

    image_name = _safe_upload_name(str(params.get("image", "")))
    image_path = UPLOAD_DIR / image_name
    if not image_path.is_file():
        job["status"] = "error"
        job["log"] = f"Görsel bulunamadı: {image_name}"
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = VIDEO_DIR / f"panel-avatar-{stamp}"
    cmd = _cli_cmd("avatar", "--image", str(image_path), "--out", str(out_dir))
    audio_name = _safe_upload_name(str(params.get("audio", "")))
    if audio_name and (AUDIO_DIR / audio_name).is_file():
        cmd += ["--audio", str(AUDIO_DIR / audio_name)]
    elif str(params.get("text", "")).strip():
        cmd += ["--text", str(params["text"]).strip()]
    else:
        job["status"] = "error"
        job["log"] = "Ses dosyası veya metin gerekli"
        return
    for field, flag in (("lang", "--lang"), ("tts_engine", "--tts-engine"),
                        ("voice", "--voice"), ("provider", "--provider")):
        value = params.get(field)
        if value and not (field == "provider" and value == "auto"):
            cmd += [flag, str(value)]
    hf = _saved_hf_token(params)
    if hf:
        cmd += ["--hf-token", hf]
    job["log"] = f"Avatar üretimi başladı: {image_name}"
    try:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=1500,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        job["log"] = out[-4000:] or "Avatar tamamlandı."
        meta = _read_meta(out_dir)
        ok = proc.returncode == 0 and (out_dir / "video.mp4").exists()
        job["status"] = "done" if ok else "error"
        job["dir_name"] = out_dir.name
        job["title"] = str(meta.get("title") or image_name)
        job["duration"] = meta.get("duration_sec", 0)
        job["provider"] = str(meta.get("provider") or "")
    except subprocess.TimeoutExpired:
        job["status"] = "error"
        job["log"] = "Avatar zaman aşımı (25 dk)"
    except Exception as exc:  # noqa: BLE001
        job["status"] = "error"
        job["log"] = f"Avatar hatası: {exc}"


def _read_meta(out_dir) -> dict:
    meta_path = out_dir / "meta.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _list_files(directory, exts: set) -> list[dict]:
    files: list[dict] = []
    if directory.is_dir():
        for p in sorted(directory.glob("*")):
            if p.is_file() and p.suffix.lower() in exts:
                files.append({"name": p.name, "bytes": p.stat().st_size})
    return files


def _gallery_items() -> list[dict]:
    from .config import VIDEO_DIR

    items: list[dict] = []
    if not VIDEO_DIR.is_dir():
        return items
    for d in VIDEO_DIR.iterdir():
        if not d.is_dir():
            continue
        video = d / "video.mp4"
        if not video.is_file():
            continue
        meta = _read_meta(d)
        items.append({
            "name": d.name,
            "title": str(meta.get("title") or d.name),
            "mode": str(meta.get("mode") or "video"),
            "duration": meta.get("duration_sec", 0),
            "created": datetime.fromtimestamp(video.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M"
            ),
            "has_subs": (d / "subtitles.srt").is_file(),
        })
    items.sort(key=lambda g: g["created"], reverse=True)
    return items[:30]


def _providers_payload() -> dict:
    from . import config

    vconf = config.load_video_config()
    return {
        "pexels": bool(vconf.get("pexels_api_key")),
        "pixabay": bool(vconf.get("pixabay_api_key")),
        "openai": bool(vconf.get("openai_api_key")),
        "elevenlabs": bool(vconf.get("elevenlabs_api_key")),
        "hf": bool(vconf.get("hf_token")),
        "viggle": bool(os.environ.get("VIGGLE_API_KEY")),
        "higgsfield": bool(os.environ.get("HIGGSFIELD_API_KEY")),
        "hedra": bool(os.environ.get("HEDRA_API_KEY")),
        "ltx": STATE.ltx_ok,
    }


def _start_probes() -> None:
    """Lisans metni + LTX musaitlik probu arka planda (ilk istekte) calisir."""
    def _license_worker() -> None:
        try:
            text = quota.status_text()
        except Exception as exc:  # noqa: BLE001
            text = f"Lisans bilgisi okunamadi: {exc}"
        STATE.license_text = text

    def _ltx_worker() -> None:
        try:
            from . import hfspace

            STATE.ltx_ok = bool(hfspace.available(hfspace.LTX_SPACE))
        except Exception:  # noqa: BLE001
            STATE.ltx_ok = False

    with PROBE_LOCK:
        if STATE.license_text is None:
            threading.Thread(target=_license_worker, daemon=True).start()
        if STATE.ltx_ok is None:
            threading.Thread(target=_ltx_worker, daemon=True).start()


def _run_scan(target: str, keywords: str, limit: int) -> None:
    import subprocess
    import sys

    STATE.busy = True
    STATE.finished = False
    STATE.log = f"Tarama başladı: {target}"
    cmd = _cli_cmd("scan", target, "--limit", str(limit))
    if keywords:
        cmd += ["--keywords", keywords]
    from .config import ROOT

    try:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        STATE.log = out[-4000:] or "Tarama tamamlandı."
        STATE.finished = proc.returncode == 0
    except Exception as exc:  # noqa: BLE001
        STATE.log = f"Tarama hatasi: {exc}"
    finally:
        STATE.busy = False
        STATE.last_analyses = []
        STATE.last_ai = []


def _run_clone(url: str, lang: str = "", aspect: str = "", duration: int = 0) -> None:
    import subprocess
    import sys

    from .config import DATA_DIR, ROOT

    STATE.clone_busy = True
    STATE.clone_log = f"Klonlanıyor: {url}"
    cmd = _cli_cmd("clone", url)
    if lang:
        cmd += ["--lang", lang]
    if aspect:
        cmd += ["--aspect", aspect]
    if duration:
        cmd += ["--duration", str(int(duration))]
    try:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=420,
        )
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        STATE.clone_log = out[-1500:] or ("Klon tamamlandı." if proc.returncode == 0 else "Klon başarısız")
        if proc.returncode == 0:
            draft_path = DATA_DIR / "clone_draft.json"
            try:
                STATE.clone_draft = json.loads(draft_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                STATE.clone_draft = None
                STATE.clone_log = "Klon çıktı üretildi ama draft okunamadı."
        else:
            STATE.clone_draft = None
    except subprocess.TimeoutExpired:
        STATE.clone_draft = None
        STATE.clone_log = "Klon zaman aşımı (7 dk)"
    except Exception as exc:  # noqa: BLE001
        STATE.clone_draft = None
        STATE.clone_log = f"Klon hatası: {exc}"
    finally:
        STATE.clone_busy = False


def _run_action(action: str) -> None:
    """Durum sekmesi aksiyonlari: lisans kaldirma / rapor yeniden uretimi."""
    import subprocess

    from .config import ROOT

    try:
        proc = subprocess.run(
            _cli_cmd(action),
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        STATE.action_log = (
            out[-800:] or (f"{action} tamamlandı." if proc.returncode == 0 else f"{action} başarısız")
        )
        if action == "deactivate":
            STATE.activate_log = STATE.action_log
    except Exception as exc:  # noqa: BLE001
        STATE.action_log = f"{action} hatasi: {exc}"


def _run_activate(key: str) -> None:
    import subprocess
    import sys

    from .config import ROOT

    STATE.activate_log = f"Deneniyor: {key[:12]}…"
    try:
        proc = subprocess.run(
            _cli_cmd("activate", key),
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=45,
        )
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        STATE.activate_log = out[-600:] or ("OK" if proc.returncode == 0 else "Basarisiz")
    except Exception as exc:  # noqa: BLE001
        STATE.activate_log = f"Aktivasyon hatasi: {exc}"


def _latest_video_path():
    from .config import VIDEO_DIR

    if not VIDEO_DIR.is_dir():
        return None
    clips = sorted(
        VIDEO_DIR.glob("*/video.mp4"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return clips[0] if clips else None


def _run_video(params: dict, job: dict | None = None) -> None:
    import subprocess
    import sys

    from .config import ROOT, VIDEO_DIR

    STATE.video_busy = True
    STATE.video_result = None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = VIDEO_DIR / f"panel-{stamp}"
    if str(params.get("script_file") or "") == "clone_draft.json":
        from .config import DATA_DIR

        draft_path = DATA_DIR / "clone_draft.json"
        cmd = _cli_cmd(
            "video",
            "--script-file", str(draft_path), "--out", str(out_dir),
        )
        if draft_path.exists():
            try:
                draft = json.loads(draft_path.read_text(encoding="utf-8"))
                params = {**params, "topic": str((draft.get("script") or {}).get("title") or "klon")}
                params.setdefault("aspect", draft.get("aspect") or "")
                params.setdefault("duration", draft.get("duration") or 0)
            except (json.JSONDecodeError, OSError):
                pass
    else:
        cmd = _cli_cmd("video", str(params.get("topic", "")), "--out", str(out_dir))
    # Kullanici elle "goruntu klasoru" yazmadiysa ve PC'den yukleme varsa
    # yuklenen fotograflar montaja girer (en oncelikli kaynak).
    if not params.get("footage_dir") and UPLOAD_DIR.is_dir() and any(
        p.is_file() for p in UPLOAD_DIR.glob("*")
    ):
        params = {**params, "footage_dir": str(UPLOAD_DIR)}
    opt_map = {
        "lang": "--lang",
        "aspect": "--aspect",
        "style": "--style",
        "preset": "--preset",
        "footage_dir": "--footage-dir",
        "pexels_key": "--pexels-key",
        "pixabay_key": "--pixabay-key",
        "tts_engine": "--tts-engine",
        "voice": "--voice",
        "openai_key": "--openai-key",
        "elevenlabs_key": "--elevenlabs-key",
        "tts_model": "--tts-model",
        "hf_token": "--hf-token",
    }
    for field, flag in opt_map.items():
        value = params.get(field)
        if value:
            cmd += [flag, str(value)]
    for field, flag in (
        ("duration", "--duration"),
        ("resolution", "--resolution"),
        ("clips", "--clips"),
    ):
        if params.get(field):
            cmd += [flag, str(int(params[field]))]
    bgm_name = str(params.get("bgm") or "").strip()
    if bgm_name:
        bgm_path = BGMDIR / _safe_upload_name(bgm_name)
        if bgm_path.is_file():
            cmd += ["--bgm", str(bgm_path)]
    if params.get("bgm_volume") is not None and params.get("bgm_volume") != "":
        try:
            vol = float(params.get("bgm_volume"))
            if 0 <= vol <= 1:
                cmd += ["--bgm-volume", str(vol)]
        except (TypeError, ValueError):
            pass
    if params.get("script_only"):
        cmd += ["--script-only"]
    if not params.get("ai_visuals", True):
        cmd += ["--no-ai-visuals"]
    if params.get("web_images", True) is False:
        cmd += ["--no-web-images"]
    if params.get("ltx_video"):
        cmd += ["--ltx-video"]
    if params.get("logo") is False:
        cmd += ["--no-logo"]
    if params.get("subs") is False:
        cmd += ["--no-subs"]
    engine = str(params.get("tts_engine") or "edge")
    mode = "senaryo+video (tum adimlar)"
    if params.get("script_only"):
        mode = "SADECE SENARYO (istek uzerinden)"
    elif str(params.get("script_file") or "") == "clone_draft.json":
        mode = "klon draft -> tum adimlar"
    if params.get("footage_dir"):
        mode += " · goruntu klasoru kullaniliyor"
    STATE.video_log = (
        f"Video üretimi başladı: {params.get('topic', '')} "
        f"(motor={engine} · {mode})"
    )
    try:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=1800,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        STATE.video_log = out[-4000:] or "Video üretimi tamamlandı."
        video = out_dir / "video.mp4"
        meta: dict = {}
        meta_path = out_dir / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                meta = {}
        STATE.video_result = {
            "ok": bool(
                proc.returncode == 0 and (video.exists() or bool(meta.get("title")))
            ),
            "dir": str(out_dir),
            "key": out_dir.name,
            "video": video.exists(),
            "video_no_subs": (out_dir / "video_no_subs.mp4").exists(),
            "title": meta.get("title", ""),
            "duration": meta.get("duration_sec", 0),
            "engine": meta.get("tts_engine", engine),
            "error": "" if proc.returncode == 0 else (out[-600:] or "bilinmeyen hata"),
        }
    except subprocess.TimeoutExpired:
        STATE.video_result = {"ok": False, "dir": str(out_dir), "key": out_dir.name, "video": False,
                              "title": "", "duration": 0, "engine": engine, "error": "Zaman aşımı (30 dk)"}
    except Exception as exc:  # noqa: BLE001
        STATE.video_result = {"ok": False, "dir": str(out_dir), "key": out_dir.name, "video": False,
                              "title": "", "duration": 0, "engine": engine, "error": str(exc)}
    finally:
        STATE.video_busy = False
        if job is not None:
            res = STATE.video_result or {}
            job["status"] = "done" if res.get("ok") else "error"
            job["dir_name"] = out_dir.name
            job["title"] = str(res.get("title") or params.get("topic") or "")
            job["duration"] = res.get("duration", 0)
            job["log"] = STATE.video_log[-4000:]
            if not res.get("ok") and res.get("error"):
                job["log"] = (job["log"] + "\n" + str(res["error"]))[-4000:]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # suskun
        if os.environ.get("PANEL_REQ_LOG"):
            try:
                with open(os.environ["PANEL_REQ_LOG"], "a", encoding="utf-8") as fh:
                    fh.write((fmt % args) + "\n")
            except OSError:
                pass

    def _send(self, body: bytes, ctype: str = "text/html; charset=utf-8", code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send(PAGE.encode("utf-8"))
        elif parsed.path == "/api/state":
            body = json.dumps(_state_payload(), ensure_ascii=False).encode("utf-8")
            self._send(body, "application/json; charset=utf-8")
        elif parsed.path == "/report":
            ensure_dirs()
            latest = REPORT_DIR / "latest.html"
            if latest.exists():
                self._send(latest.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(b"Rapor yok. Once scan calistirin.", code=404)
        elif parsed.path == "/api/uploads":
            files = []
            if UPLOAD_DIR.is_dir():
                for p in sorted(UPLOAD_DIR.glob("*")):
                    if p.is_file() and p.suffix.lower() in UPLOAD_EXTS:
                        files.append(
                            {"name": p.name, "bytes": p.stat().st_size}
                        )
            self._send(json.dumps({"files": files}).encode(), "application/json")
        elif parsed.path in (
            "/api/video/latest", "/api/video/srt", "/api/video/nosubs"
        ):
            kind = {
                "/api/video/srt": "srt",
                "/api/video/nosubs": "nosubs",
            }.get(parsed.path, "mp4")
            self._send_video_file(kind)
        elif parsed.path == "/api/audio":
            self._send(
                json.dumps(
                    {"files": _list_files(AUDIO_DIR, AUDIO_EXTS)}
                ).encode(),
                "application/json",
            )
        elif parsed.path == "/api/bgm":
            self._send(
                json.dumps(
                    {"files": _list_files(BGMDIR, AUDIO_EXTS)}
                ).encode(),
                "application/json",
            )
        elif parsed.path == "/api/gallery":
            self._send(
                json.dumps({"items": _gallery_items()}).encode(),
                "application/json",
            )
        elif parsed.path.startswith("/api/gallery/"):
            self._send_gallery_file(parsed.path[len("/api/gallery/"):])
        else:
            self._send(b"404", code=404)

    def _send_gallery_file(self, rest: str) -> None:
        from .config import VIDEO_DIR

        name, _, fname = rest.partition("/")
        name = _safe_upload_name(name)
        if not name or fname not in GALLERY_FILES:
            self._send(b"404", code=404)
            return
        target = (VIDEO_DIR / name / fname).resolve()
        try:
            target.relative_to(VIDEO_DIR.resolve())
        except ValueError:
            self._send(b"404", code=404)
            return
        if not target.is_file():
            self._send(b"404", code=404)
            return
        self._send_path(target, media=fname.endswith(".mp4"))

    def _handle_upload(
        self,
        payload: dict,
        dest: Path | None = None,
        exts: set | None = None,
        max_files: int | None = None,
    ) -> None:
        dest = dest if dest is not None else UPLOAD_DIR
        exts = exts if exts is not None else UPLOAD_EXTS
        max_files = max_files if max_files is not None else UPLOAD_MAX_FILES
        files = payload.get("files")
        if not isinstance(files, list):
            files = []
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._send(
                json.dumps({"ok": False, "error": f"klasor olusturulamadi: {exc}"}).encode(),
                "application/json",
            )
            return
        existing = sum(
            1 for p in dest.glob("*")
            if p.is_file() and p.suffix.lower() in exts
        )
        saved = 0
        errors: list[str] = []
        for item in files:
            if not isinstance(item, dict):
                continue
            if existing + saved >= max_files:
                errors.append(f"dosya limiti doldu ({max_files})")
                break
            raw_name = str(item.get("name") or "")
            name = _safe_upload_name(raw_name)
            if not name or Path(name).suffix.lower() not in exts:
                errors.append(f"uzanti desteklenmiyor: {raw_name or '?'}")
                continue
            try:
                blob = base64.b64decode(str(item.get("data") or ""), validate=True)
            except Exception:  # noqa: BLE001
                errors.append(f"{name}: gecersiz veri")
                continue
            if len(blob) < 10 or len(blob) > UPLOAD_MAX_BYTES:
                errors.append(f"{name}: boyut gecersiz")
                continue
            try:
                (dest / name).write_bytes(blob)
            except OSError as exc:
                errors.append(f"{name}: {exc}")
                continue
            saved += 1
        self._send(
            json.dumps(
                {"ok": saved > 0, "saved": saved, "errors": errors[:6]}
            ).encode(),
            "application/json",
        )

    def _send_video_file(self, kind: str) -> None:
        video = _latest_video_path()
        if not video:
            self._send(b"Video yok. Once video uretin.", code=404)
            return
        if kind == "nosubs":
            path = video.with_name("video_no_subs.mp4")
        elif kind == "srt":
            path = video.with_name("subtitles.srt")
        else:
            path = video
        if not path.exists():
            self._send(b"Dosya yok.", code=404)
            return
        self._send_path(path, media=kind in ("mp4", "nosubs"))

    def _send_path(self, path, media: bool) -> None:
        # Tam dosya bellege alinmaz: 60MB'lik video icin her Range istegi
        # tüm dosyayi okuyup video onizlemelerini yavaslatiyordu.
        ctype = "video/mp4" if media else (
            "text/plain; charset=utf-8" if path.suffix == ".srt"
            else "application/json; charset=utf-8" if path.suffix == ".json"
            else "text/plain; charset=utf-8"
        )
        size = path.stat().st_size
        rng = self.headers.get("Range")
        if rng and media and rng.startswith("bytes="):
            try:
                start_s, _, end_s = rng[6:].partition("-")
                start = int(start_s or 0)
                end = int(end_s) if end_s else size - 1
                end = min(end, size - 1)
                if start > end or start >= size:
                    raise ValueError
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            self._stream_file(path, start, end - start + 1)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(size))
        self.end_headers()
        self._stream_file(path, 0, size)

    def _stream_file(self, path, start: int, length: int) -> None:
        remaining = length
        try:
            with open(path, "rb") as fh:
                fh.seek(start)
                while remaining > 0:
                    block = fh.read(min(1024 * 1024, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in (
            "/api/scan", "/api/video", "/api/activate", "/api/clone",
            "/api/upload", "/api/upload/delete",
            "/api/klip", "/api/avatar", "/api/deactivate", "/api/report",
            "/api/gallery/delete", "/api/audio", "/api/audio/delete",
            "/api/bgm", "/api/bgm/delete",
        ):
            self._send(b"404", code=404)
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > 64 * 1024 * 1024:
            self._send(
                json.dumps({"ok": False, "error": "istek cok buyuk"}).encode(),
                "application/json",
            )
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

        if parsed.path == "/api/upload":
            self._handle_upload(payload)
            return

        if parsed.path == "/api/audio":
            self._handle_upload(payload, AUDIO_DIR, AUDIO_EXTS, 20)
            return

        if parsed.path == "/api/bgm":
            self._handle_upload(payload, BGMDIR, AUDIO_EXTS, BG_MAX_FILES)
            return

        if parsed.path in (
            "/api/upload/delete", "/api/audio/delete", "/api/bgm/delete"
        ):
            dest, exts = {
                "/api/upload/delete": (UPLOAD_DIR, UPLOAD_EXTS),
                "/api/audio/delete": (AUDIO_DIR, AUDIO_EXTS),
                "/api/bgm/delete": (BGMDIR, AUDIO_EXTS),
            }[parsed.path]
            name = _safe_upload_name(str(payload.get("name", "")))
            ok = False
            if name:
                target = dest / name
                if target.is_file() and target.suffix.lower() in exts:
                    try:
                        target.unlink()
                        ok = True
                    except OSError:
                        pass
            self._send(
                json.dumps({"ok": ok}).encode(), "application/json"
            )
            return

        if parsed.path == "/api/clone":
            url = str(payload.get("url", "")).strip()
            if not url:
                self._send(json.dumps({"ok": False, "error": "video URL gerekli"}).encode(), "application/json")
                return
            if STATE.clone_busy:
                self._send(json.dumps({"ok": False, "error": "Klon zaten çalışıyor"}).encode(), "application/json")
                return
            lang = str(payload.get("lang", "") or "")
            aspect = str(payload.get("aspect", "") or "")
            try:
                duration = int(payload.get("duration", 0) or 0)
            except (TypeError, ValueError):
                duration = 0
            thread = threading.Thread(
                target=_run_clone, args=(url, lang, aspect, duration), daemon=True
            )
            thread.start()
            self._send(json.dumps({"ok": True}).encode(), "application/json")
            return

        if parsed.path == "/api/activate":
            key = str(payload.get("key", "")).strip()
            if not key:
                self._send(json.dumps({"ok": False, "error": "anahtar gerekli"}).encode(), "application/json")
                return
            thread = threading.Thread(target=_run_activate, args=(key,), daemon=True)
            thread.start()
            self._send(json.dumps({"ok": True}).encode(), "application/json")
            return

        if parsed.path in ("/api/deactivate", "/api/report"):
            action = "deactivate" if parsed.path.endswith("deactivate") else "report"
            STATE.action_log = f"{action} başlatıldı…"
            thread = threading.Thread(
                target=_run_action, args=(action,), daemon=True
            )
            thread.start()
            self._send(json.dumps({"ok": True, "message": STATE.action_log}).encode(), "application/json")
            return

        if parsed.path == "/api/video":
            topic = str(payload.get("topic", "")).strip()
            if not topic:
                self._send(json.dumps({"ok": False, "error": "konu gerekli"}).encode(), "application/json")
                return
            payload["topic"] = topic
            job = _enqueue("video", topic, payload)
            self._send(json.dumps({"ok": True, "job": job["id"]}).encode(), "application/json")
            return

        if parsed.path == "/api/klip":
            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._send(json.dumps({"ok": False, "error": "klip prompt'u gerekli"}).encode(), "application/json")
                return
            payload["prompt"] = prompt
            job = _enqueue("klip", prompt, payload)
            self._send(json.dumps({"ok": True, "job": job["id"]}).encode(), "application/json")
            return

        if parsed.path == "/api/avatar":
            image = _safe_upload_name(str(payload.get("image", "")).strip())
            if not image or not (UPLOAD_DIR / image).is_file():
                self._send(json.dumps({"ok": False, "error": "görsel gerekli (önce yükle/seç)"}).encode(), "application/json")
                return
            if not str(payload.get("text", "")).strip() and not _safe_upload_name(
                str(payload.get("audio", "") or "")
            ):
                self._send(json.dumps({"ok": False, "error": "ses dosyası veya metin gerekli"}).encode(), "application/json")
                return
            payload["image"] = image
            job = _enqueue("avatar", image, payload)
            self._send(json.dumps({"ok": True, "job": job["id"]}).encode(), "application/json")
            return

        if parsed.path == "/api/gallery/delete":
            from .config import VIDEO_DIR

            name = _safe_upload_name(str(payload.get("name", "")))
            ok = False
            if name:
                target = VIDEO_DIR / name
                if target.is_dir():
                    try:
                        import shutil

                        shutil.rmtree(target)
                        ok = True
                    except OSError:
                        pass
            self._send(json.dumps({"ok": ok}).encode(), "application/json")
            return

        target = str(payload.get("target", "")).strip()
        if not target:
            self._send(json.dumps({"ok": False, "error": "target gerekli"}).encode(), "application/json")
            return
        if STATE.busy:
            self._send(json.dumps({"ok": False, "error": "Tarama zaten devam ediyor"}).encode(), "application/json")
            return
        thread = threading.Thread(
            target=_run_scan,
            args=(target, str(payload.get("keywords", "")), int(payload.get("limit", 10))),
            daemon=True,
        )
        thread.start()
        self._send(json.dumps({"ok": True}).encode(), "application/json")


def serve(host: str = "127.0.0.1", port: int = 8787, open_browser: bool = True) -> None:
    ensure_dirs()
    url = f"http://{host}:{port}"
    # Windows'ta SO_REUSEADDR nedeniyle bind hata vermeyebilir; once gercek
    # dinleyici var mi kontrol et (zaten calisan panelde ikinci acilis iciin).
    import socket

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        busy = probe.connect_ex((host, port)) == 0
    finally:
        probe.close()
    if busy:
        print(f"Panel zaten calisiyor: {url}")
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:  # noqa: BLE001
                pass
        return
    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        print(f"Panel baslatilamadi (port {port}): {exc}")
        return
    print(f"TubeLens panel: {url}")
    print("Durdurmak icin Ctrl+C")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPanel kapatildi.")
        server.shutdown()
