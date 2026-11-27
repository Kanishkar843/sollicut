# SolliCut Voice Intelligence V2 — Phase Progress Tracker

> Branch: `dharanish-dev` · Last updated: 2026-11-27

---

## Phase Status Summary

| Phase | Title | Status | Commit |
|---|---|---|---|
| **P0** | Baseline Audit & V2 Docs | ✅ COMPLETE | `f41bc1d` |
| **P1** | Anti-Aliased Resampler + Flush Handshake | ✅ COMPLETE | `108b6da` |
| **P2** | Reliable WebSocket Transport | ✅ COMPLETE | `23d68a4` |
| **P3** | Silero VAD Integration | 🔄 IN PROGRESS | — |
| **P4** | ASR Engine Upgrade (Tamil Kili / Whisper LV3T) | 🔲 PENDING | — |
| **P5** | Multilingual Normalization V2 | 🔲 PENDING | — |
| **P6** | Semantic Command Planner | 🔲 PENDING | — |
| **P7** | Context Manager + Validation | 🔲 PENDING | — |
| **P8** | Voice Director UX | 🔲 PENDING | — |
| **P9** | CPU Profiling & Deployment Profiles | 🔲 PENDING | — |
| **P10** | Benchmarking Framework | 🔲 PENDING | — |
| **P11** | Final Regression Suite | 🔲 PENDING | — |

---

## Phase 0 — Baseline Audit & V2 Docs

**Status:** ✅ COMPLETE

**Gate passed:** Yes

### Deliverables
- [x] `docs/VOICE_V2_BASELINE.md` — test counts, architecture, weakness analysis
- [x] `docs/VOICE_V2_ARCHITECTURE.md` — V2 layer-by-layer design
- [x] `docs/VOICE_V2_PROGRESS.md` — this file

### Baseline test counts
- Backend: **99 passed** (Windows local)
- Frontend: **13 passed** (Windows local)
- Docker container: **98 passed, 1 skipped** (known path skip)

### Key findings
- Linear interpolation resampler → aliasing risk (W1)
- No flush handshake → ~100 ms dropped at recording end (W2)
- RMS-only VAD → cannot handle natural pauses or background hum (W3)
- No session IDs on WS → no idempotency (W4)
- Forced `language="en"` for Tanglish Whisper pass → degrades Tamil (W5)
- Keyword regex parser → multi-trim collapse, no clause chaining (W6)
- No transcript review UI → immediate destructive execution (W7)
- No human voice benchmark → all WER is `NEEDS HUMAN VERIFICATION` (W8)

---

## Phase 1 — Anti-Aliased Resampler + Flush Handshake

**Status:** 🔲 PENDING

**Files to modify:**
- `frontend/public/pcm-processor.js` — FIR polyphase resampler (Kaiser window, 48000→16000, 44100→16000, 1:1)
- `frontend/src/hooks/useRecorder.ts` — `FLUSHING` state, flush ACK before AudioContext close
- `frontend/src/VoiceButton.tsx` — lifecycle label for all states

**Gate conditions:**
- [ ] Sample count accuracy ±1 at 44100, 48000, 16000 Hz
- [ ] Continuity across processing blocks (no clicks)
- [ ] Final partial-buffer flush — no dropped samples
- [ ] Microphone permission denied/unavailable/disconnected handled
- [ ] All 99 backend + 13 frontend tests still pass
- [ ] `npm run build` clean

---

## Phase 2 — Reliable WebSocket Transport

**Status:** 🔲 PENDING

**Files to modify:**
- `backend/app/main.py` — session_id, command_id, idempotency, bounded timeouts, malformed message validation
- `frontend/src/hooks/useRecorder.ts` — sequence tracking, `bufferedAmount` backpressure, session ID
- `frontend/src/api.ts` — `session_id`, `command_id` on `Command` type

**Gate conditions:**
- [ ] Duplicate `command_id` rejected by server
- [ ] Malformed control message returns structured error (not 500)
- [ ] Session timeout fires at 35 s
- [ ] All 99 backend + 13 frontend tests still pass

---

## Phase 3 — Silero VAD Integration

**Status:** 🔲 PENDING

**New files:**
- `backend/app/voice/vad.py` — Silero ONNX VAD wrapper
- `backend/app/voice/audio_quality.py` — clipping detection, noise assessment, empty rejection

**Gate conditions:**
- [ ] Silero VAD model downloaded from public URL (no auth)
- [ ] `vad.py` unit tests: speech → True, silence → False, mixed → correct segments
- [ ] Fallback to RMS gate when VAD unavailable
- [ ] Container pytest: 0 new failures
- [ ] Privacy: no VAD buffers written to disk

