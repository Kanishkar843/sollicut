"""
backend/app/voice/engines/base.py — ASR Engine Protocol (V2 Phase 4)

Defines the typed interface that all ASR engines must satisfy.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

from ...models import TranscriptResult


@runtime_checkable
class ASREngine(Protocol):
    """Minimal interface every ASR engine must implement."""

    status: str
    error: str | None

    def initialize(self) -> None:
        """Load models. Called once at startup; must not raise."""
        ...

    async def transcribe(
        self,
        audio_input: Path | np.ndarray,
        language_hint: str | None = None,
    ) -> TranscriptResult:
        """Transcribe audio. Raises ValueError for empty/short audio."""
        ...
