from pathlib import Path
from PIL import Image, features
from backend.app import storage
from backend.app.media import overlay, probe, render, capabilities, run
from backend.app.models import Asset
from scripts.generate_demo_assets import generate


def _make_sample_video(path: Path, with_audio: bool = True, duration: float = 2.0):
    args = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=#d7ef41:s=640x480:d={duration}",
    ]
    if with_audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if with_audio:
        args += ["-c:a", "aac"]
    args.append(str(path))
    run(args)


def test_tamil_overlay(tmp_path):
    path = tmp_path / "tamil.png"
    overlay("இன்று 20% ஆஃபர்", path)
    with Image.open(path) as im:
        assert im.getchannel("A").getbbox()
    artifacts = Path("test-artifacts")
    artifacts.mkdir(exist_ok=True)
    overlay("இன்று 20% ஆஃபர்", artifacts / "tamil-overlay.png")
    if features.check_feature("raqm"):
        assert capabilities()["raqm"] is True


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


def test_mixed_media_trim_and_clip_audio_render(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    generate()
    project = storage.create()
    folder = storage.project_dir(project.id)
    import shutil
    shutil.copy(storage.ROOT / "assets/demo/bakery-1.png", folder / "assets/1.png")
    project.assets.append(Asset(filename="1.png", media_type="image", path="assets/1.png"))
    _make_sample_video(folder / "assets/clip.mp4", with_audio=True, duration=3.0)
    project.assets.append(
        Asset(filename="clip.mp4", media_type="video", path="assets/clip.mp4", width=640, height=480, duration_seconds=3.0, trim_start=0.5, trim_end=2.5)
    )
    project.settings.duration_seconds = 4
    project.settings.keep_clip_audio = True
    project.settings.fit_mode = "cover"
    project.settings.overlay_text = "Fresh today"
    project.settings.overlay_color = "amber"
    output = render(project, 1)
    assert output.stat().st_size > 1000
    meta = probe(output)
    video = next(s for s in meta["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"], video["pix_fmt"]) == (720, 1280, "yuv420p")
    assert abs(float(meta["format"]["duration"]) - 4) < .2
    assert any(s["codec_type"] == "audio" for s in meta["streams"])


def test_short_video_loop_with_clip_audio_and_music(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    generate()
    project = storage.create()
    folder = storage.project_dir(project.id)
    _make_sample_video(folder / "assets/short.mp4", with_audio=True, duration=1.0)
    project.assets.append(
        Asset(filename="short.mp4", media_type="video", path="assets/short.mp4", width=640, height=480, duration_seconds=1.0)
    )
    project.settings.duration_seconds = 4
    project.settings.keep_clip_audio = True
    project.settings.music_enabled = True
    output = render(project, 1)
    meta = probe(output)
    assert abs(float(meta["format"]["duration"]) - 4) < .2
    assert any(s["codec_type"] == "audio" for s in meta["streams"])
