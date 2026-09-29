"""Yerel web paneli - standart kutuphane ile (127.0.0.1:8787).

Sekmeli arayuz: Tarama & Rapor | Video Uret | Durum & Lisans.
Sunucu kayitli veriyi gosterir, tarama/video uretimini arka planda tetikler.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import brand, quota, shopping, storage
from .config import REPORT_DIR, ensure_dirs

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
form{display:flex;gap:10px;flex-wrap:wrap;background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:16px;margin:16px 0}
input,select{background:#11141a;border:1px solid var(--line);color:var(--txt);
border-radius:8px;padding:10px 12px;font-size:14px;min-width:230px;flex:1}
input[type=checkbox]{min-width:0;flex:0;width:16px;height:16px;align-self:center;accent-color:var(--acc)}
button{background:var(--acc);border:0;color:#fff;border-radius:8px;padding:11px 18px;
font-weight:600;cursor:pointer;font-size:14px}
button:hover{filter:brightness(1.1)}
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
.tab{background:none;color:var(--mut);padding:12px 18px;border:1px solid transparent;
border-bottom:none;border-radius:10px 10px 0 0;cursor:pointer;font-weight:600;font-size:14px}
.tab.on{background:var(--card);color:var(--txt);border-color:var(--line);box-shadow:0 -2px 0 var(--acc) inset}
.tabpanel{display:none;padding-top:6px}
.tabpanel.on{display:block}
.hint{font-size:13px;color:var(--mut);margin:6px 0 0}
.brand{width:30px;height:30px;vertical-align:-7px;margin-right:10px;flex:none}
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
  <button class="tab" data-tab="status" onclick="switchTab('status')">3 · Durum &amp; Lisans</button>
</div>

<section id="tab-scan" class="tabpanel on">
<form onsubmit="return startScan()">
  <input id="target" placeholder="Video URL, video ID veya @kanal" required>
  <input id="keywords" placeholder="Anahtar kelimeler (virgülle) — opsiyonel">
  <select id="limit"><option value="5">5 video</option><option value="10" selected>10 video</option>
  <option value="20">20 video</option></select>
  <button type="submit">Tarama Başlat</button>
</form>
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
<p class="hint">Kaynak zinciri: lokal klasör → Pexels → Pixabay → <b>anahtarsız AI görsel + Ken Burns</b>
(son adım hiç anahtar istemez). Ses: Edge TTS / gTTS anahtarsız; OpenAI / ElevenLabs API anahtarlı.</p>
<div id="clonecard"></div>
<form onsubmit="return startVideo()">
  <input id="vtopic" placeholder="Video konusu (örn. Sabah koşusunun 7 faydası)" required style="min-width:100%">
  <select id="vaspect"><option value="9:16" selected>9:16 dikey (Shorts/TikTok)</option>
    <option value="16:9">16:9 yatay (YouTube)</option><option value="1:1">1:1 kare</option></select>
  <select id="vduration"><option value="30">30 sn</option><option value="45" selected>45 sn</option>
    <option value="60">60 sn</option><option value="90">90 sn</option></select>
  <select id="vres"><option value="1080" selected>1080p</option><option value="720">720p</option></select>
  <select id="vlang"><option value="tr" selected>Türkçe</option><option value="en">English</option></select>
  <input id="vstyle" placeholder="Ton (ops.) — belgesel, hızlı, eğlenceli">
  <input id="vfootage" placeholder="Görüntü klasörü (ops., en öncelikli)">
  <input id="vpexels" placeholder="Pexels API anahtarı (ops., ücretsiz)">
  <input id="vpixabay" placeholder="Pixabay API anahtarı (ops., ücretsiz)">
  <label class="sub" style="display:flex;gap:7px;align-items:center;min-width:250px">
    <input type="checkbox" id="vai" checked> AI görsel fallback (anahtarsız)</label>
  <select id="vtts">
    <option value="edge" selected>Edge TTS — anahtarsız (öneri)</option>
    <option value="gtts">Google gTTS — anahtarsız</option>
    <option value="openai">OpenAI TTS — API anahtarı</option>
    <option value="elevenlabs">ElevenLabs — API anahtarı</option>
  </select>
  <input id="vvoice" placeholder="Ses adı (ops.) — Edge: tr-TR-EmelNeural · OpenAI: alloy">
  <input id="vopenai" placeholder="OpenAI API anahtarı (ops., kaydedilir)">
  <input id="veleven" placeholder="ElevenLabs API anahtarı (ops., kaydedilir)">
  <label class="sub" style="display:flex;gap:7px;align-items:center;min-width:230px">
    <input type="checkbox" id="vlogo" checked> Videoya TubeLens filigranı + imza</label>
  <button type="submit">Video Üret</button>
</form>
<div class="log" id="vlog">Video üretimi bekleniyor…</div>
<div id="vresult"></div>
</section>

<section id="tab-status" class="tabpanel">
<h2>Durum &amp; Lisans</h2>
<div class="cards" id="statuscards"></div>
<form onsubmit="return activate()">
  <input id="akey" placeholder="Lisans anahtarı (TL1-… veya LemonSqueezy ürün anahtarı)" required>
  <button type="submit">Aktive Et</button>
</form>
<div class="log" id="alog">Aktivasyon bekleniyor…</div>
<p class="hint">CLI: <code>python -m tubelens status</code> ·
<code>python -m tubelens activate &lt;ANAHTAR&gt;</code> ·
<code>python -m tubelens deactivate</code> ·
Video CLI: <code>python -m tubelens video &lt;KONU&gt; --tts-engine edge|gtts|openai|elevenlabs</code></p>
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
function switchTab(name){{
  document.querySelectorAll('.tab').forEach(function(b){{
    b.classList.toggle('on', b.dataset.tab===name);
  }});
  document.querySelectorAll('.tabpanel').forEach(function(s){{
    s.classList.toggle('on', s.id==='tab-'+name);
  }});
  history.replaceState(null,'','#'+name);
}}
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
  const r=await fetch('/api/clone',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{url:vid}})}});
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
    const asp=document.getElementById('vaspect'); asp.value=d.aspect||'9:16';
    const dur=document.getElementById('vduration');
    const dv=String(d.duration||45);
    if(!Array.from(dur.options).some(o=>o.value===dv)){{
      const opt=document.createElement('option'); opt.value=dv; dur.add(opt);
    }}
    dur.value=dv;
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
async function startVideo(){{
  const topic=document.getElementById('vtopic').value.trim();
  if(!topic) return false;
  const payload={{topic,
    lang:document.getElementById('vlang').value,
    duration:parseInt(document.getElementById('vduration').value,10),
    aspect:document.getElementById('vaspect').value,
    resolution:parseInt(document.getElementById('vres').value,10),
    style:document.getElementById('vstyle').value.trim(),
    footage_dir:document.getElementById('vfootage').value.trim(),
    pexels_key:document.getElementById('vpexels').value.trim(),
    pixabay_key:document.getElementById('vpixabay').value.trim(),
    ai_visuals:document.getElementById('vai').checked,
    tts_engine:document.getElementById('vtts').value,
    voice:document.getElementById('vvoice').value.trim(),
    openai_key:document.getElementById('vopenai').value.trim(),
    elevenlabs_key:document.getElementById('veleven').value.trim(),
    logo:document.getElementById('vlogo').checked,
    script_file:cloneApplied?'clone_draft.json':''}};
  document.getElementById('vlog').textContent='Video üretimi başlatıldı…';
  document.getElementById('vresult').innerHTML='';
  const r=await fetch('/api/video',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify(payload)}});
  const j=await r.json();
  if(!j.ok){{document.getElementById('vlog').textContent='Hata: '+j.error;return false;}}
  switchTab('video');
  if(vtimer) clearInterval(vtimer);
  vticks=0;
  vtimer=setInterval(poll,1500); poll();
  return false;
}}
async function activate(){{
  const key=document.getElementById('akey').value.trim();
  if(!key) return false;
  document.getElementById('alog').textContent='Aktivasyon denendi…';
  const r=await fetch('/api/activate',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{key}})}});
  const j=await r.json();
  document.getElementById('alog').textContent=(j.ok?'OK: ':'Hata: ')+(j.message||j.error||'');
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
  const media=res.video
    ? '<video controls preload="metadata" width="210" src="'+url+'"></video>'
    : '<span class="badge ok">senaryo hazır</span>';
  box.innerHTML='<div class="card" style="margin-top:10px"><div class="label">Son üretim — '+
    (res.engine?((res.engine)+('' + (res.engine==='edge'||res.engine==='gtts'?' (anahtarsız)':' (API)'))):'')+'</div>'+
    '<div style="margin-top:6px"><b>'+(res.title||'—')+'</b> <span class="sub">'+(res.duration||0)+' sn</span></div>'+
    '<div style="margin-top:10px;display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap">'+media+
    '<div class="sub">'+(res.video?'<a href="'+url+'" download="video.mp4">video.mp4 indir</a><br>':'')+
    (res.video?'<a href="/api/video/srt" download="subtitles.srt">subtitles.srt</a><br>':'')+
    '<code>'+res.dir+'</code></div></div></div>';
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
    sc.innerHTML=`
     <div class="card"><div class="label">Kota</div><div class="value" style="font-size:18px">${{j.quota||'—'}}</div></div>
     <div class="card"><div class="label">Lisans</div><div class="value" style="font-size:18px">${{j.licensed?'PRO':'Ücretsiz'}}</div></div>
     <div class="card"><div class="label">Video üretimi</div><div class="value" style="font-size:18px">${{j.video&&j.video.busy?'çalışıyor':(j.video&&j.video.result&&j.video.result.ok?'son üretim hazır':'bekliyor')}}</div></div>
     <div class="card"><div class="label">Panel</div><div class="value" style="font-size:18px">127.0.0.1:8787</div></div>`;
  }}
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
  const al=document.getElementById('alog');
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
  if(j.busy===false && timer && j.finished){{
    clearInterval(timer); timer=null;
  }}
}}
(function init(){{
  const h=(location.hash||'').replace('#','');
  if(h==='video'||h==='status'||h==='scan') switchTab(h);
  poll(); setInterval(poll,4000);
}})();
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
        self.clone_busy = False
        self.clone_log = "Klon bekleniyor…"
        self.clone_draft: dict | None = None


STATE = _State()


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
        "activate_log": STATE.activate_log,
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


def _run_clone(url: str) -> None:
    import subprocess
    import sys

    from .config import DATA_DIR, ROOT

    STATE.clone_busy = True
    STATE.clone_log = f"Klonlanıyor: {url}"
    cmd = _cli_cmd("clone", url)
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


def _run_video(params: dict) -> None:
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
    opt_map = {
        "lang": "--lang",
        "aspect": "--aspect",
        "style": "--style",
        "footage_dir": "--footage-dir",
        "pexels_key": "--pexels-key",
        "pixabay_key": "--pixabay-key",
        "tts_engine": "--tts-engine",
        "voice": "--voice",
        "openai_key": "--openai-key",
        "elevenlabs_key": "--elevenlabs-key",
        "tts_model": "--tts-model",
    }
    for field, flag in opt_map.items():
        value = params.get(field)
        if value:
            cmd += [flag, str(value)]
    for field, flag in (("duration", "--duration"), ("resolution", "--resolution")):
        if params.get(field):
            cmd += [flag, str(int(params[field]))]
    if params.get("script_only"):
        cmd += ["--script-only"]
    if not params.get("ai_visuals", True):
        cmd += ["--no-ai-visuals"]
    if params.get("logo") is False:
        cmd += ["--no-logo"]
    engine = str(params.get("tts_engine") or "edge")
    mode = "senaryo+video (tum adimlar)"
    if params.get("script_only"):
        mode = "SADECE SENARYO (istek uzerinden)"
    elif str(params.get("script_file") or "") == "clone_draft.json":
        mode = "klon draft -> tum adimlar"
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


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # suskun
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
        elif parsed.path in ("/api/video/latest", "/api/video/srt"):
            self._send_video_file(
                "srt" if parsed.path.endswith("/srt") else "mp4"
            )
        else:
            self._send(b"404", code=404)

    def _send_video_file(self, kind: str) -> None:
        video = _latest_video_path()
        if not video:
            self._send(b"Video yok. Once video uretin.", code=404)
            return
        path = video if kind == "mp4" else video.with_name("subtitles.srt")
        if not path.exists():
            self._send(b"Dosya yok.", code=404)
            return
        data = path.read_bytes()
        ctype = "video/mp4" if kind == "mp4" else "text/plain; charset=utf-8"
        rng = self.headers.get("Range")
        if rng and kind == "mp4" and rng.startswith("bytes="):
            try:
                start_s, _, end_s = rng[6:].partition("-")
                start = int(start_s or 0)
                end = int(end_s) if end_s else len(data) - 1
                end = min(end, len(data) - 1)
                if start > end or start >= len(data):
                    raise ValueError
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{len(data)}")
                self.end_headers()
                return
            chunk = data[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
            self.send_header("Content-Length", str(len(chunk)))
            self.end_headers()
            self.wfile.write(chunk)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/scan", "/api/video", "/api/activate", "/api/clone"):
            self._send(b"404", code=404)
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

        if parsed.path == "/api/clone":
            url = str(payload.get("url", "")).strip()
            if not url:
                self._send(json.dumps({"ok": False, "error": "video URL gerekli"}).encode(), "application/json")
                return
            if STATE.clone_busy:
                self._send(json.dumps({"ok": False, "error": "Klon zaten çalışıyor"}).encode(), "application/json")
                return
            thread = threading.Thread(target=_run_clone, args=(url,), daemon=True)
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

        if parsed.path == "/api/video":
            topic = str(payload.get("topic", "")).strip()
            if not topic:
                self._send(json.dumps({"ok": False, "error": "konu gerekli"}).encode(), "application/json")
                return
            if STATE.video_busy:
                self._send(json.dumps({"ok": False, "error": "Video zaten uretiliyor"}).encode(), "application/json")
                return
            payload["topic"] = topic
            thread = threading.Thread(target=_run_video, args=(payload,), daemon=True)
            thread.start()
            self._send(json.dumps({"ok": True}).encode(), "application/json")
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
