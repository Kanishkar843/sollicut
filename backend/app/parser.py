"""Small, explainable command grammar with multi-turn context tracking. Raw speech is never rewritten in-place."""
import re
import unicodedata

from .models import EditOperation, ParsedCommand

NUMBERS = {
    "one": 1, "oru": 1, "ஒன்று": 1, "ஒரு": 1,
    "two": 2, "rendu": 2, "irandu": 2, "இரண்டு": 2,
    "three": 3, "moonu": 3, "moonru": 3, "மூன்று": 3,
    "four": 4, "naalu": 4, "நான்கு": 4,
    "five": 5, "anju": 5, "ஐந்து": 5,
    "six": 6, "aaru": 6, "ஆறு": 6,
    "seven": 7, "ezhu": 7, "ஏழு": 7,
    "eight": 8, "ettu": 8, "எட்டு": 8,
    "nine": 9, "onbathu": 9, "ஒன்பது": 9,
    "ten": 10, "pathu": 10, "பத்து": 10,
    "twelve": 12, "pannirendu": 12, "பன்னிரண்டு": 12,
    "fifteen": 15, "pathinainthu": 15, "பதினைந்து": 15,
    "twenty": 20, "irubathu": 20, "இருபது": 20,
    "thirty": 30, "muppathu": 30, "முப்பது": 30,
    "forty": 40, "naapathu": 40, "நாற்பது": 40,
    "fifty": 50, "ambathu": 50, "ஐம்பது": 50,
    "sixty": 60, "arubathu": 60, "அறுபது": 60,
    "seventy": 70, "ezhubathu": 70, "எழுபது": 70,
    "eighty": 80, "enbathu": 80, "எண்பது": 80,
    "ninety": 90, "thonnooru": 90, "தொண்ணூறு": 90,
    "hundred": 100, "nooru": 100, "நூறு": 100,
}

MUSIC = r"music|bgm|மியூசிக்|இசை"
REDUCE = r"kammi|reduce|lower|softer|decrease|கம்மி|குறை"
OFFER = r"offer|discount|\bsale\b(?!\s*(?:sticker|badge))|ஆஃபர்|தள்ளுபடி"
TEXT = r"text|title|caption|எழுத்து|வாசகம்|உரை"
TRIM = r"\b(?:trim|cut)\b|கட்"
SPLIT = r"\bsplit\b|பிரி"
REORDER = r"\b(?:swap|reorder|move)\b"
CHANGE_VERB = r"\b(?:change|update|modify|replace|edit|set)\b|maathu|மாற்று|ஆக்கு"


def normalize(raw: str) -> str:
    text = unicodedata.normalize("NFC", raw).lower()
    text = re.sub(r"(?<=\d)(?=[a-z])", " ", text)
    text = re.sub(r"twenty[ -]+five|irubathi[\s-]*anju|இருபத்து\s*ஐந்து", "25", text)
    text = re.sub(r"thirty[ -]+five|muppathi[\s-]*anju|முப்பத்து\s*ஐந்து", "35", text)
    text = re.sub(r"forty[ -]+five|naapathi[\s-]*anju|நாற்பத்து\s*ஐந்து", "45", text)
    text = re.sub(r"seventy[ -]+five|ezhubathi[\s-]*anju|எழுபத்து\s*ஐந்து", "75", text)
    text = re.sub(r"background\s*music", "background music", text)
    # Unicode-aware whitespace boundaries keep Tamil combining marks intact.
    for word, number in NUMBERS.items():
        text = re.sub(r"(?<!\S)" + re.escape(word) + r"(?=\s|[.,!?%]|$)", str(number), text)
    return re.sub(r"\s+", " ", text).strip()


def _substitute_percent_in_text(existing: str, new_num: str) -> str:
    """Replace an existing percentage or number inside active text while preserving wording."""
    if re.search(r"\d+(?:\.\d+)?\s*(?:%|percent|சதவீதம்)", existing, re.I):
        def _repl(m: re.Match) -> str:
            suffix = m.group(2)
            return f"{new_num}{suffix}"
        return re.sub(r"(\d+(?:\.\d+)?)(\s*(?:%|percent|சதவீதம்))", _repl, existing, count=1, flags=re.I)
    if re.search(r"\d+(?:\.\d+)?", existing):
        return re.sub(r"\d+(?:\.\d+)?", new_num, existing, count=1)
    return f"{existing.strip()} {new_num}%".strip()


