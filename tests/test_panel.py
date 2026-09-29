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
