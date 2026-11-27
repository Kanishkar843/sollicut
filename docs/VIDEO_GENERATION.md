# Optional Gemini advertisement generation

The landing page uses the participant-supplied Frosted Folder Lookbook component, customized for SolliCut. The local editor accepts photos and MP4/MOV/WebM video clips. Video clips are fitted to vertical output, looped or cut to their equal share of the requested duration; source clip audio is replaced with the selected music bed. This is not yet a full frame-level timeline editor.

The separate generation panel records the real microphone, transcribes locally, and asks the user to review before sending the prompt to Google. Set GEMINI_API_KEY in an untracked root .env, then recreate Compose. Never place keys in frontend code or commit .env. SOLLICUT_VIDEO_MODEL defaults to gemini-omni-1.2-flash.

Adapter implemented against Google's current REST Interactions documentation: https://aistudio.google.com/docs/omni.md (accessed 27 November 2026). The older Veo preview API has been shut down according to https://aistudio.google.com/docs/video. Requests carry the key in a header; model-output video is decoded from the steps array and probed before committing a revision. Missing keys produce an explicit error. Provider access, billing, generation quality and end-to-end cloud output remain unverified until a key is supplied. Mock adapter tests are not evidence of live generation.

Human microphone acceptance is still required. Automated tests cannot establish performance with the participant's laptop microphone or Tamil/Tanglish accent.
