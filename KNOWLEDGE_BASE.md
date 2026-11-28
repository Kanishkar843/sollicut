# SolliCut Knowledge Base & Agent Developer Guide

This document is the architectural, component, and operational reference for any AI agent or engineer continuing development on **SolliCut**.

---

## 1. System Overview

**SolliCut** is a voice-driven promotional reel studio tailored for Tamil, Tanglish (Tamil written with Latin script or code-mixed with English), and English local businesses (retailers, boutiques, florists, home kitchens, bakeries, etc.). 

It takes raw user media (images/videos) and voice instructions, transcribes the voice locally, maps transcripts deterministically into video editing operations, and renders vertical (9:16) H.264/AAC reels using FFmpeg and Pillow with Tamil script shaping (`libraqm`).

### Technology Stack Summary
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide icons, HTML5 `<video>` stage, browser native `MediaRecorder` API.
- **Backend API**: Python 3.11, FastAPI, Uvicorn, Pydantic v2.
- **Speech-to-Text (STT/ASR)**: `faster-whisper` (CTranslate2 backend) running OpenAI Whisper model weights (`base` default) on CPU INT8.
- **Command Parser**: Deterministic rule & regex-based natural language parser (`backend/app/parser.py`) for Tamil / Tanglish / English command extraction.
- **Rendering & Video Processing**: FFmpeg (h264, aac, filter graphs, zoompan, amix audio mixing), Pillow with `libraqm` + `NotoSansTamil.ttf` font shaping.
- **Cloud Generative Video (Optional)**: Google Gemini Omni (`gemini-omni-1.2-flash` via Generative Language Interactions API). Optional, disabled when `GEMINI_API_KEY` is omitted.
- **Containerization**: Multi-stage Docker build, orchestrated with Docker Compose.

---

## 2. In-Depth: Speech-to-Text (STT / ASR) Architecture

### 2.1 Model & Engine Specifications
- **Framework / Runtime**: [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) (v1.2.1), a reimplementation of OpenAI's Whisper model utilizing **CTranslate2**, a fast inference engine for Transformer models.
- **Default Model Weights**: `base` (multilingual OpenAI Whisper weights converted to CTranslate2 format).
- **Execution Target**: **CPU** (`device="cpu"`), quantized to **INT8** (`compute_type="int8"`), running with `cpu_threads=4`.
- **Model Acquisition**:
  - Downloaded at Docker image build time via `scripts/download_model.py` (`faster_whisper.utils.download_model(model, output_dir=...)`).
  - Stored inside the container at `/models/base` (`SOLLICUT_MODEL_DIR=/models`, `SOLLICUT_ASR_MODEL=base`).
  - Container build has a fallback: if download fails, the build still succeeds and flags ASR as unavailable rather than crashing HTTP startup.
  - Runtime initialization runs with `local_files_only=True` to eliminate external runtime dependencies and prevent offline crashes.

### 2.2 Speech Pipeline & Configuration (`backend/app/speech.py`)
```python
# Initialization
self.model = WhisperModel(
    str(local),
    device="cpu",
    compute_type="int8",
    cpu_threads=4,
    local_files_only=True
)

# Inference Parameters
segments, info = self.model.transcribe(
    str(path),
    language=language,                 # Optional language hint (e.g., 'ta', 'en') or auto-detect
    beam_size=5,                       # Beam search width
    vad_filter=True,                   # Voice Activity Detection to prune silence
    condition_on_previous_text=False   # Avoids repetition loops and hallucination propagation
)
```

### 2.3 Concurrency & Lifecycle
- **Thread Safety**: Whisper inference in CTranslate2 is synchronous and CPU-bound. `FasterWhisperSpeechEngine` wraps inference in `asyncio.to_thread` protected by an `asyncio.Lock()`. Only one transcription runs concurrently per worker process to prevent CPU starvation.
- **Non-blocking Startup**: The model is loaded in a background thread triggered during the FastAPI lifespan context manager (`track(asyncio.to_thread(speech.initialize))`). The HTTP server responds immediately on start.
- **Privacy & Storage**: Uploaded user audio clips (WAV/WebM) are processed and **deleted immediately** from the disk right after transcription finishes.

