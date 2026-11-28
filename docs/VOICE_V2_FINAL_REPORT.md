# SolliCut Voice Intelligence V2 — Final Engineering Report

> Branch: `dharanish-dev` · Remote: `https://github.com/Kanishkar843/sollicut.git` · Date: 2026-11-28

---

## 1. Executive Summary

SolliCut Voice Intelligence V2 upgrades the voice-first Tamil/Tanglish/English promotional video editor across **11 incremental phases** on branch `dharanish-dev` while preserving all core invariants: **100% keyless local operation** (zero mandatory API keys or Hugging Face tokens), zero on-disk persistence of user audio, FFmpeg `libx264`/`aac` rendering, Pillow/`libraqm` Tamil text shaping, non-destructive undo snapshots, and optional Gemini ad generation strictly gated behind `GEMINI_API_KEY`.

- **Project source lines (`scripts/count_project_code.py`):** `10,575` nonblank lines
- **Local Python test suite (`pytest tests/`):** **220 passed** (`0 skipped`) in `52.75 s`
- **Frontend suite (`vitest run`):** **19 passed** (`tsc -b && vite build` clean, `306.99 kB` JS gzip `96.43 kB`)
- **Docker Compose (`SOLLICUT_PORT=8088`, empty `.env`):** **219 passed, 1 skipped** (known relative `models/` path skip in `test_speech_router.py`), FFmpeg smoke test passed (`initial_render_seconds: 7.571 s`, `followup_render_seconds: 7.054 s`), live `/api/capabilities` reported `dual-asr`, `indicconformer_ta: true`, `faster_whisper_small: true`, `vad: silero`, `resampler: fir_kaiser`.

---

## 2. Phase & Commit History (`dharanish-dev`)

| Phase | Deliverable | Commit SHA |
|---|---|---|
| **P0** | Baseline audit, V2 architecture & progress tracker | `f41bc1d` |
| **P1** | Kaiser-windowed FIR polyphase AudioWorklet resampler + flush handshake (`pcm-processor.js`, `useRecorder.ts`, `VoiceButton.tsx`) | `108b6da` |
| **P2** | Reliable WebSocket transport (`session_id`, `command_id` idempotency, bounded `37 s` session timeout, structured malformed-frame errors) | `23d68a4` |
| **P3** | Silero VAD v5 ONNX wrapper + RMS gate fallback + audio quality inspection (`vad.py`, `audio_quality.py`, `download_model.py`) | `8cce2c1` |
| **P4** | ASR engine abstraction (`ASREngine` Protocol), `WhisperTurboEngine` (`language=None` for Tanglish), `TamilKiliEngine` stub, adaptive router | `5599761` |
| **P5–P7** | V2 understanding layer: `normalizer.py`, `number_parser.py`, `clause_parser.py`, `intent_parser.py`, multi-trim-safe `operation_planner.py`, `context_manager.py`, `validator.py` | `8ea3082` |
| **P8** | Voice Director review UX: deferred Apply (`auto_apply=false`/`preview=true` + `POST /apply`), inline transcript editing, `TranscriptReview`, `OperationPreview`, `Clarification`, `MicrophoneSettings` | `402b3fe` |
| **P9** | Deployment profiles (`SOLLICUT_PROFILE=lightweight\|balanced\|accuracy`), linear vs FIR AudioWorklet config, Silero VAD + context wiring, CPU profiler (`scripts/profile_voice.py`, `docs/CPU_PROFILE.md`) | `feb2ac5` |
| **P10** | 100-case synthetic manifest (`tests/fixtures/voice_manifest.json`), `scripts/benchmark_voice.py`, WER/CER/NLU baseline § 8 | `ebc87a2` |
| **P11** | 8 End-to-End workflow regression tests (`tests/backend/test_workflows_e2e.py`), notices (`THIRD_PARTY_NOTICES.md`), clean checkout + Docker verification, final report | (Phase 11 HEAD) |

---

## 3. Verification Matrix (Observed Outputs)

### 3.1 Automated Suites
| Check | Environment | Result | Notes |
|---|---|---|---|
| `python -m pytest tests/ -q` | Windows 11 (Python 3.14) | **220 passed** (`52.75 s`) | Includes all 7 E2E workflow tests (Workflows A–H), 35 V2 NLU tests, 10 context/validator tests, 8 profile tests, 16 VAD tests, 9 ASR engine tests, 100-case benchmark suite |
| `npm test` (`vitest run`) | Windows 11 / Node | **19 passed** (`7.03 s`) | Covers upload limits, mic error handling, AudioWorklet flush handshake, `TranscriptReview` deferred Apply + inline edit + Clarification, `MicrophoneSettings`, linear resampler config |
| `npm run build` (`tsc -b && vite build`) | Host + Docker Node 22 | **PASS** (`722 ms` Docker) | Strict TypeScript check + production Vite bundle |
| `docker compose exec -T sollicut python -m pytest tests/` | Docker Linux (`python:3.11-slim-bookworm`) | **219 passed, 1 skipped** (`58.37 s`) | Known skip: `test_indicconformer_initializes_and_decodes_synthetic_buffer` checks relative `models/`; container uses `/models/` |
| `docker compose exec -T sollicut python -m scripts.smoke_test` | Docker container (`http://localhost:8080`) | **PASS** (`7.571 s` initial, `7.054 s` follow-up) | Verifies health, capabilities, uploads, 15s Tanglish render, follow-up offer/music edit, byte-exact undo, `ffprobe` 720×1280 `yuv420p`/`h264`/`aac` |

