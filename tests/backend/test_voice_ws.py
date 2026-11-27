import io
import json
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import main, storage
from backend.app.models import DualTranscriptResult


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.speech, "initialize", lambda: None)
    main.busy.clear()
    main.jobs.clear()
    with TestClient(main.app) as c:
        yield c


def _photo_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (128, 128), "teal").save(buf, "PNG")
    return buf.getvalue()


def _pcm_chunk(seconds: float = 0.5, amplitude: int = 2000) -> bytes:
    n = int(16000 * seconds)
    t = np.linspace(0.0, seconds, n, endpoint=False)
    samples = (amplitude * np.sin(2 * np.pi * 440.0 * t)).astype(np.int16)
    return samples.tobytes()


def _wav_bytes(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm)
    return buf.getvalue()


def test_ws_voice_stream_stop_and_zero_disk_audio(client, monkeypatch):
    pid = client.post("/api/projects").json()["id"]
    assert client.post(f"/api/projects/{pid}/assets", files={"file": ("p.png", _photo_bytes(), "image/png")}).status_code == 200

    async def fake_transcribe_pcm(samples, mode="tanglish"):
        assert samples.dtype == np.float32
        assert len(samples) == 16000
        return DualTranscriptResult(
            primary_text="Offer ah 25 percent nu maathu.",
            tamil_transcript="மியூசிக் கம்மி பண்ணு",
            english_transcript="Offer ah 25 percent nu maathu.",
            mode=mode,
            engines_used=["indicconformer-ta", "faster-whisper"],
            elapsed_seconds=0.14,
        )

    monkeypatch.setattr(main.speech, "transcribe_pcm", fake_transcribe_pcm)
    chunk = _pcm_chunk(0.5)

    with client.websocket_connect(f"/ws/voice/{pid}?mode=tanglish") as ws:
        ws.send_bytes(chunk)
        ws.send_bytes(chunk)
        ws.send_text(json.dumps({"event": "stop"}))
        res = ws.receive_json()

    assert res["transcript"] == "Offer ah 25 percent nu maathu."
    assert res["secondary_transcript"] == "மியூசிக் கம்மி பண்ணு"
    assert res["asr_elapsed_ms"] == 140
    assert res["requires_clarification"] is False
    op_types = {op["type"] for op in res["parsed_command"]["operations"]}
    assert op_types == {"set_text_overlay", "set_music_volume"}
    assert "job_id" in res
    assert not list((storage.project_dir(pid) / "audio").iterdir())


def test_ws_voice_cancel_discards_without_asr(client, monkeypatch):
    pid = client.post("/api/projects").json()["id"]
    called = False

    async def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("ASR should not run on cancel")

    monkeypatch.setattr(main.speech, "transcribe_pcm", fail_if_called)
    with client.websocket_connect(f"/ws/voice/{pid}?mode=en") as ws:
        ws.send_bytes(_pcm_chunk(0.3))
        ws.send_text(json.dumps({"event": "cancel"}))
    assert not called


def test_ws_voice_invalid_project_and_over_30s_limit(client):
    with client.websocket_connect("/ws/voice/not-a-uuid?mode=tanglish") as ws:
        err = ws.receive_json()
        assert "Project not found" in err["error"]

    pid = client.post("/api/projects").json()["id"]
    oversized = b"\x01\x00" * (30 * 16000 + 100)
    with client.websocket_connect(f"/ws/voice/{pid}?mode=en") as ws:
        ws.send_bytes(oversized)
        err = ws.receive_json()
        assert "30-second limit" in err["error"]


def test_http_wav_fast_path_and_cleanup(client, monkeypatch):
    pid = client.post("/api/projects").json()["id"]
    assert client.post(f"/api/projects/{pid}/assets", files={"file": ("p.png", _photo_bytes(), "image/png")}).status_code == 200

    async def fake_transcribe_pcm(samples, mode="tanglish"):
        assert mode == "tanglish"
        return DualTranscriptResult(
            primary_text="Create a 10 seconds reel",
            english_transcript="Create a 10 seconds reel",
            mode=mode,
            engines_used=["faster-whisper"],
            elapsed_seconds=0.09,
        )

    monkeypatch.setattr(main.speech, "transcribe_pcm", fake_transcribe_pcm)
    wav = _wav_bytes(_pcm_chunk(0.6))
    resp = client.post(
        f"/api/projects/{pid}/voice-command",
        files={"file": ("cmd.wav", wav, "audio/wav")},
        data={"mode": "tanglish"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == "Create a 10 seconds reel"
    assert body["asr_mode"] == "tanglish"
    assert "job_id" in body
    assert not list((storage.project_dir(pid) / "audio").iterdir())
