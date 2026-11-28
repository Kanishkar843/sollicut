"""Public dual-ASR model download at build/setup time; never blocks HTTP startup."""
import os
import sys
import urllib.request
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
from faster_whisper.utils import download_model

INDIC_BASE_URL = "https://huggingface.co/parismitaglobalsolutions/indicconformer-sherpa-onnx/resolve/main"
INDIC_FILES = {
    "model.int8.onnx": f"{INDIC_BASE_URL}/ta/model.int8.onnx",
    "tokens.txt": f"{INDIC_BASE_URL}/tokens.txt",
}

SILERO_VAD_URL = (
    "https://github.com/snakers4/silero-vad/raw/refs/heads/master"
    "/src/silero_vad/data/silero_vad.onnx"
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _download_file(url: str, dest: Path) -> None:
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"Skipping existing {dest} ({dest.stat().st_size} bytes)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SolliCut-ModelDownloader/1.0"})
        with urllib.request.urlopen(req, timeout=300) as resp, tmp.open("wb") as out:
            while chunk := resp.read(1024 * 1024):
                out.write(chunk)
        if not tmp.is_file() or tmp.stat().st_size == 0:
            raise RuntimeError(f"Downloaded empty file from {url}")
        os.replace(tmp, dest)
        print(f"Downloaded {dest.name} to {dest} ({dest.stat().st_size} bytes)")
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def download_whisper(model: str, model_root: Path) -> bool:
    target = model_root / model
    if (target / "model.bin").is_file() and (target / "model.bin").stat().st_size > 0:
        print(f"Skipping existing Whisper '{model}' at {target}")
        return True
    try:
        target.mkdir(parents=True, exist_ok=True)
        download_model(model, output_dir=str(target))
        if not (target / "model.bin").is_file() or (target / "model.bin").stat().st_size == 0:
            raise RuntimeError(f"Whisper model.bin missing or empty in {target}")
        print(f"Public {model} model downloaded to {target}")
        return True
    except Exception as exc:
        print(f"Warning: Whisper '{model}' download failed: {exc}", file=sys.stderr)
        return False


def download_indicconformer(indic_dir: Path) -> bool:
    try:
        for filename, url in INDIC_FILES.items():
            _download_file(url, indic_dir / filename)
        return True
    except Exception as exc:
        print(f"Warning: IndicConformer-TA download failed: {exc}", file=sys.stderr)
        return False


def download_silero_vad(model_root: Path) -> bool:
    """Download the Silero VAD ONNX model (MIT license, no auth required)."""
    dest = model_root / "silero_vad" / "silero_vad.onnx"
    try:
        _download_file(SILERO_VAD_URL, dest)
        return True
    except Exception as exc:
        print(f"Warning: Silero VAD download failed: {exc}", file=sys.stderr)
        return False


if __name__ == "__main__":
    profile = (os.getenv("SOLLICUT_PROFILE") or "balanced").strip().lower()
    default_model = "large-v3-turbo" if profile == "accuracy" else "small"
    model = os.getenv("SOLLICUT_ASR_MODEL", "").strip() or default_model
    model_root = Path(os.getenv("SOLLICUT_MODEL_DIR", "models"))
    indic_enabled = _env_bool("SOLLICUT_INDIC_ASR_ENABLED", True)
    vad_enabled = _env_bool("SOLLICUT_VAD_ENABLED", profile != "lightweight")
    indic_dir = Path(os.getenv("SOLLICUT_INDIC_MODEL_DIR", "").strip() or (model_root / "indicconformer-ta"))

    ok_whisper = download_whisper(model, model_root)
    ok_indic = download_indicconformer(indic_dir) if indic_enabled else True
    ok_vad = download_silero_vad(model_root) if vad_enabled else True
    if not ok_whisper and not ok_indic:
        sys.exit(1)
    if vad_enabled and not ok_vad:
        print("Warning: Silero VAD unavailable — will fall back to RMS gate.", file=sys.stderr)
