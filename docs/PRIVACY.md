# Privacy and prototype limits

Photos and audio are processed by the SolliCut server. On a remote host they leave the user's device. No cloud AI API is used. Model weights are downloaded at build time. Recordings are deleted after transcription, including failure paths. Transcripts remain in project edit history. Photos and renders remain in the Docker volume until New reel deletes the project.

Limits: 3-5 photos, 15 MB per photo, 50 megapixels before normalization, 20 MB / 30 seconds per voice command, 100 characters per overlay, 500 MB per project. Music uploads are limited to 20 MB and 5 minutes. Only upload music you may use.

This is a single-user localhost prototype, without accounts or authentication. Compose binds localhost. Do not expose it as a public multi-user service without authentication, rate limits and storage isolation. Remote microphone use requires HTTPS. UUIDs prevent accidental path traversal, not unauthorized access by someone who knows the ID.
