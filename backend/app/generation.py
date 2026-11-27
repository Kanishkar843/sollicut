"""Optional Gemini Omni adapter. Credentials stay on the server."""
import base64
import os
from pathlib import Path
import httpx


def status():
    return {"configured": bool(os.getenv("GEMINI_API_KEY")), "model": os.getenv("SOLLICUT_VIDEO_MODEL", "gemini-omni-1.2-flash")}


async def generate(prompt: str, output: Path):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("Key not set. Configure GEMINI_API_KEY on the server to enable AI advertisements.")
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post("https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": key}, json={"model": status()["model"], "input": "Create a vertical promotional advertisement. " + prompt})
        if response.status_code != 200:
            raise RuntimeError(f"Video provider rejected the request (HTTP {response.status_code}). Check model access, billing and quota.")
        for step in response.json().get("steps", []):
            if step.get("type") != "model_output":
                continue
            for content in step.get("content", []):
                if content.get("type") == "video" and content.get("mime_type") == "video/mp4" and content.get("data"):
                    payload = base64.b64decode(content["data"], validate=True)
                    if len(payload) > 100 * 1024 * 1024:
                        raise ValueError("Generated video exceeds the local size limit")
                    output.write_bytes(payload)
                    return
        raise RuntimeError("The provider returned no video. The request may have been filtered or failed.")
