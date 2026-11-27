import asyncio
import contextlib
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError

from . import media, storage
from .models import ApplyRequest, Asset, Job, ProjectState, ReelSettings, Snapshot
from .parser import parse
from .speech import FasterWhisperSpeechEngine

Image.MAX_IMAGE_PIXELS = 50_000_000
speech = FasterWhisperSpeechEngine()
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
    return {"status": "ok", "renderer": media_status, "asr": speech.status}


@app.get("/api/capabilities")
def capabilities():
    return {"renderer": media_status, "speech": {"engine": "faster-whisper", "status": speech.status, "error": speech.error},
            "limits": {"images": 5, "image_mb": 15, "voice_seconds": 30, "voice_mb": 20, "project_mb": 500}}


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
            raise HTTPException(415, "Use JPEG, PNG, WebP photos or WAV, MP3, M4A, OGG music")
        if (is_image or is_video) and sum(a.media_type in {"image", "video"} for a in project.assets) >= 5:
            raise HTTPException(422, "A project supports at most 5 photos")
        if not is_image and not is_video and any(a.media_type == "audio" for a in project.assets):
            raise HTTPException(422, "Remove the current music file before uploading another")
        expected_prefix = "image/" if is_image else "video/" if is_video else "audio/"
        if not (file.content_type or "").startswith(expected_prefix):
            raise HTTPException(415, "The uploaded media type does not match the file extension")
        quota(project_id, (100 if is_video else 20) * 1024 * 1024)
        identifier = str(uuid4())
        path = storage.project_dir(project_id) / "assets" / (identifier + suffix)
        await receive(file, path, (15 if is_image else 100 if is_video else 20) * 1024 * 1024)
        asset = Asset(id=identifier, filename=(file.filename or "media")[:150], media_type="image" if is_image else "video" if is_video else "audio", path=f"assets/{path.name}")
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
        project.assets.append(asset)
        project.current_output = None
        project.undo_stack.clear()
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
        project.assets.remove(asset)
        project.current_output = None
        project.undo_stack.clear()
        storage.save(project)
        (storage.project_dir(project_id) / asset.path).unlink(missing_ok=True)
        return project
    finally:
        busy.discard(project_id)


def updated_settings(project, operations):
    values = project.settings.model_dump()
    for op in operations:
        p = op.parameters
        if op.type in {"create_reel", "set_duration"}:
            values["duration_seconds"] = p["duration_seconds"]
        elif op.type == "set_zoom_style":
            values["zoom_style"] = p["style"]
        elif op.type == "set_music":
            values["music_enabled"] = p["enabled"]
        elif op.type == "set_music_volume":
            values["music_volume"] = round(max(0, min(1, values["music_volume"] + (-.08 if p["direction"] == "decrease" else .08))), 2)
        elif op.type == "set_text_overlay":
            values["overlay_text"], values["overlay_position"] = p["text"], p["placement"]
        elif op.type == "set_brightness":
            values["brightness"] = p["value"]
    return ReelSettings.model_validate(values)


async def render_job(project, parsed, job):
    try:
        async with render_gate:
            job.status = "running"
            previous = Snapshot(settings=project.settings.model_copy(deep=True), edit_history=list(project.edit_history), revision=project.current_render_revision, output=project.current_output)
            project.settings = updated_settings(project, parsed.operations)
            revision = project.next_revision
            output = await asyncio.to_thread(media.render, project, revision, lambda message: setattr(job, "stage", message))
            project.undo_stack = (project.undo_stack + [previous])[-10:]
            project.edit_history.extend(parsed.operations)
            project.current_render_revision = revision
            project.next_revision = revision + 1
            project.current_output = str(output.relative_to(storage.project_dir(project.id))).replace("\\", "/")
            storage.save(project)
            job.status, job.stage, job.revision = "done", "Ready to preview", revision
    except Exception:
        job.status, job.stage = "failed", "Rendering failed"
        job.error = "The renderer could not finish. The previous reel is preserved. Check server media dependencies and retry."
        import logging
        logging.getLogger("sollicut").exception("Render failed for project %s", project.id)
    finally:
        busy.discard(project.id)


def restore(project):
    if not project.undo_stack:
        raise HTTPException(409, "There is no edit to undo")
    previous = project.undo_stack.pop()
    project.settings = previous.settings
    project.edit_history = previous.edit_history
    project.current_render_revision = previous.revision
    project.current_output = previous.output
    storage.save(project)
    return project


def dispatch(project, parsed):
    if parsed.requires_clarification:
        return {"parsed_command": parsed, "requires_clarification": True}
    if parsed.operations[0].type == "undo":
        return {"parsed_command": parsed, "project": restore(project)}
    if parsed.operations[0].type == "export":
        if not project.current_output:
            raise HTTPException(409, "Create a reel before downloading")
        return {"parsed_command": parsed, "download_url": f"/api/projects/{project.id}/download"}
    if not media_status.get("available"):
        raise HTTPException(503, "Renderer unavailable; check /api/capabilities")
    if len(busy) > 4:
        raise HTTPException(429, "The local server is busy. Try again after the current renders finish.")
    quota(project.id, 50 * 1024 * 1024)
    job = Job(project_id=project.id)
    # Keep job memory bounded; active jobs are never discarded.
    if len(jobs) >= 100:
        for key in list(jobs):
            if jobs[key].status in {"done", "failed"}:
                del jobs[key]
                break
    jobs[job.id] = job
    track(render_job(project, parsed, job))
    return {"parsed_command": parsed, "requires_clarification": False, "job_id": job.id}


@app.post("/api/projects/{project_id}/apply")
async def apply(project_id: str, body: ApplyRequest):
    project = claim(project_id)
    result = None
    try:
        parsed = parse(body.transcript, max(3, sum(a.media_type in {"image", "video"} for a in project.assets)) if any(a.media_type in {"image", "video"} for a in project.assets) else 0, bool(project.current_output))
        result = dispatch(project, parsed)
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


@app.post("/api/projects/{project_id}/voice-command")
async def voice(project_id: str, file: UploadFile = File(...), language_hint: str | None = Form(None)):
    project = claim(project_id)
    result, path = None, None
    try:
        if language_hint not in {None, "ta", "en"}:
            raise HTTPException(422, "Language must be Tamil, English or automatic")
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".webm", ".ogg", ".mp4", ".m4a", ".wav"} or not (file.content_type or "").split(";")[0] in {"audio/webm", "video/webm", "audio/ogg", "audio/mp4", "video/mp4", "audio/wav", "audio/x-wav"}:
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
            if not .2 <= duration <= 30.5:
                raise ValueError("Record between 0.2 and 30 seconds")
            transcript = await speech.transcribe(wav, language_hint)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except (RuntimeError, OSError):
            raise HTTPException(503, speech.error or "Transcription failed. Check the recording and try again.") from None
        parsed = parse(transcript.text, max(3, sum(a.media_type in {"image", "video"} for a in project.assets)) if any(a.media_type in {"image", "video"} for a in project.assets) else 0, bool(project.current_output))
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
    return FileResponse(storage.project_dir(project_id) / project.current_output, media_type="video/mp4",
        filename="SolliCut-reel.mp4" if request.url.path.endswith("download") else None,
        headers={"Cache-Control": "no-store"})


frontend = storage.ROOT / "frontend/dist"
if frontend.is_dir():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
