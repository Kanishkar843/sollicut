import asyncio
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.models import DualTranscriptResult
from backend.app.speech import (
    SAMPLE_RATE,
    TANGLISH_INITIAL_PROMPT,
    DualSpeechRouter,
    FasterWhisperSpeechEngine,
    IndicConformerTamilEngine,
    strip_primer_leak,
    validate_audio_buffer,
)


def _tone(seconds: float = 0.6, amplitude: float = 0.05) -> np.ndarray:
    t = np.linspace(0.0, seconds, int(SAMPLE_RATE * seconds), endpoint=False, dtype=np.float32)
    return (amplitude * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)


def test_indicconformer_initializes_and_decodes_synthetic_buffer(monkeypatch):
    indic_dir = Path("models/indicconformer-ta")
    if not (indic_dir / "model.int8.onnx").is_file():
        pytest.skip("IndicConformer ONNX model not downloaded locally")
    monkeypatch.setenv("SOLLICUT_INDIC_ASR_ENABLED", "true")
    monkeypatch.setenv("SOLLICUT_INDIC_MODEL_DIR", str(indic_dir))

    engine = IndicConformerTamilEngine()
    engine.initialize()
    assert engine.status == "ready"
    assert engine.recognizer is not None

    # Synthetic tone passes RMS gate and decodes without crashing (may emit text or ValueError if blank CTC).
    try:
        result = asyncio.run(engine.transcribe(_tone(0.8, 0.1)))
        assert result.language == "ta"
        assert isinstance(result.text, str)
    except ValueError as exc:
        assert "No speech" in str(exc)


def test_silence_and_short_clip_gate():
    with pytest.raises(ValueError, match="too short"):
        validate_audio_buffer(np.ones(int(SAMPLE_RATE * 0.1), dtype=np.float32))

    with pytest.raises(ValueError, match="No speech detected"):
        validate_audio_buffer(np.zeros(SAMPLE_RATE, dtype=np.float32))

    with pytest.raises(ValueError, match="No speech detected"):
        validate_audio_buffer(_tone(0.6, amplitude=0.001))

    arr = validate_audio_buffer(_tone(0.5, amplitude=0.05))
    assert arr.dtype == np.float32


def test_primer_leak_guard():
    assert strip_primer_leak(TANGLISH_INITIAL_PROMPT) == ""
    assert strip_primer_leak("Offer ah 25 percent nu maathu. Background music konjam kammi pannu. Undo. Export.") == ""
    assert strip_primer_leak(f"{TANGLISH_INITIAL_PROMPT} Make it 10 seconds") == "Make it 10 seconds"
    assert strip_primer_leak("Create a 10 seconds reel. Undo. Export.") == "Create a 10 seconds reel."
    # Genuine commands must not be stripped
    assert strip_primer_leak("Undo") == "Undo"
    assert strip_primer_leak("Export.") == "Export."
    canonical = "Indha photos ellathayum use panni oru 15 seconds Instagram reel create pannu."
    assert strip_primer_leak(canonical) == canonical


def test_dual_router_modes_and_fallbacks():
    router = DualSpeechRouter()
    router.indic.status = "ready"
    router.indic.recognizer = object()
    router.indic.transcribe_sync = lambda samples: SimpleNamespace(text="மியூசிக் கம்மி பண்ணு", language="ta", elapsed_seconds=0.1)

    router.whisper.status = "ready"
    router.whisper.model = object()
    calls = []

    def fake_whisper(samples, language="en", initial_prompt=None):
        calls.append((language, initial_prompt))
        return SimpleNamespace(text="Music kammi pannu", language="en", elapsed_seconds=0.2)

    router.whisper.transcribe_sync = fake_whisper

    # Tanglish runs both engines (Pass A + Pass B with primer)
    res_tan = asyncio.run(router.transcribe_pcm(_tone(), mode="tanglish"))
    assert isinstance(res_tan, DualTranscriptResult)
    assert res_tan.tamil_transcript == "மியூசிக் கம்மி பண்ணு"
    assert res_tan.english_transcript == "Music kammi pannu"
    assert res_tan.primary_text == "Music kammi pannu"
    assert res_tan.engines_used == ["indicconformer-ta", "faster-whisper"]
    assert calls[-1] == ("en", TANGLISH_INITIAL_PROMPT)

    # English runs Whisper only with initial_prompt=None
    res_en = asyncio.run(router.transcribe_pcm(_tone(), mode="en"))
    assert res_en.engines_used == ["faster-whisper"]
    assert calls[-1] == ("en", None)

    # Tamil runs IndicConformer only
    res_ta = asyncio.run(router.transcribe_pcm(_tone(), mode="ta"))
    assert res_ta.engines_used == ["indicconformer-ta"]
    assert res_ta.primary_text == "மியூசிக் கம்மி பண்ணு"

    # Fallback when IndicConformer unavailable
    router.indic.status = "unavailable"
    router.indic.recognizer = None
    res_ta_fb = asyncio.run(router.transcribe_pcm(_tone(), mode="ta"))
    assert res_ta_fb.engines_used == ["faster-whisper"]
    assert calls[-1] == ("ta", None)

    res_tan_fb = asyncio.run(router.transcribe_pcm(_tone(), mode="tanglish"))
    assert res_tan_fb.engines_used == ["faster-whisper"]
    assert res_tan_fb.tamil_transcript is None
    assert res_tan_fb.primary_text == "Music kammi pannu"


def test_capabilities_exposes_granular_asr_status(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.speech, "initialize", lambda: None)
    main.speech.indic.status = "ready"
    main.speech.whisper.status = "unavailable"
    with TestClient(main.app) as client:
        resp = client.get("/api/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["asr_engines"] == {"indicconformer_ta": True, "faster_whisper_small": False}
        assert data["supported_modes"] == ["tanglish", "ta", "en"]
        assert data["streaming_ws"] is True
        assert data["speech"]["status"] == "ready"
