import asyncio
import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError

from . import assets_catalog, effects, generation, media, storage
from .models import (
    ASPECT_DIMENSIONS,
    ApplyRequest,
    ApplyTemplateRequest,
    Asset,
    AttachAudioRequest,
    AutoCaptionRequest,
    EditOperation,
    GenerateRequest,
    Job,
    ProjectState,
    ReelSettings,
    Snapshot,
    TTSRequest,
    TextLayer,
    VisualEditRequest,
    uid,
)
from .parser import parse
from .speech import FasterWhisperSpeechEngine
from .tts import OfflineTTSEngine

Image.MAX_IMAGE_PIXELS = 50_000_000
speech = FasterWhisperSpeechEngine()
tts_engine = OfflineTTSEngine()
jobs: dict[str, Job] = {}
busy: set[str] = set()
tasks: set[asyncio.Task] = set()
render_gate = asyncio.Semaphore(1)
media_status = {}


def track(coroutine):
    task = asyncio.create_task(coroutine)
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return task


@asynccontextmanager
async def lifespan(app):
    global media_status
    media_status = await asyncio.to_thread(media.capabilities)
    track(asyncio.to_thread(speech.initialize))
    yield
    # Let bounded media processes finish before shutting down.
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="SolliCut", lifespan=lifespan)


