# Architecture

React/TypeScript/Vite/Tailwind provides the dark Frosted Folder Lookbook landing experience (`/`), studio preview transport, `Your media` photo/video uploader, MediaRecorder capture, 3-track interactive timeline, inspector controls (`Text`, `Audio`, `Look`, `Trim`, `AI Ad`), and HTML5 `<video>` playback. FastAPI serves the compiled UI and `/api` from a single container.

JSON project files are atomically replaced under UUID directories (`/data/projects/<uuid>`). Photos are decoded, EXIF-normalized, and fitted without stretching (`contain` or `cover`). Uploaded videos (MP4/MOV/WebM) are probed with `ffprobe`, optionally trimmed (`trim_start`/`trim_end`), fitted to 720×1280, and optionally mixed with background music via `amix` + `anullsrc` when `keep_clip_audio` is enabled.

Speech uses the public `faster-whisper` `base` model, CTranslate2 CPU INT8, and a replaceable `SpeechEngine` protocol. Initialization runs off the HTTP startup path. Missing models produce an explicit unavailable capability; no fake transcript fallback exists.

The deterministic parser (`backend/app/parser.py`) preserves raw transcripts separately, normalizes Unicode and Tamil/Tanglish/English number words, validates 1–5 uploaded media items directly (without count workarounds), and maps domain vocabulary to validated operations including `trim_clip`, `reorder_assets`, `set_clip_audio`, `set_fit_mode`, duration, zoom, music, brightness, overlays, undo, and export. No probabilistic confidence is invented.

One FFmpeg render runs at a time (`render_gate`). FFmpeg receives argument arrays without shell evaluation (`subprocess.run(..., check=False)`). Pillow/`libraqm` shapes Tamil overlays into PNGs using Noto Sans Tamil. Successful renders commit a new revision; failures preserve the previous state. Undo restores settings, asset order/trims, edit history, and the already-rendered MP4 revision without recompression (up to 10 snapshots retained). Jobs are process-local.

Optional cloud advertisement generation (`backend/app/generation.py`) targets Google's `gemini-omni-1.2-flash` Interactions REST endpoint (`POST https://generativelanguage.googleapis.com/v1beta/interactions`) with `x-goog-api-key`, explicit `aspect_ratio`/`duration` schema, bounded timeouts, and async background job polling. Without `GEMINI_API_KEY`, the API returns `"Key not set"` and core local editing remains fully operational.

Alternatives: AI4Bharat IndicConformer offers Tamil recognition but a heavier integration. Bodhan Indic-Transcribe targets code-mixed transcription and requires separate model/license evaluation. BHASHINI hosted adapters require credentials and connectivity. None is a P0 dependency. See [PITCH_SOURCES.md](PITCH_SOURCES.md) for sources accessed 27 November 2026.
