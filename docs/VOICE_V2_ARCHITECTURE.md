# SolliCut Voice Intelligence V2 — Target Architecture

> Branch: `dharanish-dev` · V2 design target (not yet fully implemented)

---

## Layer 0 — Hardware & Runtime

```
Intel Core 7 150U (12 logical cores, AVX2)
  └── Docker Desktop → python:3.11-slim-bookworm
        CPU-only INT8 quantized inference
        SOLLICUT_PORT=8088
```

---

## Layer 1 — Browser Audio Capture

```
navigator.mediaDevices.getUserMedia({
  audio: { channelCount:1, echoCancellation, noiseSuppression, autoGainControl }
})
  → AudioContext (OS sample rate: 44100 / 48000 / 16000 Hz)
  → pcm-processor.js (AudioWorkletProcessor)
      ┌─────────────────────────────────────────────┐
      │  FIR Polyphase Resampler (Kaiser window)    │
      │  Handles: 44100→16000, 48000→16000, 1:1    │
      │  No aliasing artefacts                      │
      │  Flush state: buffers last partial chunk    │
      │  Diagnostics: input_rate, rms, peak,        │
      │               clip_ratio, flush_samples     │
      └─────────────────────────────────────────────┘
      → {pcm:Int16Array, rms, peak, clip_ratio, is_flush} postMessage
```

### V2 Lifecycle States (useRecorder.ts)
```
IDLE → INITIALIZING → RECORDING → STOPPING → FLUSHING → PROCESSING
                                                       → COMPLETED | FAILED | CANCELLED
```

---

## Layer 2 — WebSocket Transport (Reliable)

```
useRecorder.ts
  → Generates session_id (UUID v4) per recording session
  → Each PCM chunk: {seq: N, pcm: ArrayBuffer} binary frame
  → Control messages: JSON {event: 'stop'|'cancel'|'flush_ack'}
  → Backpressure: checks ws.bufferedAmount before sending

Backend main.py WS /ws/voice/{project_id}?mode=tanglish|ta|en
  → Validates session_id present
  → Idempotency: reject duplicate command_id
  → Bounded timeout: 35 s max session
  → Malformed control message → structured error response
```

---

## Layer 3 — Voice Activity Detection (Silero VAD)

```
backend/app/voice/vad.py
  ┌────────────────────────────────────────────────────────┐
  │  SileroVAD (MIT, ONNX, no auth required)              │
  │  Input: 16 kHz float32 chunks (512 samples / 32 ms)   │
  │  Output: speech_prob per chunk                         │
  │  Threshold: speech ≥ 0.5, silence < 0.35             │
  │  Min speech duration: 300 ms                          │
  │  Max pause: 500 ms (before segment close)             │
  │  Fallback: RMS gate if VAD model unavailable          │
  └────────────────────────────────────────────────────────┘

backend/app/voice/audio_quality.py
  · Clipping detection (|sample| ≥ 0.99 for >0.5% of frames)
  · Empty recording rejection (< 0.3 s of speech segments)
  · Noise floor estimation
```

---

## Layer 4 — ASR Engine Layer (V2)

```
backend/app/voice/engines/base.py         ASREngine Protocol
backend/app/voice/engines/legacy.py       V1 engines (rollback)
backend/app/voice/engines/tamil_kili.py   Tamil Kili ONNX (parakeet architecture)
backend/app/voice/engines/whisper_turbo.py  Whisper Large V3 Turbo (faster-whisper)

backend/app/voice/router.py               Adaptive Router V2
  ┌────────────────────────────────────────────────────────────┐
  │  mode=tanglish:                                           │
  │    Pass A: Tamil Kili ONNX (Tamil+Tanglish native)       │
  │    Pass B: Whisper Large V3 Turbo (multilingual, no lang) │
  │                                                           │
  │  mode=ta:                                                 │
  │    Pass A: Tamil Kili ONNX only                          │
  │    Fallback: IndicConformer-TA (legacy)                   │
  │                                                           │
  │  mode=en:                                                 │
  │    Whisper Large V3 Turbo, language=en                    │
  │    Fallback: Whisper small (legacy)                       │
  │                                                           │
  │  Conditional fallback: if primary unavailable → legacy    │
  │  CPU serialization: single asyncio.Lock per engine        │
  └────────────────────────────────────────────────────────────┘
```

