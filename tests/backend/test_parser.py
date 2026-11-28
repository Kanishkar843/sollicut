import pytest
from backend.app.parser import parse

CANONICAL = 'Indha photos ellathayum use panni oru 15 seconds Instagram reel create pannu. Smooth zoom effects podu. Background music add pannu. Last la 20 percent offer nu text podu.'


def operations(text, count=3):
    result = parse(text, count, True)
    assert not result.requires_clarification, result.clarification_question
    return {op.type: op.parameters for op in result.operations}


def test_canonical():
    result = operations(CANONICAL)
    assert result == {
        "create_reel": {"duration_seconds": 15, "aspect_ratio": "9:16", "asset_selection": "all"},
        "set_zoom_style": {"style": "smooth"}, "set_music": {"enabled": True},
        "set_text_overlay": {"text": "20 percent offer", "placement": "end_card"}}


@pytest.mark.parametrize("text,kind,key,value", [
    ("Create a 15 seconds reel", "create_reel", "duration_seconds", 15),
    ("make ten seconds reel", "create_reel", "duration_seconds", 10),
    ("10 seconds", "set_duration", "duration_seconds", 10),
    ("pathu seconds pannu", "set_duration", "duration_seconds", 10),
    ("பத்து விநாடி", "set_duration", "duration_seconds", 10),
    ("பதினைந்து விநாடி ரீல் உருவாக்கு", "create_reel", "duration_seconds", 15),
    ("moonu seconds", "set_duration", "duration_seconds", 3),
    ("moonru sec", "set_duration", "duration_seconds", 3),
    ("twenty seconds", "set_duration", "duration_seconds", 20),
    ("15seconds", "set_duration", "duration_seconds", 15),
    ("ADD MUSIC!", "set_music", "enabled", True),
    ("மியூசிக் சேர்", "set_music", "enabled", True),
    ("backgroundmusic podu", "set_music", "enabled", True),
    ("music off", "set_music", "enabled", False),
    ("music konjam kammi pannu", "set_music_volume", "direction", "decrease"),
    ("இசை குறை", "set_music_volume", "direction", "decrease"),
    ("music louder", "set_music_volume", "direction", "increase"),
    ("smooth zoom podu", "set_zoom_style", "style", "smooth"),
    ("ஜூம் போடு", "set_zoom_style", "style", "smooth"),
    ("no zoom", "set_zoom_style", "style", "none"),
    ("last la 20 percent offer", "set_text_overlay", "text", "20 percent offer"),
    ("ending la irubathu percent offer", "set_text_overlay", "placement", "end_card"),
    ("இருபது சதவீதம் ஆஃபர்", "set_text_overlay", "text", "20% ஆஃபர்"),
    ('Add text "Buy 2 Get 1"', "set_text_overlay", "text", "Buy 2 Get 1"),
    ('Add text "Diwali special" at the end', "set_text_overlay", "placement", "end_card"),
    ("bright ah pannu", "set_brightness", "value", .1),
    ("reel format ku maathu", "set_aspect_ratio", "aspect_ratio", "9:16"),
    ("20 percent ஆஃபர்", "set_text_overlay", "text", "20% ஆஃபர்"),
])
def test_fields(text, kind, key, value):
    assert operations(text)[kind][key] == value


def test_followup():
    result = operations("Offer ah 25 percent nu maathu. Background music konjam kammi pannu.")
    assert result["set_text_overlay"]["text"] == "25 percent offer"
    assert result["set_music_volume"]["direction"] == "decrease"


@pytest.mark.parametrize("text,kind", [("undo", "undo"), ("last edit undo", "undo"), ("திரும்ப மாற்று", "undo"), ("download", "export"), ("save reel", "export")])
def test_controls(text, kind):
    assert kind in operations(text)


@pytest.mark.parametrize("text,count", [("", 3), ("add offer", 3), ("antha frame zoom", 3), ("make reel", 0), ("make reel", 6), ("fly to Mars", 3), ("rendu seconds", 3), ("create 120 seconds reel", 3), ("add text", 3), ('add text "../../secret"', 3), ("music and reverse", 3), ("trim", 2), ("reorder", 2)])
def test_clarification(text, count):
    result = parse(text, count)
    assert result.requires_clarification
    assert result.clarification_question


