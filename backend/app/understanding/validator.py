"""
backend/app/understanding/validator.py — Typed operation validator (V2 Phase 7)

Validates operations against project state before execution.
Returns structured {valid, errors[], warnings[]} for each operation.

Prevents:
  - Trim > clip duration (silent bad trim → now explicit error)
  - Invalid clip index (index >= number of clips)
  - Out-of-range values (e.g. brightness > 1.0)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_operation(
    op: dict[str, Any],
    project_state: dict[str, Any] | None = None,
) -> ValidationResult:
    """
    Validate a single operation dict against optional project state.

    op: {"id": ..., "type": ..., "parameters": {...}}
    project_state: simplified dict with keys:
      - "num_clips": int
      - "clip_durations": list[float | None]  (None = unknown)
    """
    op_type = op.get("type", "")
    params = op.get("parameters", {})
    errors: list[str] = []
    warnings: list[str] = []

    # --- trim_clip ---
    if op_type == "trim_clip":
        clip_index = params.get("clip_index", 0)
        trim_end = params.get("trim_end")

        if project_state:
            num_clips = project_state.get("num_clips", 0)
            if clip_index == -1:
                clip_index = num_clips - 1  # resolve "last"
            if num_clips > 0 and (clip_index < 0 or clip_index >= num_clips):
                errors.append(
                    f"Clip index {clip_index + 1} is out of range "
                    f"(project has {num_clips} clip{'s' if num_clips != 1 else ''})."
                )
            if trim_end is not None:
                durations = project_state.get("clip_durations", [])
                if clip_index < len(durations) and durations[clip_index] is not None:
                    if trim_end > durations[clip_index]:
                        errors.append(
                            f"Trim end {trim_end:.1f}s exceeds clip duration "
                            f"{durations[clip_index]:.1f}s for clip {clip_index + 1}."
                        )
        else:
            if trim_end is not None and trim_end <= 0:
                errors.append(f"Trim end must be greater than 0, got {trim_end}.")

    # --- set_brightness ---
    elif op_type == "set_brightness":
        value = params.get("value", 0)
        if not isinstance(value, (int, float)):
            errors.append(f"Brightness value must be a number, got {type(value).__name__}.")
        elif abs(value) > 1.0:
            warnings.append(
                f"Brightness value {value} is outside the recommended range [-1.0, 1.0]."
            )

    # --- set_duration ---
    elif op_type == "set_duration":
        dur = params.get("duration_seconds", 15)
        if not isinstance(dur, (int, float)) or dur <= 0:
            errors.append(f"Duration must be a positive number, got {dur}.")
        elif dur > 300:
            warnings.append(f"Duration {dur}s is very long — reels are typically 15–60 seconds.")

    # --- set_music_volume ---
    elif op_type == "set_music_volume":
        direction = params.get("direction")
        if direction not in ("increase", "decrease"):
            errors.append(f"Music volume direction must be 'increase' or 'decrease', got '{direction}'.")

    # Unknown op type — not an error (may be extension ops)

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_plan(
    operations: list[dict[str, Any]],
    project_state: dict[str, Any] | None = None,
) -> list[ValidationResult]:
    """Validate all operations in a plan. Returns one ValidationResult per op."""
    return [validate_operation(op, project_state) for op in operations]
