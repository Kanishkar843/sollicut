"""
backend/app/voice/engines/legacy.py — V1 engine wrappers (V2 Phase 4)

Re-exports the existing V1 engines so the adaptive router can use them
as a rollback target. No logic changes — purely proxy imports.
"""
from __future__ import annotations

from ...speech import FasterWhisperSpeechEngine, IndicConformerTamilEngine  # noqa: F401

__all__ = ["FasterWhisperSpeechEngine", "IndicConformerTamilEngine"]