def parse(raw: str, media_count: int, has_reel: bool = False, context: dict | None = None) -> ParsedCommand:
    text = normalize(raw)
    ctx = context or {}
    active_text_id: str | None = ctx.get("active_text_id")
    active_text: str | None = ctx.get("active_text")

    tamil = bool(re.search(r"[\u0b80-\u0bff]", raw))
    latin = bool(re.search(r"[a-zA-Z]", raw))
    tanglish = bool(re.search(r"pannu|podu|maathu|kammi|indha|panni|kootu", text))
    result = ParsedCommand(
        original_transcript=raw,
        normalized_text=text,
        language_mode="ta-en" if (tamil and latin) or tanglish else "ta" if tamil else "en" if latin else "unknown",
    )

    def add(kind: str, **parameters):
        result.operations.append(EditOperation(type=kind, parameters=parameters, source_transcript=raw))
        result.matched_rules.append(kind)

    def clarify(question: str):
        result.requires_clarification = True
        result.clarification_question = question
        return result

    if not text:
        return clarify("I did not hear a command. Please record again.")
    if re.search(r"antha frame|that frame|அந்த.*பிரேம்", text):
        return clarify("This prototype edits clips and reel settings. Say a duration, trim, reorder, music or offer change.")
    if re.search(r"\bundo\b|திரும்ப மாற்று", text):
        if re.search(r"music|percent|seconds|zoom", text):
            return clarify("Please say undo on its own, then record the next change.")
        add("undo")
        return result
    if re.search(r"\bredo\b|மீண்டும் செய்", text):
        add("redo")
        return result
    if re.fullmatch(r"(?:export|download|save)(?:\s+(?:reel|video|pannu|it))*[.!]?", text):
        add("export")
        return result

    duration_text = text

    # Split clip clauses before duration parsing so split timestamps aren't misread as reel length.
    split_match = re.search(SPLIT, text)
    if split_match:
        clip_match = re.search(r"(?:clip|video)\s*(\d+)", text)
        clip_index = int(clip_match[1]) if clip_match else 1
        at_match = re.search(r"(?:at\s+)?(\d+(?:\.\d+)?)\s*(?:s|secs?|seconds?|விநாடி|வினாடி)", text)
        if at_match:
            split_s = float(at_match[1])
            if split_s <= 0.1:
                return clarify("Choose a split timestamp greater than 0.1 seconds.")
            add("split_clip", clip_index=clip_index, split_at_seconds=split_s)
            duration_text = text[:at_match.start()] + text[at_match.end():]
        else:
            return clarify("Say where to split the clip, like: split clip 1 at 2 seconds.")

    # Strip trim clauses before detecting overall reel duration.
    trim_match = re.search(TRIM, duration_text)
    if trim_match:
        clip_match = re.search(r"(?:clip|video)\s*(\d+)", duration_text)
        clip_index = int(clip_match[1]) if clip_match else 1
        trim_scope = (
            re.sub(r"\s+", " ", (duration_text[:clip_match.start()] + " " + duration_text[clip_match.end():])).strip()
            if clip_match
            else duration_text
        )
        range_match = re.search(
            r"(?:from\s+)?(\d+(?:\.\d+)?)\s*(?:s|secs?|seconds?)?\s+to\s+(\d+(?:\.\d+)?)\s*(?:s|secs?|seconds?)?",
            trim_scope,
        )
        cut_first = re.search(
            r"(?:trim|cut|கட்)\s+(?:first|start)\s+(\d+(?:\.\d+)?)\s*(?:s|secs?|seconds?|விநாடி|வினாடி)?",
            trim_scope,
        )
        cut_last = re.search(
            r"(?:trim|cut|கட்)\s+(?:last|end)\s+(\d+(?:\.\d+)?)\s*(?:s|secs?|seconds?|விநாடி|வினாடி)?",
            trim_scope,
        )
        to_end = re.search(r"(?:trim|cut|கட்)\s+to\s+(\d+(?:\.\d+)?)\s*(?:s|secs?|seconds?)?", trim_scope)
        if range_match:
            start_s, end_s = float(range_match[1]), float(range_match[2])
            if end_s <= start_s:
                return clarify("Trim end time must be greater than start time.")
            add("trim_clip", clip_index=clip_index, trim_start=start_s, trim_end=end_s)
            duration_text = trim_scope[:range_match.start()] + trim_scope[range_match.end():]
        elif cut_first:
            cut_s = float(cut_first[1])
            if cut_s <= 0:
                return clarify("Choose a positive number of seconds to trim.")
            add("trim_clip", clip_index=clip_index, cut_start_seconds=cut_s)
            duration_text = trim_scope[:cut_first.start()] + trim_scope[cut_first.end():]
        elif cut_last:
            cut_s = float(cut_last[1])
            if cut_s <= 0:
                return clarify("Choose a positive number of seconds to trim.")
            add("trim_clip", clip_index=clip_index, cut_end_seconds=cut_s)
            duration_text = trim_scope[:cut_last.start()] + trim_scope[cut_last.end():]
        elif to_end:
            end_s = float(to_end[1])
            if end_s <= 0.2:
                return clarify("Trim end time must leave at least 0.2 seconds.")
            add("trim_clip", clip_index=clip_index, trim_start=0.0, trim_end=end_s)
            duration_text = trim_scope[:to_end.start()] + trim_scope[to_end.end():]
        else:
            return clarify("Say which clip and seconds to trim, like: trim clip 1 from 2 to 6 seconds.")

    if re.search(REORDER, text):
        swap = re.search(r"swap\s+(?:clips?\s*)?(\d+)\s+(?:and|with)\s+(\d+)", text)
        move_first = re.search(r"(?:move|put)\s+(?:clip\s*)?(\d+)\s+(?:to\s+)?first", text)
        move_to = re.search(r"move\s+(?:clip\s*)?(\d+)\s+to\s+(\d+)", text)
        if swap:
            add("reorder_assets", from_index=int(swap[1]), to_index=int(swap[2]), mode="swap")
        elif move_first:
            add("reorder_assets", from_index=int(move_first[1]), to_index=1, mode="move")
        elif move_to:
            add("reorder_assets", from_index=int(move_to[1]), to_index=int(move_to[2]), mode="move")
        else:
            return clarify("Say which clips to reorder, like: swap clip 1 and 2.")

    duration = re.search(r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|விநாடி|வினாடி)", duration_text)
    create = bool(
        re.search(
            r"create\s+(?:a\s+)?(?:\d+(?:\.\d+)?\s*(?:seconds?|secs?)\s+)?(?:instagram\s+)?reel|make\s+(?:a\s+)?(?:\d+(?:\.\d+)?\s*(?:seconds?|secs?)\s+)?reel|உருவாக்கு|உருவாக்க|(?:photos?|videos?|clips?|media).*(?:reel|ரீல்)|(?:படங்கள்|வீடியோ).*(?:ரீல்)",
            text,
        )
    )
    if create:
        add("create_reel", duration_seconds=float(duration[1]) if duration else 15, aspect_ratio="9:16", asset_selection="all")
    elif duration:
        add("set_duration", duration_seconds=float(duration[1]))
    if duration and not 3 <= float(duration[1]) <= 30:
        return clarify("Choose a reel length between 3 and 30 seconds.")
    if re.search(r"landscape|16\s*:\s*9|widescreen|youtube", text):
        add("set_aspect_ratio", aspect_ratio="16:9")
    elif re.search(r"\bsquare\b|1\s*:\s*1", text):
        add("set_aspect_ratio", aspect_ratio="1:1")
    elif re.search(r"\bportrait\b|4\s*:\s*5", text):
        add("set_aspect_ratio", aspect_ratio="4:5")
    elif re.search(r"reel format|vertical|9\s*:\s*16|செங்குத்து", text) and not create:
        add("set_aspect_ratio", aspect_ratio="9:16")
    if re.search(r"zoom|ஜூம்", text):
        add("set_zoom_style", style="none" if re.search(r"no zoom|remove zoom|zoom off", text) else "smooth")
    if re.search(r"(?:clip|video|original)\s+audio|mute\s+(?:clip|video)|வீடியோ\s*ஆடியோ", text):
        disabled = bool(re.search(r"\bmute\b|\bno\b|\boff\b|\bremove\b|வேண்டாம்|நிறுத்து", text))
        add("set_clip_audio", enabled=not disabled)
    if re.search(r"fill screen|full screen|crop to fit", text):
        add("set_fit_mode", mode="cover")
    elif re.search(r"fit frame|letterbox|no crop", text):
        add("set_fit_mode", mode="contain")
    if re.search(MUSIC, text) and not re.search(r"isolate vocals|vocals only|remove vocals|music only", text):
        if re.search(REDUCE, text):
            add("set_music_volume", direction="decrease")
        elif re.search(r"louder|increase|அதிக|kootu", text):
            add("set_music_volume", direction="increase")
        else:
            disable_music = bool(
                re.search(r"(?:remove|off|without|no)\s+(?:background\s+)?(?:music|bgm)|(?:music|bgm)\s+(?:off|remove|வேண்டாம்|நிறுத்து)", text)
            )
            add("set_music", enabled=not disable_music)
    if re.search(r"bright|dark|பிரைட்|வெளிச்ச", text):
        base_b = float(ctx.get("brightness", 0.0))
        delta = -0.1 if re.search(REDUCE + r"|dark", text) else 0.1
        next_b = round(max(-0.3, min(0.3, base_b + delta)), 2)
        add("set_brightness", value=next_b)

    # Transitions
    if re.search(r"\btransition\b|மாற்றம்", text):
        if re.search(r"(?:remove|no|off|none|clear)\s+(?:the\s+)?transition|transition\s+(?:off|none|remove|வேண்டாம்)", text):
            add("set_transition", style="none")
        elif re.search(r"dissolve", text):
            add("set_transition", style="dissolve")
        elif re.search(r"slide\s*right", text):
            add("set_transition", style="slideright")
        elif re.search(r"slide", text):
            add("set_transition", style="slideleft")
        elif re.search(r"wipe", text):
            add("set_transition", style="wipeleft")
        elif re.search(r"circle", text):
            add("set_transition", style="circleopen")
        else:
            add("set_transition", style="fade")

    # Color grading filters
    if re.search(r"\bfilter\b|black and white|\bb\s*&\s*w\b|cinematic|vintage|ஃபில்டர்", text):
        if re.search(r"(?:remove|no|off|none|clear)\s+(?:the\s+)?filter|filter\s+(?:off|none|remove|clear|வேண்டாம்)", text):
            add("set_filter", preset="none")
        elif re.search(r"cinematic", text):
            add("set_filter", preset="cinematic")
        elif re.search(r"warm", text):
            add("set_filter", preset="warm")
        elif re.search(r"cool", text):
            add("set_filter", preset="cool")
        elif re.search(r"black and white|\bbw\b|\bb\s*&\s*w\b", text):
            add("set_filter", preset="bw")
        elif re.search(r"vivid", text):
            add("set_filter", preset="vivid")
        elif re.search(r"vintage", text):
            add("set_filter", preset="vintage")
        elif re.search(r"high contrast|contrast", text):
            add("set_filter", preset="high_contrast")

    # Clip speed / speed curve
    clip_speed_target = re.search(r"(?:clip|video)\s*(\d+)", text)
    if re.search(r"slow\s*mo(?:tion)?|மெதுவா", text):
        params = {"speed": 0.5}
        if clip_speed_target:
            params["clip_index"] = int(clip_speed_target[1])
        add("set_clip_speed", **params)
    elif re.search(r"fast\s*forward|2x\s*speed|double\s*speed|வேகமா", text):
        params = {"speed": 2.0}
        if clip_speed_target:
            params["clip_index"] = int(clip_speed_target[1])
        add("set_clip_speed", **params)
    elif re.search(r"normal\s*speed|1x\s*speed", text):
        params = {"speed": 1.0}
        if clip_speed_target:
            params["clip_index"] = int(clip_speed_target[1])
        add("set_clip_speed", **params)

    # Audio post-processing (combined into a single operation)
    audio_fx: dict = {}
    if re.search(r"denoise|noise\s*reduction|reduce\s*noise|remove\s*noise", text):
        audio_fx["audio_denoise"] = True
    if re.search(r"normalize\s*audio|loudness\s*normalize|auto\s*gain", text):
        audio_fx["audio_normalize"] = True
    if re.search(r"enhance\s*voice|voice\s*enhance|clear\s*voice", text):
        audio_fx["voice_enhance"] = True
    if re.search(r"isolate\s*vocals|vocals\s*only", text):
        audio_fx["vocal_isolation"] = "vocals_only"
    elif re.search(r"remove\s*vocals|instrumental\s*only|music\s*only", text):
        audio_fx["vocal_isolation"] = "music_only"
    if audio_fx:
        add("set_audio_processing", **audio_fx)

    # Visual effects (combined into a single operation)
    fx_params: dict = {}
    if re.search(r"stabiliz|deshake|steady", text):
        disable_stab = bool(re.search(r"(?:remove|off|disable)\s+(?:video\s+)?stabiliz|stabiliz\w*\s+(?:off|remove)", text))
        fx_params["stabilize"] = not disable_stab
    if re.search(r"remove\s*background|auto\s*cutout|cutout|பின்னணி\s*நீக்கு", text):
        off_cut = bool(re.search(r"(?:cutout|background)\s+off|off\s+cutout", text))
        fx_params["cutout_mode"] = "none" if off_cut else "auto_cutout"
    if re.search(r"green\s*screen|chroma\s*key", text):
        off_ck = bool(re.search(r"(?:chroma\s*key|green\s*screen)\s+off|off\s+(?:chroma|green)", text))
        fx_params["cutout_mode"] = "none" if off_ck else "chroma_key"
    if re.search(r"relight", text):
        fx_params["relight"] = -0.2 if re.search(REDUCE, text) else 0.2
    if fx_params:
        if clip_speed_target:
            fx_params["clip_index"] = int(clip_speed_target[1])
        add("set_visual_effect", **fx_params)

    # Stickers
    if re.search(r"\bsticker\b|\bbadge\b", text):
        if re.search(r"(?:remove|no|off|none|clear)\s+(?:the\s+)?(?:sticker|badge)|(?:sticker|badge)\s+(?:off|none|remove)", text):
            add("set_sticker", sticker_badge="none")
        elif re.search(r"new", text):
            add("set_sticker", sticker_badge="new")
        elif re.search(r"tamil", text):
            add("set_sticker", sticker_badge="tamil_special")
        elif re.search(r"top|best", text):
            add("set_sticker", sticker_badge="top_pick")
        else:
            add("set_sticker", sticker_badge="sale")

    # Text overlay & persistent multi-turn updates
    # Support double quotes, typographic quotes, and balanced single-quoted literals.
    quoted = re.search(r'["“]([^"”]+)["”]', raw)
    if not quoted:
        quoted = re.search(r"(?:^|\s)'([^']+)'(?=$|\s|[.,!?])", raw)
    all_quoted = re.findall(r'["“]([^"”]+)["”]|(?:^|\s)\'([^\']+)\'(?=$|\s|[.,!?])', raw)
    quoted_values = [a or b for a, b in all_quoted if (a or b)]

    on_clip = re.search(r"(?:on\s+clip\s*|clip\s*)(\d+)(?:\s*la)?", text)
    clip_target = int(on_clip[1]) if on_clip and re.search(TEXT + "|" + OFFER, text) else None

    explicit_top = bool(re.search(r"\btop\b|மேலே", text))
    explicit_bottom = bool(re.search(r"\bbottom\b|கீழே", text))
    explicit_center = bool(re.search(r"\b(?:center|centre|middle)\b|நடு", text))
    explicit_end = bool(re.search(r"\blast\b|\bend\b|கடைசி", text))
    has_explicit_placement = explicit_top or explicit_bottom or explicit_center or explicit_end

    if explicit_end:
        placement = "end_card"
    elif explicit_center:
        placement = "center"
    elif explicit_top:
        placement = "top"
    else:
        placement = "bottom"

    animation = None
    if re.search(r"slide[\s_-]*up\s+text|text.*slide[\s_-]*up", text):
        animation = "slide_up"
    elif re.search(r"pop\s+text|text.*pop", text):
        animation = "pop"
    elif re.search(r"fade\s+text|text.*fade", text):
        animation = "fade"

    is_change_cmd = bool(re.search(CHANGE_VERB, text))
    # Detect explicit "from X% to Y%" / "X% ah Y% maathu" / "change text to Y%"
    percent_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:percent|%|சதவீதம்)", text)
    from_to_pct = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:percent|%|சதவீதம்)\s*(?:ah|to|->|la\s+irundhu)\s*(\d+(?:\.\d+)?)\s*(?:percent|%|சதவீதம்)?",
        text,
    )

    overlay = None
    updating_existing = False

    if len(quoted_values) >= 2 and is_change_cmd:
        # e.g. Change "Sale 20%" to "Sale 25%"
        overlay = quoted_values[-1]
        updating_existing = True
    elif quoted and (re.search(TEXT + "|" + OFFER, text) or (is_change_cmd and active_text)):
        overlay = quoted_values[-1] if quoted_values else quoted[1]
        updating_existing = is_change_cmd and bool(active_text_id)
    elif from_to_pct:
        target_num = from_to_pct[2]
        if active_text:
            overlay = _substitute_percent_in_text(active_text, target_num)
            updating_existing = True
        else:
            overlay = f"{target_num} percent offer" if not tamil else f"{target_num}% ஆஃபர்"
            if not has_explicit_placement:
                placement = "end_card"
    elif percent_matches and (re.search(OFFER + "|" + TEXT, text) or (is_change_cmd and active_text)):
        target_num = percent_matches[-1]
        if is_change_cmd and active_text and not re.search(r"\boffer\b.*maathu", text):
            overlay = _substitute_percent_in_text(active_text, target_num)
            updating_existing = True
        elif is_change_cmd and active_text and not re.search(r"offer\s*ah", text):
            overlay = _substitute_percent_in_text(active_text, target_num)
            updating_existing = True
        else:
            overlay = f"{target_num} percent offer" if not tamil else f"{target_num}% ஆஃபர்"
            updating_existing = is_change_cmd and bool(active_text_id)
            if not has_explicit_placement and not updating_existing:
                placement = "end_card"
    elif re.search(TEXT, text):
        # Strip explicit clip / placement suffixes cleanly without leaving 'to' or 'on clip 1'
        content = re.search(
            r"(?:(?:change|update|modify|replace|edit)\s+(?:the\s+)?(?:new\s+)?text(?:\s+to)?|text\s+(?:saying\s+)?|write\s+)(.+?)(?:\s+(?:on\s+clip\s+\d+|at\s+the\s+end|at\s+bottom|at\s+top|at\s+center|podu|pannu|maathu)|[.!]|$)",
            raw,
            re.I,
        )
        if content:
            candidate = content[1].strip().strip("'\"“”")
            if candidate:
                overlay = candidate
                updating_existing = is_change_cmd and bool(active_text_id)
        if not overlay:
            return clarify('What should the text say? Try: Add text "Diwali special" at the end.')
    elif re.search(OFFER, text):
        return clarify("What offer should I show? Try: 20 percent offer at the end.")

    if overlay:
        if len(overlay) > 100 or re.search(r"[/\\]|\.\.|[\x00-\x1f]", overlay):
            return clarify("Use up to 100 characters of promotional text, without file paths.")
        op_params: dict = {"text": overlay}
        if updating_existing and not has_explicit_placement and ctx.get("active_position"):
            op_params["placement"] = ctx["active_position"]
        else:
            op_params["placement"] = placement
        if updating_existing and active_text_id:
            op_params["target_id"] = active_text_id
            if not has_explicit_placement:
                op_params["preserve_placement"] = True
        if clip_target is not None:
            op_params["clip_index"] = clip_target
        if animation is not None:
            op_params["animation"] = animation
        add("set_text_overlay", **op_params)
    elif animation is not None:
        op_params = {"animation": animation}
        if active_text_id:
            op_params["target_id"] = active_text_id
        add("set_overlay_style", **op_params)

    if not result.operations:
        return clarify("Try: Create a 15 seconds reel, add music, trim clip 1, or change the offer to 25 percent.")
    if not 1 <= media_count <= 5:
        return clarify("Upload 1 to 5 photos or video clips before creating or editing a reel.")
    if not create and not has_reel:
        # An explicit setting command can create the first reel using the defaults.
        result.warnings.append("Using all uploaded media with the default 15-second vertical layout.")
    # Unsupported explicit edits must not quietly produce only the supported half.
    if re.search(r"remove photo|delete photo|\breverse\b|3d rotate|camera track|auto reframe", text):
        return clarify("That edit is not supported yet. Use duration, zoom, trim, split, transitions, filters, or promotional text.")
    return result
