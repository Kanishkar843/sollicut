"""
backend/app/understanding/context_manager.py — Voice command context manager (V2 Phase 7)

Tracks the last N voice commands per project session.
Resolves pronouns ("it", "that clip") from prior context.
Handles "undo last" relative to context.

Privacy: context is in-memory per process; nothing persisted to disk.
         Cleared on process restart or when explicitly reset.
"""
from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("sollicut.understanding.context")

MAX_CONTEXT_ENTRIES = 10

# Pronoun patterns (English + Tamil)
_PRONOUN_PATTERN = re.compile(
    r"\b(?:it|that|this|the\s+(?:last|previous|clip|one)|அது|இது|அந்த)\b",
    re.IGNORECASE,
)


@dataclass
class ContextEntry:
    transcript: str
    operations: list[dict[str, Any]]
    project_id: str


class VoiceContextManager:
    """
    Per-project voice command context.
    One instance per project; stored in a module-level dict.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self._history: deque[ContextEntry] = deque(maxlen=MAX_CONTEXT_ENTRIES)

    def record(self, transcript: str, operations: list[dict[str, Any]]) -> None:
        """Record a successfully executed command."""
        self._history.append(ContextEntry(
            transcript=transcript,
            operations=operations,
            project_id=self.project_id,
        ))

    def resolve_pronouns(self, text: str) -> tuple[str, bool]:
        """
        Replace pronouns in text with explicit references from recent context.
        Returns (resolved_text, was_resolved).

        Strategy:
          - If text contains a pronoun and last command operated on a clip,
            replace pronoun with "clip N" (N = most recently referenced clip index + 1).
          - If no prior context available, return original text with was_resolved=False.
        """
        if not _PRONOUN_PATTERN.search(text):
            return text, False

        last = self._last_clip_reference()
        if last is None:
            logger.debug("Pronoun in '%s' but no prior clip context", text)
            return text, False

        resolved = _PRONOUN_PATTERN.sub(f"clip {last + 1}", text, count=1)
        logger.debug("Resolved pronoun: '%s' → '%s'", text, resolved)
        return resolved, True

    def last_operations(self) -> list[dict[str, Any]]:
        """Return operations from the most recent command."""
        if not self._history:
            return []
        return self._history[-1].operations

    def clear(self) -> None:
        """Clear all context (e.g. on project reset)."""
        self._history.clear()

    def _last_clip_reference(self) -> int | None:
        """Find the clip_index from the most recent trim or similar clip operation."""
        for entry in reversed(self._history):
            for op in reversed(entry.operations):
                if "clip_index" in op.get("parameters", {}):
                    return op["parameters"]["clip_index"]
        return None


# Module-level registry: project_id → VoiceContextManager
_registry: dict[str, VoiceContextManager] = {}


def get_context(project_id: str) -> VoiceContextManager:
    """Get or create a VoiceContextManager for a project."""
    if project_id not in _registry:
        _registry[project_id] = VoiceContextManager(project_id)
    return _registry[project_id]


def clear_context(project_id: str) -> None:
    """Clear and remove context for a project (e.g. on delete)."""
    _registry.pop(project_id, None)
