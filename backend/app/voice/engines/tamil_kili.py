"""
backend/app/voice/engines/tamil_kili.py — Tamil Kili ONNX engine stub (V2 Phase 4)

Tamil Kili (shrirajh/parakeet-tamil-kili) uses a FastConformer-TDT transducer
architecture with ONNX encoder (~0.9 GB INT8) + NumPy decoder weights (dec.npz).

Integration status: RESEARCH REQUIRED
  - Custom TDT inference script needed (not standard sherpa-onnx / ONNX RT call)
  - Encoder: onnx/encoder_int8.onnx (0.9 GB)
  - Decoder: onnx/dec.npz (NumPy weights for joint network)
  - Tokenizer: SentencePiece model

This stub logs the unavailability and signals the router to fall back to V1.
Full implementation will follow in a dedicated sprint.

License: Apache-2.0 (parakeet-tdt-0.6b-v2 base + Tamil Kili fine-tune)
"""
from __future__ import annotations

import logging

logger = logging.getLogger("sollicut.voice.engines.tamil_kili")


class TamilKiliEngine:
    """
    Placeholder for Tamil Kili ONNX engine.
    Always returns status='unavailable' — triggers adaptive router fallback to V1.
    """

    def __init__(self):
        self.status = "unavailable"
        self.error = (
            "Tamil Kili ONNX engine requires custom TDT transducer inference "
            "(FastConformer encoder + dec.npz joint weights). "
            "Full integration planned for V2.1. "
            "Current active engine: IndicConformer-TA + faster-whisper (V1)."
        )

    def initialize(self) -> None:
        logger.info(
            "Tamil Kili ONNX: %s",
            "integration pending — using V1 IndicConformer-TA as primary Tamil engine."
        )

    async def transcribe(self, audio_input, language_hint=None):
        raise RuntimeError(self.error)
