"""Lisans anahtari uretim/dogrulama testleri (cevrimdisi)."""

import time

import pytest

from tubelens import cli, quota


def test_generate_unlimited_roundtrip():
    key = quota.generate_key(days=0)
    assert key.startswith("TL1-")
    payload = quota.validate_key(key)
    assert payload["exp"] == 0


def test_generate_timed_roundtrip():
    key = quota.generate_key(days=30)
    payload = quota.validate_key(key)
    assert payload["exp"] > time.time()


def test_generated_keys_unique():
    keys = {quota.generate_key(days=365) for _ in range(20)}
    assert len(keys) == 20


def test_tampered_key_rejected():
    key = quota.generate_key(days=0)
    tampered = key[:-1] + ("X" if key[-1] != "X" else "Y")
    with pytest.raises(ValueError):
        quota.validate_key(tampered)


def test_malformed_key_rejected():
    with pytest.raises(ValueError):
        quota.validate_key("TL1-yalniz-bir-parca")


def test_keygen_console_count(capsys):
    rc = cli.main(["keygen", "--count", "3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("TL1-") == 3


def test_keygen_csv_batch_and_append(tmp_path, capsys):
    csv_path = tmp_path / "keys.csv"
    rc = cli.main(["keygen", "--count", "5", "--days", "365", "--csv", str(csv_path)])
    assert rc == 0
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 6  # baslik + 5 anahtar
    assert lines[0].startswith("key,days")
    assert ",365," in lines[1]

    rc = cli.main(["keygen", "--count", "2", "--csv", str(csv_path)])
    assert rc == 0
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 8  # eklenmis hali: baslik + 5 + 2

    # CSV'deki anahtarlari dogrula
    for row in lines[1:]:
        quota.validate_key(row.split(",")[0])
