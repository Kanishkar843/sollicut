"""Centralized runtime configuration for SolliCut backend."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(1, int(raw.strip()))
    except ValueError:
        return default


def get_asr_model() -> str:
    return os.getenv("SOLLICUT_ASR_MODEL", "small").strip() or "small"


def get_asr_device() -> str:
    return os.getenv("SOLLICUT_ASR_DEVICE", "cpu").strip() or "cpu"


def get_asr_compute_type() -> str:
    return os.getenv("SOLLICUT_ASR_COMPUTE_TYPE", "int8").strip() or "int8"


def get_asr_threads() -> int:
    return _env_int("SOLLICUT_ASR_THREADS", 4)


def get_model_dir() -> Path:
    return Path(os.getenv("SOLLICUT_MODEL_DIR", str(ROOT / "models")))


def is_indic_asr_enabled() -> bool:
    return _env_bool("SOLLICUT_INDIC_ASR_ENABLED", True)


def get_indic_model_dir() -> Path:
    raw = os.getenv("SOLLICUT_INDIC_MODEL_DIR", "").strip()
    if raw:
        return Path(raw)
    return get_model_dir() / "indicconformer-ta"
