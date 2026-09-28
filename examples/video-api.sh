#!/usr/bin/env bash
# TubeLens panel video API'si — isteğe bağlı HTTP arayüzü örneği.
# Önce paneli başlat:  python -m tubelens panel --no-browser
# Kaynak zinciri: lokal klasör > Pexels > Pixabay > anahtarsız AI görsel.
# Ses: edge/gtts anahtarsız; openai/elevenlabs API anahtarlı.

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
    "pixabay_key": "",
    "ai_visuals": true,
    "tts_engine": "edge",
    "voice": "",
    "openai_key": "",
    "elevenlabs_key": "",
    "script_only": false
  }'
# -> {"ok": true}

# 2) İlerleme ve sonuç (video.result dolu + video.busy false olana kadar tekrarla)
curl -s "$BASE/api/state"
# -> { ..., "video": { "busy": true, "log": "...", "result": null } }

# 3) Üretilen video (HTTP Range destekli, seek çalışır; cache-bust ?t= opsiyonel)
curl -OJ "$BASE/api/video/latest"      # video.mp4 indir
curl -OJ "$BASE/api/video/srt"         # subtitles.srt indir

# 4) Lisans aktivasyonu
curl -s -X POST "$BASE/api/activate" \
  -H "Content-Type: application/json" \
  -d '{"key": "TL1-xxxx-yyyy"}'
