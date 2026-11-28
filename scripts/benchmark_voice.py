"""
scripts/benchmark_voice.py — Voice & NLU benchmarking harness (Phase 10).

Evaluates:
  1. NLU parser accuracy across all 100 synthetic evaluation cases in
     tests/fixtures/voice_manifest.json (labeled NOT_HUMAN).
  2. Real ASR Word Error Rate (WER) & Character Error Rate (CER) per engine
     and per mode on TTS-synthesized audio (Windows SAPI, labeled NOT_HUMAN)
     when local ASR weights are present and --with-asr is supplied.

Privacy: all temporary TTS audio is generated in a TemporaryDirectory and deleted immediately.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np

from backend.app.parser import parse
from backend.app.speech import SAMPLE_RATE, DualSpeechRouter

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "voice_manifest.json"


def _tokenize_words(text: str) -> list[str]:
    clean = re.sub(r"[^\w\s%]", " ", text.lower())
    return [t for t in clean.split() if t]


def _edit_distance(seq_a: list[str] | str, seq_b: list[str] | str) -> int:
    n, m = len(seq_a), len(seq_b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        ai = seq_a[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ai == seq_b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[m]


def compute_wer(reference: str, hypothesis: str) -> float:
    """Compute standard Word Error Rate (Levenshtein on normalized words)."""
    ref_words = _tokenize_words(reference)
    hyp_words = _tokenize_words(hypothesis)
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    return round(_edit_distance(ref_words, hyp_words) / len(ref_words), 4)


def compute_cer(reference: str, hypothesis: str) -> float:
    """Compute Character Error Rate (useful for Tamil script comparison)."""
    ref_chars = re.sub(r"\s+", "", reference.lower())
    hyp_chars = re.sub(r"\s+", "", hypothesis.lower())
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    return round(_edit_distance(ref_chars, hyp_chars) / len(ref_chars), 4)


def load_manifest(path: Path = DEFAULT_MANIFEST) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["cases"] if isinstance(data, dict) else data


def evaluate_nlu_manifest(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run deterministic parser benchmark against all manifest cases."""
    total = len(cases)
    exact_matches = 0
    by_mode: dict[str, dict[str, int]] = {}
    failures: list[dict[str, Any]] = []

    for case in cases:
        mode = case["mode"]
        by_mode.setdefault(mode, {"total": 0, "passed": 0})
        by_mode[mode]["total"] += 1

        media_count = case.get("media_count", 3)
        has_reel = case.get("has_reel", True)
        parsed = parse(case["utterance"], media_count=media_count, has_reel=has_reel)
        got_ops = [op.type for op in parsed.operations]
        expected_ops = case["expected_ops"]
        expected_clar = bool(case.get("requires_clarification", False))

        ok = (parsed.requires_clarification == expected_clar) and (
            got_ops == expected_ops if not expected_clar else True
        )
        if ok:
            exact_matches += 1
            by_mode[mode]["passed"] += 1
        else:
            failures.append({
                "id": case["id"],
                "mode": mode,
                "utterance": case["utterance"],
                "expected_ops": expected_ops,
                "got_ops": got_ops,
                "expected_clar": expected_clar,
                "got_clar": parsed.requires_clarification,
            })

    return {
        "source": "NOT_HUMAN",
        "total_cases": total,
        "exact_matches": exact_matches,
        "nlu_accuracy_pct": round(100.0 * exact_matches / max(1, total), 2),
        "by_mode": by_mode,
        "failures": failures,
    }