def test_single_media_and_video_commands():
    single = operations("Create a 10 seconds reel from my video clip", count=1)
    assert single["create_reel"]["duration_seconds"] == 10

    trimmed = operations("Trim clip 1 from 1 to 4 seconds", count=2)
    assert trimmed["trim_clip"] == {"clip_index": 1, "trim_start": 1.0, "trim_end": 4.0}

    trimmed_no_from = operations("Trim clip 2 2 to 6 seconds", count=2)
    assert trimmed_no_from["trim_clip"] == {"clip_index": 2, "trim_start": 2.0, "trim_end": 6.0}

    trimmed_to_end = operations("Cut clip 1 to 5 seconds", count=1)
    assert trimmed_to_end["trim_clip"] == {"clip_index": 1, "trim_start": 0.0, "trim_end": 5.0}

    bottom_offer = operations("Bottom la 20 percent offer nu podu", count=1)
    assert bottom_offer["set_text_overlay"] == {"text": "20 percent offer", "placement": "bottom"}

    center_offer = operations("Center la 15 percent offer", count=1)
    assert center_offer["set_text_overlay"] == {"text": "15 percent offer", "placement": "center"}

    cut_start = operations("Cut first 2 seconds", count=1)
    assert cut_start["trim_clip"] == {"clip_index": 1, "cut_start_seconds": 2.0}

    reordered = operations("Swap clip 1 and 2", count=2)
    assert reordered["reorder_assets"] == {"from_index": 1, "to_index": 2, "mode": "swap"}

    moved = operations("Move clip 3 first", count=3)
    assert moved["reorder_assets"] == {"from_index": 3, "to_index": 1, "mode": "move"}

    clip_audio = operations("Keep video audio and fill screen", count=2)
    assert clip_audio["set_clip_audio"] == {"enabled": True}
    assert clip_audio["set_fit_mode"] == {"mode": "cover"}

    muted = operations("Mute video audio", count=1)
    assert muted["set_clip_audio"] == {"enabled": False}


def test_raw_preserved():
    raw = '  ADD text "Diwali Special"! '
    result = parse(raw, 3)
    assert result.original_transcript == raw
    assert result.operations[0].parameters["text"] == "Diwali Special"


def test_multiturn_context_followup_and_capcut_rules():
    ctx = {"active_text_id": "layer-1", "active_text": "Sale 20%", "active_position": "bottom", "brightness": 0.1}
    follow = parse("Change text to 25%", 2, True, context=ctx)
    assert not follow.requires_clarification
    op = follow.operations[0]
    assert op.type == "set_text_overlay"
    assert op.parameters["text"] == "Sale 25%"
    assert op.parameters["target_id"] == "layer-1"
    assert op.parameters["placement"] == "bottom"

    from_to = parse("Change 20% to 35%", 2, True, context=ctx)
    assert from_to.operations[0].parameters["text"] == "Sale 35%"

    created = parse("Create text 'Sale 20%' on clip 1", 2, True)
    assert created.operations[0].parameters == {"text": "Sale 20%", "placement": "bottom", "clip_index": 1}

    bright2 = parse("brighter", 2, True, context=ctx)
    assert bright2.operations[0].parameters["value"] == 0.2

    fx = operations("cinematic filter podu. fade transition add pannu. clip 1 slow motion. denoise audio. stabilize video. remove background")
    assert fx["set_filter"]["preset"] == "cinematic"
    assert fx["set_transition"]["style"] == "fade"
    assert fx["set_clip_speed"] == {"speed": 0.5, "clip_index": 1}
    assert fx["set_audio_processing"]["audio_denoise"] is True
    assert fx["set_visual_effect"]["stabilize"] is True
    assert fx["set_visual_effect"]["cutout_mode"] == "auto_cutout"

    split_cmd = operations("Split clip 1 at 2 seconds", count=2)
    assert split_cmd["split_clip"] == {"clip_index": 1, "split_at_seconds": 2.0}
    assert "set_duration" not in split_cmd

    redo_cmd = operations("redo")
    assert "redo" in redo_cmd