### 3.2 CPU Profiling Summary (`docs/CPU_PROFILE.md`)
Measured on local host (`AMD64 Family 25 Model 80 Stepping 0`, 16 logical cores, Windows 11, `5.094 s` Windows SAPI TTS fixture labeled `NOT_HUMAN`):
- **`balanced` (default, 4 threads, Silero VAD + FIR polyphase):** cold init `2.228 s` (+ `17.59 ms` VAD), Peak RSS `781.12 MiB`, warm `en` RTF `0.527`, `ta` RTF `0.041`, `tanglish` dual-pass RTF `0.574`. Silero VAD ran in `0.36 ms`.
- **`lightweight` (2 threads, RMS gate + linear resampler):** cold init `2.301 s`, Peak RSS `751.10 MiB`, warm `en` RTF `0.582`, `ta` RTF `0.055`, `tanglish` dual-pass RTF `0.751`.
- **`accuracy` (`large-v3-turbo` fallback tested):** falls back cleanly to `small` if `large-v3-turbo` weights are absent locally; `large-v3-turbo` CPU RTF/RAM benchmark remains **`NEEDS HUMAN VERIFICATION`**.

### 3.3 Benchmark Summary (`docs/VOICE_V2_BASELINE.md` § 8, `NOT_HUMAN`)
- **NLU Determinism (100 synthetic cases):** **100/100 (`100.0%`)** across `en` (`40/40`), `tanglish` (`35/35`), and `ta` (`25/25`).
- **ASR on Windows SAPI en-US TTS (`NOT_HUMAN`):** `faster-whisper` (`small`) `en` WER `0.0200` (n=10), `tanglish` WER `0.2383` (n=10; canonical `tan-001`–`tan-003` achieved `0.00` WER).

---

## 4. Invariants & Honest Gaps (`NEEDS HUMAN VERIFICATION`)

### Verified Invariants
- **Keyless startup & UI (`SOLLICUT_PORT=8088`):** Tested with no `.env` file and unset `GEMINI_API_KEY`; `/api/capabilities` reports `generation.status = "key_not_set"`.
- **Zero persistent voice recordings:** Confirmed `data/projects/<uuid>/audio/` stays empty across WebSocket preview, WebSocket apply, HTTP WAV upload, and failure paths.
- **No auto-execution on voice reply:** WS/HTTP with `auto_apply=false` / `preview=true` returns parsed operations without mutating `project` or enqueuing FFmpeg jobs until `POST /api/projects/{id}/apply`.
- **Non-destructive undo & project delete cleanup:** Revision snapshots restore exact settings, asset order/trims, and MP4 bytes; project deletion deletes `/data/projects/<uuid>` and clears `VoiceContextManager`.

### Honest Gaps / `NEEDS HUMAN VERIFICATION`
1. **Human Microphone Tamil & Tanglish Acceptance:** Automated checks only use synthetic buffers and en-US SAPI TTS (`NOT_HUMAN`). Native Tamil/Tanglish microphone WER and interactive studio UX require live human evaluation (`docs/ASR_BENCHMARK.md`).
2. **`whisper-large-v3-turbo` & `TamilKiliEngine`:** `WhisperTurboEngine` is implemented behind `SOLLICUT_PROFILE=accuracy` / `SOLLICUT_ASR_MODEL=large-v3-turbo`, and falls back safely to `small`; `TamilKiliEngine` remains a documented TDT-transducer stub pending full ONNX joint/decoder wiring in V2.1.
3. **Docker Build Network Contingency:** During Phase 11's container rebuild on 2026-11-28, external requests from Docker BuildKit/bridge to HuggingFace/GitHub intermittently returned `HTTP 504: Gateway Time-out`, causing the `model` build stage to gracefully hit its `|| echo 'ASR model acquisition failed'` fallback (`219 passed, 1 skipped` in container without network models). Pre-downloaded host models (`scripts/download_model.py`, copied into `/models` on the local test container) restored full `dual-asr` + `silero` VAD container readiness cleanly. On an unrestricted network, `docker compose up --build` downloads all models cleanly during build.
4. **Live Gemini Omni Ad Generation:** Verified strictly gated behind `GEMINI_API_KEY`; live cloud video generation remains unverified without a supplied key.
