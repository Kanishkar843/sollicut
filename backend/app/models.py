from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


def uid() -> str:
    return str(uuid4())


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class ReelSettings(StrictModel):
    duration_seconds: float = Field(default=15, ge=3, le=30)
    width: Literal[720] = 720
    height: Literal[1280] = 1280
    fps: Literal[30] = 30
    zoom_style: Literal["none", "smooth"] = "smooth"
    music_enabled: bool = True
    music_volume: float = Field(default=.2, ge=0, le=1)
    keep_clip_audio: bool = False
    clip_audio_volume: float = Field(default=.7, ge=0, le=1)
    fit_mode: Literal["contain", "cover"] = "contain"
    overlay_text: str | None = Field(default=None, max_length=100)
    overlay_position: Literal["end_card", "bottom", "center"] = "end_card"
    overlay_color: Literal["lime", "white", "amber"] = "lime"
    brightness: float = Field(default=0, ge=-.3, le=.3)


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
        "set_overlay_style",
        "set_brightness",
        "trim_clip",
        "reorder_assets",
        "undo",
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


class ApplyRequest(StrictModel):
    transcript: str = Field(min_length=1, max_length=1000)


class GenerateRequest(StrictModel):
    transcript: str = Field(min_length=1, max_length=1000)
    duration_seconds: int = Field(default=10, ge=3, le=15)
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=2)


class VisualEditRequest(StrictModel):
    duration_seconds: float | None = Field(default=None, ge=3, le=30)
    zoom_style: Literal["none", "smooth"] | None = None
    music_enabled: bool | None = None
    music_volume: float | None = Field(default=None, ge=0, le=1)
    keep_clip_audio: bool | None = None
    clip_audio_volume: float | None = Field(default=None, ge=0, le=1)
    fit_mode: Literal["contain", "cover"] | None = None
    brightness: float | None = Field(default=None, ge=-.3, le=.3)
    overlay_text: str | None = Field(default=None, max_length=100)
    clear_overlay: bool = False
    overlay_position: Literal["end_card", "bottom", "center"] | None = None
    overlay_color: Literal["lime", "white", "amber"] | None = None
    reorder_asset_ids: list[str] | None = None
    trim_asset_id: str | None = None
    trim_start: float | None = Field(default=None, ge=0)
    trim_end: float | None = Field(default=None, gt=0)
    render: bool = True


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
