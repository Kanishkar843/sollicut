# Executed verification - 27 November 2026

- `docker compose up --build -d --wait --wait-timeout 120`: healthy (`sollicut-sollicut-1`), no `.env` or API keys. Initial dependency layers were built with the host's trusted CA supplied as an optional BuildKit secret; subsequent Compose rebuilds reused cached dependency and model layers.
- `docker compose exec -T sollicut python -m pytest tests/backend -q`: **70 passed in 7.65s**. Covers 54+ deterministic parser cases (Tamil, Tanglish, English, single-clip reels, clip trim, clip reorder, clip audio, fit mode, clarification cases), UUID project storage, upload validation (photos & MP4/MOV/WebM videos), visual `/edit` + undo snapshot restoration, real FFmpeg mixed-media rendering, `libraqm` Tamil shaping (`test_tamil_overlay`), and Gemini adapter missing-key / mocked REST / job lifecycle / failure-preservation tests.
- `npm.cmd test --prefix frontend`: **8 passed** (Vitest + Testing Library). Covers photo/video upload validation, mocked microphone permission/missing errors, operation chips, empty studio timeline/disabled download/undo, rendered video preview + transport controls, `AI Ad` `"Key not set"` indicator, and landing lookbook keyboard toggle + local card assets. Mocked microphone tests are not human speech evidence.
- `npm.cmd run build --prefix frontend`: TypeScript (`tsc -b`) and Vite production build succeeded in 298ms (also succeeded inside the Docker Node 22 build stage).
- `docker compose exec -T sollicut python -m scripts.smoke_test`: passed (`initial_render_seconds: 5.547`, `followup_render_seconds: 5.539`), verifying `/api/health`, `/api/capabilities`, demo uploads, canonical Tanglish render, follow-up offer/music render, MP4 download, `ffprobe` metadata (`720×1280`, `yuv420p`, `h264`, `aac`, ~15s), and byte-identical undo.
- Real ASR endpoint check (`/api/projects/{id}/voice-command` with `../jfk.wav`): HTTP 200, real English transcript in `1.625s`, deterministic parser clarification prompt. Not a Tamil/Tanglish benchmark.
- Browser UI inspection (`http://localhost:8080/` and `http://localhost:8080/#studio`): verified dark landing page, Frosted Folder Lookbook open/close and all 4 local 3:4 campaign cards (`/lookbook/*.png`), `390×844` mobile layout without horizontal page overflow, Studio photo upload, `A · Text` overlay edit + live `<video>` stream (`206`), Timeline clip/overlay/audio tracks, `Undo` & `Download MP4` states, `"Key not set"` in `AI Ad`, and `New reel` cleanup.
- Tamil overlay visual check: `libraqm` = `true`; `tamil-overlay.png` (`இன்று 20% ஆஃபர்`) visually inspected and verified for proper glyph shaping. Participant fluent-language review remains recommended.
- Pitch PDF (`pitch/generate_pitch.py`): regenerated 7-page `pitch/SolliCut_Pitch.pdf` with extractable text verified across all required sections.
- Code size (`scripts/count_project_code.py`): 4,685 project-specific nonblank source lines across `backend`, `frontend/src`, `scripts`, `tests`, and `pitch`.

## Pending human / key-dependent verification

- Real laptop microphone capture and Tamil/Tanglish speech recognition with the participant's voice (`docs/ASR_BENCHMARK.md`).
- Live Gemini Omni 1.2 Flash cloud generation (`GEMINI_API_KEY` not supplied; adapter tested via mocked REST transport and job-lifecycle tests only).
- Independent person's fresh clone and startup on an ordinary network, YouTube demo video recording/publication, and final authenticated hackathon submission.
