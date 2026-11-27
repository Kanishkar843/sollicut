import asyncio
import os
import time
from pathlib import Path
from typing import Protocol

from .models import TranscriptResult
from .storage import ROOT


class SpeechEngine(Protocol):
    async def transcribe(self, audio_path: Path, language_hint: str | None = None) -> TranscriptResult: ...


class FasterWhisperSpeechEngine:
    def __init__(self):
        self.model = None
        self.status = "loading"
        self.error = None
        self.lock = asyncio.Lock()

    def initialize(self):
        try:
            from faster_whisper import WhisperModel
            name = os.getenv("SOLLICUT_ASR_MODEL", "base")
            local = Path(os.getenv("SOLLICUT_MODEL_DIR", str(ROOT / "models"))) / name
            self.model = WhisperModel(str(local), device="cpu", compute_type="int8", cpu_threads=4, local_files_only=True)
            self.status = "ready"
        except Exception:
            self.status = "unavailable"
            self.error = "Local speech model unavailable. Run the model setup or rebuild the image with network access."

    async def transcribe(self, audio_path: Path, language_hint: str | None = None) -> TranscriptResult:
        if self.model is None:
            raise RuntimeError(self.error or "Speech model is still loading; try again shortly.")
        async with self.lock:
            return await asyncio.to_thread(self._transcribe, audio_path, language_hint)

    def _transcribe(self, path, language):
        started = time.perf_counter()
        segments, info = self.model.transcribe(str(path), language=language, beam_size=5, vad_filter=True,
            condition_on_previous_text=False)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise ValueError("No speech detected. Move closer to the microphone and try again.")
        return TranscriptResult(text=text, language=info.language, elapsed_seconds=round(time.perf_counter()-started, 3))
