import asyncio
import base64
import json
import time
import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import generation, main, media, storage


def _tiny_mp4(path):
    media.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=c=#1c2219:s=360x640:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(path),
    ])
    return path.read_bytes()


def test_key_not_set(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    info = generation.status()
    assert not info["configured"]
    assert info["label"] == "Key not set"
    with pytest.raises(ValueError, match="Key not set"):
        asyncio.run(generation.generate("A flower shop ad", tmp_path / "out.mp4"))


def test_rest_video_extraction_and_schema(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert generation.status()["configured"]
    original = httpx.AsyncClient

    def respond(request):
        assert request.headers["x-goog-api-key"] == "test-key"
        body = json.loads(request.content.decode())
        assert body["model"] == "gemini-omni-1.2-flash"
        assert body["response_format"] == {"type": "video", "aspect_ratio": "9:16", "duration": "12s"}
        return httpx.Response(200, json={"steps": [{"type": "model_output", "content": [{"type": "video", "mime_type": "video/mp4", "data": base64.b64encode(b"test-video-bytes").decode()}]}]})

    monkeypatch.setattr(generation.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    output = tmp_path / "out.mp4"
    asyncio.run(generation.generate("An ad", output, duration_seconds=12, aspect_ratio="9:16"))
    assert output.read_bytes() == b"test-video-bytes"
    assert not output.with_suffix(".tmp.mp4").exists()


def test_generation_job_commits_asset_and_preserves_undo(monkeypatch, tmp_path):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(main.speech, "initialize", lambda: None)
    main.busy.clear()
    main.jobs.clear()

    valid_mp4 = _tiny_mp4(tmp_path / "sample.mp4")

    async def fake_generate(prompt, output, **kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(valid_mp4)

    monkeypatch.setattr(generation, "generate", fake_generate)

    with TestClient(main.app) as client:
        pid = client.post("/api/projects").json()["id"]
        res = client.post(f"/api/projects/{pid}/generate", json={"transcript": "Boutique silk saree promo", "duration_seconds": 8, "aspect_ratio": "9:16"})
        assert res.status_code == 200
        job_id = res.json()["job_id"]
        for _ in range(30):
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] == "done":
                break
            time.sleep(0.05)
        assert job["status"] == "done"
        project = client.get(f"/api/projects/{pid}").json()
        assert project["current_output"]
        assert len(project["assets"]) == 1
        assert project["assets"][0]["media_type"] == "video"

        # Generated clip participates in subsequent edits and undo reverts both output and asset.
        undo = client.post(f"/api/projects/{pid}/undo").json()
        assert undo["current_output"] is None
        assert undo["assets"] == []


def test_generation_failure_preserves_prior_output(monkeypatch, tmp_path):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(main.speech, "initialize", lambda: None)
    main.busy.clear()
    main.jobs.clear()

    async def broken_generate(*args, **kwargs):
        raise RuntimeError("Provider rejected the request")

    monkeypatch.setattr(generation, "generate", broken_generate)

    with TestClient(main.app) as client:
        p = storage.create()
        p.current_output = "renders/revision-1.mp4"
        p.current_render_revision = 1
        storage.save(p)
        res = client.post(f"/api/projects/{p.id}/generate", json={"transcript": "Promo ad"})
        job_id = res.json()["job_id"]
        for _ in range(30):
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in {"done", "failed"}:
                break
            time.sleep(0.05)
        assert job["status"] == "failed"
        assert "Provider rejected" in job["error"]
        after = client.get(f"/api/projects/{p.id}").json()
        assert after["current_output"] == "renders/revision-1.mp4"
        assert p.id not in main.busy
