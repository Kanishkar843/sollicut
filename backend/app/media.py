"""Bounded FFmpeg + Pillow + OpenCV media renderer; never passes user text or filenames into filter graphs."""
import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable
from uuid import UUID

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, features

from . import effects, keyframes as kf
from .models import Asset, ProjectState, TextLayer
from .storage import ROOT, project_dir

FONT = ROOT / "assets/fonts/NotoSansTamil.ttf"
_AMIX_NORMALIZE: bool | None = None


def run(args: list[str], timeout: int = 180, cwd: Path | None = None, input_bytes: bytes | None = None) -> str:
    try:
        result = subprocess.run(
            args,
            input=input_bytes,
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd=str(cwd) if cwd else None,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Media processing exceeded its time limit") from exc
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-1800:])
    return result.stdout.decode("utf-8", errors="replace")


def _amix_filter(inputs: int) -> str:
    global _AMIX_NORMALIZE
    if _AMIX_NORMALIZE is None:
        try:
            _AMIX_NORMALIZE = "normalize" in run(["ffmpeg", "-hide_banner", "-h", "filter=amix"], 10)
        except Exception:
            _AMIX_NORMALIZE = False
    suffix = ":normalize=0" if _AMIX_NORMALIZE else ""
    return f"amix=inputs={inputs}:duration=first{suffix}"


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
            "filters": {
                "xfade": "xfade" in filters,
                "deshake": "deshake" in filters,
                "chromakey": "chromakey" in filters,
                "afftdn": "afftdn" in filters,
                "loudnorm": "loudnorm" in filters,
            },
            "ffmpeg": run(["ffmpeg", "-version"], 10).splitlines()[0],
        }
    except (OSError, RuntimeError) as exc:
        return {"available": False, "error": str(exc), "raqm": features.check_feature("raqm")}


def overlay(text: str, path: Path, position: str = "end_card", accent: str = "lime", is_caption: bool = False) -> None:
    layout = ImageFont.Layout.RAQM if features.check_feature("raqm") else ImageFont.Layout.BASIC
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGBA", (720, 1280))
    draw = ImageDraw.Draw(canvas)
    start_size = 38 if is_caption else 56
    min_size = 20 if is_caption else 24
    max_width = 610 if is_caption else 584
    for size in range(start_size, min_size - 1, -2):
        font = ImageFont.truetype(str(FONT), size, layout_engine=layout)
        lines, line = [], ""
        for word in text.split():
            candidate = f"{line} {word}".strip()
            if draw.textlength(candidate, font=font) > max_width and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        if len(lines) <= 3 and all(draw.textlength(s, font=font) <= max_width for s in lines):
            break
    else:
        raise ValueError("Text is too wide; use shorter words")

    if is_caption:
        height = len(lines) * (size + 14) + 32
        top = 1040 - height
        draw.rounded_rectangle((48, top, 672, top + height), radius=18, fill=(10, 13, 11, 224))
        for i, line in enumerate(lines):
            draw.text((360, top + 16 + i * (size + 14)), line, font=font, anchor="mt", fill="#f5f7f4")
    else:
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


def _sticker_overlay(badge: str, path: Path) -> None:
    labels = {
        "sale": ("SALE", (215, 239, 65), (17, 21, 9)),
        "new": ("NEW DROP", (63, 208, 227), (10, 18, 20)),
        "top_pick": ("TOP PICK", (251, 191, 36), (22, 16, 6)),
        "tamil_special": ("சிறப்பு", (244, 114, 182), (24, 8, 16)),
    }
    label, bg, fg = labels.get(badge, ("SALE", (215, 239, 65), (17, 21, 9)))
    layout = ImageFont.Layout.RAQM if features.check_feature("raqm") else ImageFont.Layout.BASIC
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGBA", (720, 1280))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(str(FONT), 24, layout_engine=layout)
    draw.rounded_rectangle((496, 44, 684, 98), radius=22, fill=(*bg, 245))
    draw.text((590, 71), label, font=font, anchor="mm", fill=fg)
    canvas.save(path)


