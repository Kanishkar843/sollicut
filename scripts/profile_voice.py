"""
scripts/profile_voice.py — Measure CPU cold init, warm RTF, and peak RAM for SolliCut ASR/VAD.

Measurements are real hardware timings on the local machine; models not downloaded
locally are reported explicitly as unavailable rather than extrapolated.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

from backend.app import config
from backend.app.speech import SAMPLE_RATE, DualSpeechRouter
from backend.app.voice.vad import SileroVAD


def _peak_rss_mb() -> float | None:
    """Return peak process resident set size in MiB cleanly on Windows or Linux."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = ctypes.c_void_p
            k32.K32GetProcessMemoryInfo.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
            handle = k32.GetCurrentProcess()
            if k32.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return round(counters.PeakWorkingSetSize / (1024 * 1024), 2)
        except Exception:
            return None
    else:
        try:
            import resource

            ru = resource.getrusage(resource.RUSAGE_SELF)
            denom = 1024.0 * 1024.0 if sys.platform == "darwin" else 1024.0
            return round(ru.ru_maxrss / denom, 2)
        except Exception:
            return None
    return None


def _synthesize_test_audio(seconds: float = 5.0) -> tuple[np.ndarray, str]:
    """
    Generate speech-like TTS audio on Windows (SAPI, labeled NOT_HUMAN) or fallback sine tone.
    Returns (float32 samples at 16 kHz, audio_source_label).
    """
    if sys.platform == "win32":
        try:
            import subprocess

            with tempfile.TemporaryDirectory() as tmp:
                wav_path = Path(tmp) / "tts.wav"
                ps_script = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$s.SetOutputToWaveFile('{wav_path}'); "
                    "$s.Speak('Create a fifteen seconds Instagram reel with smooth zoom and background music.'); "
                    "$s.Dispose()"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    check=True,
                    capture_output=True,
                    timeout=20,
                )
                with wave.open(str(wav_path), "rb") as wf:
                    raw = wf.readframes(wf.getnframes())
                    rate = wf.getframerate()
                    ch = wf.getnchannels()
                arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if ch > 1:
                    arr = arr.reshape(-1, ch).mean(axis=1)
                if rate != SAMPLE_RATE and len(arr) > 1:
                    idx = np.linspace(0, len(arr) - 1, int(len(arr) * SAMPLE_RATE / rate))
                    arr = np.interp(idx, np.arange(len(arr)), arr).astype(np.float32)
                return np.ascontiguousarray(arr, dtype=np.float32), "windows_sapi_tts_NOT_HUMAN"
        except Exception:
            pass

    t = np.linspace(0.0, seconds, int(SAMPLE_RATE * seconds), endpoint=False, dtype=np.float32)
    tone = (0.15 * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)
    return tone, "synthetic_220hz_tone_NOT_HUMAN"


def profile_current_environment(profile: str | None = None) -> dict[str, Any]:
    if profile:
        os.environ["SOLLICUT_PROFILE"] = profile
    spec = config.get_profile_spec()
    samples, audio_source = _synthesize_test_audio()
    audio_seconds = round(len(samples) / SAMPLE_RATE, 3)

    rss_before = _peak_rss_mb()

    router = DualSpeechRouter()
    t0 = time.perf_counter()
    router.initialize()
    cold_init_s = round(time.perf_counter() - t0, 3)

    # Silero VAD benchmark if enabled by profile
    vad = SileroVAD()
    vad_init_ms = 0.0
    vad_latency_ms = None
    if config.is_silero_vad_enabled():
        vad_init_t0 = time.perf_counter()
        vad.initialize()
        vad_init_ms = round((time.perf_counter() - vad_init_t0) * 1000, 2)
        if vad.status == "ready":
            vt0 = time.perf_counter()
            _ = vad.get_speech_segments(samples)
            vad_latency_ms = round((time.perf_counter() - vt0) * 1000, 2)
    else:
        vad.status = "disabled_rms_gate"

    modes: dict[str, Any] = {}
    if router.status == "ready":
        for mode in ("en", "ta", "tanglish"):
            timings = []
            last_text = ""
            engines = []
            # 1 warmup + 2 measured runs
            for i in range(3):
                mt0 = time.perf_counter()
                try:
                    res = asyncio.run(router.transcribe_pcm(samples, mode=mode))  # type: ignore[arg-type]
                    dt = time.perf_counter() - mt0
                    last_text = res.primary_text
                    engines = res.engines_used
                except ValueError:
                    dt = time.perf_counter() - mt0
                    last_text = "<blank/no speech>"
                if i > 0:
                    timings.append(dt)
            avg_s = round(sum(timings) / len(timings), 3)
            rtf = round(avg_s / max(audio_seconds, 0.1), 3)
            modes[mode] = {
                "warm_avg_seconds": avg_s,
                "warm_rtf": rtf,
                "engines_used": engines,
                "sample_output_preview": last_text[:80],
            }

    rss_after = _peak_rss_mb()

    return {
        "profile": spec.name,
        "threads": config.get_asr_threads(),
        "asr_model_configured": config.get_asr_model(),
        "whisper_status": router.whisper.status,
        "indic_status": router.indic.status,
        "silero_vad_status": vad.status,
        "silero_vad_init_ms": vad_init_ms,
        "silero_vad_5s_ms": vad_latency_ms,
        "cold_init_seconds": cold_init_s,
        "audio_seconds": audio_seconds,
        "audio_source": audio_source,
        "peak_rss_before_mb": rss_before,
        "peak_rss_after_mb": rss_after,
        "modes": modes,
        "host": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "python": sys.version.split()[0],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["lightweight", "balanced", "accuracy"], default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    report = profile_current_environment(args.profile)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
