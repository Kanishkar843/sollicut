"""Tests for backend/app/voice/vad.py and backend/app/voice/audio_quality.py (Phase 3)"""
import numpy as np
import pytest

from backend.app.voice.vad import (
    SileroVAD,
    _probs_to_segments,
    _rms_has_speech,
    SILERO_CHUNK_SIZE,
    MIN_SPEECH_SAMPLES,
    SILERO_SAMPLE_RATE,
)
from backend.app.voice.audio_quality import assess, MAX_CLIP_RATIO


# ---------------------------------------------------------------------------
# _rms_has_speech fallback
# ---------------------------------------------------------------------------

def test_rms_has_speech_detects_tone():
    """440 Hz sine at amplitude 0.1 should have sufficient RMS to pass."""
    t = np.linspace(0, 0.5, int(0.5 * SILERO_SAMPLE_RATE), endpoint=False)
    samples = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    assert _rms_has_speech(samples) is True


def test_rms_has_speech_rejects_silence():
    """Near-zero amplitude buffer should return False."""
    samples = np.zeros(int(0.5 * SILERO_SAMPLE_RATE), dtype=np.float32)
    assert _rms_has_speech(samples) is False


def test_rms_has_speech_rejects_too_short():
    """Buffer shorter than MIN_AUDIO_SECONDS should return False."""
    samples = (0.1 * np.ones(100, dtype=np.float32))
    assert _rms_has_speech(samples) is False


# ---------------------------------------------------------------------------
# _probs_to_segments
# ---------------------------------------------------------------------------

def test_probs_to_segments_all_speech():
    """All chunks at prob=0.9 should produce one segment covering the whole buffer."""
    n_chunks = 20
    probs = [0.9] * n_chunks
    segs = _probs_to_segments(probs, SILERO_CHUNK_SIZE)
    assert len(segs) == 1
    assert segs[0][0] == 0
    assert segs[0][1] == n_chunks * SILERO_CHUNK_SIZE


def test_probs_to_segments_all_silence():
    """All chunks at prob=0.1 (< SILENCE_THRESHOLD) should produce no segments."""
    probs = [0.1] * 20
    segs = _probs_to_segments(probs, SILERO_CHUNK_SIZE)
    assert len(segs) == 0


def test_probs_to_segments_two_distinct_speech_regions():
    """Two speech bursts separated by long silence should produce two segments."""
    # 50 chunks: 10 speech, 20 silence, 10 speech, 10 silence
    probs = [0.9] * 10 + [0.1] * 20 + [0.9] * 10 + [0.1] * 10
    segs = _probs_to_segments(probs, SILERO_CHUNK_SIZE)
    assert len(segs) == 2


def test_probs_to_segments_short_speech_below_min_duration():
    """Speech burst shorter than MIN_SPEECH_SAMPLES should be discarded."""
    # Only 2 chunks of speech (< 300 ms threshold) followed by silence
    n_chunks_min = (MIN_SPEECH_SAMPLES // SILERO_CHUNK_SIZE) - 1
    probs = [0.9] * max(1, n_chunks_min) + [0.1] * 50
    segs = _probs_to_segments(probs, SILERO_CHUNK_SIZE)
    assert len(segs) == 0, f"Expected no segments for short burst, got: {segs}"


# ---------------------------------------------------------------------------
# SileroVAD (unavailable / fallback mode)
# ---------------------------------------------------------------------------

@pytest.fixture
def vad_no_model(tmp_path):
    """SileroVAD with a non-existent model path → fallback to RMS gate."""
    v = SileroVAD(model_path=tmp_path / "nonexistent.onnx")
    v.initialize()
    assert v.status == "unavailable"
    return v


def test_silero_vad_fallback_has_speech(vad_no_model):
    """When ONNX unavailable, has_speech falls back to RMS gate — detects sine tone."""
    t = np.linspace(0, 0.5, int(0.5 * SILERO_SAMPLE_RATE), endpoint=False)
    samples = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    assert vad_no_model.has_speech(samples) is True


def test_silero_vad_fallback_no_speech_on_silence(vad_no_model):
    """When ONNX unavailable, silence returns no speech."""
    samples = np.zeros(int(0.5 * SILERO_SAMPLE_RATE), dtype=np.float32)
    assert vad_no_model.has_speech(samples) is False


def test_silero_vad_fallback_get_segments_on_tone(vad_no_model):
    """Fallback get_speech_segments returns single [(0, N)] for a tone."""
    t = np.linspace(0, 0.5, int(0.5 * SILERO_SAMPLE_RATE), endpoint=False)
    samples = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    segs = vad_no_model.get_speech_segments(samples)
    assert len(segs) == 1
    assert segs[0][0] == 0
    assert segs[0][1] == len(samples)


def test_silero_vad_fallback_filter_speech_passthrough_on_silence(vad_no_model):
    """When fallback returns no speech segments, filter_speech_only returns original array."""
    samples = np.zeros(int(0.5 * SILERO_SAMPLE_RATE), dtype=np.float32)
    result = vad_no_model.filter_speech_only(samples)
    # Should return original (not empty), so ASR can still reject it properly
    assert len(result) == len(samples)


# ---------------------------------------------------------------------------
# AudioQuality
# ---------------------------------------------------------------------------

def test_audio_quality_normal_tone():
    """440 Hz sine at 0.3 amplitude: not clipping, not empty, not too short."""
    t = np.linspace(0, 1.0, SILERO_SAMPLE_RATE, endpoint=False)
    samples = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    report = assess(samples)
    assert not report.is_clipping
    assert not report.is_empty
    assert not report.is_too_short
    assert report.is_acceptable
    assert report.duration_seconds == pytest.approx(1.0, abs=0.01)
    assert report.rms == pytest.approx(0.3 / (2 ** 0.5), abs=0.01)


def test_audio_quality_clipping_detection():
    """Buffer of near-maximum values (1.0) should trigger clipping flag."""
    samples = np.ones(SILERO_SAMPLE_RATE, dtype=np.float32)
    report = assess(samples)
    assert report.is_clipping
    assert len(report.warnings) > 0
    assert any("clip" in w.lower() for w in report.warnings)


def test_audio_quality_too_short():
    """Buffer shorter than 0.3s should be flagged as too short."""
    samples = (0.1 * np.ones(100, dtype=np.float32))  # < 0.3s
    report = assess(samples)
    assert report.is_too_short
    assert not report.is_acceptable


def test_audio_quality_silent():
    """Zero buffer should be flagged as empty."""
    samples = np.zeros(SILERO_SAMPLE_RATE, dtype=np.float32)
    report = assess(samples)
    assert report.is_empty
    assert not report.is_acceptable


def test_audio_quality_no_warnings_for_good_audio():
    """Clean 0.1 amplitude sine for 1 second should produce no warnings."""
    t = np.linspace(0, 1.0, SILERO_SAMPLE_RATE, endpoint=False)
    samples = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    report = assess(samples)
    assert report.warnings == []
