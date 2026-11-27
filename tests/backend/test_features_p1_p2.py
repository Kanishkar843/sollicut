import io
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import main, media, storage
from backend.app.keyframes import ease, interpolate_keyframes
from backend.app.models import Asset, Keyframe, TextLayer
from scripts.generate_demo_assets import generate


def _make_video(path: Path, duration: float = 2.0, with_audio: bool = True, color: str = "#00ff00"):
    args = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=360x640:d={duration}"]
    if with_audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if with_audio:
        args += ["-c:a", "aac"]
    args.append(str(path))
    media.run(args)


def _green_subject_photo(path: Path):
    img = Image.new("RGB", (320, 480), (0, 235, 0))
    for y in range(120, 360):
        for x in range(90, 230):
            img.putpixel((x, y), (220, 70, 50))
    img.save(path)


def _wait_job(client: TestClient, job_id: str) -> dict:
    for _ in range(200):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] == "done":
            return job
        if job["status"] == "failed":
            raise AssertionError(f"Job failed: {job}")
        time.sleep(0.1)
    raise TimeoutError(f"Job {job_id} timed out")


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main.speech, "initialize", lambda: None)
    main.busy.clear()
    main.jobs.clear()
    generate()
    with TestClient(main.app) as client:
        yield client


def test_keyframe_math_and_easing():
    kfs = [
        Keyframe(time_seconds=0.0, x=0.0, y=0.0, scale=1.0, rotation=0.0, opacity=1.0, easing="linear"),
        Keyframe(time_seconds=2.0, x=0.4, y=-0.2, scale=1.6, rotation=20.0, opacity=0.5, easing="ease_in_out"),
    ]
    start = interpolate_keyframes(kfs, 0.0)
    mid = interpolate_keyframes(kfs, 1.0)
    end = interpolate_keyframes(kfs, 2.0)
    assert start["scale"] == 1.0 and end["scale"] == 1.6
    assert abs(mid["scale"] - 1.3) < 0.01
    assert ease(0.5, "ease_in") == 0.25
    assert ease(0.5, "ease_out") == 0.75


