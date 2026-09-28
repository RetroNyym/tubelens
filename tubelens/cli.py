"""TubeLens CLI.

Komutlar:
  python -m tubelens scan <video-url|kanal> [--keywords a,b,c]
  python -m tubelens report
  python -m tubelens panel
  python -m tubelens status            kalan ücretsiz sorgu hakkı
  python -m tubelens activate <ANAHTAR> pro lisansını açar (LemonSqueezy veya yerel)
  python -m tubelens deactivate        lisansı bu bilgisayardan kaldırır
  python -m tubelens keygen [--days N] satıcı için lisans anahtarı üretir
  python -m tubelens video <KONU>      MPT tarzı tam video üretimi (senaryo+görüntü+ses+altyazı)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from . import brand, config, quota, shopping, storage
from .config import ensure_dirs
from .license import LicenseError
from .search import run_checks
from .youtube import YouTubeError, get_channel_title, get_channel_videos, get_video


def _default_keywords(video: dict) -> list[str]:
    """Baslik ve one cikan anahtar kelimelerden varsayilan sorgular."""
    words = [w for w in (video.get("keywords") or [])[:6]]
    title = video.get("title", "")
    queries = []
    if title:
        queries.append(title)
        if len(title.split()) > 4:
            queries.append(" ".join(title.split()[:5]))
    for word in words:
        if word and word.lower() not in {q.lower() for q in queries}:
            queries.append(word)
    return queries[:5]


def cmd_scan(args: argparse.Namespace) -> int:
    ensure_dirs()
    store = storage.load()
    target = args.target
    kw_source = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else []

    # lisans bayatligini gerekirse yenile (en fazla 7 gunde bir tek istek)
    if quota.is_licensed():
        note = quota.refresh()
        if note:
            print(f"[i] Lisans: {note}")

    # kota on kontrolu: uzun kanal cekimine girmeden once haber ver
    quota_locked = False
    if kw_source:
        left = quota.remaining()
        if left == 0:
            try:
                quota.ensure(len(kw_source))
            except quota.QuotaExceeded as exc:
                print(f"[!] AI sorgu hakkı yetersiz:\n{exc}", file=sys.stderr)
                print("    Video/affiliate analizi yine de çalışır (AI adımı atlandı).", file=sys.stderr)
            quota_locked = True
            kw_source = []
        elif left < len(kw_source):
            print(
                f"[!] Hakkınız {left} sorgu; {len(kw_source)} anahtar kelime içinden "
                f"ilk {left} tanesi kontrol edilecek.",
                file=sys.stderr,
            )
            kw_source = kw_source[:left]

    # kanal mi video mu?
    videos: list[dict] = []
    channel_name = target
    if any(s in target for s in ("youtube.com/@", "youtube.com/channel/", "youtube.com/c/")) or (
        target.startswith("@")
    ):
        print(f"[1/3] Kanal videolari cekiliyor: {target}")
        try:
            items = get_channel_videos(target, limit=args.limit)
        except YouTubeError as exc:
            print(f"  HATA: {exc}", file=sys.stderr)
            return 2
        if not items:
            print(
                f"  UYARI: {target} icin video bulunamadi "
                "(kanal yeni/gizli olabilir ya da YouTube arayuzu degismis olabilir).",
                file=sys.stderr,
            )
            return 3
        for i, item in enumerate(items, 1):
            print(f"  ({i}/{len(items)}) {item['title'][:60]}")
            try:
                videos.append(get_video(item["url"]))
            except YouTubeError as exc:
                print(f"    atlandi: {exc}", file=sys.stderr)
        if not videos:
            print("  UYARI: hicbir videonun detayi cekilemedi.", file=sys.stderr)
            return 3
        # kanal adini ilk videonun uzerinden al (yoksa ek istek yap)
        channel_name = videos[0].get("channel") or ""
        if not channel_name:
            try:
                channel_name = get_channel_title(target)
            except YouTubeError:
                channel_name = target
    else:
        print(f"[1/3] Video verisi cekiliyor: {target}")
        try:
            videos.append(get_video(target))
        except YouTubeError as exc:
            print(f"  HATA: {exc}", file=sys.stderr)
            return 2
        channel_name = videos[0].get("channel") or target

    print(f"[2/3] Affiliate / shopping analizi ({len(video_list(videos))} video)")
    analyses = [shopping.analyze(v) for v in videos]
    summary = shopping.channel_summary(analyses)

    # keyword listesi (kota on kontrolu yukarida yapildi)
    ai_checks = []
    if quota_locked:
        print("[3/3] AI kontrolü kilitli - lisans anahtarıyla açabilirsiniz")
    elif kw_source:
        print(f"[3/3] AI gorunurluk kontrolu ({len(kw_source)} anahtar kelime)")
        for v in videos[:1]:
            for kw in kw_source:
                print(f"  * {kw}")
                ai_checks.append(run_checks(kw, v))
        if ai_checks:
            quota.consume(len(ai_checks), label=target)
    else:
        print("[3/3] AI kontrolu atlandi (keywords verilmedi)")

    # kaydet
    for v, a in zip(videos, analyses):
        record = dict(v)
        record["analysis"] = a
        storage.upsert_video(store, record)
    for check in ai_checks:
        storage.add_ai_check(store, check)
    storage.add_run(store, {"channel": channel_name, "videos": len(videos), "ai_checks": len(ai_checks)})
    storage.save(store)

    # rapor
    from .report import build_report

    payload = {
        "channel": channel_name,
        "videos": analyses,
        "ai": ai_checks,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    path = build_report(payload)
    print()
    print("=" * 60)
    print(f"Video: {len(videos)}  |  Firsat skoru: {summary.get('avg_score',0)}")
    print(f"Affiliate link: {summary.get('total_affiliate_links',0)}  |  "
          f"Hiç linki olmayan video: {summary.get('videos_without_links',0)}  |  "
          f"Disclosure eksik: {summary.get('videos_missing_disclosure',0)}")
    print(f"Rapor: {path}")
    print(f"Kota : {quota.summary_line()}")
    print("=" * 60)
    return 0


def cmd_clone(args: argparse.Namespace) -> int:
    """Rakip videonun yapisini ogrenip ozgun klon senaryosu uretir.

    Cikti: data/clone_draft.json  -> `video --script-file` veya panel Klonla akisi kullanir.
    """
    ensure_dirs()
    from . import llm, youtube

    print(f"[1/3] Kaynak video cekiliyor: {args.url}")
    try:
        source = youtube.get_video(args.url)
    except youtube.YouTubeError as exc:
        print(f"  HATA: {exc}", file=sys.stderr)
        return 2
    print(f"      {source.get('title', '')[:70]} ({source.get('views', 0)} izlenme)")

    print("[2/3] Transcript aliniyor (best effort)")
    try:
        transcript = youtube.get_transcript(args.url, lang=args.lang)
    except youtube.YouTubeError:
        transcript = ""
    print(
        f"      {len(transcript)} karakter"
        + ("" if transcript else " (yok - basliga gore klonlanacak)")
    )

    duration = args.duration
    if not duration:
        length = int(source.get("length_seconds") or 45)
        duration = max(30, min(180, round(length * 0.9)))
    source["transcript"] = transcript

    print(f"[3/3] Klon senaryo uretiliyor (ayni yapi + ozgun aci, ~{duration} sn)")
    try:
        script = llm.clone_script(source, aspect=args.aspect, duration=duration, lang=args.lang)
    except llm.LLMError as exc:
        print(f"  HATA: {exc}", file=sys.stderr)
        return 3

    draft = {
        "source": {
            "id": source.get("id", ""),
            "url": source.get("url", ""),
            "title": source.get("title", ""),
            "channel": source.get("channel", ""),
            "views": source.get("views", 0),
        },
        "script": script,
        "aspect": args.aspect,
        "duration": duration,
        "lang": args.lang,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    path = config.DATA_DIR / "clone_draft.json"
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=" * 60)
    print(f"Kaynak  : {draft['source']['title'][:60]}")
    print(f"Klon    : {script['title']}")
    print(f"Senaryo : {len(script['script'].split())} kelime | {len(script['paragraphs'])} paragraf")
    print(f"Draft   : {path}")
    print(
        f"Uretim  : python -m tubelens video \"{script['title']}\" "
        f"--script-file {path} --aspect {args.aspect} --duration {duration}"
    )
    print("=" * 60)
    return 0


def video_list(videos: list) -> list:
    return videos


def cmd_report(_args: argparse.Namespace) -> int:
    from .report import build_report

    store = storage.load()
    videos = []
    analyses = []
    for v in store.get("videos", {}).values():
        a = v.get("analysis")
        if a:
            analyses.append(a)
    if not analyses:
        print("Kayitli analiz yok. Once `python -m tubelens scan <url>` calistirin.")
        return 1
    channel = store.get("runs", [{}])[-1].get("channel", "kayitli kanal") if store.get("runs") else "kayitli kanal"
    payload = {
        "channel": channel,
        "videos": analyses,
        "ai": store.get("ai_checks", []),
        "summary": shopping.channel_summary(analyses),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    path = build_report(payload)
    print(f"Rapor uretildi: {path}")
    return 0


def cmd_panel(args: argparse.Namespace) -> int:
    from .panel import serve

    serve(host="127.0.0.1", port=8787, open_browser=not args.no_browser)
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    print(quota.status_text())
    return 0


def cmd_activate(args: argparse.Namespace) -> int:
    try:
        lic = quota.activate(args.key)
    except (ValueError, LicenseError) as exc:
        print(f"Lisans hatalı: {exc}", file=sys.stderr)
        if not str(args.key).strip().startswith("TL1-"):
            print(
                "  (Bu anahtar bir ürün anahtarı ise LemonSqueezy'den doğrulandı; "
                "internet bağlantısını kontrol edin.)",
                file=sys.stderr,
            )
        return 4
    mode = "çevrimdışı" if lic.get("mode") != "online" else "LemonSqueezy üzerinden"
    print(f"Lisans aktif edildi (PRO · {mode}).")
    print(f"  anahtar sonu: ...{lic.get('key_suffix','')}")
    print(quota.status_text())
    return 0


def cmd_deactivate(_args: argparse.Namespace) -> int:
    ok, msg = quota.deactivate()
    print(msg)
    print(quota.status_text())
    return 0 if ok else 4


def cmd_keygen(args: argparse.Namespace) -> int:
    count = max(1, int(args.count or 1))
    keys = [quota.generate_key(days=args.days) for _ in range(count)]
    for key in keys:
        quota.validate_key(key)  # uretim aninda donus dogrulamasi
    validity = f"{args.days} gun" if args.days else "sinirsiz"
    if args.csv:
        import csv as _csv

        path = Path(args.csv)
        path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not path.exists() or path.stat().st_size == 0
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = _csv.writer(fh)
            if new_file:
                writer.writerow(["key", "days", "generated_at", "status"])
            for key in keys:
                writer.writerow([key, args.days or "unlimited", stamp, "new"])
        print(f"{len(keys)} anahtar yazildi: {path} (gecerlilik: {validity})")
        print("Musteri aktivasyonu: python -m tubelens activate <ANAHTAR>")
    else:
        for key in keys:
            print(key)
        print(f"({len(keys)} anahtar, gecerlilik: {validity})")
    return 0


def _slugify(text: str, max_len: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "video"


def _signed_description(description: str) -> str:
    """YouTube aciklamasinin sonuna urun imzasini ekler (mevcutsa tekrarlamaz)."""
    desc = (description or "").strip()
    if brand.SIGNATURE_LINE in desc:
        return desc
    if desc:
        return f"{desc}\n\n{brand.SIGNATURE_LINE}"
    return brand.SIGNATURE_LINE


def cmd_video(args: argparse.Namespace) -> int:
    """MoneyPrinterTurbo tarzi tam video uretim hatti (kit icinde, anahtarsiz)."""
    ensure_dirs()
    from . import assemble, footage, llm, voice

    vconf = config.load_video_config()
    key_fields = {
        "pexels_api_key": args.pexels_key,
        "pixabay_api_key": args.pixabay_key,
        "openai_api_key": args.openai_key,
        "elevenlabs_api_key": args.elevenlabs_key,
    }
    changed = False
    for field, value in key_fields.items():
        if value:
            vconf[field] = value.strip()
            changed = True
    if changed:
        config.save_video_config(vconf)
        print("[i] Anahtar(lar) kaydedildi (data/video_config.json)")
    pexels_key = (args.pexels_key or vconf.get("pexels_api_key") or "").strip()
    pixabay_key = (args.pixabay_key or vconf.get("pixabay_api_key") or "").strip()
    openai_key = (args.openai_key or vconf.get("openai_api_key") or "").strip()
    elevenlabs_key = (args.elevenlabs_key or vconf.get("elevenlabs_api_key") or "").strip()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Senaryo: dosyadan (klon/clone_draft) veya LLM ile
    script: dict = {}
    if args.script_file:
        spath = Path(args.script_file)
        try:
            draft = json.loads(spath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  HATA: script-file okunamadi: {exc}", file=sys.stderr)
            return 2
        script = draft.get("script") if isinstance(draft.get("script"), dict) else draft
        if not isinstance(script, dict) or not script.get("script"):
            print("  HATA: script-file gecerli senaryo icerigi icermiyor", file=sys.stderr)
            return 2
        if not args.topic:
            args.topic = str(script.get("title") or "klon-senaryo")
        print(f"[1/5] Senaryo dosyadan yuklendi: {spath.name} (LLM adimi atlandi)")
    else:
        print(f"[1/5] Senaryo uretiliyor (Pollinations - anahtarsiz): {args.topic}")
        try:
            script = llm.generate_script(
                args.topic,
                lang=args.lang,
                duration=args.duration,
                aspect=args.aspect,
                style=args.style,
                api_key=str(vconf.get("pollinations_api_key") or ""),
            )
        except llm.LLMError as exc:
            print(f"  HATA: {exc}", file=sys.stderr)
            return 2

    out_dir = (
        Path(args.out)
        if args.out
        else config.VIDEO_DIR / f"{stamp}-{_slugify(args.topic)}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "script.json").write_text(
        json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "script.txt").write_text(script["script"], encoding="utf-8")
    print(f"      Baslik: {script['title']}")

    if args.script_only:
        (out_dir / "meta.json").write_text(
            json.dumps(
                {
                    "title": script["title"],
                    "description": _signed_description(script.get("description", "")),
                    "tags": script.get("tags", []),
                    "hashtags": script.get("hashtags", []),
                    "duration_sec": 0,
                    "tts_engine": "",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Senaryo hazir: {out_dir}")
        return 0

    clip_count = args.clips or max(4, min(10, round(args.duration / 4)))
    print(f"[2/5] Goruntuler hazirlaniyor ({clip_count} klip, kaynak zinciri)")
    try:
        clips = footage.gather(
            script["video_terms"],
            pexels_key=pexels_key,
            pixabay_key=pixabay_key,
            footage_dir=args.footage_dir,
            dest_dir=out_dir / "assets",
            count=clip_count,
            aspect=args.aspect,
            allow_ai=not args.no_ai_visuals,
        )
    except footage.FootageError as exc:
        print(f"  HATA: {exc}", file=sys.stderr)
        return 3
    print(f"      {len(clips)} klip hazir")

    engine = (args.tts_engine or "edge").lower()
    voice_name = args.voice or (voice.default_voice(args.lang) if engine == "edge" else "")
    audio_path = out_dir / "audio.mp3"
    print(f"[3/5] Seslendirme (motor={engine}): {voice_name or 'varsayilan ses'}")
    try:
        words = voice.synthesize(
            script["script"],
            audio_path,
            voice_name or None,
            engine=engine,
            lang=args.lang,
            openai_key=openai_key,
            elevenlabs_key=elevenlabs_key,
            model=args.tts_model or "",
        )
    except voice.VoiceError as exc:
        print(f"  HATA: {exc}", file=sys.stderr)
        return 4

    print("[4/5] Altyazi zamanlamasi")
    srt_text = ""
    if args.no_subs:
        print("      atlandi (--no-subs)")
    elif not words:
        print("      uyari: kelime zamanlamasi yok, altyazi atlandi")
    else:
        srt_text = assemble.words_to_srt(words)
        print(f"      {srt_text.count('-->')} altyazi parcasi")

    print(f"[5/5] Montaj (ffmpeg {args.aspect} @{args.resolution}p)")
    final_path = out_dir / "video.mp4"
    work_dir = out_dir / "work"
    try:
        _, duration = assemble.render(
            clips,
            audio_path,
            final_path,
            aspect=args.aspect,
            resolution=args.resolution,
            srt_text=srt_text,
            bgm=Path(args.bgm) if args.bgm else None,
            bgm_volume=args.bgm_volume,
            work_dir=work_dir,
            logo=None if getattr(args, "no_logo", False) else brand.ensure_logo_png(),
        )
    except assemble.AssemblyError as exc:
        print(f"  HATA: {exc}", file=sys.stderr)
        print(f"      Ara dosyalar silinmedi: {work_dir}", file=sys.stderr)
        return 5

    meta = {
        "topic": args.topic,
        "title": script["title"],
        "description": _signed_description(script["description"]),
        "tags": script["tags"],
        "hashtags": script["hashtags"],
        "video_terms": script["video_terms"],
        "aspect": args.aspect,
        "resolution": args.resolution,
        "voice": voice_name or engine,
        "tts_engine": engine,
        "duration_sec": round(duration, 2),
        "clips": [c.name for c in clips],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    import shutil

    shutil.rmtree(work_dir, ignore_errors=True)

    print()
    print("=" * 60)
    print(f"Video : {final_path}")
    print(f"Sures : {duration:.1f} sn | Format: {args.aspect} @{args.resolution}p | Ses: {engine}/{voice_name or 'varsayilan'}")
    print(f"Baslik: {script['title']}")
    print(f"Meta  : {out_dir / 'meta.json'} (YouTube baslik/aciklama/etiketler)")
    if not args.no_subs:
        print(f"Altyazi: {out_dir / 'subtitles.srt'}")
    print("=" * 60)
    return 0


_DASH_COMMANDS = {
    "clone": {"--lang", "--aspect", "--duration"},
    "scan": {"--keywords", "--limit"},
}


def _fix_dash_positional(argv: list[str]) -> list[str]:
    """'-kX...' gibi gorunen video ID'lerinin option sanilmasini onler.

    YouTube ID'ler '-' ile baslayabilir; argparse bunlari taninmayan option
    sanir. clone/scan komutlarinda boyle bir ID tespit edilirse option'lar
    one alinir ve ID, '--' ayiricisi arkasina yerlestirilir.
    """
    if not argv or argv[0] not in _DASH_COMMANDS:
        return argv
    options = _DASH_COMMANDS[argv[0]]
    option_parts: list[str] = []
    positionals: list[str] = []
    i = 1
    while i < len(argv):
        token = argv[i]
        if token in options and i + 1 < len(argv):
            option_parts.append(token)
            option_parts.append(argv[i + 1])
            i += 2
            continue
        if token.startswith("--"):
            option_parts.append(token)
            i += 1
            continue
        positionals.append(token)
        i += 1
    has_dash_id = any(p.startswith("-") and not p.startswith("--") for p in positionals)
    if not has_dash_id:
        return argv
    return [argv[0]] + option_parts + ["--"] + positionals


def main(argv: list[str] | None = None) -> int:
    # Windows konsolu (cp1254/TR) UTF-8 karakterleri basamayabiliyor
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    argv = _fix_dash_positional(list(sys.argv[1:] if argv is None else argv))

    from . import __version__

    parser = argparse.ArgumentParser(
        prog="tubelens",
        description="YouTube AI görünürlük + affiliate denetçisi + video üretim kiti",
    )
    parser.add_argument("--version", action="version", version=f"tubelens {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="video veya kanal analiz et")
    p_scan.add_argument("target", help="video URL, video ID veya @kanal")
    p_scan.add_argument("--keywords", help="AI kontrolü için virgülle ayrılmış kelimeler")
    p_scan.add_argument("--limit", type=int, default=10, help="kanal tarama limiti (varsayılan 10)")
    p_scan.set_defaults(func=cmd_scan)

    p_rep = sub.add_parser("report", help="kayıtlı veriden HTML rapor üret")
    p_rep.set_defaults(func=cmd_report)

    p_panel = sub.add_parser("panel", help="yerel web panelini aç (127.0.0.1:8787)")
    p_panel.add_argument("--no-browser", action="store_true", help="tarayıcıyı otomatik açma")
    p_panel.set_defaults(func=cmd_panel)

    p_status = sub.add_parser("status", help="kalan ücretsiz sorgu hakkı / lisans bilgisi")
    p_status.set_defaults(func=cmd_status)

    p_act = sub.add_parser("activate", help="pro lisans anahtarını aktif et")
    p_act.add_argument("key", help="TL1-... yerel anahtar veya ürün anahtarı")
    p_act.set_defaults(func=cmd_activate)

    p_deact = sub.add_parser("deactivate", help="lisansı bu bilgisayardan kaldır")
    p_deact.set_defaults(func=cmd_deactivate)

    p_key = sub.add_parser("keygen", help="satıcı: lisans anahtarı üret")
    p_key.add_argument("--days", type=int, default=0, help="geçerlilik gün (0 = sınırsız)")
    p_key.add_argument("--count", type=int, default=1, help="üretilecek anahtar sayısı (varsayılan 1)")
    p_key.add_argument("--csv", help="anahtarları CSV dosyasına ekle (müşteriye gönderim listesi)")
    p_key.set_defaults(func=cmd_keygen)

    p_clone = sub.add_parser(
        "clone", help="rakip videonun yapısını klonlayıp özgün senaryo üret"
    )
    p_clone.add_argument("url", help="kaynak video URL veya ID")
    p_clone.add_argument("--lang", default="tr", help="senaryo dili (varsayılan tr)")
    p_clone.add_argument(
        "--aspect", choices=["9:16", "16:9", "1:1"], default="9:16", help="video formatı"
    )
    p_clone.add_argument(
        "--duration", type=int, default=0,
        help="hedef süre sn (0 = kaynak videonun süresine göre)",
    )
    p_clone.set_defaults(func=cmd_clone)

    p_video = sub.add_parser(
        "video",
        help="MPT tarzı tam video üret (senaryo + görüntü + ses + altyazı)",
    )
    p_video.add_argument(
        "topic", nargs="?", default="", help="video konusu / başlık fikri (--script-file ile opsiyonel)"
    )
    p_video.add_argument(
        "--script-file",
        help="senaryoyu dosyadan oku (LLM adımını atlar; örn. data/clone_draft.json)",
    )
    p_video.add_argument("--lang", default="tr", help="senaryo dili (varsayılan tr)")
    p_video.add_argument(
        "--duration", type=int, default=45, help="hedef seslendirme süresi (sn)"
    )
    p_video.add_argument(
        "--aspect", choices=["9:16", "16:9", "1:1"], default="9:16", help="video formatı"
    )
    p_video.add_argument(
        "--resolution", type=int, choices=[720, 1080], default=1080, help="çözünürlük"
    )
    p_video.add_argument("--voice", help="ses adı (Edge: tr-TR-EmelNeural, OpenAI: alloy, ElevenLabs: voice_id)")
    p_video.add_argument(
        "--tts-engine",
        choices=["edge", "gtts", "openai", "elevenlabs"],
        default="edge",
        help="seslendirme motoru (edge/gtts anahtarsız, openai/elevenlabs anahtarlı; varsayılan edge)",
    )
    p_video.add_argument("--tts-model", help="OpenAI TTS modeli (varsayılan gpt-4o-mini-tts)")
    p_video.add_argument("--style", help="ton/istil (örn. belgesel, hızlı, eğlenceli)")
    p_video.add_argument("--clips", type=int, default=0, help="görüntü klip sayısı (0 = oto)")
    p_video.add_argument("--footage-dir", help="kendi görüntülerinizin klasörü")
    p_video.add_argument("--pexels-key", help="Pexels API anahtarı (ücretsiz, kaydedilir)")
    p_video.add_argument("--pixabay-key", help="Pixabay API anahtarı (ücretsiz, kaydedilir)")
    p_video.add_argument("--openai-key", help="OpenAI API anahtarı (OpenAI TTS için, kaydedilir)")
    p_video.add_argument("--elevenlabs-key", help="ElevenLabs API anahtarı (kaydedilir)")
    p_video.add_argument("--no-ai-visuals", action="store_true", help="anahtarsız AI görsel fallback'ini kapat")
    p_video.add_argument("--bgm", help="arka plan müziği dosyası")
    p_video.add_argument("--bgm-volume", type=float, default=0.12, help="müzik sesi (0-1)")
    p_video.add_argument("--no-subs", action="store_true", help="altyazı üretme")
    p_video.add_argument("--no-logo", action="store_true", help="marka filigranını videoya ekleme")
    p_video.add_argument("--script-only", action="store_true", help="sadece senaryo üret")
    p_video.add_argument("--out", help="çıktı klasörü (varsayılan videos/<zaman>-<slug>)")
    p_video.set_defaults(func=cmd_video)

    args = parser.parse_args(argv)
    if args.cmd == "video" and not args.topic and not args.script_file:
        parser.error("video için `topic` veya `--script-file` gerekli")
    return args.func(args)


def main_cli() -> None:
    """`tubelens` komut satiri girisi (pyproject [project.scripts])."""
    raise SystemExit(main())


if __name__ == "__main__":
    raise SystemExit(main())
