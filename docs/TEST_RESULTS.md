# Executed verification - 27 November 2026

- `docker compose up --build -d --wait --wait-timeout 120`: healthy, no .env/API keys. Initial dependency layers were built with the host's trusted CA supplied as an optional BuildKit secret; the subsequent Compose build reused them.
- `docker compose exec -T sollicut python -m pytest tests/backend -q`: 62 passed in 5.24 seconds. Includes 48 parser cases, storage, upload/error/undo tests, real FFmpeg render and RAQM overlay test.
- `npm run build`: TypeScript and Vite production build passed.
- `npm test`: 6 UI tests passed. Microphone permission tests are mocked, not human speech evidence.
- `python -m scripts.smoke_test`: real HTTP uploads, canonical plan, 15-second render, follow-up render, download, metadata and byte-identical undo passed. Initial render 5.699 seconds; follow-up 5.743 seconds on this machine.
- Public OpenAI Whisper JFK fixture uploaded as WAV through the actual voice endpoint: HTTP 200, real English transcript, ASR 1.261 seconds. Unsupported content correctly requested clarification. Not a Tanglish benchmark.
- Browser inspection: keyless screen loads, four actual demo uploads show thumbnails and enable microphone. Human microphone recording and final video playback are still unverified.
- Tamil overlay: libraqm true; rendered sample inspected visually. Participant fluent-language review remains recommended.
- Pitch: seven pages, required text extracted and verified; page images inspected and layout corrected.

Native Windows renderer tests initially failed because Pillow had no RAQM. Linux Docker tests passed. This is why Docker is the supported runtime.

Not verified: real participant Tanglish/Tamil microphone workflow, audible/visible playback acceptance, independent person's clone, YouTube publication, final hackathon submission. Do not describe the entire P0 checklist as passed.

Fresh-clone attempt: the plain Compose build encountered this host's TLS interception when fetching npm/model dependencies. A fresh-clone build with the optional trusted CA secret was started; independent-person acceptance remains pending. The original application at localhost:8080 remains healthy.