def _atempo_chain(speed: float) -> list[str]:
    speed = max(0.25, min(4.0, float(speed)))
    if abs(speed - 1.0) < 0.01:
        return []
    filters = []
    remaining = speed
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    filters.append(f"atempo={remaining:.4f}")
    return filters


def _effective_speed(asset: Asset, settings: ProjectState) -> float:
    if abs((asset.speed or 1.0) - 1.0) > 0.01:
        return float(asset.speed)
    curve = getattr(settings, "speed_curve", "normal")
    if curve == "slow_mo":
        return 0.5
    if curve == "fast":
        return 2.0
    return 1.0


def _clip_vf_extras(asset: Asset, settings) -> list[str]:
    parts: list[str] = []
    preset = asset.filter_preset if asset.filter_preset != "none" else settings.filter_preset
    chain = effects.FILTER_CHAINS.get(preset, "")
    if chain:
        parts.append(chain)
    total_bright = max(-0.5, min(0.5, float(settings.brightness) + float(asset.relight or 0.0)))
    gamma = round(max(0.7, min(1.4, 1.0 + float(asset.relight or 0.0) * 0.45)), 3)
    if abs(total_bright) > 0.001 or abs(gamma - 1.0) > 0.001:
        parts.append(f"eq=brightness={total_bright:.3f}:gamma={gamma:.3f}")
    return parts


