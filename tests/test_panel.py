"""Panel HTTP smoke testleri - yerel sunucu, ag disi, hizli."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from tubelens import panel


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), panel.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _get(url: str) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read(), dict(resp.headers)


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_index_lists_tabbed_kits(server):
    status, body, headers = _get(f"{server}/")
    text = body.decode("utf-8")
    assert status == 200
    assert "Video Üret" in text
    assert "Tarama" in text
    assert "Durum &amp; Lisans" in text
    assert "switchTab" in text
    assert "Cache-Control" in headers


def test_state_payload_shape(server):
    status, body, _ = _get(f"{server}/api/state")
    data = json.loads(body.decode("utf-8"))
    assert status == 200
    for key in ("log", "busy", "quota", "licensed", "video", "summary"):
        assert key in data
    assert "busy" in data["video"]
    assert "result" in data["video"]
    # klon + gelir kacagi USP alanlari
    assert "clone" in data and "draft" in data["clone"]
    assert "leak" in data and "total_leak" in data["leak"]


def test_index_has_usp_buttons(server):
    status, body, _ = _get(f"{server}/")
    text = body.decode("utf-8")
    assert status == 200
    assert "Klonla" in text  # tarama -> uretim hatti
    assert "$ Kaçak" in text  # gelir kacak sutunu
    assert "Panoya kopyala" in text  # aksiyon recetesi


def test_index_has_branding(server):
    status, body, _ = _get(f"{server}/")
    text = body.decode("utf-8")
    assert status == 200
    assert 'rel="icon"' in text  # favicon
    assert 'class="brand"' in text  # header logosu
    assert "<footer>" in text  # imza footer'i
    assert "vlogo" in text  # filigran checkbox
    assert "vscript" not in text  # "sadece senaryo" kaldirildi: uretim hep videoya gider
    assert "position:fixed;inset:0" in text  # tam ekran watermark kutusu
    assert "data:image/png;base64,iVBOR" in text  # RETRO+ gomulu watermark


def test_index_has_dual_download_links(server):
    """Altyazili + altyazisiz cift indirme secenegi panelde sunulur."""
    status, body, _ = _get(f"{server}/")
    text = body.decode("utf-8")
    assert status == 200
    assert "/api/video/nosubs" in text
    assert "video_no_subs.mp4" in text
    assert "altyazısız" in text
    # nosubs ucu kayitli: video yokken 404, varken 200
    try:
        status, _, _ = _get(f"{server}/api/video/nosubs")
    except urllib.error.HTTPError as exc:
        status = exc.code
    assert status in (200, 404)


def test_clone_requires_url(server):
    body = _post(f"{server}/api/clone", {})
    assert body["ok"] is False
    assert "URL" in body["error"] or "url" in body["error"]


def test_index_script_syntax(server):
    """Panel JS'i sozdizimi hatasi icin (tarayici sekme hatalarini onler)."""
    import re
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if node is None:
        import pytest

        pytest.skip("node yok")
    status, body, _ = _get(f"{server}/")
    assert status == 200
    match = re.search(rb"(?s)<script>(.*)</script>", body)
    assert match, "script blogu yok"
    with tempfile.NamedTemporaryFile("wb", suffix=".js", delete=False) as fh:
        fh.write(match.group(1))
        path = fh.name
    proc = subprocess.run([node, "--check", path], capture_output=True)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")


def test_video_requires_topic(server):
    body = _post(f"{server}/api/video", {"lang": "tr"})
    assert body["ok"] is False
    assert "konu" in body["error"]


def test_activate_requires_key(server):
    body = _post(f"{server}/api/activate", {})
    assert body["ok"] is False


def test_unknown_route_404(server):
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(f"{server}/yok")
    assert exc.value.code == 404

def test_upload_flow(server, tmp_path, monkeypatch):
    """PC'den foto yukleme: alani, liste + yukleme + silme uclari."""
    monkeypatch.setattr(panel, "UPLOAD_DIR", tmp_path)
    status, body, _ = _get(f"{server}/")
    text = body.decode("utf-8")
    assert status == 200
    assert "vupbtn" in text and "/api/upload" in text
    data = json.loads(_get(f"{server}/api/uploads")[1])
    assert data["files"] == []
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (255, 0, 0)).save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    body = _post(f"{server}/api/upload", {"files": [{"name": "foto_test.png", "data": b64}]})
    assert body["ok"] is True and body["saved"] == 1
    data = json.loads(_get(f"{server}/api/uploads")[1])
    assert data["files"] and data["files"][0]["name"] == "foto_test.png"
    assert (tmp_path / "foto_test.png").is_file()
    body = _post(f"{server}/api/upload/delete", {"name": "foto_test.png"})
    assert body["ok"] is True
    data = json.loads(_get(f"{server}/api/uploads")[1])
    assert data["files"] == []
    # path traversal denemesi engellenir
    body = _post(f"{server}/api/upload/delete", {"name": "../meta.json"})
    assert body["ok"] is False


