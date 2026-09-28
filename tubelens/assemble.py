"""FFmpeg ile video montaji: olcullendirme, birlestirme, altyazi, ses karma.

Goruntuler hedef cozunurluge indirgenir (cover-crop), ses suresine gore
birlestirilir, istenirse SRT altyazisi yakilir ve seslendirme (+opsiyonel
arka plan muzigi) ile mux edilir. FFmpeg binary'si imageio-ffmpeg ile gelir.
"""

from __future__ import annotations

import math
import re
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg

from .voice import Word


class AssemblyError(RuntimeError):
    pass


SIZES = {
    ("9:16", 1080): (1080, 1920),
    ("9:16", 720): (720, 1280),
    ("16:9", 1080): (1920, 1080),
    ("16:9", 720): (1280, 720),
    ("1:1", 1080): (1080, 1080),
    ("1:1", 720): (720, 720),
}


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args: list[str], timeout: int = 1800) -> str:
    cmd = [ffmpeg_exe(), "-hide_banner", "-y", *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssemblyError(f"ffmpeg zaman asimi ({timeout}s)") from exc
    except OSError as exc:
        raise AssemblyError(f"ffmpeg calistirilamadi: {exc}") from exc
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").splitlines()[-8:])
        raise AssemblyError(f"ffmpeg hata (kod {proc.returncode}):\n{tail}")
    return proc.stderr or ""


def media_duration(path: Path) -> float:
    """Dosyanin tam sureisini (saniye) dogrulamak icin tam kodcozum yapar."""
    try:
        proc = subprocess.run(
            [ffmpeg_exe(), "-hide_banner", "-i", str(path), "-f", "null", "-"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise AssemblyError(f"Sure okunamadi: {exc}") from exc
    matches = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr or "")
    if not matches:
        raise AssemblyError(f"Sure okunamadi: {path.name}")
    h, m, s = matches[-1]
    return int(h) * 3600 + int(m) * 60 + float(s)


def _format_ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def words_to_srt(words: list[Word], max_words: int = 7, max_gap: float = 0.6) -> str:
    """Kelime zamanlamalarindan cumle bazli SRT metni uretir."""
    if not words:
        return ""
    groups: list[list[Word]] = []
    current: list[Word] = []
    for word in words:
        if current:
            gap = word.start - current[-1].end
            long_enough = len(current) >= max_words
            ended = current[-1].text.endswith((".", "!", "?", ",", ";", ":"))
            if gap > max_gap or long_enough or (ended and gap > 0.15):
                groups.append(current)
                current = []
        current.append(word)
    if current:
        groups.append(current)

    lines: list[str] = []
    for idx, group in enumerate(groups, 1):
        nxt = groups[idx][0].start if idx < len(groups) else group[-1].end + 1.0
        start = max(0.0, group[0].start - 0.05)
        end = min(group[-1].end + 0.2, nxt - 0.05)
        if end <= start:
            end = start + 0.4
        text = " ".join(w.text for w in group)
        lines.append(f"{idx}\n{_format_ts(start)} --> {_format_ts(end)}\n{text}\n")
    return "\n".join(lines)


def _normalize_clip(src: Path, dst: Path, size: tuple[int, int], seg_dur: float) -> None:
    width, height = size
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps=30"
    )
    run_ffmpeg(
        [
            "-stream_loop", "-1",
            "-t", f"{seg_dur:.3f}",
            "-i", str(src),
            "-vf", vf,
            "-an",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-t", f"{seg_dur:.3f}",
            str(dst),
        ]
    )


def _concat_clips(segments: list[Path], list_path: Path, out: Path) -> None:
    entries = []
    for seg in segments:
        posix = seg.resolve().as_posix().replace("'", "'\\''")
        entries.append(f"file '{posix}'")
    list_path.write_text("\n".join(entries), encoding="utf-8")
    run_ffmpeg(
        ["-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(out)]
    )


def _subtitles_filter(srt_path: Path) -> str:
    path = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\:")
    return f"subtitles=filename='{path}'"


def _finalize(
    base: Path,
    out: Path,
    target_dur: float,
    srt_path: Path | None,
) -> None:
    chain = [f"tpad=stop_mode=clone:stop_duration={target_dur:.3f}"]
    if srt_path and srt_path.exists() and srt_path.stat().st_size > 0:
        chain.append(_subtitles_filter(srt_path))

    def build(vf: str) -> list[str]:
        return [
            "-i", str(base),
            "-t", f"{target_dur:.3f}",
            "-vf", vf,
            "-an",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            str(out),
        ]

    try:
        run_ffmpeg(build(",".join(chain)))
    except AssemblyError:
        if len(chain) == 1:
            raise
        run_ffmpeg(build(chain[0]))


def _mux(
    video: Path,
    audio: Path,
    out: Path,
    bgm: Path | None = None,
    bgm_volume: float = 0.12,
) -> None:
    if bgm:
        fc = (
            "[1:a]aresample=48000[a0];"
            f"[2:a]volume={bgm_volume:.3f},aresample=48000[a1];"
            "[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[a]"
        )
        args = [
            "-i", str(video),
            "-i", str(audio),
            "-stream_loop", "-1",
            "-i", str(bgm),
            "-map", "0:v:0",
            "-map", "[a]",
            "-filter_complex", fc,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(out),
        ]
    else:
        args = [
            "-i", str(video),
            "-i", str(audio),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(out),
        ]
    run_ffmpeg(args)


def render(
    clips: list[Path],
    audio: Path,
    out_path: Path,
    *,
    aspect: str = "9:16",
    resolution: int = 1080,
    srt_text: str = "",
    bgm: Path | None = None,
    bgm_volume: float = 0.12,
    work_dir: Path | None = None,
    timeout: int = 1800,
) -> tuple[Path, float]:
    """Goruntu + seslendirmeden tam video uretir; (video yolu, sure) dondurur."""
    if not clips:
        raise AssemblyError("Montaj icin goruntu yok")
    size = SIZES.get((aspect, resolution))
    if not size:
        raise AssemblyError(f"Desteklenmeyen format: {aspect} @{resolution}")

    audio_dur = media_duration(audio)
    if audio_dur < 1.0:
        raise AssemblyError("Ses dosyasi cok kisa")

    work = work_dir or Path(tempfile.mkdtemp(prefix="tubelens_vid_"))
    work.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    count = max(1, min(len(clips), int(math.floor(audio_dur))))
    chosen = (clips * ((count // len(clips)) + 1))[:count]
    seg_dur = audio_dur / count

    segments: list[Path] = []
    for idx, clip in enumerate(chosen):
        seg = work / f"seg_{idx:02d}.mp4"
        _normalize_clip(clip, seg, size, seg_dur)
        segments.append(seg)

    base = work / "base.mp4"
    _concat_clips(segments, work / "concat.txt", base)

    srt_path = None
    if srt_text.strip():
        srt_path = out_path.parent / "subtitles.srt"
        srt_path.write_text(srt_text, encoding="utf-8")

    silent = work / "silent.mp4"
    _finalize(base, silent, audio_dur, srt_path)

    _mux(silent, audio, out_path, bgm=bgm, bgm_volume=bgm_volume)
    return out_path, media_duration(out_path)
