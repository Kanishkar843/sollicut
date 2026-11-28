# SolliCut Voice Intelligence V2 — What Changed

> **Branch:** `dharanish-dev` (`https://github.com/Kanishkar843/sollicut.git`)  
> **Baseline (V1):** `72b6f09` → **Latest V2 HEAD:** `4b2ebda` (12 commits across Phases 0–11 + audio resampler fix)  
> **Scope:** Upgrades the entire voice capture, transport, VAD, ASR engine abstraction, multilingual NLU, review UI, deployment profiles, CPU profiling, benchmarking, and E2E test suite while keeping the stack **100% local and keyless** (no required API keys or Hugging Face tokens).

---

## Quick Comparison: V1 vs V2

| Area | V1 (`72b6f09`) | V2 (`4b2ebda`) |
|---|---|---|
| **Browser Resampler** | Basic linear interpolation | Kaiser-windowed FIR polyphase (`L:M`), adaptive profile switching (`linear` / `fir_kaiser`), fixed 44.1/48 kHz state ring, flush handshake |
| **Recording Lifecycle** | `idle / recording / processing` | 9 explicit states (`idle`, `initializing`, `recording`, `stopping`, `flushing`, `processing`, `completed`, `failed`, `cancelled`), `AudioContext.resume()`, mic `deviceId` support |
| **WebSocket Transport** | Raw audio + stop/cancel | `session_id` UUID, `command_id` idempotency, bounded `37 s` timeout, structured malformed/unknown JSON errors, optional `auto_apply=false` / `preview=true` |
| **Speech Gating (VAD)** | Simple RMS energy threshold | Silero VAD v5 ONNX (`silero_vad.onnx`, MIT) + audio quality report (clipping, too-short, noise floor) + automatic RMS fallback |
| **ASR Architecture** | Concrete `DualSpeechRouter` only | `ASREngine` Protocol, `WhisperTurboEngine` (`language=None` for Tanglish), `TamilKiliEngine` TDT stub, `upgrade_router()` with `small` fallback |
| **Language & Command NLU** | Single regex parser (multi-trim dict collapse, integer numbers) | Modular `backend/app/understanding/`: `normalizer.py` (decimals, Tamil suffixes, protected quotes/prices), `number_parser.py`, `clause_parser.py`, `intent_parser.py`, multi-op `operation_planner.py`, `context_manager.py`, `validator.py` |
| **Voice Director UX** | Immediate server execution on WS reply | **Deferred review & apply:** `TranscriptReview`, `OperationPreview`, `Clarification`, `MicrophoneSettings`, plus inline **Edit** before clicking **Apply** |
| **Deployment Profiles** | Fixed single config | `SOLLICUT_PROFILE=lightweight \| balanced \| accuracy` controlling ASR model, Silero VAD vs RMS, threads, and browser resampler |
| **Profiling & Benchmarks** | None / manual notes only | Real CPU profiler (`scripts/profile_voice.py`, `docs/CPU_PROFILE.md`) + 100-case `NOT_HUMAN` manifest (`tests/fixtures/voice_manifest.json`) & WER/CER/NLU script (`scripts/benchmark_voice.py`) |
| **Automated Test Coverage** | 99 backend + 13 frontend | **220 Python tests** (`tests/backend/` + `tests/voice/`, including 7 E2E workflow tests A–H) + **20 Vitest frontend tests** |

---

## Detailed Updates by Commit & Module

### 1. Baseline Audit & Architecture Specs (`f41bc1d` — Phase 0)
- Audited V1 weaknesses (W1–W8) and documented target architecture and phase gates in:
  - [`docs/VOICE_V2_BASELINE.md`](docs/VOICE_V2_BASELINE.md)
  - [`docs/VOICE_V2_ARCHITECTURE.md`](docs/VOICE_V2_ARCHITECTURE.md)
  - [`docs/VOICE_V2_PROGRESS.md`](docs/VOICE_V2_PROGRESS.md)
  - [`docs/ASR_BENCHMARK.md`](docs/ASR_BENCHMARK.md)

