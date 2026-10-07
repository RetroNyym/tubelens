"""webimg.py birim testleri (ag gerektirmez)."""

from tubelens import webimg


def test_clean_query_collapses_and_trims():
    assert webimg._clean_query("  fazla   bosluklu   sorgu  ") == "fazla bosluklu sorgu"
    assert len(webimg._clean_query("x" * 500)) == 160
    assert webimg._clean_query("") == ""


def test_blocked_rejects_watermark_and_bad_ext():
    assert webimg._blocked("https://example.shutterstock.com/large.jpg")
    assert webimg._blocked("https://cdn.site.com/anim.svg")
    assert webimg._blocked("https://cdn.site.com/clip.gif")
    assert not webimg._blocked("https://live.staticflickr.com/photo.jpg")


def test_looks_like_image_magic_bytes():
    assert webimg._looks_like_image(b"\xff\xd8\xff\xe0rest")
    assert webimg._looks_like_image(b"\x89PNG\r\n\x1a\nrest")
    assert webimg._looks_like_image(b"RIFF\x00\x00\x00\x00WEBP")
    assert not webimg._looks_like_image(b"<html>reklam sayfasi</html>")
    assert not webimg._looks_like_image(b"")