def test_index_new_tabs_and_form_groups(server):
    """Yeni arayuz: 5 sekme, gruplu video formu, klip/avatar, galeri, durum aksiyonlari."""
    status, body, _ = _get(f"{server}/")
    text = body.decode("utf-8")
    assert status == 200
    assert "Klip &amp; Avatar" in text
    assert "Galeri &amp; Kuyruk" in text
    assert 'data-tab="modes"' in text and 'data-tab="gallery"' in text
    # grupli form alanlari
    for field_id in (
        "vpreset", "vclips", "vdurcustom", "vbgm", "vbgmvol", "vttsmodel",
        "vsubs", "cllang", "claspect", "cldur", "kprompt", "aimg", "atext",
    ):
        assert field_id in text, field_id
    assert "sinematik" in text          # stil preset
    assert "4:3" in text and "3:4" in text  # yeni aspektler
    assert "deactivate" in text         # lisans kaldirma butonu
    assert "Raporu yeniden oluştur" in text
    assert "Sağlayıcılar" in text


def test_state_payload_new_keys(server):
    status, body, _ = _get(f"{server}/api/state")
    data = json.loads(body.decode("utf-8"))
    assert status == 200
    for key in ("jobs", "gallery", "providers", "license_text", "action_log"):
        assert key in data, key
    assert isinstance(data["jobs"], list)
    assert isinstance(data["gallery"], list)
    for key in ("pexels", "pixabay", "hf", "viggle", "higgsfield", "hedra", "ltx"):
        assert key in data["providers"], key


def test_klip_requires_prompt(server):
    body = _post(f"{server}/api/klip", {})
    assert body["ok"] is False
    assert "prompt" in body["error"]


def test_avatar_requires_image_and_voice(server, tmp_path, monkeypatch):
    import base64

    body = _post(f"{server}/api/avatar", {})
    assert body["ok"] is False
    assert "görsel" in body["error"]
    # mevcut bir gorsel yukle, ses/metin yokken yine hata ver
    monkeypatch.setattr(panel, "UPLOAD_DIR", tmp_path / "photos")
    blob = base64.b64encode(b"\x89PNG" + b"\x00" * 32).decode()
    assert _post(
        f"{server}/api/upload", {"files": [{"name": "kanal.png", "data": blob}]}
    )["ok"] is True
    body = _post(f"{server}/api/avatar", {"image": "kanal.png"})
    assert body["ok"] is False
    assert "ses" in body["error"]


