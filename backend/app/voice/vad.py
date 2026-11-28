"""
SileroVAD — Silero Voice Activity Detection ONNX wrapper (V2 Phase 3)

Model: silero_vad.onnx (MIT license)
Source: https://github.com/snakers4/silero-vad
Direct URL: https://github.com/snakers4/silero-vad/raw/refs/heads/master/src/silero_vad/data/silero_vad.onnx

Input: 16 kHz float32 PCM array (whole utterance — not streaming per-chunk)
Output: list of {start_sample, end_sample} speech segments

Fallback: if ONNX model unavailable, falls back to RMS energy gate
         (same behavior as V1 — MIN_RMS_THRESHOLD=0.004, MIN_AUDIO_SECONDS=0.3)
"""

import logging
import threading
from pathlib import Path

import numpy as np

logger = logging.getLogger("sollicut.voice.vad")

# Silero VAD constants
SILERO_SAMPLE_RATE = 16000
SILERO_CHUNK_SIZE = 512          # 32 ms at 16 kHz (required by Silero ONNX v5)
SPEECH_THRESHOLD = 0.5
SILENCE_THRESHOLD = 0.35
MIN_SPEECH_SAMPLES = int(0.3 * SILERO_SAMPLE_RATE)   # 300 ms minimum speech
MAX_PAUSE_SAMPLES = int(0.5 * SILERO_SAMPLE_RATE)    # 500 ms max internal pause

# V1 fallback constants (kept for parity with speech.py)
MIN_RMS_THRESHOLD = 0.004
MIN_AUDIO_SECONDS = 0.3


def _default_model_path() -> Path:
    """Return the expected local path for the Silero VAD ONNX model."""
    from .. import config
    return config.get_model_dir() / "silero_vad" / "silero_vad.onnx"


