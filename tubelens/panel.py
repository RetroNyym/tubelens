"""Yerel web paneli - standart kutuphane ile (127.0.0.1:8787).

Sunucu, kayitli veriyi gosterir ve yeni tarama tetikler.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import quota, shopping, storage
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
.value{font-size:28px;font-weight:700;margin-top:6px}
form{display:flex;gap:10px;flex-wrap:wrap;background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:16px;margin:22px 0}
input,select{background:#11141a;border:1px solid var(--line);color:var(--txt);
border-radius:8px;padding:10px 12px;font-size:14px;min-width:240px;flex:1}
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
h2{font-size:17px;margin:32px 0 8px}
.log{background:#11141a;border:1px solid var(--line);border-radius:10px;padding:12px;
font-family:Consolas,monospace;font-size:13px;white-space:pre-wrap;max-height:260px;overflow:auto}
.empty{color:var(--mut);padding:24px;text-align:center;background:var(--card);
border:1px dashed var(--line);border-radius:12px}
a{color:var(--acc)}
"""

PAGE = f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TubeLens Panel</title><style>{CSS}</style></head><body>
<header><h1>TubeLens — YouTube AI Görünürlük + Affiliate Paneli</h1>
<span class="sub"><span id="kota" class="badge acc" style="margin-right:12px">kota: …</span><a href="/report" target="_blank">Son HTML rapor</a></span></header>
<div class="wrap">

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

<h2>Video Üret <span class="sub">(senaryo → görüntü → ses → altyazı → MP4 · anahtarsız)</span></h2>
<form onsubmit="return startVideo()">
  <input id="vtopic" placeholder="Video konusu (örn. Sabah koşusunun 7 faydası)" required>
  <select id="vaspect"><option value="9:16" selected>9:16 dikey (Shorts/TikTok)</option>
    <option value="16:9">16:9 yatay (YouTube)</option><option value="1:1">1:1 kare</option></select>
  <select id="vduration"><option value="30">30 sn</option><option value="45" selected>45 sn</option>
    <option value="60">60 sn</option><option value="90">90 sn</option></select>
  <select id="vres"><option value="1080" selected>1080p</option><option value="720">720p</option></select>
  <select id="vlang"><option value="tr" selected>Türkçe</option><option value="en">English</option></select>
  <input id="vstyle" placeholder="Ton (ops.) — belgesel, hızlı, eğlenceli">
  <input id="vfootage" placeholder="Görüntü klasörü (ops.) — boşsa Pexels">
  <input id="vpexels" placeholder="Pexels API anahtarı (ops., kaydedilir)">
  <label class="sub" style="display:flex;gap:7px;align-items:center;min-width:170px">
    <input type="checkbox" id="vscript" style="min-width:0;flex:0;width:16px;height:16px"> Sadece senaryo</label>
  <button type="submit">Video Üret</button>
</form>
<div class="log" id="vlog">Video üretimi bekleniyor…</div>
<div id="vresult"></div>

<h2>Özet</h2>
<div class="cards" id="cards"></div>

<h2>Videolar</h2>
<div id="videos"><div class="empty">Kayıtlı video yok. Yukarıdan bir hedef tarayın.</div></div>

