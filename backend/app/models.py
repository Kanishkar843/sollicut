from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def uid() -> str:
    return str(uuid4())


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


AspectRatio = Literal["9:16", "16:9", "1:1", "4:5"]
ASPECT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "1:1": (1080, 1080),
    "4:5": (864, 1080),
}

FilterPreset = Literal[
    "none",
    "cinematic",
    "warm",
    "cool",
    "bw",
    "vivid",
    "vintage",
    "high_contrast",
]

TransitionStyle = Literal[
    "none",
    "fade",
    "dissolve",
    "slideleft",
    "slideright",
    "wipeleft",
    "circleopen",
]

TextPosition = Literal["end_card", "bottom", "center", "top"]
TextColor = Literal["lime", "white", "amber", "cyan", "rose"]
TextAnimation = Literal["none", "fade", "slide_up", "pop"]
SpeedCurve = Literal["normal", "slow_mo", "fast", "ramp_in", "ramp_out"]
CutoutMode = Literal["none", "chroma_key", "auto_cutout"]
VocalIsolation = Literal["none", "vocals_only", "music_only"]
StickerBadge = Literal["none", "sale", "new", "top_pick", "tamil_special"]


class Keyframe(StrictModel):
    id: str = Field(default_factory=uid)
    time_seconds: float = Field(ge=0.0, le=30.0)
    x: float = Field(default=0.0, ge=-1.0, le=1.0)
    y: float = Field(default=0.0, ge=-1.0, le=1.0)
    scale: float = Field(default=1.0, ge=0.25, le=3.0)
    rotation: float = Field(default=0.0, ge=-180.0, le=180.0)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    easing: Literal["linear", "ease_in", "ease_out", "ease_in_out"] = "linear"


class TextLayer(StrictModel):
    id: str = Field(default_factory=uid)
    text: str = Field(min_length=1, max_length=100)
    position: TextPosition = "end_card"
    color: TextColor = "lime"
    animation: TextAnimation = "none"
    start_time: float | None = Field(default=None, ge=0.0)
    end_time: float | None = Field(default=None, gt=0.0)
    clip_index: int | None = Field(default=None, ge=1, le=5)
    is_caption: bool = False


class Asset(StrictModel):
    id: str = Field(default_factory=uid)
    filename: str
    media_type: Literal["image", "video", "audio"]
    path: str
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    trim_start: float = Field(default=0.0, ge=0.0)
    trim_end: float | None = Field(default=None, gt=0.0)
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    filter_preset: FilterPreset = "none"
    cutout_mode: CutoutMode = "none"
    chroma_color: str = "0x00ff00"
    chroma_similarity: float = Field(default=0.25, ge=0.01, le=0.6)
    stabilize: bool = False
    relight: float = Field(default=0.0, ge=-0.5, le=0.5)
    keyframes: list[Keyframe] = Field(default_factory=list)


class ReelSettings(StrictModel):
    duration_seconds: float = Field(default=15, ge=3, le=30)
    aspect_ratio: AspectRatio = "9:16"
    width: int = Field(default=720, ge=360, le=1920)
    height: int = Field(default=1280, ge=360, le=1920)
    fps: Literal[30] = 30
    zoom_style: Literal["none", "smooth"] = "smooth"
    music_enabled: bool = True
    music_volume: float = Field(default=.2, ge=0, le=1)
    keep_clip_audio: bool = False
    clip_audio_volume: float = Field(default=.7, ge=0, le=1)
    fit_mode: Literal["contain", "cover"] = "contain"
    overlay_text: str | None = Field(default=None, max_length=100)
    overlay_position: TextPosition = "end_card"
    overlay_color: TextColor = "lime"
    brightness: float = Field(default=0, ge=-.3, le=.3)
    text_layers: list[TextLayer] = Field(default_factory=list)
    active_text_id: str | None = None
    transition_style: TransitionStyle = "none"
    transition_duration: float = Field(default=0.5, ge=0.2, le=1.5)
    filter_preset: FilterPreset = "none"
    speed_curve: SpeedCurve = "normal"
    keyframes: list[Keyframe] = Field(default_factory=list)
    audio_normalize: bool = False
    audio_denoise: bool = False
    voice_enhance: bool = False
    vocal_isolation: VocalIsolation = "none"
    narration_enabled: bool = False
    narration_volume: float = Field(default=0.9, ge=0.0, le=1.5)
    narration_asset_id: str | None = None
    sticker_badge: StickerBadge = "none"
    template_id: str | None = None


