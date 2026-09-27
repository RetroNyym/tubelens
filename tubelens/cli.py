"""TubeLens CLI.

Komutlar:
  python -m tubelens scan <video-url|kanal> [--keywords a,b,c]
  python -m tubelens report
  python -m tubelens panel
  python -m tubelens status            kalan ucretsiz sorgu hakki
  python -m tubelens activate <ANAHTAR> pro lisansini acar
  python -m tubelens keygen [--days N] satici icin lisans anahtari uretir
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from . import quota, shopping, storage
from .config import ensure_dirs
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

    # kota on kontrolu: uzun kanal cekimine girmeden once haber ver
    quota_locked = False
    if kw_source:
        left = quota.remaining()
        if left == 0:
            try:
                quota.ensure(len(kw_source))
            except quota.QuotaExceeded as exc:
                print(f"[!] AI sorgu hakki yetersiz:\n{exc}", file=sys.stderr)
                print("    Video/affiliate analizi yine de calisir (AI adimi atlandi).", file=sys.stderr)
            quota_locked = True
            kw_source = []
        elif left < len(kw_source):
            print(
                f"[!] Hakkiniz {left} sorgu; {len(kw_source)} anahtar kelime icinden "
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
        print("[3/3] AI kontrolu kilitli - lisans anahtariyla acabilirsiniz")
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
    except ValueError as exc:
        print(f"Lisans hatali: {exc}", file=sys.stderr)
        return 4
    print("Lisans aktif edildi (PRO).")
    print(f"  anahtar sonu: ...{lic.get('key_suffix','')}")
    print(quota.status_text())
    return 0


def cmd_keygen(args: argparse.Namespace) -> int:
    key = quota.generate_key(days=args.days)
    print(key)
    print(f"(gecerlilik: {args.days} gun)" if args.days else "(gecerlilik: sinirsiz)")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Windows konsolu (cp1254/TR) UTF-8 karakterleri basamayabiliyor
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(prog="tubelens", description="YouTube AI gorunurluk + affiliate araci")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="video veya kanal analiz et")
    p_scan.add_argument("target", help="video URL, video ID veya @kanal")
    p_scan.add_argument("--keywords", help="AI kontrolu icin virgulle ayrilmis kelimeler")
    p_scan.add_argument("--limit", type=int, default=10, help="kanal tarama limiti (varsayilan 10)")
    p_scan.set_defaults(func=cmd_scan)

    p_rep = sub.add_parser("report", help="kayitli veriden HTML rapor uret")
    p_rep.set_defaults(func=cmd_report)

    p_panel = sub.add_parser("panel", help="yerel web panelini ac (127.0.0.1:8787)")
    p_panel.add_argument("--no-browser", action="store_true", help="tarayiciyi otomatik acma")
    p_panel.set_defaults(func=cmd_panel)

    p_status = sub.add_parser("status", help="kalan ucretsiz sorgu hakki / lisans bilgisi")
    p_status.set_defaults(func=cmd_status)

    p_act = sub.add_parser("activate", help="pro lisans anahtarini aktif et")
    p_act.add_argument("key", help="TL1-... biciminde lisans anahtari")
    p_act.set_defaults(func=cmd_activate)

    p_key = sub.add_parser("keygen", help="satici: lisans anahtari uret")
    p_key.add_argument("--days", type=int, default=0, help="gecerlilik gun (0 = sinirsiz)")
    p_key.set_defaults(func=cmd_keygen)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