> [!NOTE] V2 removes forced `language="en"` for Tanglish mode; Tamil Kili handles code-switching natively.

---

## Layer 5 — Multilingual Normalization (V2)

```
backend/app/understanding/normalizer.py      (extracted from parser.py)
  · Unicode NFC normalization
  · Tamil loanword map (photos/reel/music/offer/zoom/etc.)
  · Tanglish phonetic replacement map
  · rapidfuzz recovery (ratio ≥ 82, unquoted Latin only)
  · Decimal number handling ("2.5 seconds" → 2.5)
  · Tamil suffix stripping (-ஐ, -ல, -னு)
  · Protected promotional content (quoted strings, brand names)
  · Ambiguity preservation → clarification request (not guess)

backend/app/understanding/number_parser.py
  · Tamil number words → int/float
  · Mixed Tamil/English number expressions
```

---

## Layer 6 — Semantic Command Planner (V2)

```
backend/app/understanding/clause_parser.py
  · Splits on conjunctions: "and", "then", "also", "பின்னர்", "மேலும்"
  · Preserves quoted overlay text across clause boundaries

backend/app/understanding/intent_parser.py
  · Per-clause intent classification
  · Ambiguity score: when score < threshold → clarification

backend/app/understanding/operation_planner.py
  · Maps intent → typed Pydantic operation
  · Handles multiple trim ops on different clips (not dict-collapsing)
  · Sequential chaining: [trim, zoom, overlay, music]
  · Unknown intent → asks for clarification instead of guessing
```

---

## Layer 7 — Context Manager + Validation (V2)

```
backend/app/understanding/context_manager.py
  · Tracks last N commands per project session
  · Resolves pronouns: "it", "that clip", "the last one"
  · Handles "undo last" relative to context

backend/app/understanding/validator.py
  · Typed Pydantic schemas per operation type
  · Out-of-range value detection (trim > clip duration)
  · Returns structured {valid, errors[], warnings[]} 
```

---

## Layer 8 — Voice Director UX (V2 Frontend)

```
frontend/src/components/voice/
  TranscriptReview.tsx      Shows transcript + proposed ops; requires "Apply"
  OperationPreview.tsx      Visual diff of what will change
  Clarification.tsx         Renders server clarification requests
  MicrophoneSettings.tsx    Device selector, gain test, permission status

VoiceButton.tsx
  Lifecycle label: IDLE | INITIALIZING | RECORDING | STOPPING | FLUSHING | PROCESSING
  Confidence indicator per operation
  "Apply all" / "Edit" / "Cancel" buttons
```

> [!IMPORTANT] V2 does NOT apply edits on WS reply. All edits require explicit "Apply" confirmation.

---

## Layer 9 — CPU Deployment Profiles (V2)

| Profile | ASR | VAD | Resampler | Use case |
|---|---|---|---|---|
| `lightweight` | Whisper small + IndicConformer-TA (V1) | RMS gate | Linear interp | <4 GB RAM, slow CPU |
| `balanced` | Tamil Kili + Whisper small | Silero VAD | FIR polyphase | 4–8 GB, typical laptop |
| `accuracy` | Tamil Kili + Whisper LV3 Turbo | Silero VAD | FIR polyphase | 8+ GB, 8+ cores |

Controlled via `SOLLICUT_PROFILE=lightweight|balanced|accuracy` env var.

---

## Invariants (Must Never Break)

1. `docker compose up --build` succeeds with empty `.env` and no API keys
2. All audio streams discarded from memory/disk after transcription
3. `SOLLICUT_PORT=8088` Docker port compatibility
4. Tamil Pillow/libraqm font shaping unmodified
5. Undo stack, revision history, 14 edit operations preserved
6. Optional Gemini ad feature gated behind `GEMINI_API_KEY`
7. No model weights committed to git
8. No force-push, no push to main
