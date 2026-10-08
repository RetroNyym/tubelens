"""hf.py birim testleri (ag istegi yok; requests tamamen sahtelendirilir)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from tubelens import hf

JPEG = b"\xff\xd8\xff\xe0" + bytes(range(256)) * 8


class _Resp:
    def __init__(self, status: int = 200, content: bytes = JPEG, ctype: str = "image/jpeg"):
        self.status_code = status
        self.content = content
        self.headers = {"Content-Type": ctype}


class _StubRequests:
    """Sirayla donen yanitlari/hatalari veren sahte requests modulu."""

    RequestException = requests.RequestException

    def __init__(self, results: list):
        self.results = list(results)
        self.calls: list[dict] = []

    def post(self, url, headers=None, data=None, timeout=None, **kw):
        self.calls.append({"url": url, "headers": headers, "data": data, "timeout": timeout})
        idx = min(len(self.calls) - 1, len(self.results) - 1)
        item = self.results[idx]
        if isinstance(item, BaseException):
            raise item
        return item


def _payload(call: dict) -> dict:
    return json.loads(call["data"].decode("utf-8"))


def test_image_size_by_aspect():
    assert hf.image_size("9:16") == (768, 1344)
    assert hf.image_size("16:9") == (1344, 768)
    assert hf.image_size("1:1") == (1024, 1024)
    assert hf.image_size("4:3") == (1344, 1008)
    assert hf.image_size("3:4") == (1008, 1344)
    assert hf.image_size("bilmem") == (768, 1344)


def test_generate_image_uses_first_endpoint_and_writes(tmp_path, monkeypatch):
    stub = _StubRequests([_Resp()])
    monkeypatch.setattr(hf, "requests", stub)
    dest = tmp_path / "out.jpg"
    got = hf.generate_image("kahve, cinematic", dest, aspect="4:3", token="hf_abc")
    assert got == dest
    assert dest.read_bytes() == JPEG
    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call["url"] == hf.ENDPOINTS[0]
    assert call["headers"]["Authorization"] == "Bearer hf_abc"
    assert _payload(call)["parameters"] == {
        "width": 1344,
        "height": 1008,
        "num_inference_steps": 4,
    }


def test_generate_image_falls_through_to_next_endpoint(tmp_path, monkeypatch):
    stub = _StubRequests(
        [
            _Resp(status=503, content=b"busy", ctype="text/plain"),
            requests.ConnectionError("yok"),
            _Resp(),
        ]
    )
    monkeypatch.setattr(hf, "requests", stub)
    dest = tmp_path / "sub" / "gorsel.png"
    got = hf.generate_image("deneme", dest, aspect="3:4", token="t")
    assert got == dest
    assert dest.exists() and dest.read_bytes() == JPEG
    assert [c["url"] for c in stub.calls] == list(hf.ENDPOINTS[:3])


def test_generate_image_missing_token_raises(tmp_path, monkeypatch):
    stub = _StubRequests([_Resp()])
    monkeypatch.setattr(hf, "requests", stub)
    with pytest.raises(hf.HfImageError) as exc:
        hf.generate_image("kahve", tmp_path / "x.jpg", token="   ")
    assert "token" in str(exc.value).lower()
    assert stub.calls == []


def test_generate_image_all_endpoints_fail_raises(tmp_path, monkeypatch):
    stub = _StubRequests([_Resp(status=500, content=b"boom", ctype="text/plain")])
    monkeypatch.setattr(hf, "requests", stub)
    with pytest.raises(hf.HfImageError) as exc:
        hf.generate_image("kahve", tmp_path / "x.jpg", token="t")
    assert len(stub.calls) == len(hf.ENDPOINTS)
    assert "500" in str(exc.value)
    assert not (tmp_path / "x.jpg").exists()


def test_generate_image_invalid_token_stops_early(tmp_path, monkeypatch):
    stub = _StubRequests([_Resp(status=401, content=b"denied", ctype="application/json")])
    monkeypatch.setattr(hf, "requests", stub)
    with pytest.raises(hf.HfImageError) as exc:
        hf.generate_image("kahve", tmp_path / "x.jpg", token="gecersiz")
    assert len(stub.calls) == 1
    assert "401" in str(exc.value)


def test_generate_image_non_image_response_raises(tmp_path, monkeypatch):
    stub = _StubRequests(
        [_Resp(content=b'{"error":"kota"}', ctype="application/json") for _ in range(4)]
    )
    monkeypatch.setattr(hf, "requests", stub)
    with pytest.raises(hf.HfImageError):
        hf.generate_image("kahve", tmp_path / "x.jpg", token="t")
    assert len(stub.calls) == len(hf.ENDPOINTS)


def test_error_type_is_runtime_error():
    assert issubclass(hf.HfImageError, RuntimeError)
