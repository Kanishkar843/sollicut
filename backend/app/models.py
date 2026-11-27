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


class ReelSettings(StrictModel):
    duration_seconds: float = Field(default=15, ge=3, le=30)
    width: Literal[720] = 720
    height: Literal[1280] = 1280
    fps: Literal[30] = 30
    zoom_style: Literal["none", "smooth"] = "smooth"
    music_enabled: bool = True
    music_volume: float = Field(default=.2, ge=0, le=1)
    overlay_text: str | None = Field(default=None, max_length=100)
    overlay_position: Literal["end_card", "bottom", "center"] = "end_card"
    brightness: float = Field(default=0, ge=-.3, le=.3)


class EditOperation(StrictModel):
    id: str = Field(default_factory=uid)
    type: Literal["create_reel", "set_duration", "set_aspect_ratio", "set_zoom_style", "set_music", "set_music_volume", "set_text_overlay", "set_brightness", "undo", "export"]
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
