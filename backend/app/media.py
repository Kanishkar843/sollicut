"""Bounded FFmpeg processes; no shell, user filenames or text in filter graphs."""
import json
import subprocess
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont, ImageOps, features

from .models import ProjectState
from .storage import ROOT, project_dir

FONT = ROOT / "assets/fonts/NotoSansTamil.ttf"


def run(args: list[str], timeout: int = 180) -> str:
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Media processing exceeded its time limit") from exc
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-1800:])
    return result.stdout.decode("utf-8", errors="replace")


def probe(path: Path) -> dict:
    return json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], 20))


def capabilities() -> dict:
    try:
        filters = run(["ffmpeg", "-hide_banner", "-filters"], 10)
        encoders = run(["ffmpeg", "-hide_banner", "-encoders"], 10)
        required = ("scale", "pad", "zoompan", "overlay", "concat", "eq", "volume")
        missing = [f for f in required if f not in filters]
        if "libx264" not in encoders or " aac " not in encoders:
            missing.append("H.264/AAC encoder")
        return {"available": not missing and features.check_feature("raqm") and FONT.is_file(),
                "missing": missing, "raqm": features.check_feature("raqm"),
                "ffmpeg": run(["ffmpeg", "-version"], 10).splitlines()[0]}
    except (OSError, RuntimeError) as exc:
        return {"available": False, "error": str(exc), "raqm": features.check_feature("raqm")}


def overlay(text: str, path: Path, position: str = "end_card") -> None:
    if not features.check_feature("raqm"):
        raise RuntimeError("Tamil shaping requires Pillow with libraqm")
    canvas = Image.new("RGBA", (720, 1280))
    draw = ImageDraw.Draw(canvas)
    # Fit whole words, shrinking only when needed. Tamil shaping uses RAQM.
    for size in range(56, 23, -2):
        font = ImageFont.truetype(str(FONT), size, layout_engine=ImageFont.Layout.RAQM)
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
    top = (1280 - height) // 2 if position == "center" else 1140 - height
    draw.rounded_rectangle((36, top, 684, top + height), radius=28, fill=(19, 27, 38, 235))
    draw.rounded_rectangle((64, top + 24, 132, top + 30), radius=3, fill=(220, 255, 108))
    for i, line in enumerate(lines):
        draw.text((360, top + 48 + i * (size + 22)), line, font=font, anchor="mt", fill="white")
    canvas.save(path)


def render(project: ProjectState, revision: int, stage: Callable[[str], None] = lambda _: None) -> Path:
    images = [a for a in project.assets if a.media_type == "image"]
    if not 3 <= len(images) <= 5:
        raise ValueError("A reel needs 3 to 5 photos")
    directory = project_dir(project.id)
    scratch = directory / "renders" / f"work-{revision}"
    scratch.mkdir(parents=True, exist_ok=True)
    settings = project.settings
    total_frames = round(settings.duration_seconds * 30)
    clips = []
    try:
        for index, asset in enumerate(images):
            stage(f"Animating photo {index + 1} of {len(images)}")
            frames = total_frames // len(images) + (index < total_frames % len(images))
            normalized = scratch / f"photo-{index}.png"
            with Image.open(directory / asset.path) as source:
                fitted = ImageOps.contain(ImageOps.exif_transpose(source).convert("RGB"), (1440, 2560))
                canvas = Image.new("RGB", (1440, 2560), "#131b26")
                canvas.paste(fitted, ((1440 - fitted.width) // 2, (2560 - fitted.height) // 2))
                canvas.save(normalized)
            zoom = f"1+0.08*on/{max(1, frames-1)}" if settings.zoom_style == "smooth" else "1"
            vf = f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s=720x1280:fps=30,eq=brightness={settings.brightness},setsar=1,format=yuv420p"
            clip = scratch / f"clip-{index}.mp4"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(normalized), "-vf", vf,
                 "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "2", str(clip)])
            clips.append(clip)
        stage("Joining photos and mixing music")
        manifest = scratch / "clips.txt"
        manifest.write_text("\n".join(f"file '{c.name}'" for c in clips), encoding="utf-8")
        joined = scratch / "joined.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "1", "-i", str(manifest), "-c", "copy", str(joined)])
        args = ["ffmpeg", "-v", "error", "-y", "-i", str(joined)]
        audio = next((directory / a.path for a in project.assets if a.media_type == "audio"), ROOT / "assets/demo/music.wav")
        if settings.music_enabled:
            args += ["-stream_loop", "-1", "-i", str(audio)]
        if settings.overlay_text:
            stage("Shaping promotional text")
            png = directory / "overlays" / f"{revision}.png"
            overlay(settings.overlay_text, png, settings.overlay_position)
            args += ["-i", str(png)]
            overlay_index = 2 if settings.music_enabled else 1
            enable = f":enable='gte(t,{max(0, settings.duration_seconds-4)})'" if settings.overlay_position == "end_card" else ""
            args += ["-filter_complex_threads", "1", "-filter_complex", f"[0:v][{overlay_index}:v]overlay=0:0{enable}[v]", "-map", "[v]"]
        else:
            args += ["-map", "0:v"]
        if settings.music_enabled:
            args += ["-map", "1:a:0", "-af", f"volume={settings.music_volume},afade=t=out:st={settings.duration_seconds-.5}:d=0.5", "-c:a", "aac", "-b:a", "128k"]
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
