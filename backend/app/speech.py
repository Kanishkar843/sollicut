import asyncio
import logging
import re
import time
import wave
from pathlib import Path
from typing import Literal, Protocol

import numpy as np

from . import config
from .models import DualTranscriptResult, TranscriptResult

logger = logging.getLogger("sollicut.speech")

SAMPLE_RATE = 16000
MIN_AUDIO_SECONDS = 0.3
MIN_RMS_THRESHOLD = 0.004

TANGLISH_INITIAL_PROMPT = (
    "Indha photos ellathayum use panni oru 15 seconds Instagram reel create pannu. "
    "Smooth zoom effects podu. Background music add pannu. "
    "Last la 20 percent offer nu text podu. "
    "Offer ah 25 percent nu maathu. Background music konjam kammi pannu. "
    "Undo. Export."
)

_PRIMER_TAIL = "Undo. Export."
_PRIMER_FULL_NORM = re.sub(r"[^a-z0-9\s]", "", TANGLISH_INITIAL_PROMPT.lower()).strip()


def validate_audio_buffer(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Ensure 16 kHz mono float32 buffer has sufficient duration and RMS energy."""
    arr = np.asarray(samples, dtype=np.float32).reshape(-1)
    if arr.size < int(MIN_AUDIO_SECONDS * sample_rate):
        raise ValueError("Recording is too short. Please speak for at least 0.3 seconds.")
    rms = float(np.sqrt(np.mean(np.square(arr, dtype=np.float64))))
    if rms < MIN_RMS_THRESHOLD:
        raise ValueError("No speech detected. Move closer to the microphone and try again.")
    return np.ascontiguousarray(arr, dtype=np.float32)


def load_wav_float32(wav_path: Path) -> np.ndarray:
    """Load a 16 kHz mono PCM WAV file into a normalized float32 NumPy array."""
    with wave.open(str(wav_path), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != SAMPLE_RATE:
            raise ValueError("Expected 16 kHz mono 16-bit PCM WAV audio.")
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def strip_primer_leak(text: str) -> str:
    """Remove Whisper initial_prompt hallucinations without altering genuine single commands."""
    cleaned = text.strip()
    if not cleaned:
        return ""
    norm = re.sub(r"[^a-z0-9\s]", "", cleaned.lower()).strip()
    if norm == _PRIMER_FULL_NORM:
        return ""
    # Full prompt leaked as prefix before another utterance
    if cleaned.lower().startswith(TANGLISH_INITIAL_PROMPT.lower()):
        return cleaned[len(TANGLISH_INITIAL_PROMPT):].strip(" .,!")
    # Multi-sentence tail leak from the prompt ending in "Undo. Export."
    tail_leak = "Offer ah 25 percent nu maathu. Background music konjam kammi pannu. Undo. Export."
    if cleaned.lower() == tail_leak.lower() or cleaned.lower() == _PRIMER_TAIL.lower():
        return ""
    if cleaned.lower().endswith(" " + _PRIMER_TAIL.lower()) and not re.fullmatch(
        r"(?:undo|export)\.?", cleaned.lower().strip()
    ):
        candidate = cleaned[: -len(_PRIMER_TAIL)].strip()
        if candidate:
            cleaned = candidate
            norm_after = re.sub(r"[^a-z0-9\s]", "", cleaned.lower()).strip()
            if norm_after and _PRIMER_FULL_NORM.startswith(norm_after) and len(norm_after) > 110:
                return ""
    return cleaned


class SpeechEngine(Protocol):
    async def transcribe(self, audio_input: Path | np.ndarray, language_hint: str | None = None) -> TranscriptResult: ...


class IndicConformerTamilEngine:
    def __init__(self):
        self.recognizer = None
        self.status = "loading"
        self.error: str | None = None

    def initialize(self) -> None:
        if not config.is_indic_asr_enabled():
            self.recognizer = None
            self.status = "disabled"
            self.error = "IndicConformer Tamil ASR is disabled by configuration."
            return
        try:
            import sherpa_onnx

            indic_dir = config.get_indic_model_dir()
            model_path = indic_dir / "model.int8.onnx"
            tokens_path = indic_dir / "tokens.txt"
            if not model_path.is_file() or not tokens_path.is_file():
                raise FileNotFoundError(f"Missing IndicConformer files in {indic_dir}")
            self.recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
                model=str(model_path),
                tokens=str(tokens_path),
                num_threads=config.get_asr_threads(),
                provider="cpu",
                decoding_method="greedy_search",
            )
            self.status = "ready"
            self.error = None
        except Exception as exc:
            self.recognizer = None
            self.status = "unavailable"
            self.error = f"IndicConformer Tamil model unavailable: {exc}"
            logger.warning("IndicConformer initialization failed: %s", exc)

    def transcribe_sync(self, audio_input: Path | np.ndarray) -> TranscriptResult:
        if self.recognizer is None:
            raise RuntimeError(self.error or "IndicConformer Tamil model is not ready.")
        samples = load_wav_float32(audio_input) if isinstance(audio_input, Path) else audio_input
        samples = validate_audio_buffer(samples)
        started = time.perf_counter()
        stream = self.recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples)
        self.recognizer.decode_stream(stream)
        text = (stream.result.text or "").strip()
        if not text:
            raise ValueError("No speech detected. Move closer to the microphone and try again.")
        return TranscriptResult(
            text=text,
            language="ta",
            elapsed_seconds=round(time.perf_counter() - started, 3),
        )

    async def transcribe(self, audio_input: Path | np.ndarray, language_hint: str | None = None) -> TranscriptResult:
        return await asyncio.to_thread(self.transcribe_sync, audio_input)


class FasterWhisperSpeechEngine:
    def __init__(self):
        self.model = None
        self.status = "loading"
        self.error: str | None = None
        self.lock = asyncio.Lock()

    def initialize(self) -> None:
        try:
            from faster_whisper import WhisperModel

            name = config.get_asr_model()
            local = config.get_model_dir() / name
            if not (local / "model.bin").is_file():
                raise FileNotFoundError(f"Missing Whisper model at {local}")
            self.model = WhisperModel(
                str(local),
                device=config.get_asr_device(),
                compute_type=config.get_asr_compute_type(),
                cpu_threads=config.get_asr_threads(),
                local_files_only=True,
            )
            self.status = "ready"
            self.error = None
        except Exception:
            self.model = None
            self.status = "unavailable"
            self.error = "Local speech model unavailable. Run the model setup or rebuild the image with network access."

    def transcribe_sync(
        self,
        audio_input: Path | np.ndarray,
        language: str | None = "en",
        initial_prompt: str | None = None,
    ) -> TranscriptResult:
        if self.model is None:
            raise RuntimeError(self.error or "Speech model is still loading; try again shortly.")
        if isinstance(audio_input, np.ndarray):
            target: str | np.ndarray = validate_audio_buffer(audio_input)
        else:
            target = str(audio_input)

        started = time.perf_counter()
        kwargs: dict = {
            "language": language,
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
            language=getattr(info, "language", language or "en"),
            elapsed_seconds=round(time.perf_counter() - started, 3),
        )

    async def transcribe(
        self,
        audio_input: Path | np.ndarray,
        language_hint: str | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptResult:
        if self.model is None:
            raise RuntimeError(self.error or "Speech model is still loading; try again shortly.")
        async with self.lock:
            return await asyncio.to_thread(self.transcribe_sync, audio_input, language_hint, initial_prompt)


class DualSpeechRouter:
    """Unified CPU speech router orchestrating IndicConformer-TA and faster-whisper small."""

    def __init__(self):
        self.indic = IndicConformerTamilEngine()
        self.whisper = FasterWhisperSpeechEngine()
        self.lock = asyncio.Lock()

    @property
    def status(self) -> str:
        statuses = {self.indic.status, self.whisper.status}
        if "ready" in statuses:
            return "ready"
        if "loading" in statuses:
            return "loading"
        return "unavailable"

    @property
    def error(self) -> str | None:
        if self.status == "ready":
            return None
        if self.status == "loading":
            return "Local speech models are still loading; try again shortly."
        return self.whisper.error or self.indic.error or "Local speech models are unavailable."

    def capabilities(self) -> dict:
        indic_ready = self.indic.status == "ready"
        whisper_ready = self.whisper.status == "ready"
        engine_label = (
            "dual-asr"
            if (indic_ready and whisper_ready)
            else ("indicconformer-ta" if indic_ready else "faster-whisper")
        )
        return {
            "engine": engine_label,
            "status": self.status,
            "error": self.error,
            "asr_engines": {
                "indicconformer_ta": indic_ready,
                "faster_whisper_small": whisper_ready,
            },
            "supported_modes": ["tanglish", "ta", "en"],
            "streaming_ws": True,
        }

    def initialize(self) -> None:
        self.whisper.initialize()
        self.indic.initialize()

    async def transcribe_pcm(
        self,
        samples: np.ndarray,
        mode: Literal["tanglish", "ta", "en"] = "tanglish",
    ) -> DualTranscriptResult:
        if mode not in {"tanglish", "ta", "en"}:
            raise ValueError("Speech mode must be tanglish, ta, or en.")
        validated = validate_audio_buffer(samples)
        if self.status != "ready":
            raise RuntimeError(self.error or "Local speech model is still loading; try again shortly.")
        async with self.lock:
            return await asyncio.to_thread(self._route_sync, validated, mode)

    def _route_sync(self, samples: np.ndarray, mode: Literal["tanglish", "ta", "en"]) -> DualTranscriptResult:
        started = time.perf_counter()
        indic_ready = self.indic.recognizer is not None
        whisper_ready = self.whisper.model is not None

        if not indic_ready and not whisper_ready:
            raise RuntimeError(self.error or "No local speech engine is available.")

        if mode == "ta":
            if indic_ready:
                res = self.indic.transcribe_sync(samples)
                return DualTranscriptResult(
                    primary_text=res.text,
                    tamil_transcript=res.text,
                    english_transcript=None,
                    mode="ta",
                    engines_used=["indicconformer-ta"],
                    elapsed_seconds=res.elapsed_seconds,
                )
            res = self.whisper.transcribe_sync(samples, language="ta", initial_prompt=None)
            return DualTranscriptResult(
                primary_text=res.text,
                tamil_transcript=res.text,
                english_transcript=None,
                mode="ta",
                engines_used=["faster-whisper"],
                elapsed_seconds=res.elapsed_seconds,
            )

        if mode == "en":
            if whisper_ready:
                res = self.whisper.transcribe_sync(samples, language="en", initial_prompt=None)
                return DualTranscriptResult(
                    primary_text=res.text,
                    tamil_transcript=None,
                    english_transcript=res.text,
                    mode="en",
                    engines_used=["faster-whisper"],
                    elapsed_seconds=res.elapsed_seconds,
                )
            res = self.indic.transcribe_sync(samples)
            return DualTranscriptResult(
                primary_text=res.text,
                tamil_transcript=res.text,
                english_transcript=None,
                mode="en",
                engines_used=["indicconformer-ta"],
                elapsed_seconds=res.elapsed_seconds,
            )

        # Tanglish dual-pass: Pass A (IndicConformer-TA) + Pass B (Whisper small + primer)
        tamil_text: str | None = None
        english_text: str | None = None
        engines_used: list[str] = []

        if indic_ready:
            try:
                res_a = self.indic.transcribe_sync(samples)
                tamil_text = res_a.text
                engines_used.append("indicconformer-ta")
            except ValueError:
                tamil_text = None

        if whisper_ready:
            try:
                res_b = self.whisper.transcribe_sync(
                    samples,
                    language="en",
                    initial_prompt=TANGLISH_INITIAL_PROMPT,
                )
                english_text = res_b.text
                engines_used.append("faster-whisper")
            except ValueError:
                english_text = None

        if not tamil_text and not english_text:
            raise ValueError("No speech detected. Move closer to the microphone and try again.")

        primary_text = english_text or tamil_text or ""
        return DualTranscriptResult(
            primary_text=primary_text,
            tamil_transcript=tamil_text,
            english_transcript=english_text,
            mode="tanglish",
            engines_used=engines_used,
            elapsed_seconds=round(time.perf_counter() - started, 3),
        )

    async def transcribe(self, audio_input: Path | np.ndarray, language_hint: str | None = None) -> TranscriptResult:
        mode: Literal["tanglish", "ta", "en"] = "ta" if language_hint == "ta" else "en" if language_hint == "en" else "tanglish"
        samples = load_wav_float32(audio_input) if isinstance(audio_input, Path) else audio_input
        dual = await self.transcribe_pcm(samples, mode=mode)
        return TranscriptResult(
            text=dual.primary_text,
            language=mode if mode != "tanglish" else "ta-en",
            elapsed_seconds=dual.elapsed_seconds,
        )
