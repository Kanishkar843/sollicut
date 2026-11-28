import pytest

from backend.app.models import DualTranscriptResult, ProjectState, Asset
from backend.app.parser import normalize, parse, parse_dual_command


def test_indicconformer_tamil_loanword_normalization_canonical():
    text = "இந்த போட்டோஸ் எல்லாம் யூஸ் பண்ணி 15 செகண்ட்ஸ் இன்ஸ்டாகிராம் ரீல் உருவாக்கு. ஸ்மூத் ஜூம் போடு. பேக்கிரவுண்ட் மியூசிக் சேர். லாஸ்ட்ல 20 பர்சென்ட் ஆஃபர் போடு."
    parsed = parse(text, media_count=3, has_reel=False)
    assert not parsed.requires_clarification, parsed.clarification_question
    ops = {op.type: op.parameters for op in parsed.operations}
    assert ops["create_reel"]["duration_seconds"] == 15
    assert ops["set_zoom_style"]["style"] == "smooth"
    assert ops["set_music"]["enabled"] is True
    assert ops["set_text_overlay"]["placement"] == "end_card"
    assert "20%" in ops["set_text_overlay"]["text"]


@pytest.mark.parametrize(
    "raw,expected_type,key,val",
    [
        ("மியூசிக் கொஞ்சம் குறைச்சு பண்ணு", "set_music_volume", "direction", "decrease"),
        ("பாட்டு அதிகம் ஏத்து", "set_music_volume", "direction", "increase"),
        ("அன்டூ பண்ணு", "undo", None, None),
        ("திரும்ப", "undo", None, None),
        ("Background music come me panel", "set_music_volume", "direction", "decrease"),
        ("Music konjam gummy panu", "set_music_volume", "direction", "decrease"),
        ("last law 20 percent offer nu podo", "set_text_overlay", "placement", "end_card"),
        ("Offer ah 25 percent nu mattu", "set_text_overlay", "text", "25 percent offer"),
        ("smoth zom podu", "set_zoom_style", "style", "smooth"),
        ("creat 15 secnds reel", "create_reel", "duration_seconds", 15),
    ],
)
def test_tamil_loanwords_and_whisper_phonetic_recovery(raw, expected_type, key, val):
    parsed = parse(raw, media_count=2, has_reel=True)
    assert not parsed.requires_clarification, parsed.clarification_question
    ops = {op.type: op.parameters for op in parsed.operations}
    assert expected_type in ops
    if key is not None:
        assert ops[expected_type][key] == val


def test_rapidfuzz_does_not_mutate_numbers_or_quoted_text():
    raw = 'Add text "Come me panel 25"'
    parsed = parse(raw, media_count=2, has_reel=True)
    assert not parsed.requires_clarification
    assert parsed.operations[0].parameters["text"] == "Come me panel 25"
    assert parsed.original_transcript == raw


def test_dual_fusion_canonical_command():
    dual = DualTranscriptResult(
        primary_text="Indha photos ellathayum use panni 15 seconds reel create pannu. Smooth zoom podu. Background music add pannu. 20 percent offer.",
        tamil_transcript="போட்டோஸ் 15 செகண்ட்ஸ் ரீல். கடைசில 20 பர்சென்ட் ஆஃபர்.",
        english_transcript="Indha photos ellathayum use panni 15 seconds reel create pannu. Smooth zoom podu. Background music add pannu. 20 percent offer.",
        mode="tanglish",
        engines_used=["indicconformer-ta", "faster-whisper"],
        elapsed_seconds=0.45,
    )
    parsed = parse_dual_command(dual, media_count=3, has_reel=False)
    assert not parsed.requires_clarification
    ops = {op.type: op.parameters for op in parsed.operations}
    assert ops["create_reel"]["duration_seconds"] == 15
    assert ops["set_zoom_style"]["style"] == "smooth"
    assert ops["set_music"]["enabled"] is True
    assert ops["set_text_overlay"]["text"] == "20 percent offer"
    assert ops["set_text_overlay"]["placement"] == "end_card"
    assert parsed.matched_sources["create_reel"] == "faster-whisper"


