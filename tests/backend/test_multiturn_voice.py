import hashlib
import io
import math
import shutil
import struct
import time
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import main, storage
from backend.app.models import TranscriptResult
from scripts.generate_demo_assets import generate


def _tiny_wav_bytes(duration_sec: float = 0.5, freq: float = 440.0) -> bytes:
    rate = 16000
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(rate * duration_sec)):
            val = int(math.sin(2 * math.pi * freq * (i / rate)) * 8000)
            frames.extend(struct.pack("<h", val))
        w.writeframes(frames)
    return buf.getvalue()


def _photo_bytes(color: str = "coral") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (240, 320), color).save(buf, "PNG")
    return buf.getvalue()


def _wait_job(client: TestClient, job_id: str) -> dict:
    for _ in range(450):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] == "done":
            return job
        if job["status"] == "failed":
            raise AssertionError(f"Job failed: {job}")
        time.sleep(0.1)
    raise TimeoutError(f"Job {job_id} did not finish in time")


@pytest.fixture
def voice_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.speech, "initialize", lambda: None)
    main.busy.clear()
    main.jobs.clear()
    generate()
    with TestClient(main.app) as client:
        yield client


def test_multiturn_persistent_text_id_and_immediate_followup(voice_client, monkeypatch):
    wav = _tiny_wav_bytes()
    transcripts = iter([
        TranscriptResult(text="Create text 'Sale 20%' on clip 1", language="en", elapsed_seconds=0.1),
        TranscriptResult(text="Change text to 25%", language="en", elapsed_seconds=0.1),
    ])

    async def fake_transcribe(path, language_hint=None):
        return next(transcripts)

    monkeypatch.setattr(main.speech, "transcribe", fake_transcribe)

    pid = voice_client.post("/api/projects").json()["id"]
    root = f"/api/projects/{pid}"
    assert voice_client.post(f"{root}/assets", files={"file": ("item1.png", _photo_bytes("#d7ef41"), "image/png")}).status_code == 200
    assert voice_client.post(f"{root}/assets", files={"file": ("item2.png", _photo_bytes("#3fd0e3"), "image/png")}).status_code == 200
    assert voice_client.post(f"{root}/edit", json={"duration_seconds": 4, "render": False}).status_code == 200

    # Turn 1 via /voice-command
    r1 = voice_client.post(f"{root}/voice-command", files={"file": ("cmd1.wav", wav, "audio/wav")})
    assert r1.status_code == 200, r1.text
    _wait_job(voice_client, r1.json()["job_id"])
    p1 = voice_client.get(root).json()
    layers1 = [t for t in p1["settings"]["text_layers"] if not t["is_caption"]]
    assert len(layers1) == 1
    layer_id = layers1[0]["id"]
    assert layers1[0]["text"] == "Sale 20%"
    assert layers1[0]["clip_index"] == 1
    hash1 = hashlib.sha256(voice_client.get(f"{root}/download").content).hexdigest()

    # Turn 2 immediately after job done -> must NOT 409, must keep persistent ID and update in place
    r2 = voice_client.post(f"{root}/voice-command", files={"file": ("cmd2.wav", wav, "audio/wav")})
    assert r2.status_code == 200, r2.text
    _wait_job(voice_client, r2.json()["job_id"])
    p2 = voice_client.get(root).json()
    layers2 = [t for t in p2["settings"]["text_layers"] if not t["is_caption"]]
    assert len(layers2) == 1
    assert layers2[0]["id"] == layer_id
    assert layers2[0]["text"] == "Sale 25%"
    assert layers2[0]["clip_index"] == 1
    assert p2["settings"]["overlay_text"] == "Sale 25%"
    hash2 = hashlib.sha256(voice_client.get(f"{root}/download").content).hexdigest()
    assert hash2 != hash1