### 2. Anti-Aliased Browser Audio & Flush Handshake (`108b6da` — Phase 1 + `4b2ebda` Hotfix)
- **[`frontend/public/pcm-processor.js`](frontend/public/pcm-processor.js):**
  - Replaced plain linear interpolation with a Kaiser-windowed sinc (`β = 5.65`) rational polyphase FIR resampler (`16 kHz` passthrough, `44.1 kHz → 16 kHz` `160:441`, `48 kHz → 16 kHz` `1:3`, plus safe linear fallback when `L > 320`).
  - Added per-phase DC unity gain normalization in `buildPolyphaseBank`.
  - Added `{ type: 'flush' }` → drains partial tail chunk (`is_flush: true`) → `{ type: 'flushed', seq }` handshake so tail words are never truncated.
  - Emits per-chunk `rms`, `peak`, `clip_ratio`, `seq`, `input_rate`.
  - **Hotfix (`4b2ebda`):** Fixed an off-by-one bug (`new Float64Array(P - 1)` with `state[P - 1] = channel[i]`) that produced `NaN → 0` silent PCM at `44.1 kHz` / `48 kHz` browser rates; allocated `new Float64Array(P)` with proper causal sample shifting and verified non-zero RMS amplitude and exact sample counts across `16000`, `44100`, and `48000 Hz`.
- **[`frontend/src/hooks/useRecorder.ts`](frontend/src/hooks/useRecorder.ts) & [`frontend/src/VoiceButton.tsx`](frontend/src/VoiceButton.tsx):**
  - Added `RecorderState` lifecycle state machine with `1500 ms` flush-ACK timeout guard and clear UI hints/labels (`STATE_LABEL`, `STATE_HINT`).
  - Calls `audioCtx.resume()` if suspended, removes rigid `sampleRate: 16000` `getUserMedia` constraint, forwards selected microphone `deviceId`, and uses `/pcm-processor.js?v=2` to bypass stale browser cache.

### 3. Reliable WebSocket Voice Transport (`23d68a4` — Phase 2)
- **[`backend/app/main.py`](backend/app/main.py), [`frontend/src/api.ts`](frontend/src/api.ts):**
  - Added `session_id` query param (`crypto.randomUUID()` per recording session) and `command_id` per `stop`/`cancel` control frame (`_ws_seen_commands` idempotency guard).
  - Enforced bounded `37 s` WebSocket session timeout (`WS_SESSION_TIMEOUT_SECONDS`).
  - Non-JSON or invalid control frames return structured `{ "error": ... }` responses instead of crashing/dropping the socket.
  - Echoes `session_id` and `command_id` in server responses; added `voice_ws` PCM duration/RMS telemetry logs (`4b2ebda`, no audio written to disk).
- **Tests:** Expanded [`tests/backend/test_voice_ws.py`](tests/backend/test_voice_ws.py).

### 4. Silero Neural VAD & Audio Quality Assessment (`8cce2c1` — Phase 3)
- **[`backend/app/voice/vad.py`](backend/app/voice/vad.py):** Added `SileroVAD` ONNX v5 wrapper (`SPEECH_THRESHOLD = 0.5`, `SILENCE_THRESHOLD = 0.35`, hysteresis segmentation, `filter_speech_only()`, and automatic RMS fallback when `silero_vad.onnx` is unavailable or fails).
- **[`backend/app/voice/audio_quality.py`](backend/app/voice/audio_quality.py):** Added `assess()` returning `AudioQualityReport` (clipping detection `> 0.5%` samples at `|x| >= 0.99`, too-short `< 0.3 s`, empty buffer detection, 90th-percentile frame noise floor).
- **[`scripts/download_model.py`](scripts/download_model.py):** Added keyless download for public MIT `silero_vad.onnx` (`2.2 MB`).
- **Tests:** Added 16 unit tests in [`tests/backend/test_vad.py`](tests/backend/test_vad.py).