<h2>AI Görünürlük Kontrolleri</h2>
<div id="ai"><div class="empty">Kayıtlı AI kontrolü yok.</div></div>
</div>
<script>
let timer=null;
let vtimer=null;
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
async function poll(){{
  const r=await fetch('/api/state'); const j=await r.json();
  document.getElementById('log').textContent=j.log||'—';
  render(j); renderVideo(j);
  if(j.busy===false && timer && j.log.indexOf('Tarama')>-1 && j.finished){{
    clearInterval(timer); timer=null;
  }}
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
    script_only:document.getElementById('vscript').checked}};
  document.getElementById('vlog').textContent='Video üretimi başlatıldı…';
  document.getElementById('vresult').innerHTML='';
  const r=await fetch('/api/video',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify(payload)}});
  const j=await r.json();
  if(!j.ok){{document.getElementById('vlog').textContent='Hata: '+j.error;return false;}}
  if(vtimer) clearInterval(vtimer);
  vtimer=setInterval(pollVideo,1500); pollVideo();
  return false;
}}
async function pollVideo(){{
  const r=await fetch('/api/state'); const j=await r.json();
  renderVideo(j);
  if(j.video && j.video.busy===false && vtimer){{clearInterval(vtimer); vtimer=null;}}
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
      ((res.error||'bilinmeyen hata').slice(-400))+'</div>';
    return;
  }}
  const media=res.video
    ? '<video controls width="210" src="/api/video/latest"></video>'
    : '<span class="badge ok">senaryo hazır</span>';
  box.innerHTML='<div class="card" style="margin-top:10px"><div class="label">Son üretim</div>'+
    '<div style="margin-top:6px"><b>'+(res.title||'—')+'</b> <span class="sub">'+(res.duration||0)+' sn</span></div>'+
    '<div style="margin-top:10px;display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap">'+media+
    '<div class="sub">'+(res.video?'<a href="/api/video/latest" download="video.mp4">video.mp4 indir</a><br>':'')+
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
  document.getElementById('cards').innerHTML=`
   <div class="card"><div class="label">Fırsat Skoru</div><div class="value">${{s.avg_score??0}}</div></div>
   <div class="card"><div class="label">Video</div><div class="value">${{s.videos??0}}</div></div>
   <div class="card"><div class="label">Affiliate Link</div><div class="value">${{s.total_affiliate_links??0}}</div></div>
   <div class="card"><div class="label">Linki Olmayan</div><div class="value">${{s.videos_without_links??0}}</div></div>`;
  if(j.videos && j.videos.length){{
    document.getElementById('videos').innerHTML=`<table><tr><th>Video</th><th>Skor</th><th>Affil.</th>
     <th>Disclosure</th><th>Shopping</th></tr>`+
     j.videos.map(v=>`<tr><td><a href="https://www.youtube.com/watch?v=${{v.video_id}}" target="_blank">${{(v.title||'').slice(0,60)}}</a>
       <div class="sub">${{v.views||0}} izlenme</div></td>
      <td>${{bar(v.opportunity_score)}}</td><td>${{(v.affili||[]).length}}</td>
      <td>${{v.disc?'<span class="badge ok">var</span>':(v.affili&&v.affili.length?'<span class="badge bad">yok</span>':'<span class="badge warn">-</span>')}}</td>
      <td>${{v.shop||0}}</td></tr>`).join('')+`</table>`;
  }}
  if(j.ai && j.ai.length){{
    document.getElementById('ai').innerHTML=`<table><tr><th>Sorgu</th><th>Google</th><th>YouTube</th>
      <th>Bing</th><th>DDG</th><th>Skor</th></tr>`+
      j.ai.map(c=>`<tr><td class="sub">${{(c.query||'').slice(0,50)}}</td>`+
        c.engines.map(e=>`<td>${{e.ok?(e.found?'<span class="badge ok">#'+e.rank+(e.in_ai?'+AI':'')+'</span>':'<span class="badge warn">yok</span>'):'<span class="badge bad">hata</span>'}}</td>`).join('')+
        `<td>${{bar(c.score)}}</td></tr>`).join('')+`</table>`;
  }}
}}
poll(); setInterval(poll,4000);
</script></body></html>"""


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
        "quota": quota.summary_line(),
        "licensed": quota.is_licensed(),
        "video": {
            "busy": STATE.video_busy,
            "log": STATE.video_log,
            "result": STATE.video_result,
        },
    }


def _run_scan(target: str, keywords: str, limit: int) -> None:
    import subprocess
    import sys

    STATE.busy = True
    STATE.finished = False
    STATE.log = f"Tarama başladı: {target}"
    cmd = [sys.executable, "-m", "tubelens", "scan", target, "--limit", str(limit)]
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
    cmd = [sys.executable, "-m", "tubelens", "video", str(params.get("topic", "")), "--out", str(out_dir)]
    if params.get("lang"):
        cmd += ["--lang", str(params["lang"])]
    if params.get("duration"):
        cmd += ["--duration", str(int(params["duration"]))]
    if params.get("aspect"):
        cmd += ["--aspect", str(params["aspect"])]
    if params.get("resolution"):
        cmd += ["--resolution", str(int(params["resolution"]))]
    if params.get("style"):
        cmd += ["--style", str(params["style"])]
    if params.get("footage_dir"):
        cmd += ["--footage-dir", str(params["footage_dir"])]
    if params.get("pexels_key"):
        cmd += ["--pexels-key", str(params["pexels_key"])]
    if params.get("script_only"):
        cmd += ["--script-only"]
    STATE.video_log = f"Video üretimi başladı: {params.get('topic', '')}"
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
            "ok": proc.returncode == 0 and video.exists(),
            "dir": str(out_dir),
            "video": video.exists(),
            "title": meta.get("title", ""),
            "duration": meta.get("duration_sec", 0),
            "error": "" if proc.returncode == 0 else (out[-600:] or "bilinmeyen hata"),
        }
    except subprocess.TimeoutExpired:
        STATE.video_result = {"ok": False, "dir": str(out_dir), "video": False,
                              "title": "", "duration": 0, "error": "Zaman aşımı (30 dk)"}
    except Exception as exc:  # noqa: BLE001
        STATE.video_result = {"ok": False, "dir": str(out_dir), "video": False,
                              "title": "", "duration": 0, "error": str(exc)}
    finally:
        STATE.video_busy = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # suskun
        pass

    def _send(self, body: bytes, ctype: str = "text/html; charset=utf-8", code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
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
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
            self.send_header("Content-Length", str(len(chunk)))
            self.end_headers()
            self.wfile.write(chunk)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/scan", "/api/video"):
            self._send(b"404", code=404)
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

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
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
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
