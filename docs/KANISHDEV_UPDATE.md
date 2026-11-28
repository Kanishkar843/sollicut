# SolliCut `KANISHDEV` Upgrade Report

**Branch:** `KANISHDEV` (branched from `main`)  
**Baseline `main` Commit SHA:** `f78caf61aedb0c663bb7f0fdcb706ab28a5c8235`  
**Core Offline Guarantee:** All core editing, deterministic Tamil/Tanglish/English parsing, `faster-whisper` ASR, offline TTS, OpenCV keyframes/cutout/chroma-key, FFmpeg rendering, and asset templates run locally without any API key. Optional cloud ad generation (`AI Ad` tab) remains isolated and displays **Key not set** unless `GEMINI_API_KEY` is configured.

---

## 1. CapCut vs. SolliCut Feature Matrix

CapCut reference capabilities reviewed from official CapCut documentation and tools directories (`https://www.capcut.com`, `https://www.capcut.com/tools`, `https://www.capcut.com/resource`).

| CapCut Feature | Official CapCut Capability | SolliCut Status | Implementation / Notes | Priority |
|---|---|---|---|---|
| **Multi-Track Timeline** | Layered video, audio, text, captions, and effect tracks with trim, split, reorder, and scrub (`capcut.com`) | **Implemented** | 4-track interactive timeline (`Media`, `Text`, `Captions/TTS`, `Audio`) with drag-and-drop reorder, `<`/`>` clip moves, clip trim, video split (`split_clip`), transition chips, and playhead seek (`frontend/src/Timeline.tsx`, `backend/app/main.py`). | **P0** |
| **Multi-Turn Voice & Text Control** | Non-destructive sequential edits on project state | **Implemented** | Context-aware deterministic Tamil/Tanglish/English parser (`backend/app/parser.py`), persistent element IDs (`TextLayer.id`), manual command override bar, and 10-step `undo_stack` + `redo_stack` (`backend/app/main.py`). | **P0** |
| **Text Overlays & Styled Titles** | Multi-layer text overlays with timing, colors, and animation presets (`capcut.com`) | **Implemented** | Persistent `TextLayer` list supporting `top`/`bottom`/`center`/`end_card` placement, clip binding (`clip_index`), 5 accent colors, and `none`/`fade`/`slide_up`/`pop` animations rendered via Pillow + `Noto Sans Tamil` (`backend/app/media.py`). | **P0** |
| **Auto Captions (ASR)** | Speech-to-text subtitles placed on timeline and editable (`capcut.com/tools`) | **Implemented** | `FasterWhisperSpeechEngine.transcribe_segments()` (`backend/app/speech.py`) + `POST /api/projects/{id}/auto-captions` creates timed `is_caption=True` layers editable in the `A · Text` inspector. | **P0** |
| **Text-to-Speech (TTS)** | Convert typed script into multilingual voiceover (`capcut.com/tools`) | **Implemented** | Offline `OfflineTTSEngine` (`backend/app/tts.py`) using `espeak-ng` (Linux/Docker) or `pyttsx3` (Windows SAPI5) for English and Tamil (`POST /api/projects/{id}/tts`), mixed with BGM and clip audio. | **P1** |
| **Transitions** | Clip-to-clip fades, dissolves, slides, wipes, and shape transitions (`capcut.com`) | **Implemented** | Categorized transitions (`fade`, `dissolve`, `slideleft`, `slideright`, `wipeleft`, `circleopen`) rendered via FFmpeg `xfade` and `acrossfade` with overlap-compensated clip durations (`backend/app/media.py`). | **P0** |
| **Filters & Color Grading** | Categorized built-in looks (`Basic`, `Cinematic`, `Mood`, `Pop`) (`capcut.com`) | **Implemented** | 8 categorized presets (`none`, `vivid`, `high_contrast`, `cinematic`, `warm`, `cool`, `vintage`, `bw`) per-project or per-clip via FFmpeg `eq`/`colorbalance`/`hue`/`vignette` (`backend/app/effects.py`). | **P0** |
| **Keyframes & Speed Curves** | Animate position, scale, rotation, opacity with easing; slow-mo / speed changes (`capcut.com`) | **Implemented** | Manual `Keyframe` model (`time_seconds`, `x`, `y`, `scale`, `rotation`, `opacity`, `linear`/`ease_in`/`ease_out`/`ease_in_out`) via OpenCV `warpAffine` (`backend/app/keyframes.py`), plus per-clip speed (`0.25x–4.0x`) & global `slow_mo`/`fast` curves. | **P1** |
| **Auto Cutout (Background Removal)** | Subject isolation without green screen (`capcut.com/tools`) | **Implemented (Offline Approx.)** | Uses U²-Net ONNX (`onnxruntime`) automatically when local `models/u2net.onnx` / `u2netp.onnx` weights exist; otherwise uses OpenCV `cv2.grabCut` + morphological feathering, saving alpha masks to `overlays/mask-<id>.png` (`backend/app/effects.py`). | **P1** |
| **Chroma Key (Green Screen)** | Color-key removal and compositing (`capcut.com/tools`) | **Implemented** | OpenCV color-distance keying with mask output for photos (`effects.chroma_key_image`) and FFmpeg `chromakey` compositing for videos (`backend/app/media.py`). | **P1** |
| **Video Stabilization & Relight** | Shake smoothing and exposure relighting (`capcut.com/tools`) | **Implemented** | FFmpeg `deshake` stabilization for video clips and exposure/gamma `relight` (`-0.5` to `+0.5`) via FFmpeg `eq` (`backend/app/media.py`). | **P1** |
| **Audio Tools (Denoise, Normalize, Enhance, Vocal Isolation)** | Loudness normalization, noise removal, voice enhancement, vocal/music separation (`capcut.com`) | **Implemented (DSP)** | Per-track volume (`music_volume`, `clip_audio_volume`, `narration_volume`, per-clip `volume`), FFmpeg `afftdn` denoise, EBU R128 `loudnorm`, `highpass`/`lowpass`/`acompressor` voice enhance, and bandpass vocal/music isolation (`backend/app/effects.py`). | **P1** |
| **Templates, Stickers & Local Audio/SFX Packs** | Editable templates, stickers, music/SFX (`capcut.com/resource`) | **Implemented (Local Packs)** | 4 editable reel templates (`flash_sale`, `festival_tamil`, `new_arrival`, `product_demo`), 4 sticker badges (`sale`, `new`, `top_pick`, `tamil_special`), and 5 generated MIT-licensed WAV music/SFX beds (`backend/app/assets_catalog.py`). | **P1** |
| **Stock Video Library** | Cloud library of stock video clips (`capcut.com`) | **Deferred (Empty Placeholder)** | `stock_video` catalog returns `status: "deferred"` with explicit UI notice; avoids unlicensed third-party media downloads. | **P2+ (Deferred)** |
| **Manual Cutout Brush Refine** | Interactive pixel brush to refine segmentation masks (`capcut.com`) | **Deferred** | Deferred interactive canvas brush tooling; automated GrabCut / U²-Net + Chroma Key masks shipped first. | **P2+ (Deferred)** |
| **Camera Tracking & Auto Reframe** | Motion-locked stickers/text and subject-tracking aspect reframing (`capcut.com`) | **Deferred** | Rejected cleanly with clarification guidance (`parser.py`); requires dedicated multi-frame tracker. | **P2+ (Deferred)** |
| **Proprietary AI Video/Image Generation & Neural Vocal Separation** | Cloud generative video, CapCut proprietary voice clones, Demucs/cloud stem split (`capcut.com`) | **Blocked / Optional** | Proprietary CapCut models excluded for licensing and offline constraints. Optional `AI Ad` panel (`gemini-omni-1.2-flash`) remains inactive unless server sets `GEMINI_API_KEY`. | **Blocked / P2+** |

