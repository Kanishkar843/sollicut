"""
tests/backend/test_workflows_e2e.py — Phase 11 End-to-End Regression Workflows (A–H).

Exercises all 8 core user workflows against FastAPI TestClient, real FFmpeg/libraqm
rendering, WebSocket voice preview + explicit apply, undo snapshots, clarification
guards, optional Gemini gating, and zero-disk audio privacy.
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import main, media, storage
from backend.app.models import DualTranscriptResult


def _png_bytes(color: str = "teal", size: tuple[int, int] = (128, 128)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _mp4_file(path: Path, duration: float = 2.5) -> bytes:
    media.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=#243b2c:s=360x640:d={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(path),
    ])
    return path.read_bytes()


def _pcm_chunk(seconds: float = 0.5) -> bytes:
    t = np.linspace(0.0, seconds, int(16000 * seconds), endpoint=False)
    return (2200 * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.int16).tobytes()


def _wait_job(client: TestClient, job_id: str, timeout_s: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"done", "failed"}:
            return job
        time.sleep(0.1)
    raise TimeoutError(f"Job {job_id} did not complete in {timeout_s}s")


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.speech, "initialize", lambda: None)
    main.busy.clear()
    main.jobs.clear()
    return TestClient(main.app)


def test_workflow_a_and_b_create_followup_undo_and_export(tmp_path, monkeypatch):
    """Workflow A+B: Upload photos, create reel, follow-up offer/music change, undo restores exact bytes, download."""
    with _client(tmp_path, monkeypatch) as client:
        pid = client.post("/api/projects").json()["id"]
        for i, col in enumerate(("crimson", "gold", "teal")):
            r = client.post(f"/api/projects/{pid}/assets", files={"file": (f"p{i}.png", _png_bytes(col), "image/png")})
            assert r.status_code == 200

        # Workflow A: Create canonical Tanglish 4s-like or 5s reel for speed
        res1 = client.post(
            f"/api/projects/{pid}/apply",
            json={"transcript": "Create a 4 seconds reel. Smooth zoom podu. Music add pannu. Last la 20 percent offer podu."},
        )
        assert res1.status_code == 200
        job1 = _wait_job(client, res1.json()["job_id"])
        assert job1["status"] == "done", job1

        dl1 = client.get(f"/api/projects/{pid}/download")
        assert dl1.status_code == 200
        rev1_bytes = dl1.content
        assert len(rev1_bytes) > 1000

        # Workflow B: Follow-up edit
        res2 = client.post(
            f"/api/projects/{pid}/apply",
            json={"transcript": "Offer ah 25 percent nu maathu. Background music konjam kammi pannu."},
        )
        assert res2.status_code == 200
        job2 = _wait_job(client, res2.json()["job_id"])
        assert job2["status"] == "done", job2
        dl2 = client.get(f"/api/projects/{pid}/download")
        assert dl2.content != rev1_bytes

        # Undo restores rev 1 settings and exact MP4 bytes
        undo = client.post(f"/api/projects/{pid}/undo")
        assert undo.status_code == 200
        assert undo.json()["settings"]["overlay_text"] == "20 percent offer"
        assert client.get(f"/api/projects/{pid}/download").content == rev1_bytes

        # Explicit export intent returns download URL without new job
        exp = client.post(f"/api/projects/{pid}/apply", json={"transcript": "Download reel"})
        assert exp.status_code == 200
        assert exp.json()["download_url"] == f"/api/projects/{pid}/download"


def test_workflow_c_tamil_unicode_overlay_libraqm(tmp_path, monkeypatch):
    """Workflow C: Tamil script overlay rendered cleanly via Pillow/libraqm."""
    with _client(tmp_path, monkeypatch) as client:
        pid = client.post("/api/projects").json()["id"]
        client.post(f"/api/projects/{pid}/assets", files={"file": ("shop.png", _png_bytes("navy"), "image/png")})
        res = client.post(
            f"/api/projects/{pid}/apply",
            json={"transcript": "4 seconds. இன்று 20% ஆஃபர் கடைசில போடு."},
        )
        assert res.status_code == 200
        job = _wait_job(client, res.json()["job_id"])
        assert job["status"] == "done", job
        proj = client.get(f"/api/projects/{pid}").json()
        assert proj["settings"]["overlay_text"] == "இன்று 20% ஆஃபர்"


def test_workflow_d_mixed_media_trim_and_fit(tmp_path, monkeypatch):
    """Workflow D: Photo + video upload, trim clip & cover fit via /apply."""
    clip_bytes = _mp4_file(tmp_path / "src.mp4", duration=2.5)
    with _client(tmp_path, monkeypatch) as client:
        pid = client.post("/api/projects").json()["id"]
        client.post(f"/api/projects/{pid}/assets", files={"file": ("a.png", _png_bytes("olive"), "image/png")})
        client.post(f"/api/projects/{pid}/assets", files={"file": ("clip.mp4", clip_bytes, "video/mp4")})

        res = client.post(
            f"/api/projects/{pid}/apply",
            json={"transcript": "Trim clip 2 from 0.5 to 2.0 seconds and make 4 seconds reel. Fill screen."},
        )
        assert res.status_code == 200
        job = _wait_job(client, res.json()["job_id"])
        assert job["status"] == "done", job
        proj = client.get(f"/api/projects/{pid}").json()
        assert proj["settings"]["fit_mode"] == "cover"
        assert proj["assets"][1]["trim_start"] == 0.5
        assert proj["assets"][1]["trim_end"] == 2.0


def test_workflow_e_ws_preview_requires_explicit_apply(tmp_path, monkeypatch):
    """Workflow E: WS voice streaming preview returns plan without mutating until POST /apply."""
    with _client(tmp_path, monkeypatch) as client:
        pid = client.post("/api/projects").json()["id"]
        client.post(f"/api/projects/{pid}/assets", files={"file": ("a.png", _png_bytes(), "image/png")})

        async def fake_transcribe(samples, mode="tanglish"):
            return DualTranscriptResult(
                primary_text="Make a 5 seconds reel with smooth zoom",
                tamil_transcript="5 செகண்ட்ஸ் ரீல்",
                english_transcript="Make a 5 seconds reel with smooth zoom",
                mode=mode,
                engines_used=["faster-whisper"],
                elapsed_seconds=0.05,
            )

        monkeypatch.setattr(main.speech, "transcribe_pcm", fake_transcribe)

        with client.websocket_connect(f"/ws/voice/{pid}?mode=tanglish&auto_apply=false") as ws:
            ws.send_bytes(_pcm_chunk(0.5))
            ws.send_text(json.dumps({"event": "stop", "preview": True, "command_id": "wf-e-1"}))
            preview = ws.receive_json()

        assert preview["preview"] is True
        assert "job_id" not in preview
        assert client.get(f"/api/projects/{pid}").json()["current_output"] is None

        applied = client.post(
            f"/api/projects/{pid}/apply",
            json={
                "transcript": preview["transcript"],
                "secondary_transcript": preview["secondary_transcript"],
                "asr_mode": "tanglish",
            },
        )
        assert applied.status_code == 200
        job = _wait_job(client, applied.json()["job_id"])
        assert job["status"] == "done"
        assert not list((storage.project_dir(pid) / "audio").iterdir())


def test_workflow_f_reorder_assets_and_undo(tmp_path, monkeypatch):
    """Workflow F: Reorder timeline assets without destructive loss and undo."""
    with _client(tmp_path, monkeypatch) as client:
        pid = client.post("/api/projects").json()["id"]
        client.post(f"/api/projects/{pid}/assets", files={"file": ("first.png", _png_bytes("red"), "image/png")})
        r2 = client.post(f"/api/projects/{pid}/assets", files={"file": ("second.png", _png_bytes("blue"), "image/png")})
        ids_orig = [a["id"] for a in r2.json()["assets"]]

        res = client.post(f"/api/projects/{pid}/apply", json={"transcript": "Swap clip 1 and 2. 4 seconds reel."})
        assert res.status_code == 200
        assert _wait_job(client, res.json()["job_id"])["status"] == "done"
        ids_swapped = [a["id"] for a in client.get(f"/api/projects/{pid}").json()["assets"]]
        assert ids_swapped == [ids_orig[1], ids_orig[0]]

        restored = client.post(f"/api/projects/{pid}/undo").json()
        assert [a["id"] for a in restored["assets"]] == ids_orig


def test_workflow_g_clarification_and_error_safety(tmp_path, monkeypatch):
    """Workflow G: Ambiguous or unsupported voice input requests clarification without enqueueing."""
    with _client(tmp_path, monkeypatch) as client:
        pid = client.post("/api/projects").json()["id"]
        client.post(f"/api/projects/{pid}/assets", files={"file": ("a.png", _png_bytes(), "image/png")})

        for bad in ("Add slow motion", "Create a 120 seconds reel", "Antha frame zoom pannu"):
            res = client.post(f"/api/projects/{pid}/apply", json={"transcript": bad})
            assert res.status_code == 200
            assert res.json()["requires_clarification"] is True
            assert len(main.jobs) == 0


def test_workflow_h_gemini_gating_and_project_cleanup(tmp_path, monkeypatch):
    """Workflow H: Optional Gemini stays gated with empty env; deleting project purges dir cleanly."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with _client(tmp_path, monkeypatch) as client:
        caps = client.get("/api/capabilities").json()
        assert caps["generation"]["configured"] is False
        assert caps["generation"]["label"] == "Key not set"
        assert "voice_profile" in caps

        pid = client.post("/api/projects").json()["id"]
        gen_res = client.post(f"/api/projects/{pid}/generate", json={"transcript": "Make ad"})
        assert gen_res.status_code in {400, 409, 422, 503}

        del_res = client.delete(f"/api/projects/{pid}")
        assert del_res.status_code == 200
        assert not storage.project_dir(pid).exists()
