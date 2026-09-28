#!/usr/bin/env bash
# TubeLens panel video API'si — isteğe bağlı HTTP arayüzü örneği.
# Önce paneli başlat:  python -m tubelens panel --no-browser
# Pexels anahtarın yoksa footage_dir alanını doldur (yerel görüntüler).

BASE="http://127.0.0.1:8787"

# 1) Video üretimini başlat
curl -s -X POST "$BASE/api/video" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Sabah koşusunun 7 faydası",
    "lang": "tr",
    "duration": 45,
    "aspect": "9:16",
    "resolution": 720,
    "style": "enerjik",
    "footage_dir": "",
    "pexels_key": "",
    "script_only": false
  }'
# -> {"ok": true}

# 2) İlerleme ve sonuç (video.busy false olana kadar tekrarla)
curl -s "$BASE/api/state"
# -> { ..., "video": { "busy": true, "log": "...", "result": null } }

# 3) Üretilen video (HTTP Range destekli, seek çalışır)
curl -OJ "$BASE/api/video/latest"      # video.mp4 indir
curl -OJ "$BASE/api/video/srt"         # subtitles.srt indir
