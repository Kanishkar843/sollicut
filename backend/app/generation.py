"""Optional Gemini Omni adapter. Credentials stay on the server."""
import base64
import binascii
import os
from pathlib import Path
from typing import Callable

import httpx

MAX_VIDEO_BYTES = 100 * 1024 * 1024
INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


def status() -> dict:
    configured = bool(os.getenv("GEMINI_API_KEY", "").strip())
    return {
        "configured": configured,
        "status": "ready" if configured else "key_not_set",
        "label": "Configured" if configured else "Key not set",
        "model": os.getenv("SOLLICUT_VIDEO_MODEL", "gemini-omni-1.2-flash"),
    }


def _build_input(prompt: str, reference_images: list[tuple[bytes, str]] | None = None):
    instruction = "Create a vertical promotional advertisement. " + prompt.strip()
    if not reference_images:
        return instruction
    items: list[dict] = [
        {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mime_type": mime_type}
        for data, mime_type in reference_images[:2]
    ]
    items.append({"type": "text", "text": instruction})
    return items


async def generate(
    prompt: str,
    output: Path,
    *,
    duration_seconds: int = 10,
    aspect_ratio: str = "9:16",
    reference_images: list[tuple[bytes, str]] | None = None,
    stage: Callable[[str], None] = lambda _: None,
):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("Key not set. Configure GEMINI_API_KEY on the server to enable AI advertisements.")
    if not 3 <= duration_seconds <= 15:
        raise ValueError("Gemini Omni supports video durations between 3 and 15 seconds.")
    if aspect_ratio not in {"9:16", "16:9"}:
        raise ValueError("Unsupported aspect ratio for Gemini Omni.")

    payload = {
        "model": status()["model"],
        "input": _build_input(prompt, reference_images),
        "response_format": {
            "type": "video",
            "aspect_ratio": aspect_ratio,
            "duration": f"{duration_seconds}s",
        },
    }
    timeout = httpx.Timeout(connect=15.0, read=240.0, write=30.0, pool=15.0)
    temporary = output.with_suffix(".tmp.mp4")
    stage("Submitting prompt to Gemini")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                INTERACTIONS_URL,
                headers={"x-goog-api-key": key},
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise RuntimeError("Gemini video generation timed out. Try a shorter prompt or retry later.") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Could not reach the Gemini API ({type(exc).__name__}). Check server network access.") from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Video provider rejected the request (HTTP {response.status_code}). Check model access, billing and quota."
        )

    stage("Decoding generated video")
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError("The provider returned an invalid JSON response.") from exc

    for step in body.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for content in step.get("content", []):
            if content.get("type") == "video" and content.get("mime_type") == "video/mp4" and content.get("data"):
                try:
                    raw_video = base64.b64decode(content["data"], validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise RuntimeError("The provider returned malformed video data.") from exc
                if not raw_video:
                    raise RuntimeError("The provider returned an empty video.")
                if len(raw_video) > MAX_VIDEO_BYTES:
                    raise ValueError("Generated video exceeds the 100 MB local size limit.")
                try:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    temporary.write_bytes(raw_video)
                    temporary.replace(output)
                except BaseException:
                    temporary.unlink(missing_ok=True)
                    raise
                return
    raise RuntimeError("The provider returned no video. The request may have been filtered or failed.")