def test_dual_fusion_followup_unions_pass_a_and_pass_b():
    dual = DualTranscriptResult(
        primary_text="Offer ah 25 percent nu maathu.",
        tamil_transcript="ஆஃபர் இருபத்து ஐந்து சதவீதம் மாத்து. பேக்கிரவுண்ட் மியூசிக் கொஞ்சம் கம்மி பண்ணு.",
        english_transcript="Offer ah 25 percent nu maathu.",
        mode="tanglish",
        engines_used=["indicconformer-ta", "faster-whisper"],
        elapsed_seconds=0.32,
    )
    project = ProjectState(
        assets=[Asset(filename="a.jpg", media_type="image", path="assets/a.jpg")],
        current_output="renders/revision-1.mp4",
    )
    parsed = parse_dual_command(dual, project)
    assert not parsed.requires_clarification
    ops = {op.type: op.parameters for op in parsed.operations}
    assert ops["set_text_overlay"]["text"] == "25 percent offer"
    assert ops["set_music_volume"]["direction"] == "decrease"
    assert parsed.matched_sources["set_text_overlay"] == "faster-whisper"
    assert parsed.matched_sources["set_music_volume"] == "indicconformer-ta"


def test_dual_fusion_preserves_pure_tamil_overlay():
    dual = DualTranscriptResult(
        primary_text="20 percent offer",
        tamil_transcript="இன்று 20% ஆஃபர் கடைசில போடு",
        english_transcript="20 percent offer",
        mode="tanglish",
        engines_used=["indicconformer-ta", "faster-whisper"],
        elapsed_seconds=0.25,
    )
    parsed = parse_dual_command(dual, media_count=2, has_reel=True)
    assert not parsed.requires_clarification
    ops = {op.type: op.parameters for op in parsed.operations}
    assert ops["set_text_overlay"]["text"] == "இன்று 20% ஆஃபர்"
    assert ops["set_text_overlay"]["placement"] == "end_card"
    assert parsed.matched_sources["set_text_overlay"] == "indicconformer-ta"


def test_dual_fusion_handles_partial_clarification_from_one_pass():
    dual = DualTranscriptResult(
        primary_text="offer",
        tamil_transcript="மியூசிக் கம்மி பண்ணு",
        english_transcript="offer",
        mode="tanglish",
        engines_used=["indicconformer-ta", "faster-whisper"],
        elapsed_seconds=0.2,
    )
    parsed = parse_dual_command(dual, media_count=2, has_reel=True)
    assert not parsed.requires_clarification
    assert parsed.operations[0].type == "set_music_volume"
    assert parsed.operations[0].parameters["direction"] == "decrease"


def test_dual_fusion_empty_or_unrecognized_requires_clarification():
    dual = DualTranscriptResult(
        primary_text="",
        tamil_transcript=None,
        english_transcript="",
        mode="tanglish",
        engines_used=["faster-whisper"],
        elapsed_seconds=0.1,
    )
    parsed = parse_dual_command(dual, media_count=2, has_reel=True)
    assert parsed.requires_clarification
    assert parsed.clarification_question


def test_ta_and_en_modes_use_single_pass():
    ta_res = DualTranscriptResult(
        primary_text="இருபது சதவீதம் ஆஃபர்",
        tamil_transcript="இருபது சதவீதம் ஆஃபர்",
        mode="ta",
        engines_used=["indicconformer-ta"],
        elapsed_seconds=0.12,
    )
    ta_parsed = parse_dual_command(ta_res, media_count=1, has_reel=True)
    assert not ta_parsed.requires_clarification
    assert ta_parsed.operations[0].parameters["text"] == "20% ஆஃபர்"
    assert ta_parsed.matched_sources["set_text_overlay"] == "indicconformer-ta"

    en_res = DualTranscriptResult(
        primary_text="Create a 10 seconds reel with smooth zoom",
        english_transcript="Create a 10 seconds reel with smooth zoom",
        mode="en",
        engines_used=["faster-whisper"],
        elapsed_seconds=0.18,
    )
    en_parsed = parse_dual_command(en_res, media_count=2, has_reel=False)
    assert not en_parsed.requires_clarification
    assert en_parsed.matched_sources["create_reel"] == "faster-whisper"
