"""Bounded FFmpeg processes; no shell, user filenames or text in filter graphs."""
import json
import subprocess
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont, ImageOps, features

from .models import ProjectState
from .storage import ROOT, project_dir

FONT = ROOT / "assets/fonts/NotoSansTamil.ttf"
_AMIX_NORMALIZE: bool | None = None


def _amix_filter(inputs: int) -> str:
    global _AMIX_NORMALIZE
    if _AMIX_NORMALIZE is None:
        try:
            _AMIX_NORMALIZE = "normalize" in run(["ffmpeg", "-hide_banner", "-h", "filter=amix"], 10)
        except Exception:
            _AMIX_NORMALIZE = False
    suffix = ":normalize=0" if _AMIX_NORMALIZE else ""
    return f"amix=inputs={inputs}:duration=first{suffix}"


def run(args: list[str], timeout: int = 180, cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout, check=False, cwd=str(cwd) if cwd else None)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Media processing exceeded its time limit") from exc
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-1800:])
    return result.stdout.decode("utf-8", errors="replace")


def probe(path: Path) -> dict:
    return json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], 20))


ACCENTS = {
    "lime": (215, 239, 65),
    "white": (245, 247, 244),
    "amber": (251, 191, 36),
    "cyan": (63, 208, 227),
    "rose": (244, 114, 182),
}


def capabilities() -> dict:
    try:
        filters = run(["ffmpeg", "-hide_banner", "-filters"], 10)
        encoders = run(["ffmpeg", "-hide_banner", "-encoders"], 10)
        required = ("scale", "pad", "crop", "zoompan", "overlay", "concat", "eq", "volume", "amix", "anullsrc")
        missing = [f for f in required if f not in filters]
        if "libx264" not in encoders or " aac " not in encoders:
            missing.append("H.264/AAC encoder")
        has_raqm = features.check_feature("raqm")
        return {
            "available": not missing and FONT.is_file(),
            "missing": missing,
            "raqm": has_raqm,
            "tamil_shaping": "raqm" if has_raqm else "basic_fallback",
            "ffmpeg": run(["ffmpeg", "-version"], 10).splitlines()[0],
        }
    except (OSError, RuntimeError) as exc:
        return {"available": False, "error": str(exc), "raqm": features.check_feature("raqm")}


def overlay(text: str, path: Path, position: str = "end_card", accent: str = "lime") -> None:
    layout = ImageFont.Layout.RAQM if features.check_feature("raqm") else ImageFont.Layout.BASIC
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGBA", (720, 1280))
    draw = ImageDraw.Draw(canvas)
    # Fit whole words, shrinking only when needed. Tamil shaping uses RAQM when libraqm is installed.
    for size in range(56, 23, -2):
        font = ImageFont.truetype(str(FONT), size, layout_engine=layout)
        lines, line = [], ""
        for word in text.split():
            candidate = f"{line} {word}".strip()
            if draw.textlength(candidate, font=font) > 584 and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        if len(lines) <= 3 and all(draw.textlength(s, font=font) <= 584 for s in lines):
            break
    else:
        raise ValueError("Text is too wide; use shorter words")
    height = len(lines) * (size + 22) + 64
    if position == "center":
        top = (1280 - height) // 2
    elif position == "top":
        top = 120
    else:
        top = 1140 - height
    bar_color = ACCENTS.get(accent, ACCENTS["lime"])
    draw.rounded_rectangle((36, top, 684, top + height), radius=28, fill=(14, 17, 15, 238))
    draw.rounded_rectangle((64, top + 24, 132, top + 30), radius=3, fill=bar_color)
    for i, line in enumerate(lines):
        draw.text((360, top + 48 + i * (size + 22)), line, font=font, anchor="mt", fill="white")
    canvas.save(path)