def test_multiturn_canonical_tanglish_render_undo_redo(voice_client, monkeypatch):
    wav = _tiny_wav_bytes()
    transcripts = iter([
        TranscriptResult(
            text="Indha photos ellathayum use panni oru 5 seconds Instagram reel create pannu. Smooth zoom effects podu. Background music add pannu. Last la 20 percent offer nu text podu.",
            language="ta",
            elapsed_seconds=0.12,
        ),
        TranscriptResult(
            text="Offer ah 25 percent nu maathu. Background music konjam kammi pannu.",
            language="ta",
            elapsed_seconds=0.11,
        ),
    ])

    async def fake_transcribe(path, language_hint=None):
        return next(transcripts)

    monkeypatch.setattr(main.speech, "transcribe", fake_transcribe)

    pid = voice_client.post("/api/projects").json()["id"]
    root = f"/api/projects/{pid}"
    for i in range(1, 3):
        demo = (storage.ROOT / f"assets/demo/bakery-{i}.png").read_bytes()
        assert voice_client.post(f"{root}/assets", files={"file": (f"bakery-{i}.png", demo, "image/png")}).status_code == 200

    res1 = voice_client.post(f"{root}/voice-command", files={"file": ("turn1.wav", wav, "audio/wav")})
    assert res1.status_code == 200
    _wait_job(voice_client, res1.json()["job_id"])
    state1 = voice_client.get(root).json()
    assert state1["settings"]["overlay_text"] == "20 percent offer"
    assert state1["settings"]["music_volume"] == 0.2
    layer_id = state1["settings"]["active_text_id"]
    mp4_1 = voice_client.get(f"{root}/download").content
    sha1 = hashlib.sha256(mp4_1).hexdigest()

    res2 = voice_client.post(f"{root}/voice-command", files={"file": ("turn2.wav", wav, "audio/wav")})
    assert res2.status_code == 200
    _wait_job(voice_client, res2.json()["job_id"])
    state2 = voice_client.get(root).json()
    assert state2["settings"]["overlay_text"] == "25 percent offer"
    assert state2["settings"]["active_text_id"] == layer_id
    assert state2["settings"]["music_volume"] == 0.12
    mp4_2 = voice_client.get(f"{root}/download").content
    sha2 = hashlib.sha256(mp4_2).hexdigest()
    assert sha2 != sha1

    # Undo and Redo restore exact states and MP4 bytes
    undone = voice_client.post(f"{root}/undo").json()
    assert undone["settings"]["overlay_text"] == "20 percent offer"
    assert undone["settings"]["music_volume"] == 0.2
    assert voice_client.get(f"{root}/download").content == mp4_1

    redone = voice_client.post(f"{root}/redo").json()
    assert redone["settings"]["overlay_text"] == "25 percent offer"
    assert redone["settings"]["music_volume"] == 0.12
    assert voice_client.get(f"{root}/download").content == mp4_2


def test_multiturn_mixed_language_manual_apply_and_cumulative_brightness(voice_client):
    pid = voice_client.post("/api/projects").json()["id"]
    root = f"/api/projects/{pid}"
    assert voice_client.post(f"{root}/assets", files={"file": ("p1.png", _photo_bytes("#1f3a2e"), "image/png")}).status_code == 200
    assert voice_client.post(f"{root}/assets", files={"file": ("p2.png", _photo_bytes("#3b2e4a"), "image/png")}).status_code == 200
    assert voice_client.post(f"{root}/edit", json={"duration_seconds": 4, "render": False}).status_code == 200

    # 1. Tamil overlay
    r1 = voice_client.post(f"{root}/apply", json={"transcript": "இருபது சதவீதம் ஆஃபர்"})
    assert r1.status_code == 200
    _wait_job(voice_client, r1.json()["job_id"])
    p1 = voice_client.get(root).json()
    assert p1["settings"]["overlay_text"] == "20% ஆஃபர்"
    lid = p1["settings"]["active_text_id"]

    # 2. English replacement on Tamil text
    r2 = voice_client.post(f"{root}/apply", json={"transcript": "Change 20% to 30%"})
    assert r2.status_code == 200
    _wait_job(voice_client, r2.json()["job_id"])
    p2 = voice_client.get(root).json()
    assert p2["settings"]["overlay_text"] == "30% ஆஃபர்"
    assert p2["settings"]["active_text_id"] == lid

    # 3. Tanglish filter + transition + sticker + cumulative brightness
    r3 = voice_client.post(f"{root}/apply", json={"transcript": "cinematic filter podu. fade transition add pannu. add sale sticker. brighter"})
    assert r3.status_code == 200
    _wait_job(voice_client, r3.json()["job_id"])
    p3 = voice_client.get(root).json()
    assert p3["settings"]["filter_preset"] == "cinematic"
    assert p3["settings"]["transition_style"] == "fade"
    assert p3["settings"]["sticker_badge"] == "sale"
    assert p3["settings"]["brightness"] == 0.1

    # 4. Second "brighter" accumulates to +0.2 instead of sticking at +0.1
    r4 = voice_client.post(f"{root}/apply", json={"transcript": "brighter"})
    assert r4.status_code == 200
    _wait_job(voice_client, r4.json()["job_id"])
    p4 = voice_client.get(root).json()
    assert p4["settings"]["brightness"] == 0.2


def test_uploading_asset_preserves_undo_and_preview(voice_client):
    pid = voice_client.post("/api/projects").json()["id"]
    root = f"/api/projects/{pid}"
    assert voice_client.post(f"{root}/assets", files={"file": ("a.png", _photo_bytes("#556b2f"), "image/png")}).status_code == 200

    r = voice_client.post(f"{root}/apply", json={"transcript": "Create a 4 seconds reel"})
    _wait_job(voice_client, r.json()["job_id"])
    before_upload = voice_client.get(root).json()
    assert before_upload["current_output"]
    assert len(before_upload["undo_stack"]) == 1

    # Uploading a second photo must NOT wipe undo_stack or current_output
    up2 = voice_client.post(f"{root}/assets", files={"file": ("b.png", _photo_bytes("#8b4513"), "image/png")})
    assert up2.status_code == 200
    after_upload = up2.json()
    assert after_upload["current_output"] == before_upload["current_output"]
    assert len(after_upload["undo_stack"]) == 2
