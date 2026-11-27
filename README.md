# SolliCut
Speak it. Cut it. Sell it.

Voice-first promotional reel studio for Tamil/Tanglish/English small businesses — retailers, boutiques, florists, beauty professionals, home kitchens, bakeries and other local sellers.

```sh
git clone https://github.com/Kanishkar843/sollicut.git
cd sollicut
docker compose up --build
```

Open http://localhost:8080 for the campaign lookbook landing page, then open **Open studio** (`http://localhost:8080/#studio`). No `.env` or API key is needed for core editing. The first build downloads dependencies and public Whisper base weights; allow several minutes and sufficient disk space. Model acquisition failure leaves the UI usable with an explicit speech-unavailable notice. Rebuild with network access to enable speech.

Upload 1–5 photos or video clips (`Your media`), press the microphone, speak, and press again to finish:

> Indha photos ellathayum use panni oru 15 seconds Instagram reel create pannu. Smooth zoom effects podu. Background music add pannu. Last la 20 percent offer nu text podu.

Then say: “Offer ah 25 percent nu maathu. Background music konjam kammi pannu.” Use the studio preview transport, 3-track timeline, and inspector tabs (`Text`, `Audio`, `Look`, `Trim`, `AI Ad`), or undo and download your 9:16 MP4.

## Implemented

- **Landing & Dark Studio UX**: Frosted Folder Lookbook landing page (`/`), electric-lime dark studio (`#studio`) with live `<video>` transport controls, `Your media` library, 3-track interactive timeline, and inspector controls (`Text`, `Audio`, `Look`, `Trim`, `AI Ad`).
- **Voice & Local ASR**: Real browser `MediaRecorder` capture, local `faster-whisper` (`base`, CPU `int8`), deterministic Tamil/Tanglish/English multi-operation parser (no `max(3, ...)` count workaround; supports 1–5 media items, clip trim, clip reorder, clip audio mixing, fit mode, zoom, brightness, music, and overlays).
- **Rendering & Undo**: Validated photo (JPEG/PNG/WebP), video (MP4/MOV/WebM), and music (WAV/MP3/M4A/OGG) uploads; FFmpeg 720×1280 H.264/AAC rendering; Pillow + `libraqm` Tamil shaping (`Noto Sans Tamil`); non-destructive revision snapshots, undo (including clip order/trim), download, and project deletion.
- **Optional Gemini Cloud Ad Panel**: Prepared against `gemini-omni-1.2-flash` (`POST /v1beta/interactions`) using bounded background jobs, `9:16` / `3–15s` schema, and prompt review before sending. Clearly displays **Key not set** without `GEMINI_API_KEY`; core editing remains keyless.

See [architecture](docs/ARCHITECTURE.md) and [video generation notes](docs/VIDEO_GENERATION.md).

## Verification

```sh
docker compose exec -T sollicut python -m pytest tests/backend -q
sh scripts/smoke_test.sh
cd frontend && npm ci && npm test && npm run build
```

See [test results](docs/TEST_RESULTS.md), [manual voice benchmark](docs/ASR_BENCHMARK.md), and `scripts/fresh_clone_test.sh`. Tested on Docker/Linux Python 3.11.18, Node 22.23.5, FFmpeg 5.1.9. Native Windows Pillow lacked `libraqm`; use Docker for the supported rendering environment.

This development host required its trusted corporate CA bundle for initial package downloads. An optional BuildKit secret `corporate_ca` is supported; ordinary networks need no certificate configuration. TLS verification is never disabled.

## Configuration and privacy

- **Default ASR**: `base`, CPU, `int8`. Set `SOLLICUT_ASR_MODEL=small` before rebuilding to evaluate `small`; no accuracy improvement is claimed.
- **Optional Gemini API**: Set `GEMINI_API_KEY` in an untracked root `.env` to enable the `AI Ad` tab (`SOLLICUT_VIDEO_MODEL` defaults to `gemini-omni-1.2-flash`). Never commit `.env` or put keys in frontend code.
- **Storage & Privacy**: Docker storage uses the `sollicut_data` named volume at `/data`. Recordings are deleted immediately after transcription; uploaded media, edit transcripts, and renders stay on the server until **New reel** deletes the project. See [privacy and limits](docs/PRIVACY.md). Remote hosting requires HTTPS for microphone capture and separate authentication hardening.

Deferred: frame-accurate multi-layer compositing, user accounts, payments, cloud storage, additional Indian languages, and live Gemini key verification.

## Submission package

- [Pitch PDF](pitch/SolliCut_Pitch.pdf), with selectable text and generator
- [2:45 demo script](docs/DEMO_SCRIPT.md)
- [Submission checklist](docs/SUBMISSION_CHECKLIST.md)
- [AI assistance disclosure](docs/AI_ASSISTANCE.md)
- [Dependency licenses](THIRD_PARTY_NOTICES.md)

Deadline supplied by participant: **30 November 2026, 11:59 pm IST; verify year/time zone and cutoff against the authenticated Round 2 dashboard.** The public page currently differs. Real human microphone/Tanglish acceptance, independent-person clone, YouTube publication, and final submission remain participant tasks.
