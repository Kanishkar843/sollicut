import asyncio
import base64
import httpx
import pytest
from backend.app import generation


def test_key_not_set(monkeypatch,tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY",raising=False)
    assert not generation.status()["configured"]
    with pytest.raises(ValueError,match="Key not set"):
        asyncio.run(generation.generate("A flower shop ad",tmp_path/"out.mp4"))


def test_rest_video_extraction(monkeypatch,tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY","test-key")
    original=httpx.AsyncClient
    def respond(request):
        assert request.headers["x-goog-api-key"]=="test-key"
        return httpx.Response(200,json={"steps":[{"type":"model_output","content":[{"type":"video","mime_type":"video/mp4","data":base64.b64encode(b"test-video-bytes").decode()}]}]})
    monkeypatch.setattr(generation.httpx,"AsyncClient",lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    output=tmp_path/"out.mp4"
    asyncio.run(generation.generate("An ad",output))
    assert output.read_bytes()==b"test-video-bytes"
