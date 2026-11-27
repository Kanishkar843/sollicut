# Architecture

React/TypeScript/Vite/Tailwind provides upload, MediaRecorder capture, interpretation cards and HTML video playback. FastAPI serves the compiled UI and API from one container. JSON project files are atomically replaced under UUID directories. Images are decoded, EXIF-normalized and fitted without stretching.

Speech uses the public faster-whisper base model, CTranslate2 CPU INT8 and a replaceable SpeechEngine protocol. Initialization runs off the HTTP startup path. Missing models produce an explicit unavailable capability. No fake transcript fallback exists.

The deterministic parser preserves raw transcripts separately, normalizes Unicode and number words, and maps domain vocabulary to validated operations. It returns clarification for unsupported or incomplete edits. No probabilistic confidence is invented.

One render runs at a time. FFmpeg receives argument arrays without shell evaluation. Pillow/libraqm shapes Tamil overlays into PNGs. Source assets and declarative settings survive edits. A successful render commits a new revision; failures preserve the previous state. Undo restores a settings/history snapshot and its already-rendered MP4, avoiding recompression. Ten undo snapshots are retained. Jobs are process-local; after restart reload the project to see the last completed revision.

Alternatives: AI4Bharat IndicConformer offers Tamil recognition but a heavier integration. Bodhan Indic-Transcribe targets code-mixed transcription and requires separate model/license evaluation. BHASHINI hosted adapters require credentials and connectivity. None is a P0 dependency. See PITCH_SOURCES.md for sources accessed 27 November 2026.
