"""
backend/app/understanding/clause_parser.py — Clause-aware sentence splitter (V2 Phase 6)

Splits a transcribed command into individual clauses on conjunctions,
while preserving quoted promotional text across clause boundaries.

Tamil/Tanglish conjunctions handled:
  - English: "and", "then", "also", "after that"
  - Tamil: "மேலும்", "பின்னர்", "அதுவும்", "அதுக்கு பிறகு"
  - Tanglish: "approm", "aprom", "apaaram"
"""
from __future__ import annotations

import re

# Conjunctions that signal a new clause
CLAUSE_SPLITTERS = re.compile(
    r"\b(?:"
    r"and then|and also|after that|then also|"
    r"and|then|also|"
    r"மேலும்|பின்னர்|அதுவும்|"
    r"approm|aprom|apaaram"
    r")\b",
    re.IGNORECASE,
)

_QUOTED = re.compile(r'"[^"]*"')


def split_into_clauses(text: str) -> list[str]:
    """
    Split text into individual command clauses.

    Quoted strings are never split, even if they contain conjunctions.
    Returns a list of non-empty stripped clause strings.

    Examples:
      "zoom and add text" → ["zoom", "add text"]
      'add "offer and discount" text' → ['add "offer and discount" text']
    """
    if not text:
        return []

    # Mask quoted strings to prevent splitting inside them
    masked_quotes: list[str] = []

    def _mask_quote(m: re.Match) -> str:
        idx = len(masked_quotes)
        masked_quotes.append(m.group(0))
        return f"\x00Q{idx}\x00"

    masked = _QUOTED.sub(_mask_quote, text)

    # Split on conjunctions
    parts = CLAUSE_SPLITTERS.split(masked)

    # Restore masked quotes and clean up
    result: list[str] = []
    for part in parts:
        for i, orig in enumerate(masked_quotes):
            part = part.replace(f"\x00Q{i}\x00", orig)
        part = part.strip()
        if part:
            result.append(part)

    return result if result else [text.strip()]
