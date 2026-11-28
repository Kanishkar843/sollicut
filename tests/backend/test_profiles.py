"""
tests/backend/test_profiles.py — Phase 9: Deployment profiles & backend wiring tests.
"""
from fastapi.testclient import TestClient

from backend.app import config, main
from backend.app.speech import DualSpeechRouter
from backend.app.understanding.context_manager import clear_context, get_context


def test_profile_defaults_to_balanced(monkeypatch):
    monkeypatch.delenv("SOLLICUT_PROFILE", raising=False)
    monkeypatch.delenv("SOLLICUT_ASR_MODEL", raising=False)
    monkeypatch.delenv("SOLLICUT_VAD_ENABLED", raising=False)
    monkeypatch.delenv("SOLLICUT_RESAMPLER", raising=False)
    monkeypatch.delenv("SOLLICUT_ASR_THREADS", raising=False)

    assert config.get_profile_name() == "balanced"
    spec = config.get_profile_spec()
    assert spec.asr_model == "small"
    assert spec.use_silero_vad is True
    assert spec.resampler == "fir_kaiser"
    assert config.get_asr_threads() == 4


def test_lightweight_profile_selects_linear_and_rms(monkeypatch):
    monkeypatch.setenv("SOLLICUT_PROFILE", "lightweight")
    monkeypatch.delenv("SOLLICUT_VAD_ENABLED", raising=False)
    monkeypatch.delenv("SOLLICUT_RESAMPLER", raising=False)
    monkeypatch.delenv("SOLLICUT_ASR_THREADS", raising=False)
    monkeypatch.delenv("SOLLICUT_ASR_MODEL", raising=False)

    assert config.get_profile_name() == "lightweight"
    assert config.get_asr_model() == "small"
    assert config.is_silero_vad_enabled() is False
    assert config.get_resampler_mode() == "linear"
    assert config.get_asr_threads() == 2


def test_accuracy_profile_selects_turbo_and_silero(monkeypatch):
    monkeypatch.setenv("SOLLICUT_PROFILE", "accuracy")
    monkeypatch.delenv("SOLLICUT_ASR_MODEL", raising=False)
    monkeypatch.delenv("SOLLICUT_VAD_ENABLED", raising=False)
    monkeypatch.delenv("SOLLICUT_RESAMPLER", raising=False)

    assert config.get_profile_name() == "accuracy"
    assert config.get_asr_model() == "large-v3-turbo"
    assert config.is_silero_vad_enabled() is True
    assert config.get_resampler_mode() == "fir_kaiser"


def test_invalid_profile_falls_back_safely_to_balanced(monkeypatch):
    monkeypatch.setenv("SOLLICUT_PROFILE", "nonexistent-mode")
    assert config.get_profile_name() == "balanced"


def test_env_overrides_win_over_profile(monkeypatch):
    monkeypatch.setenv("SOLLICUT_PROFILE", "lightweight")
    monkeypatch.setenv("SOLLICUT_RESAMPLER", "fir_kaiser")
    monkeypatch.setenv("SOLLICUT_VAD_ENABLED", "true")
    monkeypatch.setenv("SOLLICUT_ASR_THREADS", "6")

    assert config.get_resampler_mode() == "fir_kaiser"
    assert config.is_silero_vad_enabled() is True
    assert config.get_asr_threads() == 6


def test_capabilities_exposes_voice_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SOLLICUT_PROFILE", "lightweight")
    monkeypatch.delenv("SOLLICUT_RESAMPLER", raising=False)
    monkeypatch.delenv("SOLLICUT_VAD_ENABLED", raising=False)
    monkeypatch.setattr(main.speech, "initialize", lambda: None)

    with TestClient(main.app) as client:
        data = client.get("/api/capabilities").json()
        assert data["voice_profile"]["profile"] == "lightweight"
        assert data["voice_profile"]["resampler"] == "linear"
        assert data["voice_profile"]["vad"] == "rms"


def test_dispatch_records_and_delete_clears_context(tmp_path, monkeypatch):
    import io
    from PIL import Image

    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.speech, "initialize", lambda: None)
    main.busy.clear()
    main.jobs.clear()

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "coral").save(buf, "PNG")

    with TestClient(main.app) as client:
        pid = client.post("/api/projects").json()["id"]
        client.post(f"/api/projects/{pid}/assets", files={"file": ("p.png", buf.getvalue(), "image/png")})
        clear_context(pid)
        res = client.post(f"/api/projects/{pid}/apply", json={"transcript": "Create a 15 seconds reel"})
        assert res.status_code == 200
        job_id = res.json().get("job_id")
        if job_id:
            import time
            for _ in range(120):
                st = client.get(f"/api/jobs/{job_id}").json()["status"]
                if st in {"done", "failed"}:
                    break
                time.sleep(0.1)

        ctx = get_context(pid)
        assert len(ctx.last_operations()) == 1
        assert ctx.last_operations()[0]["type"] == "create_reel"

        # Deleting project should clear context cleanly
        del_res = client.delete(f"/api/projects/{pid}")
        assert del_res.status_code == 200
        fresh_ctx = get_context(pid)
        assert fresh_ctx.last_operations() == []
        clear_context(pid)


def test_router_accuracy_keeps_v1_if_turbo_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_PROFILE", "accuracy")
    monkeypatch.setenv("SOLLICUT_MODEL_DIR", str(tmp_path))
    router = DualSpeechRouter()
    router.initialize()
    # Missing all weights → cleanly unavailable without crashing
    assert router.whisper.status == "unavailable"


def test_router_accuracy_falls_back_to_small_when_only_small_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_PROFILE", "accuracy")
    monkeypatch.setenv("SOLLICUT_MODEL_DIR", str(tmp_path))
    small_dir = tmp_path / "small"
    small_dir.mkdir(parents=True)
    # Touch small/model.bin (empty triggers WhisperModel error, showing fallback path attempted)
    (small_dir / "model.bin").write_bytes(b"")

    attempted_paths: list[str] = []

    class FakeWhisperModel:
        def __init__(self, path, **kwargs):
            attempted_paths.append(str(path))

    import sys
    from types import ModuleType
    fake_fw = ModuleType("faster_whisper")
    fake_fw.WhisperModel = FakeWhisperModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_fw)

    router = DualSpeechRouter()
    router.whisper.initialize()
    assert router.whisper.status == "ready"
    assert router.whisper.loaded_model_name == "small"
    assert attempted_paths == [str(small_dir)]
