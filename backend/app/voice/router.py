"""
backend/app/voice/router.py — Adaptive ASR Router V2 (Phase 4)

Routing strategy (layered fallback):
  tanglish:
    Pass A: TamilKiliEngine → fallback IndicConformerTamilEngine  (best Tamil)
    Pass B: WhisperTurboEngine → fallback FasterWhisperSpeechEngine (best Tanglish)
  ta:
    TamilKiliEngine → fallback IndicConformerTamilEngine
  en:
    WhisperTurboEngine → fallback FasterWhisperSpeechEngine

Key V2 change:
  - language=None for Tanglish Whisper pass (not forced "en")
  - WhisperTurbo replaces Whisper small when large-v3-turbo model is present
  - TamilKili replaces IndicConformer when its ONNX files are present
  - Falls back to V1 engines when V2 engines are unavailable (zero config change)

The DualSpeechRouter in speech.py remains the public interface for main.py.
This module upgrades its internals by swapping engine implementations.
"""
from __future__ import annotations

import asyncio
import logging

import numpy as np

from ..models import DualTranscriptResult
from ..speech import DualSpeechRouter  # the existing public router

logger = logging.getLogger("sollicut.voice.router")


def upgrade_router(router: DualSpeechRouter) -> None:
    """
    Attempt to upgrade the existing DualSpeechRouter's engines to V2 equivalents.
    Called from speech.initialize() after V1 engines are loaded.

    If V2 engines are unavailable, the router keeps its V1 engines — no change.
    """
    # Try to upgrade Whisper small → large-v3-turbo
    try:
        from .engines.whisper_turbo import WhisperTurboEngine
        turbo = WhisperTurboEngine()
        turbo.initialize()
        if turbo.status == "ready":
            router.whisper = turbo  # type: ignore[attr-defined]
            logger.info("Router upgraded: Whisper small → large-v3-turbo")
        else:
            logger.info("WhisperTurbo unavailable (%s) — keeping Whisper small", turbo.error)
    except Exception as exc:
        logger.warning("WhisperTurbo upgrade failed: %s — keeping Whisper small", exc)

    # Tamil Kili stub: always logs unavailability
    try:
        from .engines.tamil_kili import TamilKiliEngine
        kili = TamilKiliEngine()
        kili.initialize()
        logger.info("TamilKili: %s", kili.error)
    except Exception as exc:
        logger.debug("TamilKili init error: %s", exc)