def test_xfade_transitions_filters_and_keyframes_render(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    generate()
    project = storage.create()
    folder = storage.project_dir(project.id)
    shutil.copy(storage.ROOT / "assets/demo/bakery-1.png", folder / "assets/1.png")
    shutil.copy(storage.ROOT / "assets/demo/bakery-2.png", folder / "assets/2.png")
    _make_video(folder / "assets/3.mp4", duration=2.0, with_audio=True, color="#224433")

    project.assets = [
        Asset(
            filename="1.png",
            media_type="image",
            path="assets/1.png",
            keyframes=[
                Keyframe(time_seconds=0.0, scale=1.0, rotation=0.0, opacity=1.0),
                Keyframe(time_seconds=1.5, scale=1.25, rotation=8.0, opacity=0.9, easing="ease_in_out"),
            ],
        ),
        Asset(filename="2.png", media_type="image", path="assets/2.png", filter_preset="bw"),
        Asset(filename="3.mp4", media_type="video", path="assets/3.mp4", width=360, height=640, duration_seconds=2.0),
    ]
    project.settings.duration_seconds = 6.0
    project.settings.transition_style = "slideleft"
    project.settings.transition_duration = 0.4
    project.settings.filter_preset = "cinematic"
    project.settings.keep_clip_audio = True
    project.settings.sticker_badge = "sale"
    project.settings.text_layers = [
        TextLayer(text="Flash Offer", position="top", color="cyan", animation="slide_up"),
    ]
    out = media.render(project, 1)
    assert out.is_file() and out.stat().st_size > 2000
    info = media.probe(out)
    assert abs(float(info["format"]["duration"]) - 6.0) < 0.3
    assert any(s["codec_type"] == "audio" for s in info["streams"])


def test_auto_cutout_chroma_key_masks_and_video_fx(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLLICUT_DATA_DIR", str(tmp_path))
    generate()
    project = storage.create()
    folder = storage.project_dir(project.id)
    _green_subject_photo(folder / "assets/green.png")
    shutil.copy(storage.ROOT / "assets/demo/bakery-1.png", folder / "assets/subj.png")
    _make_video(folder / "assets/vid.mp4", duration=1.5, with_audio=True, color="#00ee00")

    a_green = Asset(filename="green.png", media_type="image", path="assets/green.png", cutout_mode="chroma_key", chroma_color="0x00eb00", chroma_similarity=0.25)
    a_subj = Asset(filename="subj.png", media_type="image", path="assets/subj.png", cutout_mode="auto_cutout", relight=0.15)
    a_vid = Asset(filename="vid.mp4", media_type="video", path="assets/vid.mp4", width=360, height=640, duration_seconds=1.5, stabilize=True, speed=0.5, cutout_mode="chroma_key")
    project.assets = [a_green, a_subj, a_vid]
    project.settings.duration_seconds = 5.0
    project.settings.keep_clip_audio = True
    project.settings.audio_denoise = True
    project.settings.audio_normalize = True
    project.settings.voice_enhance = True
    project.settings.vocal_isolation = "vocals_only"

    out = media.render(project, 1)
    assert out.is_file() and out.stat().st_size > 2000
    assert (folder / "overlays" / f"mask-{a_green.id}.png").is_file()
    assert (folder / "overlays" / f"mask-{a_subj.id}.png").is_file()


def test_split_clip_api_and_undo(api_client, tmp_path):
    vid_path = tmp_path / "split_src.mp4"
    _make_video(vid_path, duration=3.0, with_audio=True, color="#335577")
    pid = api_client.post("/api/projects").json()["id"]
    root = f"/api/projects/{pid}"
    up = api_client.post(f"{root}/assets", files={"file": ("clip.mp4", vid_path.read_bytes(), "video/mp4")})
    assert up.status_code == 200
    cid = up.json()["assets"][0]["id"]

    split_res = api_client.post(f"{root}/edit", json={"split_asset_id": cid, "split_at_seconds": 1.5, "render": False})
    assert split_res.status_code == 200
    assets = split_res.json()["project"]["assets"]
    assert len(assets) == 2
    assert assets[0]["trim_end"] == 1.5
    assert assets[1]["trim_start"] == 1.5

    undone = api_client.post(f"{root}/undo").json()
    assert len(undone["assets"]) == 1
    assert undone["assets"][0]["trim_end"] is None


def test_auto_captions_tts_and_catalog_templates(api_client, tmp_path, monkeypatch):
    vid_path = tmp_path / "speech.mp4"
    _make_video(vid_path, duration=2.5, with_audio=True, color="#222233")

    async def fake_segments(path, language_hint=None):
        return [
            {"start": 0.0, "end": 1.1, "text": "Fresh bakery treats"},
            {"start": 1.1, "end": 2.3, "text": "20% off today"},
        ]

    monkeypatch.setattr(main.speech, "transcribe_segments", fake_segments)

    # Check catalog
    cat = api_client.get("/api/assets-catalog")
    assert cat.status_code == 200
    cat_json = cat.json()
    assert len(cat_json["templates"]) >= 4
    assert len(cat_json["audio_packs"]) >= 4
    assert cat_json["stock_video"]["status"] == "deferred"

    pid = api_client.post("/api/projects").json()["id"]
    root = f"/api/projects/{pid}"
    assert api_client.post(f"{root}/assets", files={"file": ("speech.mp4", vid_path.read_bytes(), "video/mp4")}).status_code == 200

    # Auto-captions
    cap_res = api_client.post(f"{root}/auto-captions", json={"render": False})
    assert cap_res.status_code == 200, cap_res.text
    captions = cap_res.json()["captions"]
    assert len(captions) == 2
    assert captions[0]["text"] == "Fresh bakery treats"

    # Edit caption text
    proj = cap_res.json()["project"]
    layers = proj["settings"]["text_layers"]
    layers[0]["text"] = "Fresh handmade cakes"
    saved = api_client.post(f"{root}/edit", json={"text_layers": layers, "render": False}).json()["project"]
    assert saved["settings"]["text_layers"][0]["text"] == "Fresh handmade cakes"

    # Offline TTS generation & narration file serving
    tts_res = api_client.post(f"{root}/tts", json={"text": "Twenty percent festival offer today", "language": "en", "render": True})
    assert tts_res.status_code == 200, tts_res.text
    _wait_job(api_client, tts_res.json()["job_id"])
    nar_audio = api_client.get(f"{root}/narration")
    assert nar_audio.status_code == 200 and len(nar_audio.content) > 500

    # Apply template + attach catalog audio
    tpl_res = api_client.post(f"{root}/apply-template", json={"template_id": "flash_sale", "render": True})
    assert tpl_res.status_code == 200
    _wait_job(api_client, tpl_res.json()["job_id"])
    tpl_proj = api_client.get(root).json()
    assert tpl_proj["settings"]["template_id"] == "flash_sale"
    assert tpl_proj["settings"]["transition_style"] == "slideleft"

    aud_res = api_client.post(f"{root}/attach-catalog-audio", json={"audio_id": "upbeat_pulse", "render": False})
    assert aud_res.status_code == 200
    assert any(a["filename"] == "Upbeat Retail Pulse" for a in aud_res.json()["project"]["assets"])


def test_aspect_ratio_switch_and_inbuilt_soothing_music(api_client, tmp_path):
    cat = api_client.get("/api/assets-catalog").json()
    ratio_ids = {r["id"] for r in cat["aspect_ratios"]}
    assert {"9:16", "16:9", "1:1", "4:5"} <= ratio_ids
    soothing = [p for p in cat["audio_packs"] if p.get("folder") == "music"]
    assert 10 <= len(soothing) <= 15

    # Stream soothing audio preview endpoint
    preview = api_client.get("/api/assets-catalog/audio/soft_calm")
    assert preview.status_code == 200 and len(preview.content) > 1000

    pid = api_client.post("/api/projects").json()["id"]
    root = f"/api/projects/{pid}"
    img_path = tmp_path / "photo.png"
    _green_subject_photo(img_path)
    assert api_client.post(f"{root}/assets", files={"file": ("photo.png", img_path.read_bytes(), "image/png")}).status_code == 200

    # Attach inbuilt soothing track
    att = api_client.post(f"{root}/attach-catalog-audio", json={"audio_id": "soft_calm", "render": False})
    assert att.status_code == 200
    assert any(a["filename"] == "Soft Calm (Soothing)" for a in att.json()["project"]["assets"])

    # Switch to 16:9 landscape and render
    edit = api_client.post(f"{root}/edit", json={"aspect_ratio": "16:9", "duration_seconds": 3, "render": True})
    assert edit.status_code == 200
    _wait_job(api_client, edit.json()["job_id"])

    out_proj = api_client.get(root).json()
    assert out_proj["settings"]["aspect_ratio"] == "16:9"
    assert (out_proj["settings"]["width"], out_proj["settings"]["height"]) == (1280, 720)
    out_file = storage.project_dir(pid) / out_proj["current_output"]
    probe = media.probe(out_file)
    vstream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (vstream["width"], vstream["height"]) == (1280, 720)


def test_undo_redo_ten_snapshot_cap(api_client):
    pid = api_client.post("/api/projects").json()["id"]
    root = f"/api/projects/{pid}"
    for i in range(12):
        r = api_client.post(f"{root}/edit", json={"duration_seconds": 5 + i, "render": False})
        assert r.status_code == 200
    state = api_client.get(root).json()
    assert len(state["undo_stack"]) == 10
    assert state["settings"]["duration_seconds"] == 16

    for _ in range(10):
        assert api_client.post(f"{root}/undo").status_code == 200
    assert api_client.post(f"{root}/undo").status_code == 409
    assert len(api_client.get(root).json()["redo_stack"]) == 10

    for _ in range(10):
        assert api_client.post(f"{root}/redo").status_code == 200
    assert api_client.post(f"{root}/redo").status_code == 409
    assert api_client.get(root).json()["settings"]["duration_seconds"] == 16