def _process_video_auto_cutout(source_path: Path, out_path: Path, mask_path: Path, has_audio: bool) -> None:
    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video for cutout: {source_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 720
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1280
    no_audio_path = out_path.with_suffix(".silent.mp4")
    writer = cv2.VideoWriter(str(no_audio_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    saved_mask = False
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            small = cv2.resize(frame, (180, 320), interpolation=cv2.INTER_AREA)
            small_alpha = effects._grabcut_alpha(small)
            alpha = cv2.resize(small_alpha, (w, h), interpolation=cv2.INTER_LINEAR)
            if not saved_mask:
                mask_path.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(mask_path), alpha)
                saved_mask = True
            alpha_f = (alpha.astype(np.float32) / 255.0)[..., None]
            backdrop = np.full_like(frame, (15, 17, 14), dtype=np.uint8).astype(np.float32)
            comp = (frame.astype(np.float32) * alpha_f + backdrop * (1.0 - alpha_f)).astype(np.uint8)
            writer.write(comp)
    finally:
        cap.release()
        writer.release()

    if has_audio:
        run([
            "ffmpeg", "-v", "error", "-y", "-i", str(no_audio_path), "-i", str(source_path),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-shortest", str(out_path),
        ])
    else:
        run(["ffmpeg", "-v", "error", "-y", "-i", str(no_audio_path), "-c:v", "libx264", "-preset", "veryfast", str(out_path)])
    no_audio_path.unlink(missing_ok=True)


def render(project: ProjectState, revision: int, stage: Callable[[str], None] = lambda _: None) -> Path:
    media_items = [a for a in project.assets if a.media_type in {"image", "video"}]
    if not 1 <= len(media_items) <= 5:
        raise ValueError("A reel needs 1 to 5 photos or video clips")
    directory = project_dir(project.id)
    scratch = directory / "renders" / f"work-{revision}"
    scratch.mkdir(parents=True, exist_ok=True)
    settings = project.settings

    n_clips = len(media_items)
    trans_style = settings.transition_style if n_clips > 1 else "none"
    trans_dur = (
        round(min(settings.transition_duration, max(0.2, (settings.duration_seconds / n_clips) * 0.4)), 2)
        if trans_style != "none"
        else 0.0
    )
    effective_total_sec = settings.duration_seconds + max(0, n_clips - 1) * trans_dur
    total_frames = round(effective_total_sec * 30)

    clips: list[Path] = []
    clip_durations: list[float] = []
    slot_windows: list[tuple[float, float]] = []
    base_slot = settings.duration_seconds / n_clips

    try:
        for index, asset in enumerate(media_items):
            stage(f"Processing clip {index + 1} of {n_clips}")
            frames = total_frames // n_clips + (index < total_frames % n_clips)
            slot_seconds = frames / 30.0
            clip_durations.append(slot_seconds)
            slot_windows.append((round(index * base_slot, 3), round((index + 1) * base_slot, 3)))
            clip = scratch / f"clip-{index}.mp4"
            eff_speed = _effective_speed(asset, settings)
            need_audio_track = settings.keep_clip_audio

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
                    if has_audio and need_audio_track:
                        trim_args += ["-c:a", "aac", "-ar", "44100", "-ac", "1"]
                    else:
                        trim_args += ["-an"]
                    trim_args.append(str(trimmed))
                    run(trim_args)
                    source_path = trimmed

                if asset.cutout_mode == "auto_cutout":
                    cutout_vid = scratch / f"cutout-{index}.mp4"
                    mask_out = directory / "overlays" / f"mask-{asset.id}.png"
                    _process_video_auto_cutout(source_path, cutout_vid, mask_out, has_audio and need_audio_track)
                    source_path = cutout_vid

                scale_filter = (
                    "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280"
                    if settings.fit_mode == "cover"
                    else "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x0e110f"
                )
                vf_chain: list[str] = []
                if asset.stabilize:
                    vf_chain.append("deshake=rx=16:ry=16:edge=mirror")
                vf_chain.append(scale_filter)
                if abs(eff_speed - 1.0) > 0.01:
                    vf_chain.append(f"setpts={1.0 / eff_speed:.4f}*PTS")
                vf_chain.extend(_clip_vf_extras(asset, settings))
                vf_chain.extend(["setsar=1", "fps=30", "settb=1/30", "format=yuv420p"])

                clip_args = ["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", str(source_path)]
                use_chromakey = asset.cutout_mode == "chroma_key"
                if use_chromakey:
                    clip_args += ["-f", "lavfi", "-t", f"{slot_seconds:.3f}", "-i", "color=c=0x0e110f:s=720x1280:r=30"]

                clip_vol = round(float(settings.clip_audio_volume) * float(asset.volume or 1.0), 3)
                af_parts = [f"volume={clip_vol}"] + _atempo_chain(eff_speed) + ["aresample=44100", "pan=mono|c0=c0"]
                af_str = ",".join(af_parts)

                if use_chromakey:
                    fg_filters = ",".join(vf_chain)
                    fc = (
                        f"[0:v]{fg_filters},chromakey={asset.chroma_color}:{asset.chroma_similarity}:0.08[fg];"
                        f"[1:v][fg]overlay=0:0:shortest=1,format=yuv420p[vout]"
                    )
                    clip_args += ["-filter_complex", fc, "-map", "[vout]", "-frames:v", str(frames)]
                    if need_audio_track and has_audio:
                        clip_args += ["-map", "0:a:0", "-af", af_str, "-t", f"{slot_seconds:.3f}", "-c:a", "aac", "-ar", "44100", "-ac", "1"]
                    elif need_audio_track:
                        clip_args += ["-f", "lavfi", "-t", f"{slot_seconds:.3f}", "-i", "anullsrc=r=44100:cl=mono", "-map", "2:a:0", "-c:a", "aac", "-ar", "44100", "-ac", "1"]
                    else:
                        clip_args += ["-an"]
                    clip_args += ["-c:v", "libx264", "-preset", "veryfast", "-threads", "2", str(clip)]
                else:
                    vf = ",".join(vf_chain)
                    if need_audio_track:
                        if has_audio:
                            clip_args += [
                                "-vf", vf, "-frames:v", str(frames),
                                "-af", af_str,
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

            # Photo processing
            source_img_path = directory / asset.path
            if asset.cutout_mode == "auto_cutout":
                cutout_img = scratch / f"cutout-{index}.png"
                mask_out = directory / "overlays" / f"mask-{asset.id}.png"
                effects.auto_cutout_image(source_img_path, cutout_img, mask_out)
                source_img_path = cutout_img
            elif asset.cutout_mode == "chroma_key":
                chroma_img = scratch / f"chroma-{index}.png"
                mask_out = directory / "overlays" / f"mask-{asset.id}.png"
                effects.chroma_key_image(source_img_path, chroma_img, mask_out, asset.chroma_color, asset.chroma_similarity)
                source_img_path = chroma_img

            normalized = scratch / f"photo-{index}.png"
            with Image.open(source_img_path) as source:
                oriented = ImageOps.exif_transpose(source).convert("RGB")
                if settings.fit_mode == "cover":
                    canvas = ImageOps.fit(oriented, (1440, 2560))
                else:
                    fitted = ImageOps.contain(oriented, (1440, 2560))
                    canvas = Image.new("RGB", (1440, 2560), "#0e110f")
                    canvas.paste(fitted, ((1440 - fitted.width) // 2, (2560 - fitted.height) // 2))
                canvas.save(normalized)

            eff_keyframes = asset.keyframes if asset.keyframes else settings.keyframes
            extras = _clip_vf_extras(asset, settings)

            if eff_keyframes:
                base_bgr = cv2.resize(cv2.imread(str(normalized), cv2.IMREAD_COLOR), (720, 1280), interpolation=cv2.INTER_AREA)
                raw_buf = bytearray()
                for f_idx in range(frames):
                    props = kf.interpolate_keyframes(eff_keyframes, f_idx / 30.0)
                    raw_buf.extend(kf.apply_keyframes_to_image(base_bgr, props, 720, 1280).tobytes())
                vf_list = extras + ["setsar=1", "settb=1/30", "format=yuv420p"]
                photo_args = [
                    "ffmpeg", "-v", "error", "-y",
                    "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "720x1280", "-r", "30", "-i", "-",
                ]
                if need_audio_track:
                    photo_args += [
                        "-f", "lavfi", "-t", f"{slot_seconds:.3f}", "-i", "anullsrc=r=44100:cl=mono",
                        "-vf", ",".join(vf_list), "-frames:v", str(frames),
                        "-map", "0:v:0", "-map", "1:a:0", "-shortest",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "2",
                        "-c:a", "aac", "-ar", "44100", "-ac", "1", str(clip),
                    ]
                else:
                    photo_args += [
                        "-vf", ",".join(vf_list), "-frames:v", str(frames), "-an",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "2", str(clip),
                    ]
                run(photo_args, input_bytes=bytes(raw_buf))
            else:
                zoom_factor = 0.08 * min(2.0, eff_speed)
                zoom = f"1+{zoom_factor:.3f}*on/{max(1, frames - 1)}" if settings.zoom_style == "smooth" else "1"
                vf_list = [f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s=720x1280:fps=30"]
                vf_list.extend(extras)
                vf_list.extend(["setsar=1", "settb=1/30", "format=yuv420p"])
                vf = ",".join(vf_list)
                photo_args = ["ffmpeg", "-v", "error", "-y", "-i", str(normalized)]
                if need_audio_track:
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

        stage("Joining clips and applying transitions")
        joined = scratch / "joined.mp4"
        if trans_style != "none" and len(clips) > 1:
            t_args = ["ffmpeg", "-v", "error", "-y"]
            for c in clips:
                t_args += ["-i", str(c)]
            fc_parts: list[str] = []
            for idx in range(len(clips)):
                fc_parts.append(f"[{idx}:v]settb=1/30,fps=30,setsar=1,format=yuv420p,setpts=PTS-STARTPTS[v{idx}]")
            prev_v = "v0"
            elapsed = clip_durations[0]
            for idx in range(1, len(clips)):
                offset = max(0.05, round(elapsed - idx * trans_dur, 3))
                out_v = "vx" if idx == len(clips) - 1 else f"x{idx}"
                fc_parts.append(f"[{prev_v}][v{idx}]xfade=transition={trans_style}:duration={trans_dur:.2f}:offset={offset:.3f}[{out_v}]")
                prev_v = out_v
                elapsed += clip_durations[idx]
            t_args_map = ["-map", f"[{prev_v}]"]
            if settings.keep_clip_audio:
                for idx in range(len(clips)):
                    fc_parts.append(f"[{idx}:a]asetpts=PTS-STARTPTS[a{idx}]")
                prev_a = "a0"
                for idx in range(1, len(clips)):
                    out_a = "ax" if idx == len(clips) - 1 else f"ax{idx}"
                    fc_parts.append(f"[{prev_a}][a{idx}]acrossfade=d={trans_dur:.2f}:c1=tri:c2=tri[{out_a}]")
                    prev_a = out_a
                t_args_map += ["-map", f"[{prev_a}]", "-c:a", "aac", "-ar", "44100", "-ac", "1"]
            else:
                t_args_map += ["-an"]
            t_args += ["-filter_complex", ";".join(fc_parts)] + t_args_map + [
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "2", "-pix_fmt", "yuv420p", str(joined),
            ]
            run(t_args)
        else:
            manifest = scratch / "clips.txt"
            manifest.write_text("\n".join(f"file '{c.name}'" for c in clips), encoding="utf-8")
            run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "1", "-i", manifest.name, "-c", "copy", joined.name], cwd=scratch)

        # Final composition: multi-layer text/captions, sticker badge, BGM + narration + audio FX
        args = ["ffmpeg", "-v", "error", "-y", "-i", str(joined)]
        next_input = 1

        bgm_index = None
        audio_path = next((directory / a.path for a in project.assets if a.media_type == "audio"), ROOT / "assets/demo/music.wav")
        if settings.music_enabled:
            args += ["-stream_loop", "-1", "-i", str(audio_path)]
            bgm_index = next_input
            next_input += 1

        narration_index = None
        if settings.narration_enabled and settings.narration_asset_id:
            try:
                if str(UUID(settings.narration_asset_id)) == settings.narration_asset_id:
                    tts_wav = directory / "audio" / f"tts-{settings.narration_asset_id}.wav"
                    if tts_wav.is_file():
                        args += ["-i", str(tts_wav)]
                        narration_index = next_input
                        next_input += 1
            except ValueError:
                pass

        # Collect text/caption layers
        layers: list[TextLayer] = list(settings.text_layers or [])
        if not layers and settings.overlay_text:
            layers = [TextLayer(text=settings.overlay_text, position=settings.overlay_position, color=settings.overlay_color)]
        layers = layers[:12]

        filter_parts: list[str] = []
        video_map = "0:v"

        if layers:
            stage("Shaping text & captions")
            prev_v = "[0:v]"
            for idx, layer in enumerate(layers):
                png = directory / "overlays" / f"{revision}-txt-{idx}.png"
                overlay(layer.text, png, layer.position, layer.color, is_caption=layer.is_caption)
                args += ["-i", str(png)]
                txt_idx = next_input
                next_input += 1

                if layer.start_time is not None or layer.end_time is not None:
                    t0 = max(0.0, float(layer.start_time or 0.0))
                    t1 = min(settings.duration_seconds, float(layer.end_time or settings.duration_seconds))
                elif layer.clip_index is not None and 1 <= layer.clip_index <= len(slot_windows):
                    t0, t1 = slot_windows[layer.clip_index - 1]
                elif layer.position == "end_card" and not layer.is_caption:
                    t0 = max(0.0, settings.duration_seconds - 4.0)
                    t1 = float(settings.duration_seconds)
                else:
                    t0, t1 = 0.0, float(settings.duration_seconds)

                src_label = f"[{txt_idx}:v]"
                if layer.animation == "fade":
                    filter_parts.append(f"[{txt_idx}:v]format=rgba,fade=t=in:st={t0:.2f}:d=0.35:alpha=1[txt{idx}]")
                    src_label = f"[txt{idx}]"
                elif layer.animation == "pop":
                    filter_parts.append(f"[{txt_idx}:v]format=rgba,fade=t=in:st={t0:.2f}:d=0.18:alpha=1[txt{idx}]")
                    src_label = f"[txt{idx}]"

                y_expr = "0"
                if layer.animation == "slide_up":
                    y_expr = f"'if(lt(t-{t0:.2f},0.4),(1-(t-{t0:.2f})/0.4)*80,0)'"

                enable_expr = "" if (t0 <= 0.001 and t1 >= settings.duration_seconds - 0.001) else f":enable='between(t,{t0:.2f},{t1:.2f})'"
                out_label = f"[ov{idx}]"
                filter_parts.append(f"{prev_v}{src_label}overlay=x=0:y={y_expr}{enable_expr}{out_label}")
                prev_v = out_label
            video_map = prev_v

        if settings.sticker_badge != "none":
            badge_png = directory / "overlays" / f"{revision}-badge.png"
            _sticker_overlay(settings.sticker_badge, badge_png)
            args += ["-i", str(badge_png)]
            b_idx = next_input
            next_input += 1
            filter_parts.append(f"{video_map}[{b_idx}:v]overlay=0:0[vbadge]")
            video_map = "[vbadge]"

        # Audio bus mixing + DSP processing
        audio_fx = effects.build_audio_filter_chain(
            denoise=settings.audio_denoise,
            normalize=settings.audio_normalize,
            voice_enhance=settings.voice_enhance,
            vocal_isolation=settings.vocal_isolation,
        )
        audio_streams: list[str] = []
        if settings.keep_clip_audio:
            if audio_fx:
                filter_parts.append(f"[0:a]{','.join(audio_fx)}[clipa]")
                audio_streams.append("[clipa]")
            else:
                audio_streams.append("[0:a]")
        if bgm_index is not None:
            bgm_chain = [
                f"volume={settings.music_volume}",
                f"afade=t=out:st={max(0, settings.duration_seconds - 0.5)}:d=0.5",
            ]
            if not settings.keep_clip_audio and not narration_index and audio_fx:
                bgm_chain.extend(audio_fx)
            filter_parts.append(f"[{bgm_index}:a]{','.join(bgm_chain)}[bgm]")
            audio_streams.append("[bgm]")
        if narration_index is not None:
            nar_chain = [f"volume={settings.narration_volume}", "aresample=44100", "pan=mono|c0=c0"]
            if audio_fx:
                nar_chain.extend(audio_fx)
            filter_parts.append(f"[{narration_index}:a]{','.join(nar_chain)}[nar]")
            audio_streams.append("[nar]")

        audio_map: str | None = None
        if len(audio_streams) > 1:
            filter_parts.append(f"{''.join(audio_streams)}{_amix_filter(len(audio_streams))}[aout]")
            audio_map = "[aout]"
        elif len(audio_streams) == 1:
            audio_map = audio_streams[0].strip("[]")
            # Ensure filter_complex outputs are mapped with brackets if processed inside filter_complex
            if audio_streams[0] in {"[clipa]", "[bgm]", "[nar]"}:
                audio_map = audio_streams[0]

        if filter_parts:
            args += ["-filter_complex_threads", "1", "-filter_complex", ";".join(filter_parts)]

        args += ["-map", video_map]
        if audio_map is not None:
            args += ["-map", audio_map, "-c:a", "aac", "-b:a", "128k"]
        else:
            args += ["-an"]

        output = directory / "renders" / f"revision-{revision}.mp4"
        temporary = directory / "renders" / f"revision-{revision}.tmp.mp4"
        args += [
            "-t", str(settings.duration_seconds),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "2",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary),
        ]
        run(args)
        metadata = probe(temporary)
        if not any(s["codec_type"] == "video" for s in metadata["streams"]):
            raise RuntimeError("Rendered output has no video")
        temporary.replace(output)
        return output
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
