import json
import os
from pathlib import Path
from uuid import UUID

from .models import ProjectState

ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return Path(os.getenv("SOLLICUT_DATA_DIR", str(ROOT / "data")))


def project_dir(project_id: str) -> Path:
    try:
        if str(UUID(project_id)) != project_id:
            raise ValueError("Noncanonical UUID")
    except (ValueError, AttributeError):
        raise ValueError("Invalid project ID") from None
    return data_dir() / "projects" / project_id


def save(project: ProjectState) -> None:
    folder = project_dir(project.id)
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / "project.json.tmp"
    temporary.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, folder / "project.json")


def load(project_id: str) -> ProjectState:
    path = project_dir(project_id) / "project.json"
    if not path.is_file():
        raise FileNotFoundError("Project not found")
    return ProjectState.model_validate(json.loads(path.read_text(encoding="utf-8")))


def create() -> ProjectState:
    project = ProjectState()
    for directory in ("assets", "audio", "renders", "overlays"):
        (project_dir(project.id) / directory).mkdir(parents=True, exist_ok=True)
    save(project)
    return project
