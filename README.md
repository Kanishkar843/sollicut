# SolliCut
Speak it. Cut it. Sell it.

Voice-first promotional reel creation for Tamil/Tanglish/English micro-business owners.

```sh
git clone https://github.com/Kanishkar843/sollicut.git
cd sollicut
docker compose up --build
```

Open http://localhost:8080. No .env or API key is needed. The first build downloads dependencies and public Whisper base weights; allow several minutes and sufficient disk space. Model acquisition failure leaves the screen usable with an explicit speech-unavailable notice. Rebuild with network access to enable speech.

Upload 3-5 photos, press the microphone, speak, and press again to finish:

> Indha photos ellathayum use panni oru 15 seconds Instagram reel create pannu. Smooth zoom effects podu. Background music add pannu. Last la 20 percent offer nu text podu.

Then say: “Offer ah 25 percent nu maathu. Background music konjam kammi pannu.” Preview, undo and download. Real human microphone/Tanglish acceptance remains to be completed; automated rendering tests are not a substitute.

## Implemented

Real MediaRecorder capture, local faster-whisper, deterministic multi-operation parser, validated photo/music uploads, 720×1280 H.264/AAC rendering, smooth zoom, shaped Tamil text, revision undo, download and project deletion. See [architecture](docs/ARCHITECTURE.md).

## Verification

```sh
docker compose exec -T sollicut python -m pytest tests/backend -q
sh scripts/smoke_test.sh
cd frontend
npm ci
npm test
npm run build
```

See [test results](docs/TEST_RESULTS.md), [manual voice benchmark](docs/ASR_BENCHMARK.md), and scripts/fresh_clone_test.sh. Tested: Docker 29.9.3, Linux Python 3.11.18, Node 22.23.5, FFmpeg 5.1.9. Exact Python dependencies and npm dependency graph are locked. Native Windows Pillow lacked libraqm; use Docker for the supported rendering environment.

This development host required its trusted corporate CA bundle for initial package downloads. An optional BuildKit secret `corporate_ca` is supported; ordinary networks need no certificate configuration. TLS verification is never disabled.

## Configuration and privacy

Default ASR: base, CPU, int8. Set SOLLICUT_ASR_MODEL=small before rebuilding to evaluate small; no accuracy improvement is claimed. SOLLICUT_PORT controls the localhost port. Docker storage is the sollicut_data named volume at /data. Recordings are removed after transcription; source photos, edit transcripts and renders persist until New reel deletes the project. See [privacy and limits](docs/PRIVACY.md). Remote hosting requires HTTPS for microphone capture and separate authentication hardening.

Deferred: advanced video timelines, trimming, accounts, payments, cloud storage, additional languages and generative video models.

## Submission package

- [Pitch PDF](pitch/SolliCut_Pitch.pdf), with selectable text and generator
- [2:45 demo script](docs/DEMO_SCRIPT.md)
- [Submission checklist](docs/SUBMISSION_CHECKLIST.md)
- [AI assistance disclosure](docs/AI_ASSISTANCE.md)
- [Dependency licenses](THIRD_PARTY_NOTICES.md)

Deadline supplied by participant: **30 November 2026, 11:59 pm IST; verify year/time zone and cutoff against the authenticated Round 2 dashboard.** The public page currently differs. YouTube publication and final submission remain participant tasks.