---

## 2. Voice-Command Static-Edit Bug Diagnosis & Fix

### Symptom Reproduced
When a user gave an initial voice or manual command inserting text (e.g. `"Create text 'Sale 20%' on clip 1"` or `"Last la 20 percent offer nu text podu"`) and followed up immediately with a second command (e.g. `"Change text to 25%"` or `"Offer ah 25 percent nu maathu"`), either nothing changed, placement/clip context was lost, or rapid requests failed with HTTP `409`.

### Root Causes Identified
1. **Parser lacked active project context & follow-up replacement handling (`backend/app/parser.py`)**:
   - `parse(raw, media_count, has_reel)` took no active element context, had no persistent `TextLayer` IDs to target, only matched double-quoted strings (`"..."`) rather than single quotes (`'Sale 20%'`), left `"to "` inside `"change text to ..."` captures, and picked the **first** percentage in `"Change 20% to 25%"` instead of substituting `20% -> 25%` into the active text.
   - `set_brightness` always emitted an absolute `0.1` instead of accumulating from current brightness.
2. **Monolithic `overlay_text` string without persistent IDs (`backend/app/models.py`, `backend/app/main.py`)**:
   - `apply_operations()` overwrote `values["overlay_text"]` and `values["overlay_position"]` globally, discarding original placement/clip bindings whenever a follow-up omitted position words.
3. **Render `busy` flag race condition (`backend/app/main.py`)**:
   - `_run_render_job()` set `job.status = "done"` **before** `finally: busy.discard(project.id)` ran outside `async with render_gate:`, causing rapid follow-up requests right after polling `done` to fail with HTTP `409`.
