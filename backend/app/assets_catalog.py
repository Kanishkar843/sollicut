"""Built-in royalty-free local templates, audio/SFX packs, filter/transition categories, and stickers."""

TEMPLATES = [
    {
        "id": "flash_sale",
        "name": "Flash Sale Drop",
        "description": "Fast 10s vertical showcase with slide transition, vivid color, and bottom lime offer banner.",
        "badge": "Retail / Boutique",
        "settings": {
            "duration_seconds": 10,
            "zoom_style": "smooth",
            "transition_style": "slideleft",
            "transition_duration": 0.4,
            "filter_preset": "vivid",
            "fit_mode": "cover",
            "sticker_badge": "sale",
            "text_layers": [
                {
                    "id": "tpl-flash-1",
                    "text": "20% Flash Sale Today",
                    "position": "end_card",
                    "color": "lime",
                    "animation": "pop",
                    "is_caption": False,
                }
            ],
            "active_text_id": "tpl-flash-1",
            "template_id": "flash_sale",
        },
    },
    {
        "id": "festival_tamil",
        "name": "Festive Tamil Promo",
        "description": "Warm 15s festive reel with smooth dissolve, Noto Sans Tamil overlay, and warm amber badge.",
        "badge": "Tamil / Festive",
        "settings": {
            "duration_seconds": 15,
            "zoom_style": "smooth",
            "transition_style": "dissolve",
            "transition_duration": 0.6,
            "filter_preset": "warm",
            "fit_mode": "contain",
            "sticker_badge": "tamil_special",
            "text_layers": [
                {
                    "id": "tpl-tamil-1",
                    "text": "பண்டிகை சிறப்பு 20% ஆஃபர்",
                    "position": "end_card",
                    "color": "amber",
                    "animation": "fade",
                    "is_caption": False,
                }
            ],
            "active_text_id": "tpl-tamil-1",
            "template_id": "festival_tamil",
        },
    },
    {
        "id": "new_arrival",
        "name": "Cinematic New Arrival",
        "description": "12s moody cinematic grading with fade transitions and crisp white title card.",
        "badge": "Craft / Studio",
        "settings": {
            "duration_seconds": 12,
            "zoom_style": "smooth",
            "transition_style": "fade",
            "transition_duration": 0.5,
            "filter_preset": "cinematic",
            "fit_mode": "cover",
            "sticker_badge": "new",
            "text_layers": [
                {
                    "id": "tpl-new-1",
                    "text": "New Collection Out Now",
                    "position": "bottom",
                    "color": "white",
                    "animation": "slide_up",
                    "is_caption": False,
                }
            ],
            "active_text_id": "tpl-new-1",
            "template_id": "new_arrival",
        },
    },
    {
        "id": "product_demo",
        "name": "Clean Product Showcase",
        "description": "15s crisp high-contrast layout preserving clip audio and top product callout.",
        "badge": "Kitchen / Demo",
        "settings": {
            "duration_seconds": 15,
            "zoom_style": "none",
            "transition_style": "wipeleft",
            "transition_duration": 0.4,
            "filter_preset": "high_contrast",
            "fit_mode": "contain",
            "sticker_badge": "top_pick",
            "text_layers": [
                {
                    "id": "tpl-demo-1",
                    "text": "Order Fresh Today",
                    "position": "top",
                    "color": "cyan",
                    "animation": "fade",
                    "is_caption": False,
                }
            ],
            "active_text_id": "tpl-demo-1",
            "template_id": "product_demo",
        },
    },
]

AUDIO_PACKS = [
    {
        "id": "demo_chord_bed",
        "name": "Original Demo Chord Bed",
        "category": "Music",
        "filename": "music.wav",
        "duration_seconds": 8.0,
        "license": "Generated in-repo (MIT)",
    },
    {
        "id": "upbeat_pulse",
        "name": "Upbeat Retail Pulse",
        "category": "Music",
        "filename": "upbeat-pulse.wav",
        "duration_seconds": 8.0,
        "license": "Generated in-repo (MIT)",
    },
    {
        "id": "ambient_pad",
        "name": "Warm Ambient Craft Pad",
        "category": "Music",
        "filename": "ambient-pad.wav",
        "duration_seconds": 8.0,
        "license": "Generated in-repo (MIT)",
    },
    {
        "id": "sfx_whoosh",
        "name": "Transition Whoosh SFX",
        "category": "SFX",
        "filename": "sfx-whoosh.wav",
        "duration_seconds": 1.2,
        "license": "Generated in-repo (MIT)",
    },
    {
        "id": "sfx_chime",
        "name": "Offer Reveal Chime SFX",
        "category": "SFX",
        "filename": "sfx-chime.wav",
        "duration_seconds": 1.5,
        "license": "Generated in-repo (MIT)",
    },
]

FILTERS = [
    {"id": "none", "label": "Original", "category": "Basic"},
    {"id": "vivid", "label": "Vivid", "category": "Pop"},
    {"id": "high_contrast", "label": "High Contrast", "category": "Basic"},
    {"id": "cinematic", "label": "Cinematic", "category": "Cinematic"},
    {"id": "warm", "label": "Warm", "category": "Mood"},
    {"id": "cool", "label": "Cool", "category": "Mood"},
    {"id": "vintage", "label": "Vintage", "category": "Cinematic"},
    {"id": "bw", "label": "B&W", "category": "Mood"},
]

TRANSITIONS = [
    {"id": "none", "label": "Cut (None)", "category": "Basic"},
    {"id": "fade", "label": "Fade", "category": "Basic"},
    {"id": "dissolve", "label": "Dissolve", "category": "Basic"},
    {"id": "slideleft", "label": "Slide Left", "category": "Motion"},
    {"id": "slideright", "label": "Slide Right", "category": "Motion"},
    {"id": "wipeleft", "label": "Wipe", "category": "Motion"},
    {"id": "circleopen", "label": "Circle Reveal", "category": "Shape"},
]

STICKERS = [
    {"id": "none", "label": "None"},
    {"id": "sale", "label": "SALE"},
    {"id": "new", "label": "NEW"},
    {"id": "top_pick", "label": "TOP PICK"},
    {"id": "tamil_special", "label": "சிறப்பு (Special)"},
]


def get_catalog() -> dict:
    return {
        "templates": TEMPLATES,
        "audio_packs": AUDIO_PACKS,
        "filters": FILTERS,
        "transitions": TRANSITIONS,
        "stickers": STICKERS,
        "stock_video": {
            "status": "deferred",
            "note": "Remote stock video libraries are deferred (P2+) to keep SolliCut 100% offline-capable and free of unlicensed third-party media.",
            "items": [],
        },
    }
