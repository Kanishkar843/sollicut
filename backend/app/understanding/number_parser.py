"""
backend/app/understanding/number_parser.py — Tamil/English number word parsing (V2 Phase 5)

Converts Tamil number words and mixed Tamil/English numeric expressions to int/float.
"""
from __future__ import annotations
import re

# Tamil number words (digit names)
TAMIL_DIGIT_WORDS: dict[str, int] = {
    "பூஜ்யம்": 0, "ஒன்று": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4,
    "ஐந்து": 5, "ஆறு": 6, "ஏழு": 7, "எட்டு": 8, "ஒன்பது": 9, "பத்து": 10,
    "பதினொரு": 11, "பன்னிரண்டு": 12, "பதிமூன்று": 13, "பதினான்கு": 14,
    "பதினைந்து": 15, "பதினாறு": 16, "பதினேழு": 17, "பதினெட்டு": 18,
    "பத்தொன்பது": 19, "இருபது": 20, "முப்பது": 30, "நாற்பது": 40,
    "ஐம்பது": 50, "அறுபது": 60, "எழுபது": 70, "எண்பது": 80,
    "தொண்ணூறு": 90, "நூறு": 100,
}

# Tanglish number transliterations
TANGLISH_NUMBER_WORDS: dict[str, int] = {
    "onnu": 1, "rendu": 2, "moonu": 3, "naalu": 4, "anju": 5,
    "aaru": 6, "ezhu": 7, "ettu": 8, "onbadu": 9, "pathu": 10,
    "pannirandu": 12, "pathinanju": 15, "irupadu": 20,
    "muppadu": 30, "naarpadu": 40, "aimbadu": 50,
    "arubadu": 60, "ezhubadu": 70, "enbadu": 80,
    "thonnooru": 90, "nooru": 100,
}

# English ordinal → cardinal
ORDINAL_MAP: dict[str, int] = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "last": -1,  # sentinel: "last clip"
}


def parse_number(token: str) -> int | float | None:
    """
    Parse a single numeric token to int or float.
    Returns None if the token is not a recognizable number.
    Handles:
      - Plain integers: "5", "25"
      - Decimal floats: "2.5", "0.5"
      - Tamil digit words: "ஐந்து" → 5
      - Tanglish number words: "anju" → 5
      - English ordinals: "first" → 1
    """
    t = token.strip().lower()
    # Plain integer
    if re.fullmatch(r"\d+", t):
        return int(t)
    # Decimal float (e.g. "2.5 seconds")
    if re.fullmatch(r"\d+\.\d+", t):
        return float(t)
    # Tamil
    for word, val in TAMIL_DIGIT_WORDS.items():
        if t == word:
            return val
    # Tanglish
    if t in TANGLISH_NUMBER_WORDS:
        return TANGLISH_NUMBER_WORDS[t]
    # English ordinal
    if t in ORDINAL_MAP:
        return ORDINAL_MAP[t]
    return None


def extract_number_from_phrase(phrase: str) -> int | float | None:
    """
    Extract a leading number from a phrase like "2.5 seconds", "25 percent", "10".
    Returns the first numeric token found, or None.
    """
    tokens = phrase.strip().split()
    for tok in tokens:
        result = parse_number(tok.rstrip(".,!?;:"))
        if result is not None:
            return result
    return None
