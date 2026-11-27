import asyncio
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import main, storage
from backend.app.models import TranscriptResult
from backend.app.speech import FasterWhisperSpeechEngine


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.speech, "initialize", lambda: None)
    main.busy.clear()
    main.jobs.clear()
    with TestClient(main.app) as client:
        yield client


def photo():
    stream = io.BytesIO()
    Image.new("RGB", (128, 128), "coral").save(stream, "PNG")
    return stream.getvalue()


def test_upload_validation_and_reset(client):
    pid = client.post("/api/projects").json()["id"]
    root = f"/api/projects/{pid}"
    assert client.get(root).status_code == 200
    assert client.post(root+"/assets", files={"file": ("run.exe", b"bad", "application/octet-stream")}).status_code == 415
    assert client.post(root+"/assets", files={"file": ("fake.png", b"bad", "image/png")}).status_code == 422
    assert client.post(root+"/assets", files={"file": ("fake.jpg", photo(), "image/jpeg")}).status_code == 422
    for i in range(5):
        result = client.post(root+"/assets", files={"file": ("../../photo.png", photo(), "image/png")})
        assert result.status_code == 200, result.text
    state = result.json()
    assert all(".." not in a["path"] for a in state["assets"])
    assert client.post(root+"/assets", files={"file": ("six.png", photo(), "image/png")}).status_code == 422
    assert client.get(root+"/assets/"+state["assets"][0]["id"]).status_code == 200
    assert client.delete(root+"/assets/"+state["assets"][0]["id"]).status_code == 200
    assert client.delete(root).status_code == 200
    assert client.get(root).status_code == 404
    assert not storage.project_dir(pid).exists()


def test_clarification_and_busy(client):
    pid = client.post("/api/projects").json()["id"]
    result = client.post(f"/api/projects/{pid}/apply", json={"transcript": "make reel"})
    assert result.json()["requires_clarification"]
    assert not main.jobs
    assert pid not in main.busy
    main.busy.add(pid)
    assert client.delete(f"/api/projects/{pid}").status_code == 409


def test_bad_project_and_cross_origin(client):
    assert client.get("/api/projects/not-a-uuid").status_code == 404
    assert client.post("/api/projects", headers={"origin": "https://unrelated.example"}).status_code == 403


def test_undo_restores_exact_revision(client):
    p = storage.create()
    from backend.app.models import Snapshot
    p.undo_stack.append(Snapshot(settings=p.settings.model_copy(), edit_history=[], revision=1, output="renders/revision-1.mp4"))
    p.settings.overlay_text = "25 percent offer"
    p.settings.music_volume = .12
    p.current_render_revision = 2
    p.next_revision = 3
    storage.save(p)
    response = client.post(f"/api/projects/{p.id}/undo")
    assert response.status_code == 200
    state = response.json()
    assert state["settings"]["music_volume"] == .2
    assert state["settings"]["overlay_text"] is None
    assert state["current_render_revision"] == 1
    assert state["next_revision"] == 3
    assert client.post(f"/api/projects/{p.id}/undo").status_code == 409


def test_voice_rejects_empty_and_bad_formats(client):
    pid = client.post("/api/projects").json()["id"]
    url = f"/api/projects/{pid}/voice-command"
    assert client.post(url, files={"file": ("a.exe", b"audio", "audio/webm")}).status_code == 415
    assert client.post(url, files={"file": ("a.webm", b"", "audio/webm")}).status_code == 422
    assert not list((storage.project_dir(pid)/"audio").iterdir())


def test_missing_speech_model(monkeypatch, tmp_path):
    monkeypatch.setenv("SOLLICUT_MODEL_DIR", str(tmp_path))
    engine = FasterWhisperSpeechEngine()
    engine.initialize()
    assert engine.status == "unavailable"
    with pytest.raises(RuntimeError, match="unavailable"):
        asyncio.run(engine.transcribe(Path("missing.wav")))


def test_speech_empty_segments():
    from types import SimpleNamespace
    engine = FasterWhisperSpeechEngine()
    engine.model = SimpleNamespace(transcribe=lambda *a, **k: ([], SimpleNamespace(language="en")))
    with pytest.raises(ValueError, match="No speech"):
        asyncio.run(engine.transcribe(Path("fixture.wav")))


def test_video_upload_visual_edit_and_undo(client, tmp_path):
    from backend.app import media
    clip_path = tmp_path / "clip.mp4"
    media.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=c=#223c30:s=360x640:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip_path),
    ])
    pid = client.post("/api/projects").json()["id"]
    root = f"/api/projects/{pid}"
    # Reject invalid video payloads cleanly.
    assert client.post(root + "/assets", files={"file": ("broken.mp4", b"not-a-video", "video/mp4")}).status_code == 422

    # Upload 1 photo + 1 real MP4 video clip.
    assert client.post(root + "/assets", files={"file": ("item.png", photo(), "image/png")}).status_code == 200
    uploaded = client.post(root + "/assets", files={"file": ("clip.mp4", clip_path.read_bytes(), "video/mp4")})
    assert uploaded.status_code == 200
    assets = uploaded.json()["assets"]
    assert [a["media_type"] for a in assets] == ["image", "video"]
    photo_id, video_id = assets[0]["id"], assets[1]["id"]

    # Reorder & trim without rendering, then undo and verify assets revert.
    edit = client.post(root + "/edit", json={
        "reorder_asset_ids": [video_id, photo_id],
        "trim_asset_id": video_id,
        "trim_start": 0.25,
        "trim_end": 1.5,
        "overlay_text": "Boutique drop",
        "overlay_color": "amber",
        "render": False,
    })
    assert edit.status_code == 200
    edited = edit.json()["project"]
    assert [a["id"] for a in edited["assets"]] == [video_id, photo_id]
    assert edited["assets"][0]["trim_start"] == 0.25
    assert edited["assets"][0]["trim_end"] == 1.5
    assert edited["settings"]["overlay_text"] == "Boutique drop"
    assert edited["settings"]["overlay_color"] == "amber"

    restored = client.post(root + "/undo")
    assert restored.status_code == 200
    rev = restored.json()
    assert [a["id"] for a in rev["assets"]] == [photo_id, video_id]
    assert rev["assets"][1]["trim_start"] == 0.0
    assert rev["assets"][1]["trim_end"] is None
    assert rev["settings"]["overlay_text"] is None
