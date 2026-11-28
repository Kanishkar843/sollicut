# SolliCut — Day One Upgrade Log (`KANISHDEV`)

- **Branch:** `KANISHDEV` (branched cleanly from `main` at baseline commit `f78caf6`)
- **Remote:** `https://github.com/Kanishkar843/sollicut`
- **Verification Status:**
  - Backend: `85 passed` (`python -m pytest tests/backend -q`)
  - Frontend: `14 passed` (`cd frontend && npm test`) + clean production bundle (`npm run build`)

---

## What Was Completed on Day One

### 1. Multi-Turn Voice & Text Static-Edit Bug Fix
- **Root causes fixed:**
  - Added persistent `TextLayer` IDs (`TextLayer.id`), `clip_index`, `start_time`/`end_time`, `animation`, and `is_caption` in [backend/app/models.py](backend/app/models.py) so follow-up commands reference existing layers instead of overwriting blindly.
  - Passed `_parser_context(project)` into `parse()` in [backend/app/main.py](backend/app/main.py) and upgraded [backend/app/parser.py](backend/app/parser.py) to support single/double quotes, follow-up value substitutions (`"Change 20% to 25%"`), cumulative brightness, and Tamil / Tanglish / English parity.
  - Resolved the `busy` flag release ordering race in `_run_render_job()`, stopped asset uploads/removals from clearing `undo_stack` and `current_output`, and added 10-step `undo_stack` + `redo_stack` (`POST /undo`, `POST /redo`).
  - Stabilized callback refs in [frontend/src/VoiceButton.tsx](frontend/src/VoiceButton.tsx) and added an interactive typed command override bar + polling guard (`pollingRef`) in [frontend/src/App.tsx](frontend/src/App.tsx).

### 2. Core CapCut-Style Studio & Editing Features (100% Offline & Keyless Core)
- **4-Track Interactive Timeline ([frontend/src/Timeline.tsx](frontend/src/Timeline.tsx)):** Media track (drag-and-drop reorder, `<`/`>` move, trim, split), persistent multi-layer Text track, Auto-Captions / Offline TTS track, and Audio DSP track with playhead scrubbing.
- **Video Clip Audio Auto-Preservation & Preview Fixes ([backend/app/main.py](backend/app/main.py), [backend/app/media.py](backend/app/media.py), [frontend/src/App.tsx](frontend/src/App.tsx)):**
  - Uploading a video that contains an audio track now automatically enables `settings.keep_clip_audio = True` (unless explicitly toggled off by the user in `edit_history`).
  - Fixed FFmpeg stereo downmixing (`aformat=sample_rates=44100:channel_layouts=mono` instead of dropping the right channel), explicit stream mapping (`-map 0:v:0 -map 0:a:0`), and `amix` volume normalization compensation (`volume={inputs}` when FFmpeg lacks `normalize=0`).
  - Enabled immediate unmuted video playback (`Selected clip preview`) in the center stage right after uploading a video clip, before even triggering the first render.
- **Multiple Aspect Ratios & Resolutions ([backend/app/models.py](backend/app/models.py), [backend/app/assets_catalog.py](backend/app/assets_catalog.py), [backend/app/media.py](backend/app/media.py), [frontend/src/App.tsx](frontend/src/App.tsx)):**
  - Added selectable formats across both the Studio topbar dropdown and Look tab:
    - `9:16` Vertical (`720×1280`)
    - `16:9` Landscape (`1280×720`)
    - `1:1` Square (`1080×1080`)
    - `4:5` Portrait (`864×1080`)
  - Voice/command parser also supports aspect switching (`16:9`/`landscape`, `1:1`/`square`, `4:5`/`portrait`, `9:16`/`vertical`).
- **Inbuilt Soothing Music Library + “Your music” Device Upload ([assets/music/](assets/music/), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)):**
  - Renamed `"Original demo music"` across UI and catalog to **"Inbuilt music"**.
  - Added **14 CC0 1.0 soothing audio tracks** sourced from Wikimedia Commons into `assets/music/*.mp3` with in-browser audio preview (`GET /api/assets-catalog/audio/{audio_id}`) and one-click attach (`POST /api/projects/{id}/attach-catalog-audio`).
  - Added a **"Your music"** button in both the Media footer and Audio inspector tab to pick custom audio from the device anytime (automatically replacing any existing audio track).
- **Visual Effects, Filters, Transitions, Keyframes & Audio DSP ([backend/app/effects.py](backend/app/effects.py), [backend/app/keyframes.py](backend/app/keyframes.py), [backend/app/tts.py](backend/app/tts.py)):**
  - Categorized transitions (`fade`, `dissolve`, `slideleft`, `slideright`, `wipeleft`, `circleopen`), 8 color filters (`none`, `vivid`, `high_contrast`, `cinematic`, `warm`, `cool`, `vintage`, `bw`), keyframes with easing, speed curves, Chroma Key + GrabCut / optional U²-Net ONNX Auto Cutout, FFmpeg `deshake` + `relight`, audio denoise (`afftdn`), loudness normalization (`loudnorm`), voice enhance, vocal/music isolation, auto-captions (`faster-whisper`), offline Tamil/English TTS (`pyttsx3` / `espeak-ng`), sticker badges, and 4 editable templates.
- **Single-Viewport Studio UX ([frontend/src/style.css](frontend/src/style.css), [frontend/src/App.tsx](frontend/src/App.tsx)):**
  - Fitted the desktop Studio inside a single `100vh` non-scrolling workstation grid with internal panel scroll areas.
  - Wired left-rail **Media** button to open the upload picker directly and **Voice** button to focus/scroll the Voice Director command bar.

---

## Commit History on `KANISHDEV` (Prior to This Final Commit)

1. `a09c1a5` — `fix: resolve static-edit multi-turn voice bug, add persistent text layers, undo/redo, and offline TTS/captions`
2. `0d4f65a` — `feat: add transitions, filters, keyframes, cutout/chroma/stabilize/relight FX, audio DSP, and asset catalog`
3. `5c4be0b` — `feat: upgrade studio UI with 4-track timeline, manual command bar, redo, FX, keyframes, and assets`
4. `be6d046` — `test: add multi-turn voice, CapCut feature tests, CI workflow, and Unicode-safe OpenCV I/O`
5. `1a5ed96` — `docs: add KANISHDEV_UPDATE.md feature matrix, bug report, and verification results`
6. `b22d5f5` — `style: fit studio workstation inside single 100vh viewport without outer scroll`
7. `3ef4a46` — `fix: open media file picker from left rail Media button and focus command bar on Voice`
8. `a1869e0` — `Add multi-aspect ratio support, 14 CC0 inbuilt soothing tracks, and Your music upload`
9. *(Final Day One commit)* — Auto-enable `keep_clip_audio` on video-with-audio upload, FFmpeg stereo/amix audio fixes, unmuted pre-render clip preview, and `DAYONE.md`.

---

## Architecture & Feature Documentation

- Full CapCut comparison matrix, limitations, dependency licenses, and reproduction steps: [docs/KANISHDEV_UPDATE.md](docs/KANISHDEV_UPDATE.md)
- Third-party & CC0 asset notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
