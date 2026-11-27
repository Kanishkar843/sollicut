# SolliCut pitch content

SolliCut

LIVELIHOODS AND SMALL BUSINESS

Your products. Your words.

Speak it. Cut it. Sell it.  |  Round 2 prototype

01 / 07

Speak it.
Cut it. Sell it.

Voice-first promotional video creation
for India's micro-businesses.

Tamil / Tanglish / English

Real photos. Local speech recognition.
Actual downloadable MP4.

SolliCut

PROBLEM AND SOLUTION

Creative intent should not need a timeline.

Speak it. Cut it. Sell it.  |  Round 2 prototype

02 / 07

The problem

A small seller has product photos and an offer. Making a reel still asks them to learn timelines, keyframes and editing controls.

The solution

Say the creative instruction in a comfortable language. SolliCut maps it to validated edits and renders the seller's own photos.

Programmatic video creation. No diffusion model, no paid AI key, no invented footage.

SolliCut

USERS AND WORKFLOW

A home baker's next offer reel.

Speak it. Cut it. Sell it.  |  Round 2 prototype

03 / 07

Initial users: home bakers, boutiques, florists, local retailers and beauty professionals in Tamil Nadu.

"Indha photos ellathayum use panni oru 15 seconds Instagram reel create pannu. Smooth zoom effects podu. Background music add pannu. Last la 20 percent offer nu text podu."

Upload 3-5 photos

Speak your idea

Preview the reel

Say another edit

Undo / download

Follow-up: change the offer to 25 percent and reduce the background music.

SolliCut

MARKET CONTEXT

A large universe. A deliberately small pilot.

Speak it. Cut it. Sell it.  |  Round 2 prototype

04 / 07

6.05 million

Tamil Nadu enterprise registrations
including informal micro enterprises on UAP

ILLUSTRATIVE SCENARIOS

5% with recurring reel needs: ~302,552

20% of that group reachable: ~60,510

Registration counts are upper-bound context, not customer counts. The 5% and 20% rates are planning assumptions, not measured demand.

Pilot goal: 1,000 active businesses. Start by observing 20-30 sellers.

Source: Ministry of MSME Annual Report 2025-26, Table 3.2, printed p.35; as of 31 Jan 2026. Accessed 27 Nov 2026.

SolliCut

TECHNOLOGY AND DEPENDENCIES

Local by default. Replaceable where it matters.

Speak it. Cut it. Sell it.  |  Round 2 prototype

05 / 07

MediaRecorder  /  faster-whisper + CTranslate2 CPU INT8  /  deterministic parser
FastAPI  /  FFmpeg  /  Pillow + libraqm + Noto Sans Tamil  /  React  /  Docker Compose

API prices rise or cloud services fail

Core speech and rendering need no hosted AI API.

Tamil / Tanglish recognition varies

Benchmark real voices; ask for clarification. Replace the speech engine if needed.

CPU processing takes too long

Short commands, 720p reels and one render at a time; measure on actual hardware.

Alternative engine needed

Evaluate AI4Bharat / Bodhan; review model terms. Hosted BHASHINI needs credentials.

No accuracy or real-time performance claim is made without a project-specific benchmark.

SolliCut

LAUNCH AND GROWTH

Learn the language of the first 30 sellers.

Speak it. Cut it. Sell it.  |  Round 2 prototype

06 / 07

OBSERVE

20-30 Tamil-speaking home businesses

Recruit through personal outreach and local seller / creator communities. Watch natural commands and record consented failures.

REFINE

Turn repeated needs into reliable edits

Measure intent success, repeat use and time to a usable reel. Add bakery, boutique and beauty templates after the core is reliable.

EXPAND

Reach 1,000 active pilot businesses

Approach seller networks, entrepreneurship cells and digital-marketing trainers. These are planned channels, not claimed partnerships.

Growth hypothesis: shared reels bring other sellers. Test an optional Made with SolliCut end card later. Expand languages only after demand and ASR validation.

SolliCut

ROUND 2 PROTOTYPE

One honest end-to-end demonstration.

Speak it. Cut it. Sell it.  |  Round 2 prototype

07 / 07

Verified in automated tests

Multilingual command parsing
Validated uploads and project storage
Real vertical H.264 / AAC MP4 rendering
Tamil overlay generation with libraqm
Undo state and UI controls

Still needs human acceptance

Real browser microphone + participant voice
Tanglish intent success benchmark
Independent person's fresh clone
Public/unlisted demo under 3 minutes

Deferred: advanced timelines, video trimming, accounts, payments, diffusion video generation and additional languages.

Submission cutoff supplied by participant: 30 Nov 2026, 11:59 pm IST. VERIFY in the authenticated dashboard; the public page currently differs.

github.com/Kanishkar843/sollicut  |  AI assistance disclosed in docs/AI_ASSISTANCE.md