### 2.4 Language Handling & Tanglish Challenge
- Whisper is trained on multilingual speech, but colloquial **Tanglish** (Tamil grammar/words spoken with English loanwords or transcribed in Romanized phonetics) requires specific post-processing.
- Whisper either transcribes Tamil speech into native Tamil script (Unicode `\u0B80-\u0BFF`) or Romanized script depending on acoustic clarity and context.
- **Design Decision**: SolliCut deliberately decouples raw acoustic transcription from command parsing:
  1. The speech engine outputs raw transcript string + detected language code (`TranscriptResult(text=..., language=..., elapsed_seconds=...)`).
  2. The raw text is passed to the deterministic rule parser (`backend/app/parser.py`), which normalizes Tamil script numbers, Tanglish number loanwords (`oru`, `rendu`, `moonu`, `naalu`, `anju`, `pathu`), and English numerals into normalized integer tokens before extracting intent.
  3. No black-box generative rewrite is used for parsing commands; every parsed operation is traceable and reproducible.

### 2.5 Alternative STT Models Evaluated / Future Paths
- **`small` / `medium` Whisper**: Supported via environment variable `SOLLICUT_ASR_MODEL=small`. Increases memory and latency with marginal gain on Tanglish phonetics on CPU.
- **AI4Bharat IndicConformer**: Specialised for Indian languages (Tamil), but requires PyTorch/Triton dependencies and higher resource footprint.
- **Bodhan Indic-Transcribe**: Targeted code-mixing, requires licensing and separate distribution checks.
- **BHASHINI Hosted APIs**: High accuracy for Indian languages, but requires cloud API keys and active internet connection, conflicting with SolliCut's offline-first local edge privacy posture.

---

## 3. Detailed Component Architecture

### 3.1 Project State & Storage (`backend/app/storage.py`, `backend/app/models.py`)
- Projects are assigned UUIDs (`/data/projects/<uuid>`).
- State is serialized as JSON (`project.json`) and saved **atomically** (write to temp file + `os.replace`).
- Holds assets (photos, videos, music), reel settings (duration, aspect ratio, fit mode, zoom, brightness, audio levels), overlays (text, font size, position), and a stack of up to 10 snapshots for **zero-recompression undo**.

### 3.2 Command Grammar & Parser (`backend/app/parser.py`)
Deterministic parser supporting multi-operation extraction in a single voice command:
- **Operations Supported**:
  - `create_reel`: Duration (3–30s), aspect ratio `9:16`.
  - `set_duration`: Reel duration adjust.
  - `set_fit_mode`: `cover` (fill screen) vs `contain` (letterbox).
  - `set_zoom_style`: `smooth` (Ken Burns effect) vs `none`.
  - `set_music` / `set_music_volume`: Add/remove music, increase/decrease volume.
  - `set_clip_audio`: Mute or preserve original video clip audio.
  - `set_brightness`: Increase/decrease visual brightness.
  - `trim_clip`: Cuts by start/end timestamps or duration (`cut first 2s`, `trim from 1 to 5s`).
  - `reorder_assets`: Swap clips or move to position (`swap clip 1 and 2`, `move clip 3 to first`).
  - `set_text_overlay`: Text strings, discounts/offers (`20 percent offer`), positions (`top`, `bottom`, `center`).
  - `undo`: Reverts state and restores prior rendered video artifact.
  - `export`: Triggers final MP4 delivery.
- **Explainability**: Never mutates user transcripts in-place. Generates clarification questions when input is ambiguous or violates constraints (e.g. reel duration < 3s or > 30s).

### 3.3 Media Engine & FFmpeg Pipeline (`backend/app/media.py`)
- **Photos**: EXIF orientation correction, padded or cropped to 720×1280. Animated using FFmpeg `zoompan` filter when zoom is enabled.
- **Videos**: Probed with `ffprobe` for duration, dimensions, fps, audio streams. Filtered with `scale`, `pad`, `setsar=1`.
- **Text Rendering**: Pillow renders text using `NotoSansTamil.ttf` with HarfBuzz/Raqm (`libraqm`) shaping to prevent broken Tamil ligatures. Rendered text is saved as a transparent PNG overlay and composited via FFmpeg overlay filter.
- **Audio Mixing**: Background music loop (`-stream_loop -1`) mixed with video audio using `amix=inputs=2:duration=first:dropout_transition=2`.
- **Concurrency Gate**: Protected by `render_gate = asyncio.Semaphore(1)`. All arguments passed as direct arrays to `subprocess.run` (no shell execution).

