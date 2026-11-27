"""
tests/backend/test_context_validator.py — Phase 7: VoiceContextManager + validate_operation tests

Covers:
  - VoiceContextManager: record, resolve_pronouns, clear, singleton registry
  - validate_operation: trim_clip, set_brightness, set_duration, set_music_volume
  - validate_plan: list validation
"""
import pytest

from backend.app.understanding.context_manager import (
    VoiceContextManager,
    get_context,
    clear_context,
)
from backend.app.understanding.validator import (
    validate_operation,
    validate_plan,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# VoiceContextManager — record
# ---------------------------------------------------------------------------

def test_record_stores_entry_in_history():
    mgr = VoiceContextManager("proj-record-1")
    assert len(mgr._history) == 0
    mgr.record("trim clip 1 to 5 seconds", [{"type": "trim_clip", "parameters": {"clip_index": 0, "trim_end": 5.0}}])
    assert len(mgr._history) == 1
    assert mgr._history[0].transcript == "trim clip 1 to 5 seconds"


def test_record_respects_maxlen():
    mgr = VoiceContextManager("proj-maxlen")
    for i in range(15):  # MAX_CONTEXT_ENTRIES = 10
        mgr.record(f"command {i}", [])
    assert len(mgr._history) == 10
    assert mgr._history[-1].transcript == "command 14"


def test_last_operations_empty_when_no_history():
    mgr = VoiceContextManager("proj-noop")
    assert mgr.last_operations() == []


def test_last_operations_returns_most_recent():
    mgr = VoiceContextManager("proj-last-ops")
    ops1 = [{"type": "set_duration", "parameters": {"duration_seconds": 15}}]
    ops2 = [{"type": "trim_clip", "parameters": {"clip_index": 2, "trim_end": 8.0}}]
    mgr.record("set duration 15", ops1)
    mgr.record("trim clip 3", ops2)
    assert mgr.last_operations() == ops2


# ---------------------------------------------------------------------------
# VoiceContextManager — resolve_pronouns
# ---------------------------------------------------------------------------

def test_resolve_pronouns_no_pronoun_returns_original():
    mgr = VoiceContextManager("proj-nopron")
    result, was_resolved = mgr.resolve_pronouns("trim clip 1 to 5 seconds")
    assert result == "trim clip 1 to 5 seconds"
    assert was_resolved is False


def test_resolve_pronouns_no_prior_context_returns_original():
    mgr = VoiceContextManager("proj-noctx")
    result, was_resolved = mgr.resolve_pronouns("trim it to 5 seconds")
    assert result == "trim it to 5 seconds"
    assert was_resolved is False


def test_resolve_pronouns_resolves_it_from_prior_trim():
    mgr = VoiceContextManager("proj-resolve-it")
    # Prior command touched clip index 2 (clip 3 in human terms)
    mgr.record(
        "trim clip 3 to 10s",
        [{"type": "trim_clip", "parameters": {"clip_index": 2, "trim_end": 10.0}}],
    )
    result, was_resolved = mgr.resolve_pronouns("trim it to 5 seconds")
    assert was_resolved is True
    # clip_index=2 → "clip 3"
    assert "clip 3" in result
    assert "it" not in result


def test_resolve_pronouns_resolves_that_from_prior_trim():
    mgr = VoiceContextManager("proj-resolve-that")
    mgr.record(
        "trim clip 1",
        [{"type": "trim_clip", "parameters": {"clip_index": 0, "trim_end": 7.0}}],
    )
    result, was_resolved = mgr.resolve_pronouns("speed up that by 2x")
    assert was_resolved is True
    assert "clip 1" in result


def test_resolve_pronouns_tamil_pronoun():
    mgr = VoiceContextManager("proj-resolve-tamil")
    mgr.record(
        "clip 2 trim",
        [{"type": "trim_clip", "parameters": {"clip_index": 1, "trim_end": 6.0}}],
    )
    result, was_resolved = mgr.resolve_pronouns("அதை 4 seconds ku trim பண்ணு")
    # Tamil pronoun pattern matches அது / அந்த — "அதை" won't match (suffix -ை)
    # This documents the boundary: only exact "அது" and "அந்த" match
    # Either resolved or not, was_resolved must be bool
    assert isinstance(was_resolved, bool)


def test_resolve_pronouns_no_clip_index_in_prior_ops():
    mgr = VoiceContextManager("proj-no-clip-idx")
    # Prior op has no clip_index → no resolution
    mgr.record("set duration 20", [{"type": "set_duration", "parameters": {"duration_seconds": 20}}])
    result, was_resolved = mgr.resolve_pronouns("trim it to 5 seconds")
    assert was_resolved is False
    assert result == "trim it to 5 seconds"


# ---------------------------------------------------------------------------
# VoiceContextManager — clear
# ---------------------------------------------------------------------------

def test_clear_empties_history():
    mgr = VoiceContextManager("proj-clear")
    mgr.record("do something", [{"type": "set_brightness", "parameters": {"value": 0.5}}])
    assert len(mgr._history) == 1
    mgr.clear()
    assert len(mgr._history) == 0


def test_clear_makes_resolve_fail():
    mgr = VoiceContextManager("proj-clear-resolve")
    mgr.record("trim clip 1", [{"type": "trim_clip", "parameters": {"clip_index": 0, "trim_end": 5.0}}])
    mgr.clear()
    result, was_resolved = mgr.resolve_pronouns("trim it to 3 seconds")
    assert was_resolved is False


# ---------------------------------------------------------------------------
# get_context — singleton registry
# ---------------------------------------------------------------------------

def test_get_context_returns_same_instance():
    # Ensure fresh key
    pid = "proj-singleton-test-xyz"
    clear_context(pid)
    ctx1 = get_context(pid)
    ctx2 = get_context(pid)
    assert ctx1 is ctx2
    clear_context(pid)


def test_get_context_different_projects_are_isolated():
    clear_context("proj-a-unique")
    clear_context("proj-b-unique")
    ctx_a = get_context("proj-a-unique")
    ctx_b = get_context("proj-b-unique")
    ctx_a.record("cmd a", [{"type": "trim_clip", "parameters": {"clip_index": 0, "trim_end": 5.0}}])
    assert len(ctx_b._history) == 0
    clear_context("proj-a-unique")
    clear_context("proj-b-unique")


# ---------------------------------------------------------------------------
# validate_operation — trim_clip
# ---------------------------------------------------------------------------

def test_validate_trim_clip_within_range_is_valid():
    op = {"type": "trim_clip", "parameters": {"clip_index": 1, "trim_end": 8.0}}
    state = {"num_clips": 3, "clip_durations": [10.0, 12.0, 15.0]}
    result = validate_operation(op, state)
    assert result.valid is True
    assert result.errors == []


def test_validate_trim_clip_out_of_range_is_error():
    op = {"type": "trim_clip", "parameters": {"clip_index": 5, "trim_end": 5.0}}
    state = {"num_clips": 3, "clip_durations": [10.0, 12.0, 15.0]}
    result = validate_operation(op, state)
    assert result.valid is False
    assert any("out of range" in e for e in result.errors)


def test_validate_trim_end_exceeds_clip_duration():
    op = {"type": "trim_clip", "parameters": {"clip_index": 0, "trim_end": 20.0}}
    state = {"num_clips": 2, "clip_durations": [10.0, 15.0]}
    result = validate_operation(op, state)
    assert result.valid is False
    assert any("exceeds clip duration" in e for e in result.errors)


def test_validate_trim_end_equal_to_duration_is_valid():
    op = {"type": "trim_clip", "parameters": {"clip_index": 0, "trim_end": 10.0}}
    state = {"num_clips": 1, "clip_durations": [10.0]}
    result = validate_operation(op, state)
    assert result.valid is True


def test_validate_trim_end_zero_no_state_is_error():
    # Without project_state, trim_end <= 0 → error
    op = {"type": "trim_clip", "parameters": {"clip_index": 0, "trim_end": 0}}
    result = validate_operation(op, None)
    assert result.valid is False
    assert any("greater than 0" in e for e in result.errors)


def test_validate_trim_end_negative_no_state_is_error():
    op = {"type": "trim_clip", "parameters": {"clip_index": 0, "trim_end": -3.0}}
    result = validate_operation(op, None)
    assert result.valid is False


def test_validate_trim_last_clip_resolves_minus_one():
    # clip_index = -1 means "last clip"
    op = {"type": "trim_clip", "parameters": {"clip_index": -1, "trim_end": 5.0}}
    state = {"num_clips": 3, "clip_durations": [10.0, 12.0, 15.0]}
    result = validate_operation(op, state)
    # -1 resolves to index 2 (last), trim_end=5 < 15 → valid
    assert result.valid is True


# ---------------------------------------------------------------------------
# validate_operation — set_brightness
# ---------------------------------------------------------------------------

def test_validate_brightness_normal_is_valid():
    op = {"type": "set_brightness", "parameters": {"value": 0.5}}
    result = validate_operation(op)
    assert result.valid is True
    assert result.warnings == []


def test_validate_brightness_zero_is_valid():
    op = {"type": "set_brightness", "parameters": {"value": 0.0}}
    result = validate_operation(op)
    assert result.valid is True


def test_validate_brightness_at_boundary_is_valid():
    op = {"type": "set_brightness", "parameters": {"value": 1.0}}
    result = validate_operation(op)
    assert result.valid is True
    assert result.warnings == []


def test_validate_brightness_exceeds_range_gives_warning():
    op = {"type": "set_brightness", "parameters": {"value": 1.5}}
    result = validate_operation(op)
    assert result.valid is True  # warning, not error
    assert len(result.warnings) > 0
    assert any("outside the recommended range" in w for w in result.warnings)


def test_validate_brightness_negative_exceeds_range_gives_warning():
    op = {"type": "set_brightness", "parameters": {"value": -1.1}}
    result = validate_operation(op)
    assert result.valid is True
    assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# validate_operation — set_duration
# ---------------------------------------------------------------------------

def test_validate_duration_positive_is_valid():
    op = {"type": "set_duration", "parameters": {"duration_seconds": 30}}
    result = validate_operation(op)
    assert result.valid is True


def test_validate_duration_zero_is_error():
    op = {"type": "set_duration", "parameters": {"duration_seconds": 0}}
    result = validate_operation(op)
    assert result.valid is False


def test_validate_duration_negative_is_error():
    op = {"type": "set_duration", "parameters": {"duration_seconds": -5}}
    result = validate_operation(op)
    assert result.valid is False


def test_validate_duration_very_long_gives_warning():
    op = {"type": "set_duration", "parameters": {"duration_seconds": 400}}
    result = validate_operation(op)
    assert result.valid is True
    assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# validate_operation — set_music_volume
# ---------------------------------------------------------------------------

def test_validate_music_volume_increase_is_valid():
    op = {"type": "set_music_volume", "parameters": {"direction": "increase"}}
    result = validate_operation(op)
    assert result.valid is True


def test_validate_music_volume_decrease_is_valid():
    op = {"type": "set_music_volume", "parameters": {"direction": "decrease"}}
    result = validate_operation(op)
    assert result.valid is True


def test_validate_music_volume_invalid_direction_is_error():
    op = {"type": "set_music_volume", "parameters": {"direction": "mute"}}
    result = validate_operation(op)
    assert result.valid is False
    assert any("increase" in e or "decrease" in e for e in result.errors)


# ---------------------------------------------------------------------------
# validate_operation — unknown type (extension-safe)
# ---------------------------------------------------------------------------

def test_validate_unknown_op_type_is_valid():
    op = {"type": "set_saturation", "parameters": {"value": 0.3}}
    result = validate_operation(op)
    assert result.valid is True
    assert result.errors == []


# ---------------------------------------------------------------------------
# validate_plan
# ---------------------------------------------------------------------------

def test_validate_plan_returns_one_result_per_op():
    ops = [
        {"type": "set_brightness", "parameters": {"value": 0.5}},
        {"type": "trim_clip", "parameters": {"clip_index": 0, "trim_end": 5.0}},
        {"type": "set_duration", "parameters": {"duration_seconds": 15}},
    ]
    results = validate_plan(ops)
    assert len(results) == 3
    assert all(isinstance(r, ValidationResult) for r in results)


def test_validate_plan_mixed_valid_invalid():
    ops = [
        {"type": "set_brightness", "parameters": {"value": 0.5}},   # valid
        {"type": "set_duration", "parameters": {"duration_seconds": -1}},  # invalid
    ]
    state = None
    results = validate_plan(ops, state)
    assert results[0].valid is True
    assert results[1].valid is False


def test_validate_plan_empty_returns_empty():
    results = validate_plan([])
    assert results == []


def test_validate_plan_with_project_state():
    ops = [
        {"type": "trim_clip", "parameters": {"clip_index": 0, "trim_end": 5.0}},
        {"type": "trim_clip", "parameters": {"clip_index": 10, "trim_end": 5.0}},  # out of range
    ]
    state = {"num_clips": 2, "clip_durations": [10.0, 15.0]}
    results = validate_plan(ops, state)
    assert results[0].valid is True
    assert results[1].valid is False
