"""Tests for V2 Phase 4 ASR engine abstraction layer."""
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.app.voice.engines.base import ASREngine
from backend.app.voice.engines.tamil_kili import TamilKiliEngine
from backend.app.voice.engines.whisper_turbo import WhisperTurboEngine
from backend.app.voice.engines.legacy import FasterWhisperSpeechEngine, IndicConformerTamilEngine
from backend.app.models import TranscriptResult


# ---------------------------------------------------------------------------
# ASREngine protocol
# ---------------------------------------------------------------------------

def test_faster_whisper_satisfies_asr_engine_protocol():
    """FasterWhisperSpeechEngine must conform to ASREngine Protocol."""
    engine = FasterWhisperSpeechEngine()
    assert isinstance(engine, ASREngine)


def test_indic_conformer_satisfies_asr_engine_protocol():
    """IndicConformerTamilEngine must conform to ASREngine Protocol."""
    engine = IndicConformerTamilEngine()
    assert isinstance(engine, ASREngine)


# ---------------------------------------------------------------------------
# TamilKiliEngine stub
# ---------------------------------------------------------------------------

def test_tamil_kili_stub_status_unavailable():
    """TamilKili stub must always report 'unavailable'."""
    kili = TamilKiliEngine()
    assert kili.status == "unavailable"
    assert kili.error is not None
    assert len(kili.error) > 10  # has a meaningful message


def test_tamil_kili_stub_initialize_does_not_raise():
    """TamilKili.initialize() must not raise — it only logs."""
    kili = TamilKiliEngine()
    kili.initialize()  # should not raise
    assert kili.status == "unavailable"


def test_tamil_kili_stub_transcribe_raises_runtime_error():
    """TamilKili.transcribe() must raise RuntimeError (triggers router fallback)."""
    kili = TamilKiliEngine()
    with pytest.raises(RuntimeError, match="integration pending|TDT|Tamil Kili"):
        asyncio.run(kili.transcribe(np.zeros(16000, dtype=np.float32)))


# ---------------------------------------------------------------------------
# WhisperTurboEngine — model missing → unavailable
# ---------------------------------------------------------------------------

def test_whisper_turbo_unavailable_when_model_missing(tmp_path, monkeypatch):
    """WhisperTurboEngine must be unavailable when model.bin is not on disk."""
    monkeypatch.setenv("SOLLICUT_MODEL_DIR", str(tmp_path))
    turbo = WhisperTurboEngine()
    turbo.initialize()
    assert turbo.status == "unavailable"
    assert turbo.error is not None


def test_whisper_turbo_transcribe_raises_when_unavailable():
    """WhisperTurboEngine.transcribe() must raise RuntimeError when not ready."""
    turbo = WhisperTurboEngine()
    # Don't initialize — model is None
    with pytest.raises(RuntimeError):
        asyncio.run(turbo.transcribe(np.zeros(16000, dtype=np.float32)))


def test_whisper_turbo_transcribe_uses_no_forced_language(tmp_path, monkeypatch):
    """When language_hint is 'tanglish', Whisper Turbo must NOT force language='en'."""
    monkeypatch.setenv("SOLLICUT_MODEL_DIR", str(tmp_path))
    # Mock the WhisperModel so we can inspect the transcribe call
    mock_model = MagicMock()
    mock_segments = [MagicMock(text="indha photos use pannunga")]
    mock_info = MagicMock(language="ta")
    mock_model.transcribe.return_value = (mock_segments, mock_info)

    turbo = WhisperTurboEngine()
    turbo.model = mock_model
    turbo.status = "ready"
    turbo.error = None

    result = t_ = np.linspace(0, 1.0, 16000, endpoint=False)
    tone_ = (0.1 * np.sin(2 * np.pi * 440 * t_)).astype(np.float32)
    result = asyncio.run(turbo.transcribe(tone_, language_hint="tanglish"))    # The language parameter passed to model.transcribe must be None (not "en") for Tanglish
    call_kwargs = mock_model.transcribe.call_args[1]
    assert call_kwargs.get("language") is None, (
        f"Tanglish mode must NOT force language='en', got: {call_kwargs.get('language')}"
    )
    assert isinstance(result, TranscriptResult)


# ---------------------------------------------------------------------------
# Adaptive router upgrade (no V2 models present → V1 kept)
# ---------------------------------------------------------------------------

def test_upgrade_router_keeps_v1_when_turbo_missing(tmp_path, monkeypatch):
    """upgrade_router must keep V1 engines when large-v3-turbo is not downloaded."""
    monkeypatch.setenv("SOLLICUT_MODEL_DIR", str(tmp_path))
    from backend.app.speech import DualSpeechRouter
    from backend.app.voice.router import upgrade_router
    router = DualSpeechRouter()
    original_whisper = router.whisper
    upgrade_router(router)
    # Whisper engine should be unchanged (V1 kept)
    assert router.whisper is original_whisper
