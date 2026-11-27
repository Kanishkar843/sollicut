"""Small, explainable command grammar. Raw speech is never rewritten in-place."""
import re
import unicodedata

from .models import EditOperation, ParsedCommand

NUMBERS = {
    "one": 1, "oru": 1, "ஒன்று": 1, "ஒரு": 1,
    "two": 2, "rendu": 2, "irandu": 2, "இரண்டு": 2,
    "three": 3, "moonu": 3, "moonru": 3, "மூன்று": 3,
    "five": 5, "anju": 5, "ஐந்து": 5,
    "ten": 10, "pathu": 10, "பத்து": 10,
    "fifteen": 15, "pathinainthu": 15, "பதினைந்து": 15,
    "twenty": 20, "irubathu": 20, "இருபது": 20,
    "thirty": 30, "muppathu": 30, "முப்பது": 30,
}
MUSIC = r"music|bgm|மியூசிக்|இசை"
REDUCE = r"kammi|reduce|lower|கம்மி|குறை"
OFFER = r"offer|discount|ஆஃபர்|தள்ளுபடி"
TEXT = r"text|எழுத்து|வாசகம்|உரை"


def normalize(raw: str) -> str:
    text = unicodedata.normalize("NFC", raw).lower()
    text = re.sub(r"(?<=\d)(?=[a-z])", " ", text)
    text = re.sub(r"twenty[ -]+five|irubathi anju|இருபத்து ஐந்து", "25", text)
    text = re.sub(r"background\s*music", "background music", text)
    # Unicode-aware whitespace boundaries keep Tamil combining marks intact.
    for word, number in NUMBERS.items():
        text = re.sub(r"(?<!\S)" + re.escape(word) + r"(?=\s|[.,!?%]|$)", str(number), text)
    return re.sub(r"\s+", " ", text).strip()


def parse(raw: str, image_count: int, has_reel: bool = False) -> ParsedCommand:
    text = normalize(raw)
    tamil = bool(re.search(r"[\u0b80-\u0bff]", raw))
    latin = bool(re.search(r"[a-zA-Z]", raw))
    tanglish = bool(re.search(r"pannu|podu|maathu|kammi|indha|panni", text))
    result = ParsedCommand(original_transcript=raw, normalized_text=text,
        language_mode="ta-en" if (tamil and latin) or tanglish else "ta" if tamil else "en" if latin else "unknown")

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
        return clarify("This prototype edits the whole reel. Say a duration, music or offer change.")
    if re.search(r"undo|திரும்ப மாற்று", text):
        if re.search(r"music|percent|seconds|zoom", text):
            return clarify("Please say undo on its own, then record the next change.")
        add("undo")
        return result
    if re.fullmatch(r"(?:export|download|save)(?:\s+(?:reel|video|pannu|it))*[.!]?", text):
        add("export")
        return result

    duration = re.search(r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|விநாடி|வினாடி)", text)
    create = bool(re.search(r"create|make|உருவாக்கு|உருவாக்க|photos.*(?:reel|ரீல்)|படங்கள்.*ரீல்", text))
    if create:
        add("create_reel", duration_seconds=float(duration[1]) if duration else 15, aspect_ratio="9:16", asset_selection="all")
    elif duration:
        add("set_duration", duration_seconds=float(duration[1]))
    if duration and not 3 <= float(duration[1]) <= 30:
        return clarify("Choose a reel length between 3 and 30 seconds.")
    if re.search(r"reel format|vertical|9\s*:\s*16|செங்குத்து", text) and not create:
        add("set_aspect_ratio", aspect_ratio="9:16")
    if re.search(r"landscape|16\s*:\s*9|square", text):
        return clarify("Only vertical 9:16 reels are supported in this prototype.")
    if re.search(r"zoom|ஜூம்", text):
        add("set_zoom_style", style="none" if re.search(r"no zoom|remove zoom|zoom off", text) else "smooth")
    if re.search(MUSIC, text):
        if re.search(REDUCE, text):
            add("set_music_volume", direction="decrease")
        elif re.search(r"louder|increase|அதிக|kootu", text):
            add("set_music_volume", direction="increase")
        else:
            add("set_music", enabled=not bool(re.search(r"\b(?:remove|off|without)\b|வேண்டாம்|நிறுத்து", text)))
    if re.search(r"bright|பிரைட்|வெளிச்ச", text):
        add("set_brightness", value=-.1 if re.search(REDUCE, text) else .1)

    quoted = re.search(r'["“]([^"”]+)["”]', raw)
    percent = re.search(r"(\d+(?:\.\d+)?)\s*(?:percent|%|சதவீதம்)", text)
    placement = "end_card" if re.search(r"last|end|கடைசி", text) else "bottom"
    overlay = None
    if quoted and re.search(TEXT + "|" + OFFER, text):
        overlay = quoted[1]
    elif percent and re.search(OFFER + "|" + TEXT, text):
        overlay = f"{percent[1]} percent offer" if not tamil else f"{percent[1]}% ஆஃபர்"
        placement = "end_card"
    elif re.search(TEXT, text):
        content = re.search(r"(?:text\s+(?:saying\s+)?|write\s+)(.+?)(?:\s+(?:at the end|at bottom|podu|pannu)|[.!]|$)", raw, re.I)
        if content:
            overlay = content[1].strip()
        else:
            return clarify('What should the text say? Try: Add text "Diwali special" at the end.')
    elif re.search(OFFER, text):
        return clarify("What offer should I show? Try: 20 percent offer at the end.")
    if overlay:
        if len(overlay) > 100 or re.search(r"[/\\]|\.\.|[\x00-\x1f]", overlay):
            return clarify("Use up to 100 characters of promotional text, without file paths.")
        add("set_text_overlay", text=overlay, placement=placement)
    if not result.operations:
        return clarify("Try: Create a 15 seconds reel, add music, or change the offer to 25 percent.")
    if not 3 <= image_count <= 5:
        return clarify("Upload 3 to 5 product photos before creating or editing a reel.")
    if not create and not has_reel:
        # An explicit setting command can create the first reel using the defaults.
        result.warnings.append("Using all uploaded photos with the default 15-second vertical layout.")
    # Unsupported explicit edits must not quietly produce only the supported half.
    if re.search(r"trim|slow motion|subtitle|remove photo|delete photo|reorder|reverse|rotate", text):
        return clarify("That edit is not supported yet. Use duration, zoom, music or promotional text.")
    return result