4. **Asset uploads cleared `undo_stack` and `current_output` (`backend/app/main.py`)**:
   - `upload_asset()` and `delete_asset()` called `project.undo_stack.clear()` and set `project.current_output = None`, erasing edit history when adding audio or media.
5. **Frontend callback staleness & polling overlap (`frontend/src/VoiceButton.tsx`, `frontend/src/App.tsx`)**:
   - `VoiceButton.tsx` captured `onAudio`/`onError` closures at recording start instead of reading latest refs; `App.tsx` lacked an in-flight `pollingRef` guard and had no manual typed command bar to test/override parsed commands.

### Implemented Fixes
- Added `TextLayer` with persistent UUID `id`, `clip_index`, `animation`, `start_time`/`end_time`, and `is_caption` (`backend/app/models.py`).
- Added `_parser_context(project)` passed into `parse()` from both `/apply` and `/voice-command` (`backend/app/main.py`).
- Updated `backend/app/parser.py` to support single/double quotes, `"on clip N"`, `"from X% to Y%"` substitution preserving active `target_id` and placement, `"change text to ..."` stripping, cumulative `set_brightness`, and multi-language Tamil/Tanglish/English parity.
- Moved `busy.discard(project.id)` directly before `job.status = "done"`/`"failed"` inside `_run_render_job()`, preserved `undo_stack` on asset upload (`_snapshot` push instead of `.clear()`), and added `redo_stack` (`POST /redo`).
- Stabilized `VoiceButton.tsx` callbacks with refs, added `pollingRef` + forced `<video key={...}>` reload + manual command bar in `App.tsx`.

---

## 3. Executed Test & Multi-Turn Verification Results

### Automated Test Suites (Run After Final Edit)
- **Backend (`python -m pytest tests/backend -q`)**: **83 passed in 139.77s** (`0 failed`).
  - Covers multi-turn `/voice-command` (mocked `speech.transcribe` returning real transcript fixtures) & `/apply` (`tests/backend/test_multiturn_voice.py`), CapCut P1/P2 features (`tests/backend/test_features_p1_p2.py`), deterministic parser (`tests/backend/test_parser.py`), upload/API/undo/redo (`tests/backend/test_api.py`), Gemini mocked REST lifecycle (`tests/backend/test_generation.py`), storage (`tests/backend/test_storage.py`), and real FFmpeg/OpenCV rendering (`tests/backend/test_media.py`).
- **Frontend (`cd frontend && npm test`)**: **11 passed in 14.89s** (`vitest run`).
- **Frontend TypeScript & Production Build (`cd frontend && npm run build`)**: `tsc -b && vite build` succeeded in **1.03s** (`dist/assets/index-BUGel2ku.js`, `319.26 kB`).
- **Source Code Size (`python scripts/count_project_code.py`)**: **8,291** nonblank project-specific source lines across `backend`, `frontend/src`, `scripts`, `tests`, and `pitch`.

### Observed Multi-Turn Command & Export Checksums (Real `TestClient` + FFmpeg Renders)
| Turn | Endpoint / Command | Persistent `TextLayer.id` | Resulting State | Exported MP4 Size & SHA-256 |
|---|---|---|---|---|
| **Turn 1** | `POST /apply`: `"Create a 4 seconds reel. Create text 'Sale 20%' on clip 1"` | `de5a76ab-f7c1-4674-aba6-9de3a8e20988` | `rev=1`, `overlay_text="Sale 20%"`, `clip_index=1` | `139,695` bytes · `e04366ff01c86a1ae306d065cccacf3cfb9e8d91317581127293e5bd1c9375fb` |
| **Turn 2** | `POST /apply`: `"Change text to 25%"` | `de5a76ab-f7c1-4674-aba6-9de3a8e20988` *(preserved)* | `rev=2`, `overlay_text="Sale 25%"`, `clip_index=1` | `139,606` bytes · `15a8205e520b66abf9209e0a2093d98c7307ec2c11206f48edbd1da6746609c2` |
| **Turn 3** | `POST /apply`: `"Offer ah 30 percent nu maathu. Background music konjam kammi pannu. cinematic filter podu. fade transition add pannu"` | `de5a76ab-f7c1-4674-aba6-9de3a8e20988` *(preserved)* | `rev=3`, `overlay_text="30 percent offer"`, `music_volume=0.12`, `filter="cinematic"`, `transition="fade"` | `117,070` bytes · `739baf04607d0dcd8ca4616ceb4eb6683b129f93b428182cd170c650ae43b270` |
| **Undo / Redo** | `POST /undo` then `POST /redo` | `de5a76ab-...` | Undo byte-matches Turn 2 SHA (`True`); Redo byte-matches Turn 3 SHA (`True`) | Verified via `ffprobe`: `720×1280`, `h264`, `yuv420p`, `4.05s` |