class EditOperation(StrictModel):
    id: str = Field(default_factory=uid)
    type: Literal[
        "create_reel",
        "set_duration",
        "set_aspect_ratio",
        "set_zoom_style",
        "set_music",
        "set_music_volume",
        "set_clip_audio",
        "set_fit_mode",
        "set_text_overlay",
        "update_text_layer",
        "remove_text_layer",
        "set_overlay_style",
        "set_brightness",
        "set_transition",
        "set_filter",
        "set_clip_speed",
        "split_clip",
        "set_audio_processing",
        "set_visual_effect",
        "set_keyframes",
        "set_sticker",
        "apply_template",
        "generate_tts",
        "trim_clip",
        "reorder_assets",
        "undo",
        "redo",
        "export",
    ]
    parameters: dict = Field(default_factory=dict)
    source_transcript: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ParsedCommand(StrictModel):
    original_transcript: str
    normalized_text: str
    language_mode: Literal["ta", "en", "ta-en", "unknown"]
    operations: list[EditOperation] = Field(default_factory=list)
    requires_clarification: bool = False
    clarification_question: str | None = None
    warnings: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)


class Snapshot(StrictModel):
    settings: ReelSettings
    edit_history: list[EditOperation]
    revision: int
    output: str | None
    assets: list[Asset] | None = None


class ProjectState(StrictModel):
    id: str = Field(default_factory=uid)
    assets: list[Asset] = Field(default_factory=list)
    settings: ReelSettings = Field(default_factory=ReelSettings)
    edit_history: list[EditOperation] = Field(default_factory=list)
    current_render_revision: int = 0
    next_revision: int = 1
    current_output: str | None = None
    undo_stack: list[Snapshot] = Field(default_factory=list)
    redo_stack: list[Snapshot] = Field(default_factory=list)


class ApplyRequest(StrictModel):
    transcript: str = Field(min_length=1, max_length=1000)


class GenerateRequest(StrictModel):
    transcript: str = Field(min_length=1, max_length=1000)
    duration_seconds: int = Field(default=10, ge=3, le=15)
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=2)


class VisualEditRequest(StrictModel):
    duration_seconds: float | None = Field(default=None, ge=3, le=30)
    aspect_ratio: AspectRatio | None = None
    zoom_style: Literal["none", "smooth"] | None = None
    music_enabled: bool | None = None
    music_volume: float | None = Field(default=None, ge=0, le=1)
    keep_clip_audio: bool | None = None
    clip_audio_volume: float | None = Field(default=None, ge=0, le=1)
    fit_mode: Literal["contain", "cover"] | None = None
    brightness: float | None = Field(default=None, ge=-.3, le=.3)
    overlay_text: str | None = Field(default=None, max_length=100)
    clear_overlay: bool = False
    overlay_position: TextPosition | None = None
    overlay_color: TextColor | None = None
    overlay_animation: TextAnimation | None = None
    active_text_id: str | None = None
    text_layers: list[TextLayer] | None = None
    reorder_asset_ids: list[str] | None = None
    trim_asset_id: str | None = None
    trim_start: float | None = Field(default=None, ge=0)
    trim_end: float | None = Field(default=None, gt=0)
    transition_style: TransitionStyle | None = None
    transition_duration: float | None = Field(default=None, ge=0.2, le=1.5)
    filter_preset: FilterPreset | None = None
    speed_curve: SpeedCurve | None = None
    keyframes: list[Keyframe] | None = None
    audio_normalize: bool | None = None
    audio_denoise: bool | None = None
    voice_enhance: bool | None = None
    vocal_isolation: VocalIsolation | None = None
    narration_enabled: bool | None = None
    narration_volume: float | None = Field(default=None, ge=0.0, le=1.5)
    sticker_badge: StickerBadge | None = None
    clip_asset_id: str | None = None
    clip_speed: float | None = Field(default=None, ge=0.25, le=4.0)
    clip_volume: float | None = Field(default=None, ge=0.0, le=2.0)
    clip_filter_preset: FilterPreset | None = None
    clip_cutout_mode: CutoutMode | None = None
    clip_chroma_color: str | None = None
    clip_chroma_similarity: float | None = Field(default=None, ge=0.01, le=0.6)
    clip_stabilize: bool | None = None
    clip_relight: float | None = Field(default=None, ge=-0.5, le=0.5)
    clip_keyframes: list[Keyframe] | None = None
    split_asset_id: str | None = None
    split_at_seconds: float | None = Field(default=None, gt=0.1)
    render: bool = True


class TTSRequest(StrictModel):
    text: str = Field(min_length=1, max_length=500)
    language: Literal["en", "ta"] = "en"
    voice: str | None = None
    rate: int = Field(default=165, ge=90, le=260)
    render: bool = True


class AutoCaptionRequest(StrictModel):
    asset_id: str | None = None
    language_hint: Literal["en", "ta"] | None = None
    render: bool = True


class ApplyTemplateRequest(StrictModel):
    template_id: str = Field(min_length=1, max_length=64)
    render: bool = True


class AttachAudioRequest(StrictModel):
    audio_id: str = Field(min_length=1, max_length=64)
    render: bool = False


class Job(StrictModel):
    id: str = Field(default_factory=uid)
    project_id: str
    status: Literal["queued", "running", "done", "failed"] = "queued"
    stage: str = "Waiting for renderer"
    error: str | None = None
    revision: int | None = None


class TranscriptResult(StrictModel):
    text: str
    language: str
    elapsed_seconds: float