class SileroVAD:
    """
    Silero VAD ONNX engine.

    Usage:
        vad = SileroVAD()
        vad.initialize()          # loads ONNX model
        segments = vad.get_speech_segments(samples_float32)
        # segments: list of (start_sample, end_sample) tuples
        has_speech = vad.has_speech(samples_float32)  # bool shorthand
    """

    def __init__(self, model_path: Path | None = None):
        self._model_path = model_path or _default_model_path()
        self._session = None
        self._lock = threading.Lock()
        self.status = "not_initialized"
        self.error: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Load the Silero VAD ONNX model. Call once at startup."""
        try:
            import onnxruntime as ort

            if not self._model_path.is_file():
                raise FileNotFoundError(
                    f"Silero VAD model not found at {self._model_path}. "
                    "Run scripts/download_model.py to download it."
                )
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            opts.log_severity_level = 3  # suppress verbose ONNX logs
            self._session = ort.InferenceSession(
                str(self._model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self.status = "ready"
            self.error = None
            logger.info("Silero VAD loaded from %s", self._model_path)
        except Exception as exc:
            self._session = None
            self.status = "unavailable"
            self.error = str(exc)
            logger.warning("Silero VAD unavailable: %s — falling back to RMS gate", exc)

    def has_speech(self, samples: np.ndarray) -> bool:
        """Return True if the audio contains detectable speech."""
        if self._session is None:
            return _rms_has_speech(samples)
        try:
            segments = self.get_speech_segments(samples)
            return len(segments) > 0
        except Exception as exc:
            logger.debug("Silero VAD inference error: %s — using RMS fallback", exc)
            return _rms_has_speech(samples)

    def get_speech_segments(
        self, samples: np.ndarray
    ) -> list[tuple[int, int]]:
        """
        Return list of (start_sample, end_sample) speech segments.
        Falls back to [(0, len(samples))] when ONNX unavailable and RMS > threshold.
        """
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        if self._session is None:
            if _rms_has_speech(samples):
                return [(0, len(samples))]
            return []
        try:
            return self._run_silero(samples)
        except Exception as exc:
            logger.debug("Silero VAD segment inference error: %s — using RMS fallback", exc)
            if _rms_has_speech(samples):
                return [(0, len(samples))]
            return []

    def filter_speech_only(self, samples: np.ndarray) -> np.ndarray:
        """
        Concatenate only speech segments from samples into a single array.
        Returns the original array when VAD is unavailable (safe fallback).
        """
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        segments = self.get_speech_segments(samples)
        if not segments:
            return samples  # return whole buffer — ASR will reject if truly silent
        if len(segments) == 1 and segments[0] == (0, len(samples)):
            return samples
        parts = [samples[s:e] for s, e in segments if e > s]
        return np.concatenate(parts) if parts else samples

    # ------------------------------------------------------------------
    # Internal Silero ONNX inference (Silero V5 ONNX API)
    # ------------------------------------------------------------------

    def _run_silero(self, samples: np.ndarray) -> list[tuple[int, int]]:
        """Run Silero VAD ONNX inference and return speech segments."""
        with self._lock:
            session = self._session
        if session is None:
            raise RuntimeError("Silero VAD session not initialized.")

        # Pad to multiple of SILERO_CHUNK_SIZE
        pad_len = (-len(samples)) % SILERO_CHUNK_SIZE
        if pad_len:
            samples = np.concatenate([samples, np.zeros(pad_len, dtype=np.float32)])

        # Silero V5 ONNX expects: sr=int64, input=float32[1,chunk]
        # State tensors: h[2,1,64], c[2,1,64] initialized to zeros
        h = np.zeros((2, 1, 64), dtype=np.float32)
        c = np.zeros((2, 1, 64), dtype=np.float32)
        sr = np.array(SILERO_SAMPLE_RATE, dtype=np.int64)

        input_names = [inp.name for inp in session.get_inputs()]
        output_names = [out.name for out in session.get_outputs()]

        probs: list[float] = []
        num_chunks = len(samples) // SILERO_CHUNK_SIZE
        for i in range(num_chunks):
            chunk = samples[i * SILERO_CHUNK_SIZE:(i + 1) * SILERO_CHUNK_SIZE].reshape(1, -1)
            feed: dict = {}
            for name in input_names:
                if "input" in name.lower():
                    feed[name] = chunk
                elif "sr" in name.lower():
                    feed[name] = sr
                elif name == "h":
                    feed[name] = h
                elif name == "c":
                    feed[name] = c

            outputs = session.run(output_names, feed)
            # outputs: [speech_prob, h_out, c_out]
            out_dict = dict(zip(output_names, outputs))
            # Update state
            for name, val in out_dict.items():
                if name == "h" or "h" in name.lower() and name != "threshold":
                    if val.shape == h.shape:
                        h = val
                elif name == "c" or "c" in name.lower():
                    if val.shape == c.shape:
                        c = val
            # Speech probability — shape varies: (1,1) or (1,) or scalar
            prob_val = None
            for name, val in out_dict.items():
                if "prob" in name.lower() or (name not in ("h", "c") and name not in input_names):
                    prob_val = float(np.asarray(val).reshape(-1)[0])
                    break
            if prob_val is None:
                prob_val = float(np.asarray(outputs[0]).reshape(-1)[0])
            probs.append(prob_val)

        return _probs_to_segments(probs, SILERO_CHUNK_SIZE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rms_has_speech(samples: np.ndarray) -> bool:
    """V1-compatible RMS gate fallback."""
    arr = np.asarray(samples, dtype=np.float32).reshape(-1)
    if arr.size < int(MIN_AUDIO_SECONDS * SILERO_SAMPLE_RATE):
        return False
    rms = float(np.sqrt(np.mean(np.square(arr, dtype=np.float64))))
    return rms >= MIN_RMS_THRESHOLD


def _probs_to_segments(
    probs: list[float],
    chunk_size: int,
) -> list[tuple[int, int]]:
    """
    Convert per-chunk speech probabilities to (start_sample, end_sample) segments.
    Applies hysteresis: speech starts when prob≥SPEECH_THRESHOLD,
    ends when prob<SILENCE_THRESHOLD for MAX_PAUSE_SAMPLES worth of chunks.
    """
    segments: list[tuple[int, int]] = []
    in_speech = False
    speech_start = 0
    pause_samples = 0
    max_pause_chunks = MAX_PAUSE_SAMPLES // chunk_size

    for i, prob in enumerate(probs):
        sample_pos = i * chunk_size
        if not in_speech:
            if prob >= SPEECH_THRESHOLD:
                in_speech = True
                speech_start = sample_pos
                pause_samples = 0
        else:
            if prob >= SPEECH_THRESHOLD:
                pause_samples = 0
            elif prob < SILENCE_THRESHOLD:
                pause_samples += chunk_size
                if pause_samples >= max_pause_chunks * chunk_size:
                    end = sample_pos - pause_samples + chunk_size
                    if end - speech_start >= MIN_SPEECH_SAMPLES:
                        segments.append((speech_start, end))
                    in_speech = False
                    pause_samples = 0
            # else: in hysteresis zone — stay in speech

    if in_speech:
        end = len(probs) * chunk_size
        if end - speech_start >= MIN_SPEECH_SAMPLES:
            segments.append((speech_start, end))

    return segments


# Module-level singleton — initialized by speech.py
vad = SileroVAD()