Additional verified multi-turn sequences in `tests/backend/test_multiturn_voice.py`:
- Sequential `/voice-command` Turn 1 (`"Create text 'Sale 20%' on clip 1"`) -> Turn 2 (`"Change text to 25%"`) immediately on job `done`: persistent ID retained, zero HTTP `409`, distinct MP4 SHA-256 outputs.
- Canonical Tanglish Turn 1 (`"...20 percent offer nu text podu."`) -> Turn 2 (`"Offer ah 25 percent nu maathu. Background music konjam kammi pannu."`) -> Undo -> Redo: byte-identical MP4 restoration.
- Mixed Tamil/English/Tanglish (`"இருபது சதவீதம் ஆஃபர்"` -> `"Change 20% to 30%"` -> `"cinematic filter podu. fade transition add pannu. add sale sticker. brighter"` -> `"brighter"`): `"20% ஆஃபர்"` -> `"30% ஆஃபர்"` with cumulative brightness `+0.1 -> +0.2`.

---

## 4. Limitations & Deferred Items

- **Native Windows vs. Docker Tamil Shaping (`libraqm`)**: Native Windows Python Pillow lacks `libraqm` (`raqm: False`), so local Windows runs fall back to `ImageFont.Layout.BASIC` (`media.capabilities()["tamil_shaping"] == "basic_fallback"`). Full HarfBuzz/FriBidi Tamil shaping (`raqm: True`) runs in Docker/Linux (`Dockerfile` installs `libraqm0`) and GitHub Actions CI.
- **Background Removal Weights**: `effects.auto_cutout_image` automatically uses `U^2-Net` ONNX (`onnxruntime`) if a user supplies `models/u2net.onnx` or `u2netp.onnx` (or `SOLLICUT_U2NET_MODEL`), and falls back offline to OpenCV GrabCut when no neural weights are bundled.
- **Vocal Isolation**: Implemented via lightweight FFmpeg frequency-band DSP (`highpass`/`lowpass`), not deep-learning stem separation (e.g., Demucs), to preserve fast CPU-only headless execution.
- **Offline Tamil TTS Voices**: Linux/Docker (`espeak-ng -v ta`) supports Tamil phonology out of the box; Windows SAPI5 (`pyttsx3`) uses installed OS voices (`Microsoft David`/`Zira` for English unless Windows Tamil voice packs are installed).
- **Human & Cloud Acceptance**: Live microphone accent capture and live `GEMINI_API_KEY` cloud generation remain unexecuted in this offline automated verification pass (ASR/auto-captions tested via mocked Whisper transcripts; Gemini tested via mocked REST transport).

---

## 5. New Dependencies & Licenses

| Package / Binary | Version | License | Purpose |
|---|---|---|---|
| `opencv-python-headless` | `5.0.0.93` | Apache 2.0 | Keyframe affine transforms, GrabCut auto-cutout, chroma-key masking |
| `pyttsx3` | `2.99` | MPL-2.0 | Offline TTS synthesis fallback (`SAPI5` on Windows / `espeak` on Linux) |
| `espeak-ng` *(Docker/Linux)* | Debian bookworm | GPL-3.0-or-later | Offline English & Tamil CLI TTS synthesis |
| `onnxruntime` *(already in lock)* | `1.32.0` | MIT | Optional local `U^2-Net` ONNX cutout inference when weights are supplied |

Updated in [backend/requirements.in](../backend/requirements.in), [backend/requirements.lock](../backend/requirements.lock), [Dockerfile](../Dockerfile), and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

---

## 6. Verification Commands & Branch History

### Reproduce Locally
```sh
# 1. Generate local demo & SFX/music assets
python scripts/generate_demo_assets.py

# 2. Run backend suite (83 tests)
python -m pytest tests/backend -q

# 3. Install, test, and build frontend (11 tests + Vite bundle)
cd frontend && npm ci && npm test && npm run build

# 4. Run full Docker stack (includes libraqm0 & espeak-ng)
docker compose up --build
```

### `KANISHDEV` Milestone Commits (Pre-Report)
- `a09c1a5` — `fix: resolve static-edit multi-turn voice bug, add persistent text layers, undo/redo, and offline TTS/captions`
- `0d4f65a` — `feat: add transitions, filters, keyframes, cutout/chroma/stabilize/relight FX, audio DSP, and asset catalog`
- `5c4be0b` — `feat: upgrade studio UI with 4-track timeline, manual command bar, redo, FX, keyframes, and assets`
- `be6d046` — `test: add multi-turn voice, CapCut feature tests, CI workflow, and Unicode-safe OpenCV I/O`

*(Followed by this `docs/KANISHDEV_UPDATE.md` documentation commit and push to `origin/KANISHDEV`.)*