---

## Phase 4 — ASR Engine Upgrade

**Status:** 🔲 PENDING

**Research tasks (before coding):**
- [ ] Verify `shrirajh/parakeet-tamil-kili` ONNX artifacts availability
- [ ] Verify `faster-whisper` model for `whisper-large-v3-turbo`
- [ ] Measure memory footprint on target hardware
- [ ] Confirm license compatibility

**New files:**
- `backend/app/voice/engines/base.py`
- `backend/app/voice/engines/tamil_kili.py`
- `backend/app/voice/engines/whisper_turbo.py`
- `backend/app/voice/engines/legacy.py`
- `backend/app/voice/router.py`

**Gate conditions:**
- [ ] Tamil Kili decodes Tamil+Tanglish synthetic utterance without error
- [ ] Whisper LV3 Turbo decodes English utterance without error
- [ ] Fallback to V1 engines when V2 models unavailable
- [ ] All 99 backend tests still pass with legacy engines
- [ ] Docker build succeeds; `/api/capabilities` updated

---

## Phase 5 — Multilingual Normalization V2

**Status:** 🔲 PENDING

**New files:**
- `backend/app/understanding/normalizer.py`
- `backend/app/understanding/number_parser.py`

**Gate conditions:**
- [ ] Decimal number "2.5 seconds" → 2.5 float
- [ ] Tamil suffix stripping tests (5 cases)
- [ ] Quoted promotional text preserved
- [ ] Ambiguous input returns clarification (not guess)
- [ ] 15+ parser tests still pass

---

## Phase 6 — Semantic Command Planner

**Status:** 🔲 PENDING

**New files:**
- `backend/app/understanding/clause_parser.py`
- `backend/app/understanding/intent_parser.py`
- `backend/app/understanding/operation_planner.py`

**Gate conditions:**
- [ ] "trim first clip and trim last clip" → 2 separate trim ops (not collapsed)
- [ ] "zoom in then add text" → [zoom, overlay] sequential plan
- [ ] All 99 backend tests still pass

---

## Phase 7 — Context Manager + Validation

**Status:** 🔲 PENDING

**New files:**
- `backend/app/understanding/context_manager.py`
- `backend/app/understanding/validator.py`

**Gate conditions:**
- [ ] "trim it to 5 seconds" resolves "it" from last command context
- [ ] Trim > clip duration → validation error (not silent bad trim)
- [ ] All 99 backend tests still pass

---

## Phase 8 — Voice Director UX

**Status:** 🔲 PENDING

**New files:**
- `frontend/src/components/voice/TranscriptReview.tsx`
- `frontend/src/components/voice/OperationPreview.tsx`
- `frontend/src/components/voice/Clarification.tsx`
- `frontend/src/components/voice/MicrophoneSettings.tsx`

**Gate conditions:**
- [ ] WS reply does NOT immediately execute; "Apply" required
- [ ] Clarification UI renders server questions
- [ ] `npm run build` clean
- [ ] 13 frontend tests still pass

---

## Phase 9 — CPU Profiling & Deployment Profiles

**Status:** 🔲 PENDING

**Gate conditions:**
- [ ] 3 profiles (lightweight/balanced/accuracy) selectable via `SOLLICUT_PROFILE` env var
- [ ] Cold init time, warm RTF, peak RAM measured and documented
- [ ] No fabricated metrics — real measurements only

---

## Phase 10 — Benchmarking Framework

**Status:** 🔲 PENDING

**New files:**
- `scripts/benchmark_voice.py`
- `tests/voice/`
- `tests/fixtures/voice_manifest.json`

**Gate conditions:**
- [ ] 100 evaluation cases (TTS synthetic, labeled `NOT_HUMAN`)
- [ ] WER computed per engine per mode
- [ ] Results saved to `docs/VOICE_V2_BASELINE.md` section 8

---

## Phase 11 — Final Regression Suite

**Status:** 🔲 PENDING

**Gate conditions:**
- [ ] Clean checkout from remote `dharanish-dev` succeeds
- [ ] `docker compose up --build -d` succeeds with empty `.env`
- [ ] All 8 workflow end-to-end tests (A–H) pass
- [ ] `docs/VOICE_V2_FINAL_REPORT.md` written
- [ ] All previous phase commits present on `dharanish-dev` remote

---

## Report Template (fill per phase)

```
## Phase N — <Title>
Commit: <SHA>
Gate: PASS | FAIL
Backend tests: XX passed
Frontend tests: XX passed
Docker build: PASS | FAIL
Key changes:
- <file>: <description>
Issues fixed:
- <error> → <fix>
Outstanding:
- <item>
```
