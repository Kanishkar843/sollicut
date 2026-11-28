"""
backend/app/understanding/operation_planner.py — Multi-operation planner (V2 Phase 6)

Converts a list of IntentResult objects into a list of operations.
Key fix over V1: multiple trim operations on different clips are NOT collapsed
(V1 parser stored operations in a dict keyed by op.type → only last trim survived).

Returns a PlanResult with:
  - operations: list of {id, type, parameters} dicts
  - requires_clarification: True if any intent is 'unknown'
  - clarification_question: human-readable question for the user
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .intent_parser import IntentResult


@dataclass
class PlanResult:
    operations: list[dict[str, Any]] = field(default_factory=list)
    requires_clarification: bool = False
    clarification_question: str | None = None
    warnings: list[str] = field(default_factory=list)
    language_mode: str = "en"


def plan_operations(
    intents: list[IntentResult],
    language_mode: str = "en",
) -> PlanResult:
    """
    Convert classified intents to executable operations.

    Rules:
      - Each intent produces one operation dict with a unique UUID id
      - Multiple trim ops → multiple separate operations (not collapsed)
      - 'unknown' intent → requires_clarification = True
      - Confident ops before unknown still included (partial execution request)
    """
    operations: list[dict[str, Any]] = []
    requires_clarification = False
    clarification_parts: list[str] = []
    warnings: list[str] = []

    for intent in intents:
        if intent.intent == "unknown":
            requires_clarification = True
            clarification_parts.append(
                f"I didn't understand: '{intent.raw_clause}'. "
                "Could you rephrase that part?"
            )
            continue

        if intent.confidence < 0.4:
            requires_clarification = True
            clarification_parts.append(
                f"I'm not sure what you mean by '{intent.raw_clause}'. "
                "Could you be more specific?"
            )
            continue

        operations.append({
            "id": str(uuid.uuid4()),
            "type": intent.intent,
            "parameters": intent.parameters,
        })

    clarification_question = " ".join(clarification_parts) if clarification_parts else None

    return PlanResult(
        operations=operations,
        requires_clarification=requires_clarification,
        clarification_question=clarification_question,
        warnings=warnings,
        language_mode=language_mode,
    )
