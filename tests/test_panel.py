"""Panel HTTP smoke testleri - yerel sunucu, ag disi, hizli."""

from __future__ import annotations

import json
import threading
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
