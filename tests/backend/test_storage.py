import pytest
from backend.app import storage


def test_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    project = storage.create()
    project.settings.overlay_text = "இன்று 20% ஆஃபர்"
    storage.save(project)
    assert storage.load(project.id) == project
    assert (storage.project_dir(project.id) / "audio").is_dir()


@pytest.mark.parametrize("value", ["../etc", "/tmp", "not-a-uuid", ""])
def test_reject_paths(value):
    with pytest.raises(ValueError):
        storage.project_dir(value)