def test_audio_and_bgm_upload_flow(server, tmp_path, monkeypatch):
    import base64

    monkeypatch.setattr(panel, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(panel, "BGMDIR", tmp_path / "bgm")
    blob = base64.b64encode(b"ID3" + b"\x00" * 64).decode()
    body = _post(f"{server}/api/audio", {"files": [{"name": "ses.mp3", "data": blob}]})
    assert body["ok"] is True and body["saved"] == 1
    data = json.loads(_get(f"{server}/api/audio")[1])
    assert data["files"][0]["name"] == "ses.mp3"
    body = _post(f"{server}/api/bgm", {"files": [{"name": "muzik.mp3", "data": blob}]})
    assert body["ok"] is True
    data = json.loads(_get(f"{server}/api/bgm")[1])
    assert data["files"][0]["name"] == "muzik.mp3"
    # uzanti filtresi
    body = _post(f"{server}/api/audio", {"files": [{"name": "photo.png", "data": blob}]})
    assert body["ok"] is False
    # silme
    body = _post(f"{server}/api/audio/delete", {"name": "ses.mp3"})
    assert body["ok"] is True
    data = json.loads(_get(f"{server}/api/audio")[1])
    assert data["files"] == []


def test_gallery_list_and_file_guard(server, tmp_path, monkeypatch):
    from tubelens import config

    gal = tmp_path / "panel-klip-test"
    gal.mkdir()
    (gal / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 64)
    (gal / "meta.json").write_text(
        json.dumps({"mode": "klip", "title": "Deneme klip", "duration_sec": 4}),
        encoding="utf-8",
    )
    (gal / "subtitles.srt").write_text("1\n", encoding="utf-8")
    monkeypatch.setattr(config, "VIDEO_DIR", tmp_path)
    data = json.loads(_get(f"{server}/api/gallery")[1])
    items = data["items"]
    assert any(i["name"] == "panel-klip-test" and i["mode"] == "klip" for i in items)
    item = next(i for i in items if i["name"] == "panel-klip-test")
    assert item["title"] == "Deneme klip" and item["has_subs"] is True
    # dosya servisi
    status, body, _ = _get(f"{server}/api/gallery/panel-klip-test/video.mp4")
    assert status == 200 and body.startswith(b"\x00\x00\x00\x18")
    status, body, _ = _get(f"{server}/api/gallery/panel-klip-test/subtitles.srt")
    assert status == 200
    # izin disi dosya
    try:
        _get(f"{server}/api/gallery/panel-klip-test/script.json")
        raise AssertionError("404 beklenirdi")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
    # silme
    body = _post(f"{server}/api/gallery/delete", {"name": "panel-klip-test"})
    assert body["ok"] is True
    assert not gal.exists()


def test_video_enqueue_goes_through_queue(server, monkeypatch):
    import time

    executed: list[dict] = []

    def fake_execute(job):
        executed.append(dict(job))
        job["status"] = "done"

    monkeypatch.setattr(panel, "_execute_job", fake_execute)
    body = _post(f"{server}/api/video", {"topic": "kuyruk testi", "clips": 2})
    assert body["ok"] is True and "job" in body
    deadline = time.time() + 5
    while time.time() < deadline and not executed:
        time.sleep(0.05)
    assert [j["kind"] for j in executed] == ["video"]
    # params worker'a ulasir (topic + alanlar), yoksa CLI topic'siz calisir
    assert executed[0]["params"]["topic"] == "kuyruk testi"
    assert executed[0]["params"]["clips"] == 2
    # fakat state'te params sızdırılmaz (anahtar guvenligi)
    data = json.loads(_get(f"{server}/api/state")[1])
    assert all("params" not in j for j in data["jobs"])


def test_deactivate_and_report_actions(server, monkeypatch):
    import time

    calls: list[str] = []
    monkeypatch.setattr(panel, "_run_action", lambda a: calls.append(a))
    assert _post(f"{server}/api/deactivate", {})["ok"] is True
    assert _post(f"{server}/api/report", {})["ok"] is True
    deadline = time.time() + 5
    while time.time() < deadline and len(calls) < 2:
        time.sleep(0.05)
    assert calls == ["deactivate", "report"]


def test_preset_choices_wired():
    from tubelens import cli
    from tubelens.presets import PRESET_CHOICES, resolve

    choices = cli._preset_choices()
    assert choices == PRESET_CHOICES
    assert len(choices) == 6
    assert "sinematik" in resolve("sinematik", "hızlı")
    assert resolve("", "belgesel") == "belgesel"


def test_port_busy_detects_listener():
    import socket

    guard = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        guard.bind(("127.0.0.1", 0))
        guard.listen(1)
        occupied = guard.getsockname()[1]
        assert panel._port_busy("127.0.0.1", occupied) is True
    finally:
        guard.close()


def test_looks_like_tubelens_true(server):
    port = int(server.rsplit(":", 1)[1])
    assert panel._looks_like_tubelens("127.0.0.1", port) is True


def test_looks_like_tubelens_false_for_foreign_server():
    import threading
    from http.server import BaseHTTPRequestHandler

    class Foreign(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"other app")

        def log_message(self, *args) -> None:
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Foreign)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    try:
        assert panel._looks_like_tubelens("127.0.0.1", port) is False
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_pick_free_port_skips_occupied():
    import socket

    guard = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        guard.bind(("127.0.0.1", 0))
        guard.listen(1)
        occupied = guard.getsockname()[1]
        free = panel._pick_free_port("127.0.0.1", occupied)
        assert free is not None
        assert free != occupied
    finally:
        guard.close()


def test_pick_free_port_returns_none_when_all_busy(monkeypatch):
    monkeypatch.setattr(panel, "_port_busy", lambda host, port: True)
    assert panel._pick_free_port("127.0.0.1", 8787) is None


def test_serve_falls_back_to_next_port(monkeypatch, capsys):
    """Kapsanmis port TubeLens degilse panel sonraki bos porta tasinmali."""
    import threading
    from http.server import BaseHTTPRequestHandler

    class Foreign(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"other app")

        def log_message(self, *args) -> None:
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Foreign)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    occupied = httpd.server_address[1]

    bound_ports: list[int] = []

    class DummyServer:
        def __init__(self, addr, handler):
            bound_ports.append(addr[1])

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def shutdown(self) -> None:
            pass

    monkeypatch.setattr(panel, "ThreadingHTTPServer", DummyServer)
    try:
        panel.serve(host="127.0.0.1", port=occupied, open_browser=False)
    finally:
        httpd.shutdown()
        httpd.server_close()
    text = capsys.readouterr().out
    assert "tasindi" in text
    assert bound_ports and bound_ports[0] != occupied


def test_serve_reports_already_running(monkeypatch, capsys):
    """Zaten calisan panelde ikinci acilis yeni sunucu acmamali."""
    monkeypatch.setattr(panel, "_port_busy", lambda host, port: True)
    monkeypatch.setattr(panel, "_looks_like_tubelens", lambda host, port: True)
    opened: list[str] = []
    monkeypatch.setattr(panel.webbrowser, "open", lambda url: opened.append(url))

    def _fail_server(*args):
        raise AssertionError("yeni sunucu acilmamaliydi")

    monkeypatch.setattr(panel, "ThreadingHTTPServer", _fail_server)
    panel.serve(host="127.0.0.1", port=8787, open_browser=True)
    text = capsys.readouterr().out
    assert "zaten calisiyor" in text
    assert opened == ["http://127.0.0.1:8787"]
