"""Real HTTP uploads/render/follow-up/undo/download; deliberately bypasses ASR."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import httpx

from backend.app.media import probe
from scripts.generate_demo_assets import generate


def smoke(url: str, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    generate()
    root = Path(__file__).resolve().parents[1]
    with httpx.Client(base_url=url, timeout=60) as client:
        health = client.get("/api/health").raise_for_status().json()
        assert health["renderer"]["available"], health
        caps = client.get("/api/capabilities").raise_for_status().json()
        assert caps["renderer"]["available"], caps
        assert "generation" in caps, caps
        pid = client.post("/api/projects").raise_for_status().json()["id"]
        endpoint = f"/api/projects/{pid}"
        timings = {}
        try:
            for index in range(1, 5):
                with (root / f"assets/demo/bakery-{index}.png").open("rb") as photo:
                    client.post(endpoint+"/assets", files={"file": (f"bakery-{index}.png", photo, "image/png")}).raise_for_status()

            def apply(text, label):
                start = time.perf_counter()
                response = client.post(endpoint+"/apply", json={"transcript": text}).raise_for_status().json()
                assert "job_id" in response, response
                deadline = time.monotonic()+240
                while time.monotonic() < deadline:
                    job = client.get("/api/jobs/"+response["job_id"]).raise_for_status().json()
                    if job["status"] == "failed":
                        raise AssertionError(job)
                    if job["status"] == "done":
                        timings[label] = round(time.perf_counter()-start, 3)
                        return client.get(endpoint).raise_for_status().json()
                    time.sleep(.5)
                raise TimeoutError("Render did not finish")

            first = apply("Indha photos ellathayum use panni oru 15 seconds Instagram reel create pannu. Smooth zoom effects podu. Background music add pannu. Last la 20 percent offer nu text podu.", "initial_render_seconds")
            original = client.get(endpoint+"/download").raise_for_status().content
            second = apply("Offer ah 25 percent nu maathu. Background music konjam kammi pannu.", "followup_render_seconds")
            assert second["settings"]["overlay_text"] == "25 percent offer"
            assert second["settings"]["music_volume"] < first["settings"]["music_volume"]
            assert second["current_render_revision"] != first["current_render_revision"]
            revised = client.get(endpoint+"/download").raise_for_status().content
            assert hashlib.sha256(original).digest() != hashlib.sha256(revised).digest()
            restored = client.post(endpoint+"/undo").raise_for_status().json()
            assert restored["settings"] == first["settings"]
            assert restored["current_render_revision"] == first["current_render_revision"]
            assert client.get(endpoint+"/download").raise_for_status().content == original
            video = destination / "smoke-reel.mp4"
            video.write_bytes(original)
            (destination / "followup-reel.mp4").write_bytes(revised)
            info = probe(video)
            stream = next(s for s in info["streams"] if s["codec_type"] == "video")
            assert (stream["width"], stream["height"], stream["pix_fmt"], stream["codec_name"]) == (720, 1280, "yuv420p", "h264")
            assert any(s["codec_type"] == "audio" and s["codec_name"] == "aac" for s in info["streams"])
            assert abs(float(info["format"]["duration"])-15) < .15
            report = {"passed": True, "asr_tested": False, "timings": timings, "metadata": info}
            (destination/"smoke-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"passed": True, "asr_tested": False, **timings}))
        finally:
            client.delete(endpoint).raise_for_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--output", type=Path, default=Path("test-artifacts"))
    args = parser.parse_args()
    smoke(args.url, args.output)
