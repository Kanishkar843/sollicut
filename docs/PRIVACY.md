# Privacy and prototype limits

Uploaded photos, video clips, music, and voice commands are processed locally by this SolliCut server. On a remote host they leave the user's device. No cloud AI API is used for core voice editing or video rendering. Whisper model weights are downloaded at Docker build time. Voice recordings are deleted immediately after transcription, including failure paths. Transcripts remain in project edit history; media and renders remain in the Docker volume until **New reel** deletes the project.

Optional Gemini advertisement generation (`AI Ad` tab) is inactive by default (`Key not set`). Only when the server administrator configures `GEMINI_API_KEY` and the user explicitly reviews and submits a generation prompt does that prompt (and up to 2 optional selected project photos) go to Google's Gemini Interactions API.

Limits: 1–5 media items (photos or video clips), 15 MB per photo (50 megapixels before normalization), 100 MB and 120 seconds per video clip (up to 4K), 20 MB / 30 seconds per voice command, 100 characters per text overlay, 500 MB per project. Music uploads are limited to 20 MB and 5 minutes. Only upload media and music you may use.

This is a single-user localhost prototype without accounts or authentication. Compose binds `127.0.0.1:8080`. Do not expose it as a public multi-user service without authentication, rate limits, and storage isolation. Remote microphone use requires HTTPS. UUIDs prevent accidental path traversal, not unauthorized access by someone who knows a project ID.
