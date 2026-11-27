"""Offline Text-to-Speech (TTS) engine using espeak-ng or pyttsx3."""
import asyncio
import shutil
import subprocess
import wave
from pathlib import Path


class OfflineTTSEngine:
    def __init__(self):
        self.lock = asyncio.Lock()

    def backend_name(self) -> str:
        if shutil.which("espeak-ng"):
            return "espeak-ng"
        if shutil.which("espeak"):
            return "espeak"
        try:
            import pyttsx3  # noqa: F401
            return "pyttsx3"
        except ImportError:
            return "unavailable"

    def status(self) -> dict:
        backend = self.backend_name()
        return {
            "available": backend != "unavailable",
            "backend": backend,
            "languages": ["en", "ta"],
        }

    def _synthesize_sync(self, text: str, output_wav: Path, language: str = "en", rate: int = 165) -> float:
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        temp = output_wav.with_suffix(".tmp.wav")
        espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
        try:
            if espeak_bin:
                voice = "ta" if language == "ta" else "en"
                result = subprocess.run(
                    [espeak_bin, "-v", voice, "-s", str(rate), "-w", str(temp), text],
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                if result.returncode != 0 or not temp.is_file() or temp.stat().st_size < 100:
                    raise RuntimeError(result.stderr.decode("utf-8", errors="replace") or "espeak synthesis failed")
            else:
                import pyttsx3

                com_initialized = False
                try:
                    import pythoncom
                    pythoncom.CoInitialize()
                    com_initialized = True
                except ImportError:
                    pass

                engine = pyttsx3.init()
                try:
                    engine.setProperty("rate", rate)
                    voices = engine.getProperty("voices") or []
                    if language == "ta":
                        for v in voices:
                            meta = f"{getattr(v, 'name', '')} {getattr(v, 'id', '')} {getattr(v, 'languages', '')}".lower()
                            if "tamil" in meta or "ta-in" in meta or "ta_" in meta:
                                engine.setProperty("voice", v.id)
                                break
                    engine.save_to_file(text, str(temp))
                    engine.runAndWait()
                finally:
                    try:
                        engine.stop()
                    except Exception:
                        pass
                    if com_initialized:
                        try:
                            pythoncom.CoUninitialize()
                        except Exception:
                            pass
                if not temp.is_file() or temp.stat().st_size < 100:
                    raise RuntimeError("Offline TTS produced no audio")

            with wave.open(str(temp), "rb") as wav_file:
                frames = wav_file.getnframes()
                framerate = wav_file.getframerate() or 22050
                duration = round(frames / framerate, 2)
            if duration <= 0:
                raise RuntimeError("Generated TTS clip is empty")
            temp.replace(output_wav)
            return duration
        except BaseException:
            temp.unlink(missing_ok=True)
            raise

    async def synthesize(self, text: str, output_wav: Path, language: str = "en", rate: int = 165) -> float:
        if self.backend_name() == "unavailable":
            raise RuntimeError("No offline TTS backend installed (install espeak-ng or pyttsx3).")
        async with self.lock:
            return await asyncio.to_thread(self._synthesize_sync, text, output_wav, language, rate)