@app.middleware("http")
async def local_origin(request: Request, call_next):
    # Prevent cross-site browser writes to the localhost service.
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin != str(request.base_url).rstrip("/"):
        return JSONResponse({"detail": "Cross-origin writes are not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def get_project(project_id: str):
    try:
        return storage.load(project_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Project not found") from None


def claim(project_id: str):
    project = get_project(project_id)
    if project_id in busy:
        raise HTTPException(409, "This project is processing a command. Please wait.")
    busy.add(project_id)
    return project


def quota(project_id: str, extra: int = 0):
    total = sum(p.stat().st_size for p in storage.project_dir(project_id).rglob("*") if p.is_file())
    if total + extra > 500 * 1024 * 1024:
        raise HTTPException(413, "Project storage limit reached. Download your reel and reset this project.")


async def receive(upload: UploadFile, path: Path, limit: int):
    size = 0
    try:
        with path.open("wb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, "Upload exceeds the file size limit")
                target.write(chunk)
        if size == 0:
            raise HTTPException(422, "Empty upload")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "renderer": media_status, "asr": speech.status, "tts": tts_engine.status()}


@app.get("/api/capabilities")
def capabilities():
    return {
        "generation": generation.status(),
        "renderer": media_status,
        "speech": {"engine": "faster-whisper", "status": speech.status, "error": speech.error},
        "tts": tts_engine.status(),
        "cutout": effects.cutout_capabilities(),
        "limits": {
            "images": 5,
            "media_items": 5,
            "image_mb": 15,
            "video_mb": 100,
            "video_seconds": 120,
            "voice_seconds": 30,
            "voice_mb": 20,
            "project_mb": 500,
        },
    }


@app.post("/api/projects", response_model=ProjectState)
async def create_project():
    return storage.create()


@app.get("/api/projects/{project_id}", response_model=ProjectState)
async def read_project(project_id: str):
    return get_project(project_id)


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    claim(project_id)
    try:
        shutil.rmtree(storage.project_dir(project_id))
        for job_id in [k for k, v in jobs.items() if v.project_id == project_id]:
            del jobs[job_id]
        return {"deleted": True}
    finally:
        busy.discard(project_id)


@app.post("/api/projects/{project_id}/assets")
async def upload_asset(project_id: str, file: UploadFile = File(...)):
    project = claim(project_id)
    path = None
    try:
        suffix = Path(file.filename or "").suffix.lower()
        image_types = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
        is_image = suffix in image_types
        is_video = suffix in {".mp4", ".mov", ".webm"}
        if not is_image and not is_video and suffix not in {".wav", ".mp3", ".m4a", ".ogg"}:
            raise HTTPException(415, "Use JPEG, PNG, WebP photos, MP4, MOV, WebM videos, or WAV, MP3, M4A, OGG music")
        if (is_image or is_video) and sum(a.media_type in {"image", "video"} for a in project.assets) >= 5:
            raise HTTPException(422, "A project supports at most 5 photos or video clips")
        if not is_image and not is_video and any(a.media_type == "audio" for a in project.assets):
            raise HTTPException(422, "Remove the current music file before uploading another")
        expected_prefix = "image/" if is_image else "video/" if is_video else "audio/"
        if not (file.content_type or "").startswith(expected_prefix):
            raise HTTPException(415, "The uploaded media type does not match the file extension")
        quota(project_id, (100 if is_video else 20) * 1024 * 1024)
        identifier = str(uuid4())
        path = storage.project_dir(project_id) / "assets" / (identifier + suffix)
        await receive(file, path, (15 if is_image else 100 if is_video else 20) * 1024 * 1024)
        asset = Asset(
            id=identifier,
            filename=(file.filename or "media")[:150],
            media_type="image" if is_image else "video" if is_video else "audio",
            path=f"assets/{path.name}",
        )
        if is_image:
            try:
                with Image.open(path) as image:
                    if image.format != image_types[suffix] or image.width * image.height > 50_000_000 or min(image.size) < 32:
                        raise ValueError("Invalid image format or dimensions")
                    image.load()
                    normalized = ImageOps.exif_transpose(image).convert("RGB")
                    # Bound decompressed working size without stretching product photos.
                    normalized.thumbnail((2560, 2560))
                    asset.width, asset.height = normalized.size
                    clean = path.with_suffix(".jpg")
                    normalized.save(clean, quality=95)
                if clean != path:
                    path.unlink()
                path = clean
                asset.path = f"assets/{clean.name}"
            except (ValueError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError):
                raise HTTPException(422, "Could not decode a valid photo (32 pixels minimum, 50 megapixels maximum)") from None
        elif is_video:
            try:
                info = await asyncio.to_thread(media.probe, path)
                video = next(s for s in info["streams"] if s["codec_type"] == "video")
                asset.width, asset.height = video["width"], video["height"]
                asset.duration_seconds = float(info["format"]["duration"])
                if not 0 < asset.duration_seconds <= 120 or asset.width * asset.height > 8_500_000:
                    raise ValueError("Video too large")
            except (RuntimeError, KeyError, ValueError, StopIteration):
                raise HTTPException(422, "Use a valid video up to 120 seconds and 4K resolution") from None
        else:
            try:
                info = await asyncio.to_thread(media.probe, path)
                streams = info.get("streams", [])
                if not any(s["codec_type"] == "audio" for s in streams) or any(s["codec_type"] == "video" for s in streams):
                    raise ValueError("Expected audio only")
                asset.duration_seconds = float(info["format"]["duration"])
                if not 0 < asset.duration_seconds <= 300:
                    raise ValueError("Music must be at most 5 minutes")
            except (RuntimeError, KeyError, ValueError):
                raise HTTPException(422, "Unsupported audio or music longer than 5 minutes") from None
        if project.current_output or project.edit_history or project.assets:
            project.undo_stack = (project.undo_stack + [_snapshot(project)])[-10:]
            project.redo_stack.clear()
        project.assets.append(asset)
        storage.save(project)
        return project
    except BaseException:
        if path:
            path.unlink(missing_ok=True)
        raise
    finally:
        busy.discard(project_id)


@app.get("/api/projects/{project_id}/assets/{asset_id}")
async def asset_file(project_id: str, asset_id: str):
    project = get_project(project_id)
    asset = next((a for a in project.assets if a.id == asset_id), None)
    if not asset:
        raise HTTPException(404, "Asset not found")
    return FileResponse(storage.project_dir(project_id) / asset.path)


@app.delete("/api/projects/{project_id}/assets/{asset_id}")
async def delete_asset(project_id: str, asset_id: str):
    project = claim(project_id)
    try:
        asset = next((a for a in project.assets if a.id == asset_id), None)
        if not asset:
            raise HTTPException(404, "Asset not found")
        # Only unlink physical file when no other clip or undo snapshot points to it (e.g. split clips).
        still_referenced = any(
            snap.assets and any(a.path == asset.path for a in snap.assets)
            for snap in (project.undo_stack + project.redo_stack)
        )
        project.assets.remove(asset)
        if _media_count(project) == 0:
            project.current_output = None
        if not still_referenced:
            (storage.project_dir(project_id) / asset.path).unlink(missing_ok=True)
        storage.save(project)
        return project
    finally:
        busy.discard(project_id)


def _sync_overlay_fields(values: dict) -> None:
    layers = values.get("text_layers") or []
    active_id = values.get("active_text_id")
    active = next((t for t in layers if t["id"] == active_id), None)
    if active is None:
        non_captions = [t for t in layers if not t.get("is_caption")]
        active = non_captions[-1] if non_captions else None
        values["active_text_id"] = active["id"] if active else None
    if active:
        values["overlay_text"] = active["text"]
        values["overlay_position"] = active["position"]
        values["overlay_color"] = active["color"] if active["color"] in {"lime", "white", "amber"} else "lime"
    else:
        values["overlay_text"] = None


def _ensure_hydrated_layers(values: dict) -> list[dict]:
    layers = list(values.get("text_layers") or [])
    if not layers and values.get("overlay_text"):
        layer = TextLayer(
            text=values["overlay_text"],
            position=values.get("overlay_position", "end_card"),
            color=values.get("overlay_color", "lime"),
        ).model_dump()
        layers.append(layer)
        values["text_layers"] = layers
        values["active_text_id"] = layer["id"]
    return layers


def _resolve_clip(new_assets: list[Asset], p: dict) -> Asset:
    media_indices = [idx for idx, a in enumerate(new_assets) if a.media_type in {"image", "video"}]
    if "asset_id" in p and p["asset_id"]:
        target = next((a for a in new_assets if a.id == p["asset_id"]), None)
        if not target:
            raise HTTPException(404, "Clip not found")
        return target
    clip_index = int(p.get("clip_index", 1))
    if not 1 <= clip_index <= len(media_indices):
        raise HTTPException(422, f"Choose clip numbers between 1 and {len(media_indices)}.")
    return new_assets[media_indices[clip_index - 1]]


def _parser_context(project: ProjectState) -> dict:
    s = project.settings
    active = None
    if s.active_text_id:
        active = next((t for t in s.text_layers if t.id == s.active_text_id), None)
    if active is None:
        non_captions = [t for t in s.text_layers if not t.is_caption]
        active = non_captions[-1] if non_captions else None
    return {
        "active_text_id": active.id if active else s.active_text_id,
        "active_text": active.text if active else s.overlay_text,
        "active_position": active.position if active else s.overlay_position,
        "brightness": s.brightness,
        "text_layers": [t.model_dump() for t in s.text_layers],
    }


def apply_operations(project: ProjectState, operations: list[EditOperation]) -> tuple[ReelSettings, list[Asset]]:
    values = project.settings.model_dump()
    new_assets = [a.model_copy(deep=True) for a in project.assets]
    for op in operations:
        p = op.parameters
        if op.type in {"create_reel", "set_duration"}:
            values["duration_seconds"] = p["duration_seconds"]
            if "aspect_ratio" in p and p["aspect_ratio"] in ASPECT_DIMENSIONS:
                w, h = ASPECT_DIMENSIONS[p["aspect_ratio"]]
                values["aspect_ratio"] = p["aspect_ratio"]
                values["width"], values["height"] = w, h
        elif op.type == "set_aspect_ratio":
            ratio = p.get("aspect_ratio", "9:16")
            if ratio in ASPECT_DIMENSIONS:
                w, h = ASPECT_DIMENSIONS[ratio]
                values["aspect_ratio"] = ratio
                values["width"], values["height"] = w, h
        elif op.type == "set_zoom_style":
            values["zoom_style"] = p["style"]
        elif op.type == "set_music":
            values["music_enabled"] = p["enabled"]
        elif op.type == "set_music_volume":
            values["music_volume"] = round(max(0, min(1, values["music_volume"] + (-0.08 if p["direction"] == "decrease" else 0.08))), 2)
        elif op.type == "set_clip_audio":
            values["keep_clip_audio"] = bool(p["enabled"])
        elif op.type == "set_fit_mode":
            values["fit_mode"] = p["mode"]
        elif op.type in {"set_text_overlay", "update_text_layer"}:
            layers = _ensure_hydrated_layers(values)
            target_id = p.get("target_id") or p.get("layer_id")
            if p.get("text") is None and op.type == "set_text_overlay":
                if target_id:
                    layers = [t for t in layers if t["id"] != target_id]
                else:
                    layers = [t for t in layers if t.get("is_caption")]
                values["text_layers"] = layers
                values["active_text_id"] = None
                _sync_overlay_fields(values)
            else:
                existing = next((t for t in layers if t["id"] == target_id), None) if target_id else None
                if existing is not None:
                    if "text" in p and p["text"] is not None:
                        existing["text"] = p["text"]
                    if not p.get("preserve_placement") and p.get("placement"):
                        existing["position"] = p["placement"]
                    if p.get("color"):
                        existing["color"] = p["color"]
                    if p.get("animation"):
                        existing["animation"] = p["animation"]
                    if p.get("clip_index") is not None:
                        existing["clip_index"] = p["clip_index"]
                    values["active_text_id"] = existing["id"]
                else:
                    new_layer = TextLayer(
                        id=target_id or uid(),
                        text=p["text"],
                        position=p.get("placement") or values.get("overlay_position", "end_card"),
                        color=p.get("color") or values.get("overlay_color", "lime"),
                        animation=p.get("animation") or "none",
                        clip_index=p.get("clip_index"),
                    ).model_dump()
                    layers.append(new_layer)
                    values["text_layers"] = layers
                    values["active_text_id"] = new_layer["id"]
                _sync_overlay_fields(values)
        elif op.type == "remove_text_layer":
            layers = _ensure_hydrated_layers(values)
            layer_id = p.get("layer_id") or values.get("active_text_id")
            values["text_layers"] = [t for t in layers if t["id"] != layer_id]
            if values.get("active_text_id") == layer_id:
                values["active_text_id"] = None
            _sync_overlay_fields(values)
        elif op.type == "set_overlay_style":
            layers = _ensure_hydrated_layers(values)
            target_id = p.get("target_id") or values.get("active_text_id")
            active = next((t for t in layers if t["id"] == target_id), None)
            if p.get("position") is not None:
                values["overlay_position"] = p["position"]
                if active:
                    active["position"] = p["position"]
            if p.get("color") is not None:
                values["overlay_color"] = p["color"]
                if active:
                    active["color"] = p["color"]
            if p.get("animation") is not None and active:
                active["animation"] = p["animation"]
            values["text_layers"] = layers
        elif op.type == "set_brightness":
            if "delta" in p:
                values["brightness"] = round(max(-0.3, min(0.3, float(values["brightness"]) + float(p["delta"]))), 2)
            else:
                values["brightness"] = p["value"]
        elif op.type == "set_transition":
            if p.get("style") is not None:
                values["transition_style"] = p["style"]
            if p.get("duration") is not None:
                values["transition_duration"] = p["duration"]
        elif op.type == "set_filter":
            values["filter_preset"] = p["preset"]
        elif op.type == "set_clip_speed":
            speed = float(p["speed"])
            if "clip_index" in p or "asset_id" in p:
                target = _resolve_clip(new_assets, p)
                target.speed = speed
            else:
                values["speed_curve"] = "slow_mo" if speed < 0.9 else "fast" if speed > 1.1 else "normal"
                for a in new_assets:
                    if a.media_type in {"image", "video"}:
                        a.speed = speed
        elif op.type == "split_clip":
            media_indices = [idx for idx, a in enumerate(new_assets) if a.media_type in {"image", "video"}]
            if len(media_indices) >= 5:
                raise HTTPException(422, "Cannot split clip: project already has the maximum 5 media clips.")
            target = _resolve_clip(new_assets, p)
            if target.media_type != "video":
                raise HTTPException(422, f"Only video clips can be split; {target.filename} is a photo.")
            dur = target.duration_seconds or 0.0
            eff_start = target.trim_start or 0.0
            eff_end = target.trim_end if target.trim_end is not None else dur
            split_at = float(p["split_at_seconds"])
            if not (eff_start + 0.2 <= split_at <= eff_end - 0.2):
                raise HTTPException(422, f"Choose a split point between {eff_start + 0.2:.1f}s and {eff_end - 0.2:.1f}s.")
            target_idx = new_assets.index(target)
            second = target.model_copy(deep=True)
            second.id = uid()
            second.filename = f"{Path(target.filename).stem}-part2{Path(target.filename).suffix}"
            target.trim_end = round(split_at, 2)
            second.trim_start = round(split_at, 2)
            second.trim_end = round(eff_end, 2)
            new_assets.insert(target_idx + 1, second)
        elif op.type == "set_audio_processing":
            for key in ("audio_normalize", "audio_denoise", "voice_enhance", "vocal_isolation"):
                if key in p and p[key] is not None:
                    values[key] = p[key]
        elif op.type == "set_visual_effect":
            targets = [_resolve_clip(new_assets, p)] if ("clip_index" in p or "asset_id" in p) else [a for a in new_assets if a.media_type in {"image", "video"}]
            if not targets:
                raise HTTPException(422, "Upload a photo or video clip before applying visual effects.")
            for target in targets:
                if "cutout_mode" in p and p["cutout_mode"] is not None:
                    target.cutout_mode = p["cutout_mode"]
                if "chroma_color" in p and p["chroma_color"] is not None:
                    target.chroma_color = p["chroma_color"]
                if "chroma_similarity" in p and p["chroma_similarity"] is not None:
                    target.chroma_similarity = p["chroma_similarity"]
                if "stabilize" in p and p["stabilize"] is not None:
                    target.stabilize = bool(p["stabilize"])
                if "relight" in p and p["relight"] is not None:
                    target.relight = float(p["relight"])
        elif op.type == "set_keyframes":
            if "asset_id" in p and p["asset_id"]:
                target = _resolve_clip(new_assets, p)
                target.keyframes = p["keyframes"]
            else:
                values["keyframes"] = p["keyframes"]
        elif op.type == "set_sticker":
            values["sticker_badge"] = p["sticker_badge"]
        elif op.type == "apply_template":
            for key, val in p.items():
                if key in values:
                    values[key] = val
            _sync_overlay_fields(values)
        elif op.type == "reorder_assets":
            media_indices = [idx for idx, a in enumerate(new_assets) if a.media_type in {"image", "video"}]
            if "ordered_ids" in p:
                ordered_ids = list(p["ordered_ids"])
                current_media = [new_assets[idx] for idx in media_indices]
                by_id = {a.id: a for a in current_media}
                if set(ordered_ids) != set(by_id) or len(ordered_ids) != len(current_media):
                    raise HTTPException(422, "Invalid clip order")
                reordered = [by_id[aid] for aid in ordered_ids]
                for slot, idx in enumerate(media_indices):
                    new_assets[idx] = reordered[slot]
            else:
                from_idx, to_idx = int(p["from_index"]), int(p["to_index"])
                if not (1 <= from_idx <= len(media_indices) and 1 <= to_idx <= len(media_indices)):
                    raise HTTPException(422, f"Choose clip numbers between 1 and {len(media_indices)}.")
                i1, i2 = media_indices[from_idx - 1], media_indices[to_idx - 1]
                if p.get("mode") == "swap":
                    new_assets[i1], new_assets[i2] = new_assets[i2], new_assets[i1]
                else:
                    media_list = [new_assets[idx] for idx in media_indices]
                    item = media_list.pop(from_idx - 1)
                    media_list.insert(to_idx - 1, item)
                    for slot, idx in enumerate(media_indices):
                        new_assets[idx] = media_list[slot]
        elif op.type == "trim_clip":
            target = _resolve_clip(new_assets, p)
            if target.media_type != "video":
                raise HTTPException(422, f"Only video clips can be trimmed; {target.filename} is a photo.")
            dur = target.duration_seconds or 0.0
            if dur <= 0.2:
                raise HTTPException(422, "This video clip is too short to trim.")
            if "trim_start" in p or "trim_end" in p:
                new_start = float(p["trim_start"]) if p.get("trim_start") is not None else target.trim_start
                new_end = float(p["trim_end"]) if p.get("trim_end") is not None else target.trim_end
            elif "cut_start_seconds" in p:
                new_start = target.trim_start + float(p["cut_start_seconds"])
                new_end = target.trim_end
            elif "cut_end_seconds" in p:
                base_end = target.trim_end if target.trim_end is not None else dur
                new_start = target.trim_start
                new_end = base_end - float(p["cut_end_seconds"])
            else:
                raise HTTPException(422, "Specify start or end trim times.")
            effective_end = dur if new_end is None else min(dur, new_end)
            if new_start < 0 or effective_end - new_start < 0.2:
                raise HTTPException(422, "Trim range must leave at least 0.2 seconds of video.")
            target.trim_start = round(new_start, 2)
            target.trim_end = round(effective_end, 2) if new_end is not None else None
    return ReelSettings.model_validate(values), new_assets


def _snapshot(project: ProjectState) -> Snapshot:
    return Snapshot(
        settings=project.settings.model_copy(deep=True),
        edit_history=list(project.edit_history),
        revision=project.current_render_revision,
        output=project.current_output,
        assets=[a.model_copy(deep=True) for a in project.assets],
    )


def _commit_render(
    project: ProjectState,
    new_settings: ReelSettings,
    new_assets: list[Asset],
    operations: list[EditOperation],
    output: Path,
    revision: int,
) -> None:
    previous = _snapshot(project)
    project.settings = new_settings
    project.assets = new_assets
    project.undo_stack = (project.undo_stack + [previous])[-10:]
    project.redo_stack.clear()
    project.edit_history.extend(operations)
    project.current_render_revision = revision
    project.next_revision = revision + 1
    project.current_output = str(output.relative_to(storage.project_dir(project.id))).replace("\\", "/")
    storage.save(project)


async def _run_render_job(project: ProjectState, new_settings: ReelSettings, new_assets: list[Asset], operations: list[EditOperation], job: Job):
    try:
        async with render_gate:
            job.status = "running"
            candidate = project.model_copy(deep=True)
            candidate.settings = new_settings
            candidate.assets = new_assets
            revision = project.next_revision
            output = await asyncio.to_thread(media.render, candidate, revision, lambda message: setattr(job, "stage", message))
            _commit_render(project, new_settings, new_assets, operations, output, revision)
            # Clear busy flag BEFORE publishing done status so immediate follow-ups never hit 409.
            busy.discard(project.id)
            job.status, job.stage, job.revision = "done", "Ready to preview", revision
    except HTTPException as exc:
        busy.discard(project.id)
        job.status, job.stage = "failed", "Rendering failed"
        job.error = exc.detail
    except Exception:
        busy.discard(project.id)
        job.status, job.stage = "failed", "Rendering failed"
        job.error = "The renderer could not finish. The previous reel is preserved. Check server media dependencies and retry."
        logging.getLogger("sollicut").exception("Render failed for project %s", project.id)
    finally:
        busy.discard(project.id)


async def render_job(project, parsed, job):
    try:
        new_settings, new_assets = apply_operations(project, parsed.operations)
    except HTTPException as exc:
        busy.discard(project.id)
        job.status, job.stage, job.error = "failed", "Rendering failed", exc.detail
        return
    await _run_render_job(project, new_settings, new_assets, parsed.operations, job)


def restore(project: ProjectState) -> ProjectState:
    if not project.undo_stack:
        raise HTTPException(409, "There is no edit to undo")
    current = _snapshot(project)
    previous = project.undo_stack.pop()
    project.redo_stack = (project.redo_stack + [current])[-10:]
    project.settings = previous.settings
    project.edit_history = previous.edit_history
    project.current_render_revision = previous.revision
    project.current_output = previous.output
    if previous.assets is not None:
        project.assets = previous.assets
    storage.save(project)
    return project


def redo_restore(project: ProjectState) -> ProjectState:
    if not project.redo_stack:
        raise HTTPException(409, "There is no edit to redo")
    current = _snapshot(project)
    nxt = project.redo_stack.pop()
    project.undo_stack = (project.undo_stack + [current])[-10:]
    project.settings = nxt.settings
    project.edit_history = nxt.edit_history
    project.current_render_revision = nxt.revision
    project.current_output = nxt.output
    if nxt.assets is not None:
        project.assets = nxt.assets
    storage.save(project)
    return project


def _enqueue_job(project: ProjectState, stage: str) -> Job:
    if len(busy) > 4:
        raise HTTPException(429, "The local server is busy. Try again after the current renders finish.")
    job = Job(project_id=project.id, stage=stage)
    # Keep job memory bounded; active jobs are never discarded.
    if len(jobs) >= 100:
        for key in list(jobs):
            if jobs[key].status in {"done", "failed"}:
                del jobs[key]
                break
    jobs[job.id] = job
    return job


def dispatch(project, parsed):
    if parsed.requires_clarification:
        return {"parsed_command": parsed, "requires_clarification": True}
    if parsed.operations[0].type == "undo":
        return {"parsed_command": parsed, "project": restore(project)}
    if parsed.operations[0].type == "redo":
        return {"parsed_command": parsed, "project": redo_restore(project)}
    if parsed.operations[0].type == "export":
        if not project.current_output:
            raise HTTPException(409, "Create a reel before downloading")
        return {"parsed_command": parsed, "download_url": f"/api/projects/{project.id}/download"}
    if not media_status.get("available"):
        raise HTTPException(503, "Renderer unavailable; check /api/capabilities")
    quota(project.id, 50 * 1024 * 1024)
    # Validate operations synchronously before queueing so invalid clip indices/trims return 422 immediately.
    apply_operations(project, parsed.operations)
    job = _enqueue_job(project, "Waiting for renderer")
    track(render_job(project, parsed, job))
    return {"parsed_command": parsed, "requires_clarification": False, "job_id": job.id}


def _media_count(project: ProjectState) -> int:
    return sum(a.media_type in {"image", "video"} for a in project.assets)


@app.post("/api/projects/{project_id}/apply")
async def apply(project_id: str, body: ApplyRequest):
    project = claim(project_id)
    result = None
    try:
        parsed = parse(body.transcript, _media_count(project), bool(project.current_output), context=_parser_context(project))
        result = dispatch(project, parsed)
        return result
    finally:
        if not result or "job_id" not in result:
            busy.discard(project_id)


@app.post("/api/projects/{project_id}/edit")
async def visual_edit(project_id: str, body: VisualEditRequest):
    project = claim(project_id)
    result = None
    try:
        operations: list[EditOperation] = []
        if body.reorder_asset_ids is not None:
            operations.append(EditOperation(type="reorder_assets", parameters={"ordered_ids": body.reorder_asset_ids}, source_transcript="[editor reorder]"))
        if body.split_asset_id is not None and body.split_at_seconds is not None:
            operations.append(EditOperation(type="split_clip", parameters={"asset_id": body.split_asset_id, "split_at_seconds": body.split_at_seconds}, source_transcript="[editor split]"))
        if body.trim_asset_id is not None:
            operations.append(EditOperation(type="trim_clip", parameters={"asset_id": body.trim_asset_id, "trim_start": body.trim_start, "trim_end": body.trim_end}, source_transcript="[editor trim]"))
        if body.duration_seconds is not None:
            operations.append(EditOperation(type="set_duration", parameters={"duration_seconds": body.duration_seconds}, source_transcript="[editor duration]"))
        if body.aspect_ratio is not None:
            operations.append(EditOperation(type="set_aspect_ratio", parameters={"aspect_ratio": body.aspect_ratio}, source_transcript="[editor aspect ratio]"))
        if body.zoom_style is not None:
            operations.append(EditOperation(type="set_zoom_style", parameters={"style": body.zoom_style}, source_transcript="[editor zoom]"))
        if body.music_enabled is not None:
            operations.append(EditOperation(type="set_music", parameters={"enabled": body.music_enabled}, source_transcript="[editor music]"))
        if body.keep_clip_audio is not None:
            operations.append(EditOperation(type="set_clip_audio", parameters={"enabled": body.keep_clip_audio}, source_transcript="[editor clip audio]"))
        if body.fit_mode is not None:
            operations.append(EditOperation(type="set_fit_mode", parameters={"mode": body.fit_mode}, source_transcript="[editor fit mode]"))
        if body.brightness is not None:
            operations.append(EditOperation(type="set_brightness", parameters={"value": body.brightness}, source_transcript="[editor brightness]"))
        if body.transition_style is not None or body.transition_duration is not None:
            operations.append(EditOperation(type="set_transition", parameters={"style": body.transition_style, "duration": body.transition_duration}, source_transcript="[editor transition]"))
        if body.filter_preset is not None:
            operations.append(EditOperation(type="set_filter", parameters={"preset": body.filter_preset}, source_transcript="[editor filter]"))
        if body.sticker_badge is not None:
            operations.append(EditOperation(type="set_sticker", parameters={"sticker_badge": body.sticker_badge}, source_transcript="[editor sticker]"))
        if any(x is not None for x in (body.audio_normalize, body.audio_denoise, body.voice_enhance, body.vocal_isolation)):
            operations.append(EditOperation(
                type="set_audio_processing",
                parameters={
                    "audio_normalize": body.audio_normalize,
                    "audio_denoise": body.audio_denoise,
                    "voice_enhance": body.voice_enhance,
                    "vocal_isolation": body.vocal_isolation,
                },
                source_transcript="[editor audio processing]",
            ))
        if body.clip_asset_id and any(x is not None for x in (body.clip_cutout_mode, body.clip_chroma_color, body.clip_chroma_similarity, body.clip_stabilize, body.clip_relight)):
            operations.append(EditOperation(
                type="set_visual_effect",
                parameters={
                    "asset_id": body.clip_asset_id,
                    "cutout_mode": body.clip_cutout_mode,
                    "chroma_color": body.clip_chroma_color,
                    "chroma_similarity": body.clip_chroma_similarity,
                    "stabilize": body.clip_stabilize,
                    "relight": body.clip_relight,
                },
                source_transcript="[editor clip fx]",
            ))
        if body.clip_asset_id and body.clip_speed is not None:
            operations.append(EditOperation(type="set_clip_speed", parameters={"asset_id": body.clip_asset_id, "speed": body.clip_speed}, source_transcript="[editor clip speed]"))
        if body.keyframes is not None:
            operations.append(EditOperation(type="set_keyframes", parameters={"keyframes": [k.model_dump() for k in body.keyframes]}, source_transcript="[editor keyframes]"))
        if body.clip_asset_id and body.clip_keyframes is not None:
            operations.append(EditOperation(type="set_keyframes", parameters={"asset_id": body.clip_asset_id, "keyframes": [k.model_dump() for k in body.clip_keyframes]}, source_transcript="[editor clip keyframes]"))
        if body.clear_overlay:
            operations.append(EditOperation(
                type="set_text_overlay",
                parameters={"text": None, "target_id": body.active_text_id or project.settings.active_text_id, "placement": body.overlay_position or project.settings.overlay_position},
                source_transcript="[editor clear text]",
            ))
        elif body.overlay_text is not None:
            clean_text = body.overlay_text.strip()
            if clean_text and ("/" in clean_text or "\\" in clean_text or ".." in clean_text):
                raise HTTPException(422, "Use promotional text without file paths.")
            operations.append(EditOperation(
                type="set_text_overlay",
                parameters={
                    "text": clean_text or None,
                    "target_id": body.active_text_id or project.settings.active_text_id,
                    "placement": body.overlay_position or project.settings.overlay_position,
                    "color": body.overlay_color,
                    "animation": body.overlay_animation,
                },
                source_transcript="[editor text]",
            ))
        if body.overlay_color is not None or body.overlay_animation is not None or (
            body.overlay_position is not None and not body.clear_overlay and body.overlay_text is None
        ):
            operations.append(EditOperation(
                type="set_overlay_style",
                parameters={
                    "target_id": body.active_text_id or project.settings.active_text_id,
                    "position": body.overlay_position,
                    "color": body.overlay_color,
                    "animation": body.overlay_animation,
                },
                source_transcript="[editor overlay style]",
            ))

        new_settings, new_assets = apply_operations(project, operations)
        settings_dump = new_settings.model_dump()
        if body.text_layers is not None:
            settings_dump["text_layers"] = [t.model_dump() for t in body.text_layers]
        if body.active_text_id is not None:
            settings_dump["active_text_id"] = body.active_text_id
        if body.text_layers is not None or body.active_text_id is not None:
            _sync_overlay_fields(settings_dump)
        if body.music_volume is not None:
            settings_dump["music_volume"] = round(body.music_volume, 2)
        if body.clip_audio_volume is not None:
            settings_dump["clip_audio_volume"] = round(body.clip_audio_volume, 2)
        if body.speed_curve is not None:
            settings_dump["speed_curve"] = body.speed_curve
        if body.narration_enabled is not None:
            settings_dump["narration_enabled"] = body.narration_enabled
        if body.narration_volume is not None:
            settings_dump["narration_volume"] = round(body.narration_volume, 2)
        if body.clip_asset_id and body.clip_volume is not None:
            for a in new_assets:
                if a.id == body.clip_asset_id:
                    a.volume = round(body.clip_volume, 2)
        if body.clip_asset_id and body.clip_filter_preset is not None:
            for a in new_assets:
                if a.id == body.clip_asset_id:
                    a.filter_preset = body.clip_filter_preset
        merged_settings = ReelSettings.model_validate(settings_dump)

        if not body.render or _media_count(project) == 0:
            previous = _snapshot(project)
            project.settings = merged_settings
            project.assets = new_assets
            project.undo_stack = (project.undo_stack + [previous])[-10:]
            project.redo_stack.clear()
            project.edit_history.extend(operations)
            storage.save(project)
            result = {"project": project}
            return result

        if not media_status.get("available"):
            raise HTTPException(503, "Renderer unavailable; check /api/capabilities")
        quota(project.id, 50 * 1024 * 1024)
        job = _enqueue_job(project, "Waiting for renderer")
        track(_run_render_job(project, merged_settings, new_assets, operations, job))
        result = {"job_id": job.id}
        return result
    finally:
        if not result or "job_id" not in result:
            busy.discard(project_id)


@app.post("/api/projects/{project_id}/undo")
async def undo(project_id: str):
    project = claim(project_id)
    try:
        return restore(project)
    finally:
        busy.discard(project_id)


@app.post("/api/projects/{project_id}/redo")
async def redo(project_id: str):
    project = claim(project_id)
    try:
        return redo_restore(project)
    finally:
        busy.discard(project_id)


@app.get("/api/assets-catalog")
def read_assets_catalog():
    return assets_catalog.get_catalog()


@app.post("/api/projects/{project_id}/apply-template")
async def apply_template(project_id: str, body: ApplyTemplateRequest):
    project = claim(project_id)
    result = None
    try:
        tpl = next((t for t in assets_catalog.TEMPLATES if t["id"] == body.template_id), None)
        if not tpl:
            raise HTTPException(404, "Template not found")
        op = EditOperation(
            type="apply_template",
            parameters=tpl["settings"],
            source_transcript=f"[template: {tpl['id']}]",
        )
        new_settings, new_assets = apply_operations(project, [op])
        if not body.render or _media_count(project) == 0 or not media_status.get("available"):
            previous = _snapshot(project)
            project.settings = new_settings
            project.assets = new_assets
            project.undo_stack = (project.undo_stack + [previous])[-10:]
            project.redo_stack.clear()
            project.edit_history.append(op)
            storage.save(project)
            result = {"project": project}
            return result
        quota(project.id, 50 * 1024 * 1024)
        job = _enqueue_job(project, f"Applying {tpl['name']}")
        track(_run_render_job(project, new_settings, new_assets, [op], job))
        result = {"job_id": job.id}
        return result
    finally:
        if not result or "job_id" not in result:
            busy.discard(project_id)


@app.post("/api/projects/{project_id}/attach-catalog-audio")
async def attach_catalog_audio(project_id: str, body: AttachAudioRequest):
    project = claim(project_id)
    result = None
    try:
        pack = next((a for a in assets_catalog.AUDIO_PACKS if a["id"] == body.audio_id), None)
        if not pack:
            raise HTTPException(404, "Audio pack not found")
        folder = pack.get("folder", "demo")
        src = storage.ROOT / "assets" / folder / pack["filename"]
        if not src.is_file():
            raise HTTPException(404, "Audio pack file missing")
        previous = _snapshot(project)
        pdir = storage.project_dir(project_id)
        for existing in [a for a in project.assets if a.media_type == "audio"]:
            project.assets.remove(existing)
        asset_id = str(uuid4())
        ext = Path(pack["filename"]).suffix or ".wav"
        dest = pdir / "assets" / f"{asset_id}{ext}"
        shutil.copy2(src, dest)
        asset = Asset(
            id=asset_id,
            filename=pack["name"],
            media_type="audio",
            path=f"assets/{dest.name}",
            duration_seconds=float(pack["duration_seconds"]),
        )
        project.assets.append(asset)
        project.settings.music_enabled = True
        project.undo_stack = (project.undo_stack + [previous])[-10:]
        project.redo_stack.clear()
        if not body.render or _media_count(project) == 0 or not media_status.get("available"):
            storage.save(project)
            result = {"project": project}
            return result
        job = _enqueue_job(project, f"Attaching {pack['name']}")
        track(_run_render_job(project, project.settings.model_copy(deep=True), [a.model_copy(deep=True) for a in project.assets], [], job))
        result = {"job_id": job.id}
        return result
    finally:
        if not result or "job_id" not in result:
            busy.discard(project_id)


@app.get("/api/assets-catalog/audio/{audio_id}")
def preview_catalog_audio(audio_id: str):
    pack = next((a for a in assets_catalog.AUDIO_PACKS if a["id"] == audio_id), None)
    if not pack:
        raise HTTPException(404, "Audio pack not found")
    src = storage.ROOT / "assets" / pack.get("folder", "demo") / pack["filename"]
    if not src.is_file():
        raise HTTPException(404, "Audio pack file missing")
    media_type = "audio/mpeg" if src.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(src, media_type=media_type)


@app.post("/api/projects/{project_id}/tts")
async def generate_tts(project_id: str, body: TTSRequest):
    project = claim(project_id)
    result = None
    try:
        if not tts_engine.status()["available"]:
            raise HTTPException(503, "Offline TTS engine unavailable on server.")
        narration_id = str(uuid4())
        wav_path = storage.project_dir(project_id) / "audio" / f"tts-{narration_id}.wav"
        dur = await tts_engine.synthesize(body.text.strip(), wav_path, language=body.language, rate=body.rate)
        new_settings = project.settings.model_copy(deep=True)
        new_settings.narration_enabled = True
        new_settings.narration_asset_id = narration_id
        op = EditOperation(
            type="generate_tts",
            parameters={"language": body.language, "duration_seconds": dur},
            source_transcript=body.text[:100],
        )
        if not body.render or _media_count(project) == 0 or not media_status.get("available"):
            previous = _snapshot(project)
            project.settings = new_settings
            project.undo_stack = (project.undo_stack + [previous])[-10:]
            project.redo_stack.clear()
            project.edit_history.append(op)
            storage.save(project)
            result = {"project": project, "narration_duration": dur, "narration_url": f"/api/projects/{project_id}/narration"}
            return result
        job = _enqueue_job(project, "Mixing TTS narration")
        track(_run_render_job(project, new_settings, [a.model_copy(deep=True) for a in project.assets], [op], job))
        result = {"job_id": job.id, "narration_duration": dur, "narration_url": f"/api/projects/{project_id}/narration"}
        return result
    finally:
        if not result or "job_id" not in result:
            busy.discard(project_id)


@app.get("/api/projects/{project_id}/narration")
async def narration_file(project_id: str):
    project = get_project(project_id)
    nid = project.settings.narration_asset_id
    if not nid:
        raise HTTPException(404, "No narration track generated")
    try:
        if str(UUID(nid)) != nid:
            raise ValueError("Invalid narration id")
    except ValueError:
        raise HTTPException(404, "Invalid narration id") from None
    wav_path = storage.project_dir(project_id) / "audio" / f"tts-{nid}.wav"
    if not wav_path.is_file():
        raise HTTPException(404, "Narration file not found")
    return FileResponse(wav_path, media_type="audio/wav")


@app.post("/api/projects/{project_id}/auto-captions")
async def auto_captions(project_id: str, body: AutoCaptionRequest):
    project = claim(project_id)
    result = None
    wav_path = None
    try:
        pdir = storage.project_dir(project_id)
        if body.asset_id:
            source_asset = next((a for a in project.assets if a.id == body.asset_id), None)
        else:
            source_asset = next((a for a in project.assets if a.media_type == "video"), None) or next(
                (a for a in project.assets if a.media_type == "audio"), None
            )
        if not source_asset:
            raise HTTPException(422, "Upload a video clip or audio track first to auto-generate captions.")
        wav_path = pdir / "audio" / f"cap-{uuid4()}.wav"
        await asyncio.to_thread(
            media.run,
            ["ffmpeg", "-v", "error", "-y", "-i", str(pdir / source_asset.path), "-vn", "-ar", "16000", "-ac", "1", str(wav_path)],
            45,
        )
        try:
            segments = await speech.transcribe_segments(wav_path, body.language_hint)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from None
        new_settings = project.settings.model_copy(deep=True)
        kept_non_captions = [t for t in new_settings.text_layers if not t.is_caption]
        caption_layers = [
            TextLayer(
                text=seg["text"][:100],
                position="bottom",
                color="white",
                start_time=seg["start"],
                end_time=max(seg["start"] + 0.3, seg["end"]),
                is_caption=True,
            )
            for seg in segments
        ]
        new_settings.text_layers = kept_non_captions + caption_layers
        op = EditOperation(
            type="set_text_overlay",
            parameters={"captions_count": len(caption_layers)},
            source_transcript="[auto captions]",
        )
        if not body.render or _media_count(project) == 0 or not media_status.get("available"):
            previous = _snapshot(project)
            project.settings = new_settings
            project.undo_stack = (project.undo_stack + [previous])[-10:]
            project.redo_stack.clear()
            project.edit_history.append(op)
            storage.save(project)
            result = {"project": project, "captions": [c.model_dump() for c in caption_layers]}
            return result
        job = _enqueue_job(project, "Burning auto-captions")
        track(_run_render_job(project, new_settings, [a.model_copy(deep=True) for a in project.assets], [op], job))
        result = {"job_id": job.id, "captions": [c.model_dump() for c in caption_layers]}
        return result
    finally:
        if wav_path:
            wav_path.unlink(missing_ok=True)
        if not result or "job_id" not in result:
            busy.discard(project_id)


@app.post("/api/projects/{project_id}/voice-command")
async def voice(project_id: str, file: UploadFile = File(...), language_hint: str | None = Form(None), mode: str = Form("edit")):
    project = claim(project_id)
    result, path = None, None
    try:
        if language_hint not in {None, "ta", "en"}:
            raise HTTPException(422, "Language must be Tamil, English or automatic")
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".webm", ".ogg", ".mp4", ".m4a", ".wav"} or not (file.content_type or "").split(";")[0] in {
            "audio/webm", "video/webm", "audio/ogg", "audio/mp4", "video/mp4", "audio/wav", "audio/x-wav"
        }:
            raise HTTPException(415, "Unsupported microphone recording format")
        quota(project_id, 20 * 1024 * 1024)
        path = storage.project_dir(project_id) / "audio" / f"{uuid4()}{suffix}"
        await receive(file, path, 20 * 1024 * 1024)
        try:
            info = await asyncio.to_thread(media.probe, path)
            if not any(s["codec_type"] == "audio" for s in info["streams"]):
                raise ValueError("No audio stream")
            # MediaRecorder WebM may omit duration. Decode to bounded PCM and measure it.
            wav = path.with_suffix(".decoded.wav")
            await asyncio.to_thread(media.run, ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vn", "-t", "31", "-ar", "16000", "-ac", "1", str(wav)], 35)
            import wave
            with wave.open(str(wav)) as recording:
                duration = recording.getnframes() / recording.getframerate()
            if not 0.2 <= duration <= 30.5:
                raise ValueError("Record between 0.2 and 30 seconds")
            transcript = await speech.transcribe(wav, language_hint)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except (RuntimeError, OSError):
            raise HTTPException(503, speech.error or "Transcription failed. Check the recording and try again.") from None
        if mode == "generate":
            return {"generation_prompt": transcript.text, "transcript": transcript.text, "requires_confirmation": True}
        parsed = parse(transcript.text, _media_count(project), bool(project.current_output), context=_parser_context(project))
        result = dispatch(project, parsed)
        return {**result, "transcript": transcript.text, "language": transcript.language, "asr_seconds": transcript.elapsed_seconds}
    finally:
        if path:
            path.unlink(missing_ok=True)
            path.with_suffix(".decoded.wav").unlink(missing_ok=True)
        if not result or "job_id" not in result:
            busy.discard(project_id)


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found; reload the project after a server restart")
    return jobs[job_id]


@app.get("/api/projects/{project_id}/video")
@app.get("/api/projects/{project_id}/download")
async def video(project_id: str, request: Request):
    project = get_project(project_id)
    if not project.current_output:
        raise HTTPException(404, "No rendered reel yet")
    return FileResponse(
        storage.project_dir(project_id) / project.current_output,
        media_type="video/mp4",
        filename="SolliCut-reel.mp4" if request.url.path.endswith("download") else None,
        headers={"Cache-Control": "no-store"},
    )


async def generate_job(project: ProjectState, body: GenerateRequest, ref_images: list[tuple[bytes, str]], job: Job):
    pdir = storage.project_dir(project.id)
    revision = project.next_revision
    output = pdir / "renders" / f"revision-{revision}.mp4"
    asset_id = str(uuid4())
    asset_path = pdir / "assets" / f"{asset_id}.mp4"
    try:
        job.status = "running"
        await generation.generate(
            body.transcript,
            output,
            duration_seconds=body.duration_seconds,
            aspect_ratio=body.aspect_ratio,
            reference_images=ref_images,
            stage=lambda message: setattr(job, "stage", message),
        )
        job.stage = "Validating generated video"
        info = await asyncio.to_thread(media.probe, output)
        video_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
        if not video_stream:
            raise RuntimeError("Generated file contains no video stream.")
        raw_dur = info.get("format", {}).get("duration") or video_stream.get("duration")
        try:
            duration = float(raw_dur) if raw_dur not in (None, "N/A") else float(body.duration_seconds)
        except ValueError:
            duration = float(body.duration_seconds)
        previous = _snapshot(project)
        if _media_count(project) < 5:
            shutil.copy2(output, asset_path)
            project.assets.append(
                Asset(
                    id=asset_id,
                    filename=f"gemini-ad-{revision}.mp4",
                    media_type="video",
                    path=f"assets/{asset_path.name}",
                    width=int(video_stream.get("width") or 720),
                    height=int(video_stream.get("height") or 1280),
                    duration_seconds=duration,
                )
            )
        project.undo_stack = (project.undo_stack + [previous])[-10:]
        project.redo_stack.clear()
        project.current_output = f"renders/{output.name}"
        project.current_render_revision = revision
        project.next_revision = revision + 1
        project.settings.duration_seconds = min(30.0, max(3.0, round(duration, 1)))
        storage.save(project)
        busy.discard(project.id)
        job.status, job.stage, job.revision = "done", "Ready to preview", revision
    except (ValueError, RuntimeError, OSError) as exc:
        output.unlink(missing_ok=True)
        asset_path.unlink(missing_ok=True)
        busy.discard(project.id)
        job.status, job.stage = "failed", "Generation failed"
        job.error = str(exc)
    except Exception:
        output.unlink(missing_ok=True)
        asset_path.unlink(missing_ok=True)
        busy.discard(project.id)
        job.status, job.stage = "failed", "Generation failed"
        job.error = "Cloud advertisement generation failed. Your previous reel is preserved."
        logging.getLogger("sollicut").exception("Gemini generation failed for project %s", project.id)
    finally:
        busy.discard(project.id)


@app.post("/api/projects/{project_id}/generate")
async def generate_ad(project_id: str, body: GenerateRequest):
    project = claim(project_id)
    started = False
    try:
        if not generation.status()["configured"]:
            raise HTTPException(503, "Key not set. Configure GEMINI_API_KEY on the server.")
        if len(body.reference_asset_ids) >= 2 and body.duration_seconds > 10:
            raise HTTPException(422, "When using 2 reference photos, Gemini Omni supports durations up to 10 seconds.")
        quota(project_id, 100 * 1024 * 1024)
        ref_images: list[tuple[bytes, str]] = []
        pdir = storage.project_dir(project_id)
        for ref_id in body.reference_asset_ids:
            asset = next((a for a in project.assets if a.id == ref_id), None)
            if not asset or asset.media_type != "image":
                raise HTTPException(422, "Reference media must be an uploaded photo from this project.")
            ref_images.append(((pdir / asset.path).read_bytes(), "image/jpeg"))
        job = _enqueue_job(project, "Submitting prompt to Gemini")
        track(generate_job(project, body, ref_images, job))
        started = True
        return {"job_id": job.id, "status": job.status, "stage": job.stage}
    finally:
        if not started:
            busy.discard(project_id)


frontend = storage.ROOT / "frontend/dist"
if frontend.is_dir():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
