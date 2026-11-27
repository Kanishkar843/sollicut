from pathlib import Path
from PIL import Image, features
from backend.app import storage
from backend.app.media import overlay, probe, render, capabilities
from backend.app.models import Asset
from scripts.generate_demo_assets import generate


def test_tamil_overlay(tmp_path):
    assert features.check_feature("raqm")
    path = tmp_path / "tamil.png"
    overlay("இன்று 20% ஆஃபர்", path)
    with Image.open(path) as im:
        assert im.getchannel("A").getbbox()
    artifacts = Path("test-artifacts")
    artifacts.mkdir(exist_ok=True)
    overlay("இன்று 20% ஆஃபர்", artifacts / "tamil-overlay.png")


def test_real_render(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    assert capabilities()["available"]
    generate()
    project = storage.create()
    folder = storage.project_dir(project.id)
    import shutil
    for i in range(1, 4):
        name = f"assets/{i}.png"
        shutil.copy(storage.ROOT / f"assets/demo/bakery-{i}.png", folder / name)
        project.assets.append(Asset(filename=f"{i}.png", media_type="image", path=name))
    project.settings.duration_seconds = 5
    project.settings.overlay_text = "இன்று 20% ஆஃபர்"
    output = render(project, 1)
    assert output.stat().st_size > 1000
    meta = probe(output)
    video = next(s for s in meta["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"], video["pix_fmt"]) == (720, 1280, "yuv420p")
    assert abs(float(meta["format"]["duration"]) - 5) < .15
    assert any(s["codec_type"] == "audio" for s in meta["streams"])
