"""
backend/app/understanding/intent_parser.py — Per-clause intent classifier (V2 Phase 6)

Classifies a single clause into an intent with extracted parameters.
Uses keyword matching extended from parser.py's existing patterns.

Returns a typed dict with intent and confidence score.
When confidence < 0.4, returns intent='unknown' — caller should ask for clarification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .number_parser import extract_number_from_phrase


@dataclass
class IntentResult:
    intent: str
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    raw_clause: str = ""


# Intent patterns: (pattern, intent_name, parameter_extractor_fn)
# Each extractor fn takes the match + full clause and returns a dict

def _create_reel(m: re.Match, clause: str) -> dict:
    dur = extract_number_from_phrase(clause)
    return {"duration_seconds": int(dur) if dur else 15}

def _set_duration(m: re.Match, clause: str) -> dict:
    dur = extract_number_from_phrase(clause)
    return {"duration_seconds": int(dur) if dur else 15}

def _set_music_on(m: re.Match, clause: str) -> dict:
    return {"enabled": True}

def _set_music_off(m: re.Match, clause: str) -> dict:
    return {"enabled": False}

def _set_music_volume_down(m: re.Match, clause: str) -> dict:
    return {"direction": "decrease"}

def _set_music_volume_up(m: re.Match, clause: str) -> dict:
    return {"direction": "increase"}

def _set_zoom_smooth(m: re.Match, clause: str) -> dict:
    return {"style": "smooth"}

def _set_zoom_none(m: re.Match, clause: str) -> dict:
    return {"style": "none"}

def _set_text_overlay(m: re.Match, clause: str) -> dict:
    # Try to extract quoted text first
    q = re.search(r'"([^"]+)"', clause)
    text = q.group(1) if q else ""
    placement = "end_card"
    if re.search(r"\b(?:bottom|கீழ்)\b", clause, re.IGNORECASE):
        placement = "bottom"
    elif re.search(r"\b(?:center|centre|நடு)\b", clause, re.IGNORECASE):
        placement = "center"
    return {"text": text, "placement": placement}

def _clear_text(m: re.Match, clause: str) -> dict:
    return {"text": None}

def _trim_clip(m: re.Match, clause: str) -> dict:
    # Look for clip index
    idx_match = re.search(r"\b(\d+)(?:st|nd|rd|th)?\s*(?:clip|video|photo|image)?\b", clause)
    idx = int(idx_match.group(1)) - 1 if idx_match else 0
    # Look for duration
    dur = extract_number_from_phrase(clause)
    result: dict[str, Any] = {"clip_index": idx}
    if dur:
        result["trim_end"] = float(dur)
    return result

def _set_brightness_up(m: re.Match, clause: str) -> dict:
    return {"value": 0.3}

def _set_brightness_down(m: re.Match, clause: str) -> dict:
    return {"value": -0.3}

def _set_fit_cover(m: re.Match, clause: str) -> dict:
    return {"mode": "cover"}

def _set_fit_contain(m: re.Match, clause: str) -> dict:
    return {"mode": "contain"}

def _undo(m: re.Match, clause: str) -> dict:
    return {}

def _export(m: re.Match, clause: str) -> dict:
    return {}


INTENT_PATTERNS: list[tuple[re.Pattern, str, Any]] = [
    # Create reel (highest specificity first)
    (re.compile(r"\b(?:create|make|pannu|போடு|create\s+a?)\b.*?\b(?:reel|video|clip)\b", re.I), "create_reel", _create_reel),
    # Duration
    (re.compile(r"\b(?:set|change|make).*?\b(?:duration|seconds|sec|sec\.)\b|\b(?:\d+)\s*sec(?:ond)?s?\s*reel\b", re.I), "set_duration", _set_duration),
    # Music on/off
    (re.compile(r"\b(?:remove|off|stop|no|வேண்டாம்)\b.*?\bmusic\b|\bmusic\b.*?\b(?:off|stop|remove|வேண்டாம்)\b", re.I), "set_music", _set_music_off),
    (re.compile(r"\b(?:add|enable|on|போடு)\b.*?\bmusic\b|\bmusic\b.*?\b(?:add|on|enable)\b|\bbackground\s+music\b", re.I), "set_music", _set_music_on),
    # Music volume
    (re.compile(r"\bmusic\b.*?\b(?:less|low|soft|down|கம்மி|குறை)\b|\b(?:less|low|soft|down|கம்மி|குறை)\b.*?\bmusic\b", re.I), "set_music_volume", _set_music_volume_down),
    (re.compile(r"\bmusic\b.*?\b(?:more|high|loud|up|அதிக|கூட்டு)\b|\b(?:more|high|loud|up)\b.*?\bmusic\b", re.I), "set_music_volume", _set_music_volume_up),
    # Zoom
    (re.compile(r"\b(?:smooth\s+)?zoom\b.*?\b(?:on|add|போடு|enable)\b|\b(?:add|enable|போடு)\b.*?\b(?:smooth\s+)?zoom\b|\bzoom\s+(?:in|effect)\b", re.I), "set_zoom_style", _set_zoom_smooth),
    (re.compile(r"\b(?:remove|off|no)\b.*?\bzoom\b|\bzoom\b.*?\b(?:off|remove|no)\b|\bzoom\s+off\b", re.I), "set_zoom_style", _set_zoom_none),
    # Text overlay / overlay
    (re.compile(r"\b(?:add|put|set|போடு|show)\b.*?\b(?:text|overlay|caption|title)\b|\b(?:write|type)\b", re.I), "set_text_overlay", _set_text_overlay),
    (re.compile(r"\b(?:remove|clear|delete)\b.*?\b(?:text|overlay|caption)\b", re.I), "set_text_overlay", _clear_text),
    # Trim
    (re.compile(r"\b(?:trim|cut|clip|குறை)\b", re.I), "trim_clip", _trim_clip),
    # Brightness
    (re.compile(r"\b(?:bright|brighter|increase\s+brightness|light)\b", re.I), "set_brightness", _set_brightness_up),
    (re.compile(r"\b(?:dark|darker|decrease\s+brightness|dim)\b", re.I), "set_brightness", _set_brightness_down),
    # Fit mode
    (re.compile(r"\b(?:fill|cover|stretch)\b.*?\b(?:frame|screen)?\b", re.I), "set_fit_mode", _set_fit_cover),
    (re.compile(r"\b(?:fit|contain|letterbox)\b.*?\b(?:frame|screen)?\b", re.I), "set_fit_mode", _set_fit_contain),
    # Undo / export
    (re.compile(r"\b(?:undo|revert|back|திரும்ப)\b", re.I), "undo", _undo),
    (re.compile(r"\b(?:export|download|save|render|ready)\b", re.I), "export", _export),
]


def classify_clause(clause: str) -> IntentResult:
    """
    Classify a single clause into an intent.
    Returns IntentResult with confidence=0.0 and intent='unknown' when no match.
    """
    for pattern, intent_name, extractor in INTENT_PATTERNS:
        m = pattern.search(clause)
        if m:
            params = extractor(m, clause)
            return IntentResult(
                intent=intent_name,
                parameters=params,
                confidence=0.9,
                raw_clause=clause,
            )
    return IntentResult(intent="unknown", confidence=0.0, raw_clause=clause)