### 5. Modular ASR Engine Layer (`5599761` — Phase 4)
- **[`backend/app/voice/engines/base.py`](backend/app/voice/engines/base.py):** Defined `@runtime_checkable` `ASREngine` Protocol.
- **[`backend/app/voice/engines/legacy.py`](backend/app/voice/engines/legacy.py):** Wrapped V1 `FasterWhisperSpeechEngine` and `IndicConformerTamilEngine`.
- **[`backend/app/voice/engines/whisper_turbo.py`](backend/app/voice/engines/whisper_turbo.py):** Added `WhisperTurboEngine` (`large-v3-turbo` via CTranslate2 INT8) with `language=None` for `tanglish` mode (fixing V1's forced `"en"` bias when large turbo is enabled).
- **[`backend/app/voice/engines/tamil_kili.py`](backend/app/voice/engines/tamil_kili.py):** Documented `TamilKiliEngine` TDT transducer stub (`status = "unavailable"`, triggering automatic fallback to IndicConformer-TA).
- **[`backend/app/voice/router.py`](backend/app/voice/router.py):** Added `upgrade_router(router)` to swap engines dynamically when V2 models are present.
- **Tests:** Added 9 tests in [`tests/backend/test_asr_engines.py`](tests/backend/test_asr_engines.py).

### 6. V2 Multilingual Normalization, Planning, Context & Validation (`8ea3082` — Phases 5–7)
Built a modular V2 understanding package under [`backend/app/understanding/`](backend/app/understanding/):
- **[`number_parser.py`](backend/app/understanding/number_parser.py):** Parses decimals (`"2.5"`), English words/ordinals, Tanglish numbers (`anju`, `pathu`), and Tamil Unicode numerals (`ஐந்து`, `பத்து`, `இருபது`).
- **[`normalizer.py`](backend/app/understanding/normalizer.py):** 7-step `normalize_v2()` pipeline with Unicode NFC, masked protected spans (quoted overlay text, prices `Rs./₹`, decimals, percentages), extended Tamil loanword map, Tamil suffix stripping (`-ஐ`, `-ல`, `-னு`, `-ஓட`, `-கிட்ட`, etc.), Tanglish phonetic cleanup, and `detect_ambiguity()`.
- **[`clause_parser.py`](backend/app/understanding/clause_parser.py):** `split_into_clauses()` splits chained commands on English/Tamil/Tanglish conjunctions (`and`, `then`, `also`, `மேலும்`, `பின்னர்`, `approm`) without breaking inside quoted text.
- **[`intent_parser.py`](backend/app/understanding/intent_parser.py):** Per-clause classification (`classify_clause()`) across 17 edit patterns with confidence scores.
- **[`operation_planner.py`](backend/app/understanding/operation_planner.py):** `plan_operations()` generates ordered operation dicts with unique UUIDs — fixing V1 dict-collapsing so multi-clip commands like `"trim first clip and trim last clip"` emit two separate `trim_clip` ops.
- **[`context_manager.py`](backend/app/understanding/context_manager.py):** `VoiceContextManager` tracks up to 10 recent commands per project in memory (never written to disk) and resolves pronouns (`it`, `that`, `this`, `அது`, `அந்த`) to prior clips (`get_context()`, `clear_context()`).
- **[`validator.py`](backend/app/understanding/validator.py):** Pre-execution operation validator checking clip index bounds, trim end > clip duration, non-positive durations, brightness bounds, and music volume directions (`ValidationResult`).
- **Tests:** Added 35 tests in [`tests/backend/test_understanding.py`](tests/backend/test_understanding.py) and 28 tests in [`tests/backend/test_context_validator.py`](tests/backend/test_context_validator.py).

### 7. Voice Director Deferred-Apply UX (`402b3fe` — Phase 8)
- **Backend preview & apply flow ([`main.py`](backend/app/main.py), [`models.py`](backend/app/models.py)):**
  - `/ws/voice/{project_id}` (`auto_apply=false` or `{"event":"stop","preview":true}`) and `POST /api/projects/{project_id}/voice-command` (`auto_apply=false`) now return parsed operations without modifying project state or enqueuing FFmpeg render jobs.
  - Extended `ApplyRequest` / `POST /api/projects/{project_id}/apply` with optional `secondary_transcript` and `asr_mode` so Tanglish dual-pass fused operations execute cleanly after user confirmation (or re-parse if the transcript was edited).
- **Frontend review components ([`frontend/src/components/voice/`](frontend/src/components/voice/)):**
  - [`TranscriptReview.tsx`](frontend/src/components/voice/TranscriptReview.tsx): Shows transcript, optional dual-ASR Tamil pass, engine badges, and **Cancel / Edit / Apply** actions (with inline textarea editing).
  - [`OperationPreview.tsx`](frontend/src/components/voice/OperationPreview.tsx): Renders proposed operations and matched engine provenance badges.
  - [`Clarification.tsx`](frontend/src/components/voice/Clarification.tsx): Displays server `clarification_question` and hides Apply when input is ambiguous.
  - [`MicrophoneSettings.tsx`](frontend/src/components/voice/MicrophoneSettings.tsx): Safe permission indicator + `enumerateDevices()` audio input selector wired to `App.tsx` / `VoiceButton.tsx`.
- **Tests:** Added deferred-Apply, inline edit, Cancel, Clarification, MicSettings, and backend preview-to-apply tests in [`frontend/src/App.test.tsx`](frontend/src/App.test.tsx) and [`tests/backend/test_voice_ws.py`](tests/backend/test_voice_ws.py).

### 8. CPU Deployment Profiles & Hardware Profiling (`feb2ac5` — Phase 9)
- **[`backend/app/config.py`](backend/app/config.py), [`backend/app/speech.py`](backend/app/speech.py), [`.env.example`](.env.example), [`Dockerfile`](Dockerfile), [`docker-compose.yml`](docker-compose.yml):**
  - Added `SOLLICUT_PROFILE`:
    - `lightweight`: Whisper `small`, IndicConformer-TA, RMS gate, `linear` browser resampler, `2` threads.
    - `balanced` *(default)*: Whisper `small`, IndicConformer-TA, Silero VAD v5 ONNX, `fir_kaiser` browser resampler, `4` threads.
    - `accuracy`: Attempts `large-v3-turbo` via `upgrade_router()` (with graceful fallback to `small` if missing locally), Silero VAD v5 ONNX, `fir_kaiser` resampler, `4` threads.
  - Wired `SileroVAD` initialization & speech filtering into `DualSpeechRouter`, `assess_audio_quality()` warnings into WS/HTTP voice responses, `VoiceContextManager` into `dispatch()` & project deletion, and `voice_profile` metadata into `/api/capabilities`.
- **[`scripts/profile_voice.py`](scripts/profile_voice.py) & [`docs/CPU_PROFILE.md`](docs/CPU_PROFILE.md):** Measured cold init, Silero VAD latency, real Peak RSS (`K32GetProcessMemoryInfo`), and warm RTF on `5.094 s` synthesized speech (`NOT_HUMAN`).
- **Tests:** Added 8 tests in [`tests/backend/test_profiles.py`](tests/backend/test_profiles.py).

### 9. 100-Case Benchmark Framework (`ebc87a2` — Phase 10)
- Added [`tests/fixtures/voice_manifest.json`](tests/fixtures/voice_manifest.json) (100 evaluation cases: `40 en`, `35 tanglish`, `25 ta`, all tagged `source: "NOT_HUMAN"`).
- Added [`scripts/benchmark_voice.py`](scripts/benchmark_voice.py) (Levenshtein WER/CER per engine per mode + 100-case NLU scoring + optional batch Windows SAPI TTS evaluation) and [`tests/voice/test_voice_benchmark.py`](tests/voice/test_voice_benchmark.py).
- Recorded observed results in [`docs/VOICE_V2_BASELINE.md`](docs/VOICE_V2_BASELINE.md) § 8 (**100/100 NLU**, synthetic en-US SAPI TTS WER `0.0200` English / `0.2383` Tanglish).

### 10. End-to-End Regression Suite & Final Report (`1591c36` — Phase 11)
- Added 7 end-to-end workflow tests covering Workflows A–H in [`tests/backend/test_workflows_e2e.py`](tests/backend/test_workflows_e2e.py): multi-photo create + render (`ffprobe`), follow-up edits + byte-exact undo + download, Tamil `libraqm` shaping, mixed-media trim + cover fit, WS preview + `/apply` with empty audio dir, asset reorder + undo, clarification safety, and `GEMINI_API_KEY` gating + project cleanup.
- Updated [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) with Silero VAD (MIT) and compiled [`docs/VOICE_V2_FINAL_REPORT.md`](docs/VOICE_V2_FINAL_REPORT.md).

---

## Verification Snapshot

| Check | Outcome | Reference Commit |
|---|---|---|
| Local Python Suite (`pytest tests/`) | **220 passed** (`0 skipped`, `52.75 s`) | `1591c36` |
| Frontend Suite (`vitest run`) | **20 passed** (including `pcm-processor.js` 44.1/48 kHz worklet test) | `4b2ebda` |
| Frontend Build (`tsc -b && vite build`) | Clean (`307.13 kB` JS bundle, `710 ms`) | `4b2ebda` |
| Targeted WS & Voice Tests after fix (`pytest tests/backend/test_voice_ws.py tests/voice/`) | **11 passed** (`20.94 s`) | `4b2ebda` |
| Docker Container Tests & FFmpeg Smoke (`SOLLICUT_PORT=8088`, empty `.env`) | **219 passed, 1 skipped** (known relative path skip) + smoke **PASS** (`7.571 s` / `7.054 s`) | `1591c36` |
| Live 48 kHz SAPI → served `pcm-processor.js` → `ws://127.0.0.1:8088` E2E | Returned transcript `"Create a 15 seconds reel with smooth zoom and background music."` (`dual-asr` + `silero`) | `4b2ebda` |
| Clean Remote Clone (`dharanish-dev`) | Verified **85 passed** (`8.45 s`) on V2 unit/benchmark suites | `1591c36` |

### Items Marked `NEEDS HUMAN VERIFICATION`
- Live human microphone speech recognition in Tamil and code-switched Tanglish across accents (`docs/ASR_BENCHMARK.md`).
- `SOLLICUT_PROFILE=accuracy` CPU runtime/WER benchmarks with downloaded `whisper-large-v3-turbo` weights (`~1.5 GB`).
- Live cloud video generation with a configured `GEMINI_API_KEY`.
