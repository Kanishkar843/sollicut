"""
audio_quality.py — Audio quality assessment (V2 Phase 3)

Checks for:
  - Clipping (|sample| >= 0.99 for > 0.5% of frames)
  - Empty / too-short recording
  - Noise floor estimation (90th-percentile frame RMS)

All checks return an AudioQualityReport — no exceptions raised.
The caller (speech router) decides whether to reject or warn.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field

CLIP_THRESHOLD = 0.99
MAX_CLIP_RATIO = 0.005      # 0.5 % of samples clipping → flag
MIN_DURATION_S = 0.3
SAMPLE_RATE = 16000
FRAME_SIZE = 160            # 10 ms at 16 kHz — for noise floor estimation


@dataclass
class AudioQualityReport:
    duration_seconds: float
    rms: float
    peak: float
    clip_ratio: float       # fraction of samples with |x| >= CLIP_THRESHOLD
    noise_floor: float      # 90th-percentile 10ms frame RMS
    is_clipping: bool
    is_empty: bool
    is_too_short: bool
    warnings: list[str] = field(default_factory=list)

    @property
    def is_acceptable(self) -> bool:
        return not self.is_empty and not self.is_too_short


def assess(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> AudioQualityReport:
    """Assess audio quality. samples must be float32, range [-1, 1]."""
    arr = np.asarray(samples, dtype=np.float32).reshape(-1)
    n = len(arr)

    duration = n / sample_rate
    rms = float(np.sqrt(np.mean(np.square(arr, dtype=np.float64)))) if n > 0 else 0.0
    peak = float(np.max(np.abs(arr))) if n > 0 else 0.0
    clip_count = int(np.sum(np.abs(arr) >= CLIP_THRESHOLD))
    clip_ratio = clip_count / max(1, n)

    # Noise floor: 90th-percentile frame RMS over 10ms windows
    noise_floor = 0.0
    if n >= FRAME_SIZE:
        num_frames = n // FRAME_SIZE
        frames = arr[: num_frames * FRAME_SIZE].reshape(num_frames, FRAME_SIZE)
        frame_rms = np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1))
        noise_floor = float(np.percentile(frame_rms, 90))

    is_clipping = clip_ratio > MAX_CLIP_RATIO
    is_too_short = duration < MIN_DURATION_S
    is_empty = rms < 1e-6

    warnings: list[str] = []
    if is_clipping:
        warnings.append(
            f"Audio clipping detected ({clip_ratio:.1%} of samples). "
            "Move the microphone further away or reduce system input gain."
        )
    if is_too_short:
        warnings.append(
            f"Recording is very short ({duration:.2f}s). "
            "Please speak for at least 0.3 seconds."
        )
    if is_empty:
        warnings.append("Recording appears to be silent. Check microphone connection.")

    return AudioQualityReport(
        duration_seconds=duration,
        rms=rms,
        peak=peak,
        clip_ratio=clip_ratio,
        noise_floor=noise_floor,
        is_clipping=is_clipping,
        is_empty=is_empty,
        is_too_short=is_too_short,
        warnings=warnings,
    )
