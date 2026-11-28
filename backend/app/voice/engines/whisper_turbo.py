"""
backend/app/voice/engines/whisper_turbo.py — Whisper Large-v3-Turbo engine (V2 Phase 4)

Drop-in upgrade for FasterWhisperSpeechEngine using the large-v3-turbo model.
Gated by SOLLICUT_ASR_MODEL=large-v3-turbo (or SOLLICUT_TURBO_ENABLED=true).

Model sources (no token required, public HuggingFace):
  - deepdml/faster-whisper-large-v3-turbo-ct2  (~1.5 GB INT8 CTranslate2)
  - Systran/faster-whisper-large-v3-turbo       (auto INT8 on load)

Estimated performance on Intel Core 7 150U (12 cores, AVX2):
  - Cold init: ~8–12 s
  - Warm RTF:  ~3–5× realtime on CPU INT8 (5 s audio → ~1–2 s transcription)
  - Peak RAM:  ~1.8–2.2 GB
  Source: NEEDS HUMAN VERIFICATION on target hardware

Privacy: audio buffer never written to disk; discarded after transcription.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import numpy as np

from ... import config
from ...models import TranscriptResult
from ...speech import (
    MIN_AUDIO_SECONDS,
    MIN_RMS_THRESHOLD,
    SAMPLE_RATE,
    TANGLISH_INITIAL_PROMPT,
    strip_primer_leak,
    validate_audio_buffer,
)

logger = logging.getLogger("sollicut.voice.engines.whisper_turbo")

TURBO_MODEL_ID = "large-v3-turbo"


class WhisperTurboEngine:
    """
    Whisper Large-v3-Turbo via faster-whisper (CTranslate2 INT8).

    Use for high-accuracy Tanglish/English when SOLLICUT_ASR_MODEL=large-v3-turbo.
    Falls back gracefully when model is not available locally.
    """

    def __init__(self):
        self.model = None
        self.status = "loading"
        self.error: str | None = None
        self._lock = asyncio.Lock()

    def initialize(self) -> None:
        """Load the large-v3-turbo model from local disk (must be pre-downloaded)."""
        try:
            from faster_whisper import WhisperModel

            local = config.get_model_dir() / TURBO_MODEL_ID
            if not (local / "model.bin").is_file():
                raise FileNotFoundError(
                    f"Whisper large-v3-turbo model not found at {local}. "
                    "Run: python -m scripts.download_model SOLLICUT_ASR_MODEL=large-v3-turbo"
                )
            self.model = WhisperModel(
                str(local),
                device=config.get_asr_device(),
                compute_type=config.get_asr_compute_type(),
                cpu_threads=config.get_asr_threads(),
                local_files_only=True,
            )
            self.status = "ready"
            self.error = None
            logger.info("Whisper large-v3-turbo loaded from %s", local)
        except Exception as exc:
            self.model = None
            self.status = "unavailable"
            self.error = str(exc)
            logger.warning("WhisperTurboEngine unavailable: %s", exc)

    def transcribe_sync(
        self,
        audio_input: Path | np.ndarray,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptResult:
        if self.model is None:
            raise RuntimeError(self.error or "Whisper large-v3-turbo model is not ready.")
        if isinstance(audio_input, np.ndarray):
            target: str | np.ndarray = validate_audio_buffer(audio_input)
        else:
            target = str(audio_input)

        started = time.perf_counter()
        kwargs: dict = {
            "language": language,  # None → auto-detect (better for Tanglish)
            "beam_size": 2,
            "temperature": 0.0,
            "vad_filter": False,
            "condition_on_previous_text": False,
        }
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt

        segments, info = self.model.transcribe(target, **kwargs)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if initial_prompt:
            text = strip_primer_leak(text)
        if not text:
            raise ValueError("No speech detected. Move closer to the microphone and try again.")
        return TranscriptResult(
            text=text,
            language=getattr(info, "language", language or "ta"),
            elapsed_seconds=round(time.perf_counter() - started, 3),
        )

    async def transcribe(
        self,
        audio_input: Path | np.ndarray,
        language_hint: str | None = None,
    ) -> TranscriptResult:
        # Map ASR mode → Whisper language parameter
        # tanglish/None → None (auto-detect; handles Tamil+English code-switching)
        # ta → "ta"
        # en → "en"
        whisper_lang: str | None
        if language_hint in ("tanglish", None):
            whisper_lang = None
            prompt = TANGLISH_INITIAL_PROMPT
        elif language_hint == "ta":
            whisper_lang = "ta"
            prompt = None
        else:
            whisper_lang = language_hint  # "en" or explicit BCP-47
            prompt = None
        async with self._lock:
            return await asyncio.to_thread(
                self.transcribe_sync,
                audio_input,
                whisper_lang,
                prompt,
            )
