# SolliCut Voice Intelligence V2 — CPU Profiling Report

> Measured on real hardware using `python -m scripts.profile_voice` · Date: 2026-11-27

## Test Hardware & Environment
- **OS:** Windows 11 (`Windows-11-10.0.26200-SP0`)
- **CPU:** `AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD` (16 logical cores)
- **Python:** `3.14.0` (local) · Docker runtime targets `python:3.11-slim-bookworm`
- **Audio Fixture:** `5.094 s` Windows SAPI synthesized English command (`windows_sapi_tts_NOT_HUMAN`: *"Create a 15 seconds Instagram reel with smooth zoom and background music."*)
- **Measurement Protocol:** 1 warmup pass + 2 timed warm runs per mode; Peak RSS measured via Win32 `K32GetProcessMemoryInfo` (`PeakWorkingSetSize`).

---

## Profile Configurations (`SOLLICUT_PROFILE`)

| Profile | Whisper Model | IndicConformer-TA | VAD | Browser Resampler | Default CPU Threads |
|---|---|---|---|---|---|
| `lightweight` | `small` (INT8) | Enabled (INT8 ONNX) | RMS energy gate | Linear interpolation | 2 |
| `balanced` (default) | `small` (INT8) | Enabled (INT8 ONNX) | Silero VAD v5 ONNX | Kaiser FIR polyphase | 4 |
| `accuracy` | `large-v3-turbo` (INT8) with fallback to `small` | Enabled (INT8 ONNX) | Silero VAD v5 ONNX | Kaiser FIR polyphase | 4 |

---

## Measured Results (Local CPU, Real Timings)

| Metric | `lightweight` (2 threads) | `balanced` (4 threads) | `accuracy` (4 threads, turbo) |
|---|---|---|---|
| **Cold Init Time** | `2.301 s` | `2.228 s` (+ `17.59 ms` Silero VAD) | `NEEDS HUMAN VERIFICATION` (turbo weights ~1.5 GB not installed locally) |
| **Silero VAD (5.094 s buffer)** | Disabled (`RMS gate`) | `0.36 ms` | `0.45 ms` (Silero only) |
| **Peak RSS (Before → After Load)** | `51.88 → 751.10 MiB` (`+699.22 MiB`) | `51.88 → 781.12 MiB` (`+729.24 MiB`) | `NEEDS HUMAN VERIFICATION` (expected ~1.8–2.2 GiB with `large-v3-turbo`; falls back to `small` if absent) |
| **Warm Time — `en` (`faster-whisper`)** | `2.964 s` (`RTF 0.582`) | `2.683 s` (`RTF 0.527`) | `NEEDS HUMAN VERIFICATION` |
| **Warm Time — `ta` (`indicconformer-ta`)** | `0.281 s` (`RTF 0.055`) | `0.207 s` (`RTF 0.041`) | `~0.18–0.21 s` (`RTF ~0.04`) |
| **Warm Time — `tanglish` (Dual-ASR)** | `3.826 s` (`RTF 0.751`) | `2.924 s` (`RTF 0.574`) | `NEEDS HUMAN VERIFICATION` |

> [!NOTE]
> All `accuracy` Whisper `large-v3-turbo` and Docker Linux container (`python:3.11-slim-bookworm`) benchmarks are marked `NEEDS HUMAN VERIFICATION` where weights were not downloaded locally (~1.5 GB model). All `lightweight` and `balanced` values above are direct wall-clock and OS memory measurements from this session.
> Notice that with 4 threads (`balanced`), dual-ASR Tanglish inference on a 5.09 s utterance completes in `2.924 s` (`RTF 0.574`), 24% faster than 2 threads (`3.826 s`), at the cost of only `+30 MiB` additional Peak RSS (`781.12 MiB` vs `751.10 MiB`) for Silero VAD + 4-thread runtime buffers.
