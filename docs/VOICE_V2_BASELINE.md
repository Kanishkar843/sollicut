# SolliCut Voice Intelligence V2 — Baseline Audit

> Generated: 2026-11-27 · Branch: `dharanish-dev` · Commit: `72b6f09`

---

## 1. Test Counts at Baseline

| Suite | Count | Status |
|---|---|---|
| Backend (pytest) | **99 passed** | ✅ Windows local |
| Frontend (Vitest) | **13 passed** | ✅ Windows local |
| Docker container (pytest) | **98 passed, 1 skipped** | ✅ Container verified |

The 1 skipped test is `test_indicconformer_initializes_and_decodes_synthetic_buffer` — it checks the relative path `models/indicconformer-ta` on Windows but the Docker container uses `/models/indicconformer-ta` (absolute). This is a **known, documented skip** and does not indicate a code defect.

---

## 2. Current Architecture (V1 State)

### Backend stack (`backend/app/`)
| File | Role |
|---|---|
| `speech.py` | `DualSpeechRouter` → `IndicConformerTamilEngine` (sherpa-onnx) + `FasterWhisperSpeechEngine` (CTranslate2) |
| `parser.py` | Tamil/Tanglish normalizer, rapidfuzz recovery, `parse_dual_command()` |
| `config.py` | Env-based settings (model dir, threads, device, compute_type) |
| `main.py` | FastAPI, `WS /ws/voice/{project_id}`, `POST /api/projects/{id}/voice-command` |
| `models.py` | `TranscriptResult`, `DualTranscriptResult`, `ParsedCommand` |

### Audio pipeline (V1)
```
Browser mic
  → getUserMedia (channelCount:1, sampleRate:16000, echoCancellation, noiseSuppression)
  → AudioContext (actual OS rate: 44100 or 48000 Hz)
  → pcm-processor.js AudioWorkletProcessor
      · Linear interpolation resampler (source_rate → 16000)
      · 100 ms Int16 chunks → postMessage {pcm, rms}
  → useRecorder.ts
      · RMS gate: speechDetected @ RMS≥0.015, silence endpoint @ RMS<0.006 for 1800 ms
      · Max recording: 30 s
      · WS send: raw Int16 ArrayBuffer chunks
  → WS /ws/voice/{project_id}?mode=tanglish|ta|en (FastAPI)
  → DualSpeechRouter.transcribe() (asyncio.Lock)
  → parse_dual_command()
  → WS reply: {action, params, transcript, secondary_transcript, matched_sources}
```

### ASR models loaded
| Engine | Model | Size | License |
|---|---|---|---|
| `IndicConformerTamilEngine` | `AI4Bharat/indic-conformer-600m-multilingual` Tamil INT8 ONNX | 197 MB | AI4Bharat Open (Apache-2.0 compatible) |
| `FasterWhisperSpeechEngine` | `Systran/faster-whisper-small` CTranslate2 INT8 | 483 MB | MIT |

---

## 3. Identified Weaknesses (against V2 Master Prompt § 4)

### W1 — Linear Interpolation Resampler (No Anti-Aliasing)
- **Location:** `frontend/public/pcm-processor.js` lines 24–34
- **Impact:** Aliasing artefacts on 44.1 kHz → 16 kHz (factor ~2.75×); high-frequency noise from cymbal/HVAC can survive into ASR input
- **V2 target:** Polyphase FIR resampler with Kaiser-windowed filter

### W2 — No Flush Handshake
- **Location:** `useRecorder.ts` `finalizeStop()` → `ws.send({ event:'stop' })`
- **Impact:** Last ~100 ms of audio (partial 100 ms chunk still buffered in `pcm-processor.js`) is silently dropped on recording stop
- **V2 target:** Worklet sends `flush` message, host waits for `flushed` ack before sending `stop`

### W3 — Fixed RMS VAD (No Neural VAD)
- **Location:** `useRecorder.ts` lines 301–309
- **Impact:** RMS gate cannot distinguish real speech from low-energy background hum; aggressive silence endpoint (1800 ms) clips natural pauses
- **V2 target:** Silero VAD ONNX (MIT, public URL, no auth) for per-chunk speech/noise classification

### W4 — No Session IDs or Sequence Tracking
- **Location:** WS protocol in `main.py` and `useRecorder.ts`
- **Impact:** Duplicate command delivery on reconnect; server cannot detect lost chunks; no idempotency
- **V2 target:** `session_id` (UUID) + `seq` counter per chunk; server idempotency table per session

### W5 — Forced English Decoding for Tanglish (Whisper Pass)
- **Location:** `speech.py` `FasterWhisperSpeechEngine.transcribe_sync()` default `language="en"`
- **Impact:** Native Tamil words in Tanglish are transcribed using English phonetics → degraded WER for code-switched sentences
- **V2 target:** Remove forced language; Whisper `small` with `language=None` + Tamil Kili ONNX for V2 upgrade

### W6 — Keyword Regex Parser (No Clause Awareness)
- **Location:** `backend/app/parser.py`
- **Impact:** Multiple trim operations collapse (dict keyed by `op.type`); "trim first clip and last clip" only retains one trim; no sequential command chaining
- **V2 target:** Clause-aware semantic planner with intent segmentation

### W7 — No Transcript Review UI
- **Location:** `frontend/src/VoiceButton.tsx` — applies operations immediately on WS reply
- **Impact:** Misrecognition executes destructive edits without user confirmation
- **V2 target:** Transcript + proposed operations shown; "Apply" required before execution