def _synthesize_batch_tts(utterances: list[tuple[str, str]], out_dir: Path) -> dict[str, np.ndarray]:
    """Synthesize synthetic English/Tanglish WAVs via Windows SAPI in a single batch (NOT_HUMAN)."""
    if sys.platform != "win32" or not utterances:
        return {}
    lines = ["Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"]
    targets: list[tuple[str, Path]] = []
    for cid, text in utterances:
        wav_path = out_dir / f"{cid}.wav"
        safe_text = text.replace("'", "''").replace('"', "")
        lines.append(f"$s.SetOutputToWaveFile('{wav_path}'); $s.Speak('{safe_text}');")
        targets.append((cid, wav_path))
    lines.append("$s.Dispose()")

    script_path = out_dir / "synth.ps1"
    script_path.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
        check=True,
        capture_output=True,
        timeout=60,
    )

    buffers: dict[str, np.ndarray] = {}
    for cid, wav_path in targets:
        if not wav_path.is_file():
            continue
        with wave.open(str(wav_path), "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            rate = wf.getframerate()
            ch = wf.getnchannels()
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if ch > 1:
            arr = arr.reshape(-1, ch).mean(axis=1)
        if rate != SAMPLE_RATE and len(arr) > 1:
            idx = np.linspace(0, len(arr) - 1, int(len(arr) * SAMPLE_RATE / rate))
            arr = np.interp(idx, np.arange(len(arr)), arr).astype(np.float32)
        buffers[cid] = np.ascontiguousarray(arr, dtype=np.float32)
    return buffers


def evaluate_asr_tts(cases: list[dict[str, Any]], max_per_mode: int = 10) -> dict[str, Any]:
    """Run real ASR WER/CER measurement on SAPI TTS audio (English/Tanglish Latin) labeled NOT_HUMAN."""
    router = DualSpeechRouter()
    router.initialize()
    if router.status != "ready":
        return {"status": "unavailable", "reason": router.error}

    selected: list[dict[str, Any]] = []
    counts = {"en": 0, "tanglish": 0}
    for c in cases:
        m = c["mode"]
        if m in counts and not c.get("requires_clarification") and counts[m] < max_per_mode:
            # SAPI default en voice can only voice Latin script reasonably
            if not any("\u0b80" <= ch <= "\u0bff" for ch in c["utterance"]):
                selected.append(c)
                counts[m] += 1

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        buffers = _synthesize_batch_tts([(c["id"], c["utterance"]) for c in selected], tmp_dir)
        if not buffers:
            return {"status": "skipped", "reason": "Local TTS synthesizer unavailable on this platform"}

        results_by_mode: dict[str, list[dict[str, Any]]] = {"en": [], "tanglish": []}
        per_engine: dict[str, dict[str, list[float]]] = {
            "faster-whisper": {"en_wer": [], "en_cer": [], "tanglish_wer": [], "tanglish_cer": []},
            "indicconformer-ta": {"ta_cer": [], "tanglish_cer": []},
        }
        for c in selected:
            pcm = buffers.get(c["id"])
            if pcm is None:
                continue
            mode = c["mode"]
            try:
                dual = asyncio.run(router.transcribe_pcm(pcm, mode=mode))
                hyp = dual.primary_text
                wer = compute_wer(c["utterance"], hyp)
                cer = compute_cer(c["utterance"], hyp)
                engines = dual.engines_used
                if dual.english_transcript is not None:
                    per_engine["faster-whisper"][f"{mode}_wer"].append(
                        compute_wer(c["utterance"], dual.english_transcript)
                    )
                    per_engine["faster-whisper"][f"{mode}_cer"].append(
                        compute_cer(c["utterance"], dual.english_transcript)
                    )
                if dual.tamil_transcript is not None and mode == "tanglish":
                    # Phonetic transliteration baseline — tracked separately via CER
                    per_engine["indicconformer-ta"]["tanglish_cer"].append(
                        compute_cer(c["utterance"], dual.tamil_transcript)
                    )
            except ValueError:
                hyp = ""
                wer = 1.0
                cer = 1.0
                engines = []
            results_by_mode[mode].append({
                "id": c["id"],
                "ref": c["utterance"],
                "hyp": hyp,
                "wer": wer,
                "cer": cer,
                "engines": engines,
            })

    engine_summary: dict[str, dict[str, Any]] = {}
    for eng, metrics in per_engine.items():
        engine_summary[eng] = {
            k: round(sum(vals) / len(vals), 4) if vals else "NEEDS_HUMAN_VERIFICATION"
            for k, vals in metrics.items()
        }

    summary: dict[str, Any] = {
        "source": "NOT_HUMAN (Windows SAPI en-US TTS — Tamil native accent NEEDS HUMAN VERIFICATION)",
        "whisper_status": router.whisper.status,
        "indic_status": router.indic.status,
        "per_engine": engine_summary,
        "modes": {},
    }
    for mode, items in results_by_mode.items():
        if not items:
            continue
        avg_wer = round(sum(x["wer"] for x in items) / len(items), 4)
        avg_cer = round(sum(x["cer"] for x in items) / len(items), 4)
        summary["modes"][mode] = {
            "count": len(items),
            "avg_wer": avg_wer,
            "avg_cer": avg_cer,
            "samples": items[:3],
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--with-asr", action="store_true")
    parser.add_argument("--max-per-mode", type=int, default=8)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    cases = load_manifest(args.manifest)
    report: dict[str, Any] = {"nlu": evaluate_nlu_manifest(cases)}
    if args.with_asr:
        report["asr_tts"] = evaluate_asr_tts(cases, max_per_mode=args.max_per_mode)

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