### 3.4 Frontend Studio Architecture (`frontend/src/`)
- **Landing Page (`Landing.tsx`)**: Frosted folder lookbook UI highlighting business categories (beauty, florist, food, retail).
- **Studio Workstation (`App.tsx`, `Timeline.tsx`, `GeneratePanel.tsx`, `VoiceButton.tsx`)**:
  - **Left Bin (`Your media`)**: Media upload with preview cards, reorder badges, trim badges, and clip audio toggle.
  - **Center Cinema Stage**: 9:16 responsive HTML5 video player with custom transport scrubber, playback speed controls, and fullscreen toggle.
  - **Bottom Timeline (`Timeline.tsx`)**: 3-track non-linear editor timeline (Video/Photos Track with draggable/reorderable thumbnails, Overlay Track, Audio Track).
  - **Right Inspector Tabs**:
    - `Voice Director`: Active microphone recording and real-time execution feedback.
    - `Text`: Banner, offer, subtitle, and placement controls.
    - `Audio`: BGM volume, track selection, clip audio mute.
    - `Look`: Fit mode (`cover`/`contain`), zoom (`smooth`/`none`), brightness sliders.
    - `Trim`: Visual clip start/end trim sliders.
    - `AI Ad`: Gemini Omni cloud video prompt generator (when key is active).

### 3.5 Optional Gemini Cloud Generation (`backend/app/generation.py`)
- Target: `gemini-omni-1.2-flash` via `https://generativelanguage.googleapis.com/v1beta/interactions`.
- Enabled only if `GEMINI_API_KEY` is supplied in environment.
- Asynchronous task model: Submits prompt + up to 2 reference photos, polls background task until MP4 is generated, bounded to a maximum file size of 100 MB.

---

## 4. Environment Variables Reference

| Variable | Default | Purpose |
|---|---|---|
| `SOLLICUT_PORT` | `8080` (use `8088` if 8080 occupied) | Host port exposed by Docker Compose |
| `SOLLICUT_DATA_DIR` | `/data` | Path to persistent volume for projects & renders |
| `SOLLICUT_ASR_ENGINE` | `faster-whisper` | Speech engine provider |
| `SOLLICUT_ASR_MODEL` | `base` | Model size (`tiny`, `base`, `small`, `medium`) |
| `SOLLICUT_ASR_DEVICE` | `cpu` | Device for inference (`cpu`, `cuda`) |
| `SOLLICUT_ASR_COMPUTE_TYPE` | `int8` | Quantization type (`int8`, `float16`, `float32`) |
| `SOLLICUT_MODEL_DIR` | `/models` | Directory holding offline Whisper model assets |
| `GEMINI_API_KEY` | *(empty)* | Optional Google AI Studio API key for Gemini Omni |
| `SOLLICUT_VIDEO_MODEL` | `gemini-omni-1.2-flash` | Gemini model name for generative cloud video ads |

---

## 5. Development, Testing & Verification Commands

### Docker Commands
```bash
# Start container (using port 8088 to avoid port conflicts)
$env:SOLLICUT_PORT="8088"; docker compose up -d

# View container logs
docker logs -f sollicut-sollicut-1

# Execute backend test suite inside container
docker compose exec -T sollicut python -m pytest tests/backend -q

# Run automated smoke test
docker compose exec -T sollicut python scripts/smoke_test.py
```

### Local Frontend Development
```bash
cd frontend
npm install
npm test
npm run build
```

---

## 6. Critical Guidelines for Future Agents
1. **Speech Pipeline Decoupling**: Do not bind speech recognition directly to fuzzy LLM prompting. Keep the raw transcript traceable and process it through test-covered deterministic parsing rules (`backend/app/parser.py` and `tests/backend/test_parser.py`).
2. **Text Shaping Constraints**: Always verify Tamil rendering with Pillow using `libraqm`. Standard Pillow without Raqm will render disjointed, unshaped Tamil characters.
3. **Audio Deletion Guarantee**: Respect user privacy; never persist voice recording WAV/WebM files beyond the transcription request lifecycle.
4. **Port Sensitivity**: Windows hosts often have port 8080 bound by system services or proxies. Always verify availability or default to `SOLLICUT_PORT=8088`.
5. **No Shell Injections**: Keep FFmpeg argument construction as discrete lists passed to `subprocess.run(..., shell=False)`. Never evaluate shell strings for media operations.
