"""
tests/voice/test_voice_benchmark.py — Phase 10 benchmarking framework tests.

Validates:
  - Manifest contains 100 cases, all labeled source='NOT_HUMAN'
  - WER and CER metric computations
  - All 100 cases pass NLU evaluation through scripts/benchmark_voice.py
"""
from scripts.benchmark_voice import (
    DEFAULT_MANIFEST,
    compute_cer,
    compute_wer,
    evaluate_nlu_manifest,
    load_manifest,
)


def test_wer_and_cer_calculations():
    assert compute_wer("create a 15 seconds reel", "Create a 15 seconds reel.") == 0.0
    assert compute_wer("create a 15 seconds reel", "make a 15 seconds reel") == 0.2
    assert compute_wer("hello", "") == 1.0
    assert compute_wer("", "") == 0.0

    assert compute_cer("இன்று 20% ஆஃபர்", "இன்று 20% ஆஃபர்") == 0.0
    assert 0.0 < compute_cer("இன்று", "இன்") < 1.0


def test_manifest_has_100_cases_all_labeled_not_human():
    cases = load_manifest(DEFAULT_MANIFEST)
    assert len(cases) == 100
    assert all(c.get("source") == "NOT_HUMAN" for c in cases)
    modes = {c["mode"] for c in cases}
    assert modes == {"en", "tanglish", "ta"}
    ids = [c["id"] for c in cases]
    assert len(set(ids)) == 100


def test_nlu_benchmark_passes_all_100_cases():
    cases = load_manifest(DEFAULT_MANIFEST)
    report = evaluate_nlu_manifest(cases)
    assert report["source"] == "NOT_HUMAN"
    assert report["total_cases"] == 100
    assert report["failures"] == [], f"Failures: {report['failures']}"
    assert report["nlu_accuracy_pct"] == 100.0