### W8 — No Human Voice Benchmark
- **Location:** `docs/ASR_BENCHMARK.md`
- **Impact:** All WER/accuracy figures are `NEEDS HUMAN VERIFICATION`; no synthetic speech baselines
- **V2 target:** 100-case evaluation set (TTS synthetic labeled `NOT_HUMAN` for regression)

---

## 4. Models Summary

### Currently loaded (V1)
- `faster-whisper small` (483 MB) — primary English/Tanglish CTranslate2 INT8
- `AI4Bharat IndicConformer Tamil INT8 ONNX` (197 MB) — primary Tamil sherpa-onnx

### V2 candidates under evaluation
- `Tamil Kili` (`shrirajh/parakeet-tamil-kili`) — ONNX parakeet, Tamil/Tanglish native — **status: research required**
- `faster-whisper large-v3-turbo` — Whisper Large V3 Turbo CTranslate2 — **status: research required**
- `Silero VAD` ONNX (MIT) — neural voice activity detection — **status: approved for Phase 3**

### Not selected
- Bodhan Indic-Transcribe — requires separate license evaluation
- BHASHINI hosted adapters — requires credentials
- NeMo full PyTorch models — too large for target hardware

---

## 5. Hardware Context
- **Host:** Intel Core 7 150U Windows laptop
- **Runtime:** Docker Desktop / Linux container (python:3.11-slim-bookworm)
- **Inference:** CPU-only (no CUDA), INT8 quantized models
- **Port:** `SOLLICUT_PORT=8088` (8080 occupied by host process)

---

## 6. Known Skip (Container Test)

```
SKIP tests/backend/test_speech_router.py::test_indicconformer_initializes_and_decodes_synthetic_buffer
Reason: test checks relative path models/indicconformer-ta; container uses /models/indicconformer-ta
```

This will be fixed in V2 Phase 3 when `config.py` is updated to always resolve absolute paths.

---

## 7. Git Log at Baseline

```
72b6f09 docs: update architecture, third-party notices, and benchmark template for dual-ASR
7a69852 feat(ui): add 16kHz AudioWorklet WebSocket streaming and Tanglish/Tamil/English mode selector
df898df feat(api): add 16kHz PCM WebSocket voice stream and mode-aware HTTP fallback
5373d65 feat(nlu): add Tamil cross-script normalizer, rapidfuzz recovery, and dual-pass fusion
bb7df36 feat(asr): implement IndicConformer-TA + faster-whisper small dual speech router
2b3091f chore(asr): add sherpa-onnx, rapidfuzz, and dual-model download config
```

---

## 8. Synthetic Voice & NLU Benchmark (`NOT_HUMAN`)

> Measured: 2026-11-27 via `python -m pytest tests/voice` and `python -m scripts.benchmark_voice --with-asr --max-per-mode 10`.
> **IMPORTANT:** All automated benchmarks below use text fixtures and Windows SAPI en-US TTS synthesis (`NOT_HUMAN`). Native Tamil human microphone recognition remains **`NEEDS HUMAN VERIFICATION`**.

### 8.1 NLU Determinism & Normalization Benchmark (100 Cases, `NOT_HUMAN`)

| Mode | Cases | Passed | Accuracy | Notes |
|---|---:|---:|---:|---|
| `en` (English) | 40 | 40 | **100.0%** | Includes trim, reorder, music, overlay, duration limits, clarification |
| `tanglish` (Code-switched) | 35 | 35 | **100.0%** | Includes Tamil loanword/phonetic variants (`come me`, `panu`, `maathu`, numbers) |
| `ta` (Tamil Unicode) | 25 | 25 | **100.0%** | Includes Tamil numerals, loanwords, festival offers, undo/brightness/clarification |
| **Total** | **100** | **100** | **100.0%** | Fixture: `tests/fixtures/voice_manifest.json` |

### 8.2 ASR Engine WER / CER on Synthetic TTS (`NOT_HUMAN`)

Audio generated in temporary directory via Windows SAPI (`System.Speech.Synthesis`, en-US voice) and discarded immediately after inference.

| Engine | Mode | Samples | Avg WER | Avg CER | Notes |
|---|---|---:|---:|---:|---|
| `faster-whisper` (`small`, INT8) | `en` | 10 | **0.0200 (2.0%)** | 0.0677 | Trailing punctuation accounts for CER delta (`reel.` vs `reel`) |
| `faster-whisper` (`small`, INT8) | `tanglish` | 10 | **0.2383 (23.8%)** | 0.1365 | `tan-001`–`tan-003` achieved 0.00 WER with Tanglish primer; en-US TTS mispronounces isolated Tamil number words |
| `indicconformer-ta` (INT8 ONNX) | `ta` | — | **NEEDS HUMAN VERIFICATION** | **NEEDS HUMAN VERIFICATION** | No Tamil TTS voice installed; requires live Tamil speaker audio |
| `indicconformer-ta` (INT8 ONNX) | `tanglish` | 10 | n/a (Tamil script vs Latin ref) | 1.1593 (cross-script) | Outputs Tamil Unicode transliteration; fused cleanly by `parse_dual_command()` |
| `whisper-large-v3-turbo` (`accuracy`) | All | — | **NEEDS HUMAN VERIFICATION** | **NEEDS HUMAN VERIFICATION** | Model weights (~1.5 GB) not downloaded on local test host |
