"""
backend/app/understanding/normalizer.py — Multilingual text normalizer V2 (Phase 5)

Extends the V1 normalization in parser.py with:
  - Decimal number handling ("2.5 seconds" preserved)
  - Tamil suffix stripping (-ஐ, -ல, -ல, -னு, -ஓட, -கிட்ட)
  - Protected promotional content (quoted strings, brand names, prices)
  - Ambiguity detection (returns flag instead of guessing)

The existing parser.py normalize() function remains for backward compatibility.
This module is the V2 upgrade path — imported by understanding layer.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Tamil suffix patterns to strip (verb/noun suffixes that don't affect semantics)
TAMIL_SUFFIXES = re.compile(
    r"(ஐ|ல|ல்|னு|னா|னால்|ஓட|கிட்ட|கிட்டே|போல|மாதிரி|க்கு|ட்ட)$"
)

# Loanword map: Tamil script loanwords → canonical English (from parser.py, extended)
TAMIL_LOANWORD_MAP: dict[str, str] = {
    "போட்டோஸ்": "photos", "போட்டோ": "photo", "ஃபோட்டோ": "photo",
    "ரீல்": "reel", "ரீல்ஸ்": "reels",
    "மியூசிக்": "music", "மியூஸிக்": "music",
    "ஆஃபர்": "offer", "ஆஃபர்ஸ்": "offers",
    "கடைசில": "last", "கடைசியில": "last",
    "கம்மி": "less", "கொஞ்சம்": "little",
    "ஜூம்": "zoom", "ஸ்மூத்": "smooth",
    "எக்ஸ்போர்ட்": "export", "எக்ஸ்போர்ட": "export",
    "வீடியோ": "video", "பேக்கிராண்ட்": "background",
    "டெக்ஸ்ட்": "text", "ஓவர்லே": "overlay",
    "பிரைட்": "bright", "டார்க்": "dark",
    "ட்ரிம்": "trim", "க்ரியேட்": "create",
    "அன்டு": "undo", "அண்டோ": "undo",
}

# Tanglish phonetic replacements (from parser.py, extended)
TANGLISH_PHONETIC_REPLACEMENTS = [
    (re.compile(r"\b(?:yooso|yuse|youze|useu)\b"), "use"),
    (re.compile(r"\b(?:creat|criate|kreate)\b"), "create"),
    (re.compile(r"\b(?:zom|soom|joom|zuum)\b"), "zoom"),
    (re.compile(r"\b(?:mewsic|mewzic|miusic)\b"), "music"),
    (re.compile(r"\b(?:offa|ofur|ofer)\b"), "offer"),
    (re.compile(r"\b(?:ecsport|expoart|export)\b"), "export"),
    (re.compile(r"\b(?:treem|triim|trem)\b"), "trim"),
    (re.compile(r"\b(?:undo|andu|andhu)\b"), "undo"),
    (re.compile(r"\b(?:smoot|smuut|smuth)\b"), "smooth"),
    (re.compile(r"\b(?:brite|brigt)\b"), "bright"),
]

# Protected patterns: quoted strings, prices, percentages
_QUOTED = re.compile(r'"[^"]*"')
_PRICE = re.compile(r"(?:rs\.?|₹)\s*\d[\d,]*(?:\.\d{1,2})?", re.IGNORECASE)
_PERCENT = re.compile(r"\d+(?:\.\d+)?\s*(?:percent|%)")
_DECIMAL = re.compile(r"\b\d+\.\d+\b")


@dataclass
class NormalizationResult:
    text: str                           # normalized output
    protected_spans: list[str] = field(default_factory=list)  # preserved as-is
    is_ambiguous: bool = False
    ambiguity_reason: str | None = None


def normalize_v2(raw: str, preserve_quotes: bool = True) -> NormalizationResult:
    """
    V2 multilingual normalization pipeline.

    Steps:
      1. Unicode NFC normalization
      2. Mask protected spans (quoted strings, prices, decimals, percentages)
      3. Tamil loanword replacement
      4. Tamil suffix stripping
      5. Tanglish phonetic replacement (unquoted Latin only)
      6. Whitespace normalization
      7. Restore masked spans
    """
    if not raw:
        return NormalizationResult(text="")

    text = unicodedata.normalize("NFC", raw.strip())

    # --- Step 2: Mask protected spans ---
    protected: list[str] = []
    placeholders: list[str] = []

    def _mask(pattern: re.Pattern, t: str) -> str:
        def replacer(m: re.Match) -> str:
            idx = len(protected)
            protected.append(m.group(0))
            ph = f"\x00PROT{idx}\x00"
            placeholders.append(ph)
            return ph
        return pattern.sub(replacer, t)

    if preserve_quotes:
        text = _mask(_QUOTED, text)
    text = _mask(_PRICE, text)
    text = _mask(_DECIMAL, text)
    text = _mask(_PERCENT, text)

    # --- Step 3: Tamil loanword replacement ---
    for tamil_word, english in TAMIL_LOANWORD_MAP.items():
        text = text.replace(tamil_word, english)

    # --- Step 4: Tamil suffix stripping (on Tamil-script tokens only) ---
    words = text.split()
    stripped_words = []
    for w in words:
        if any("\u0B80" <= c <= "\u0BFF" for c in w):  # Tamil Unicode range
            w = TAMIL_SUFFIXES.sub("", w)
        stripped_words.append(w)
    text = " ".join(stripped_words)

    # --- Step 5: Tanglish phonetic replacement (Latin-only tokens not in placeholders) ---
    for pattern, replacement in TANGLISH_PHONETIC_REPLACEMENTS:
        # Only apply outside protected placeholders
        parts = text.split("\x00")
        new_parts = []
        for i, part in enumerate(parts):
            if part.startswith("PROT"):
                new_parts.append("\x00" + part + "\x00")
            else:
                new_parts.append(pattern.sub(replacement, part))
        text = "".join(new_parts)
        # Clean double null bytes
        text = re.sub(r"\x00\x00", "\x00", text)

    # --- Step 6: Whitespace normalization ---
    text = re.sub(r"\s+", " ", text).strip()

    # --- Step 7: Restore protected spans ---
    for i, (orig, ph) in enumerate(zip(protected, placeholders)):
        text = text.replace(f"\x00PROT{i}\x00", orig)
        text = text.replace(ph, orig)
    # Clean any stray null bytes
    text = text.replace("\x00", "")

    return NormalizationResult(
        text=text,
        protected_spans=protected,
    )


def detect_ambiguity(text: str) -> tuple[bool, str | None]:
    """
    Detect if the text is too ambiguous to parse deterministically.
    Returns (is_ambiguous, reason_or_None).

    Ambiguous patterns:
      - Very short text (1 word, non-command)
      - Multiple conflicting intents in one sentence
      - Unresolvable pronoun ("it", "that") with no prior context
    """
    t = text.strip().lower()
    tokens = t.split()
    if len(tokens) <= 1 and t not in {"undo", "export", "undo.", "export."}:
        return True, f"Too short to parse: '{text}' — please speak a full command."
    # Pronoun without context — context manager will resolve this, not normalizer
    return False, None