def render(project: ProjectState, revision: int, stage: Callable[[str], None] = lambda _: None) -> Path:
    media_items = [a for a in project.assets if a.media_type in {"image", "video"}]
    if not 1 <= len(media_items) <= 5:
        raise ValueError("A reel needs 1 to 5 photos or video clips")
    directory = project_dir(project.id)
    scratch = directory / "renders" / f"work-{revision}"
    scratch.mkdir(parents=True, exist_ok=True)
    settings = project.settings
    total_frames = round(settings.duration_seconds * 30)
    clips = []
    try:
        for index, asset in enumerate(media_items):
            stage(f"Processing clip {index + 1} of {len(media_items)}")
            frames = total_frames // len(media_items) + (index < total_frames % len(media_items))
            slot_seconds = frames / 30.0
            clip = scratch / f"clip-{index}.mp4"
            if asset.media_type == "video":
                source_path = directory / asset.path
                info = probe(source_path)
                has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
                trim_start = asset.trim_start or 0.0
                trim_end = asset.trim_end
                if trim_start > 0 or trim_end is not None:
                    trimmed = scratch / f"trimmed-{index}.mp4"
                    trim_args = ["ffmpeg", "-v", "error", "-y", "-ss", f"{trim_start:.3f}", "-i", str(source_path)]
                    if trim_end is not None and trim_end > trim_start:
                        trim_args += ["-t", f"{trim_end - trim_start:.3f}"]
                    trim_args += ["-c:v", "libx264", "-preset", "veryfast", "-threads", "2"]
                    if has_audio and settings.keep_clip_audio:
                        trim_args += ["-c:a", "aac", "-ar", "44100", "-ac", "1"]
                    else:
                        trim_args += ["-an"]
                    trim_args.append(str(trimmed))
                    run(trim_args)
                    source_path = trimmed
                scale_filter = (
                    "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280"
                    if settings.fit_mode == "cover"
                    else "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x0e110f"
                )
                vf = f"{scale_filter},setsar=1,fps=30,eq=brightness={settings.brightness},format=yuv420p"
                clip_args = ["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", str(source_path)]
                if settings.keep_clip_audio:
                    if has_audio:
                        clip_args += [
                            "-vf", vf, "-frames:v", str(frames),
                            "-af", f"volume={settings.clip_audio_volume},aresample=44100,pan=mono|c0=c0",
                            "-t", f"{slot_seconds:.3f}",
                            "-c:v", "libx264", "-preset", "veryfast", "-threads", "2",
                            "-c:a", "aac", "-ar", "44100", "-ac", "1", str(clip),
                        ]
                    else:
                        clip_args += [
                            "-f", "lavfi", "-t", f"{slot_seconds:.3f}", "-i", "anullsrc=r=44100:cl=mono",
                            "-vf", vf, "-frames:v", str(frames),
                            "-map", "0:v:0", "-map", "1:a:0", "-shortest",
                            "-c:v", "libx264", "-preset", "veryfast", "-threads", "2",
                            "-c:a", "aac", "-ar", "44100", "-ac", "1", str(clip),
                        ]
                else:
                    clip_args += ["-vf", vf, "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast", "-threads", "2", str(clip)]
                run(clip_args)
                clips.append(clip)
                continue

            normalized = scratch / f"photo-{index}.png"
            with Image.open(directory / asset.path) as source:
                oriented = ImageOps.exif_transpose(source).convert("RGB")
                if settings.fit_mode == "cover":
                    canvas = ImageOps.fit(oriented, (1440, 2560))
                else:
                    fitted = ImageOps.contain(oriented, (1440, 2560))
                    canvas = Image.new("RGB", (1440, 2560), "#0e110f")
                    canvas.paste(fitted, ((1440 - fitted.width) // 2, (2560 - fitted.height) // 2))
                canvas.save(normalized)
            zoom = f"1+0.08*on/{max(1, frames-1)}" if settings.zoom_style == "smooth" else "1"
            vf = f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s=720x1280:fps=30,eq=brightness={settings.brightness},setsar=1,format=yuv420p"
            photo_args = ["ffmpeg", "-v", "error", "-y", "-i", str(normalized)]
            if settings.keep_clip_audio:
                photo_args += [
                    "-f", "lavfi", "-t", f"{slot_seconds:.3f}", "-i", "anullsrc=r=44100:cl=mono",
                    "-vf", vf, "-frames:v", str(frames),
                    "-map", "0:v:0", "-map", "1:a:0", "-shortest",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "2",
                    "-c:a", "aac", "-ar", "44100", "-ac", "1", str(clip),
                ]
            else:
                photo_args += [
                    "-vf", vf, "-frames:v", str(frames), "-an",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "2", str(clip),
                ]
            run(photo_args)
            clips.append(clip)

        stage("Joining clips and mixing audio")
        manifest = scratch / "clips.txt"
        manifest.write_text("\n".join(f"file '{c.name}'" for c in clips), encoding="utf-8")
        joined = scratch / "joined.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "1", "-i", manifest.name, "-c", "copy", joined.name], cwd=scratch)
        args = ["ffmpeg", "-v", "error", "-y", "-i", str(joined)]
        audio = next((directory / a.path for a in project.assets if a.media_type == "audio"), ROOT / "assets/demo/music.wav")
        if settings.music_enabled:
            args += ["-stream_loop", "-1", "-i", str(audio)]
        filter_parts = []
        video_map = "0:v"
        if settings.overlay_text:
            stage("Shaping promotional text")
            png = directory / "overlays" / f"{revision}.png"
            overlay(settings.overlay_text, png, settings.overlay_position, settings.overlay_color)
            args += ["-i", str(png)]
            overlay_index = 2 if settings.music_enabled else 1
            enable = f":enable='gte(t,{max(0, settings.duration_seconds-4)})'" if settings.overlay_position == "end_card" else ""
            filter_parts.append(f"[0:v][{overlay_index}:v]overlay=0:0{enable}[v]")
            video_map = "[v]"
        if settings.keep_clip_audio and settings.music_enabled:
            filter_parts.append(
                f"[1:a]volume={settings.music_volume},afade=t=out:st={max(0, settings.duration_seconds-.5)}:d=0.5[bgm];"
                f"[0:a][bgm]{_amix_filter(2)}[aout]"
            )
        if filter_parts:
            args += ["-filter_complex_threads", "1", "-filter_complex", ";".join(filter_parts)]
        args += ["-map", video_map]
        if settings.keep_clip_audio and settings.music_enabled:
            args += ["-map", "[aout]", "-c:a", "aac", "-b:a", "128k"]
        elif settings.music_enabled:
            args += ["-map", "1:a:0", "-af", f"volume={settings.music_volume},afade=t=out:st={max(0, settings.duration_seconds-.5)}:d=0.5", "-c:a", "aac", "-b:a", "128k"]
        elif settings.keep_clip_audio:
            args += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "128k"]
        else:
            args += ["-an"]
        output = directory / "renders" / f"revision-{revision}.mp4"
        temporary = directory / "renders" / f"revision-{revision}.tmp.mp4"
        args += ["-t", str(settings.duration_seconds), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "2", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary)]
        run(args)
        metadata = probe(temporary)
        if not any(s["codec_type"] == "video" for s in metadata["streams"]):
            raise RuntimeError("Rendered output has no video")
        temporary.replace(output)
        return output
    finally:
        import shutil
        shutil.rmtree(scratch, ignore_errors=True)
