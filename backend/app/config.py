"""Centralized runtime configuration for SolliCut backend."""
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger("sollicut.config")

DeploymentProfileName = Literal["lightweight", "balanced", "accuracy"]


@dataclass(frozen=True)
class ProfileSpec:
    """Resolved CPU deployment profile settings."""

    name: DeploymentProfileName
    asr_model: str
    indic_enabled: bool
    use_silero_vad: bool
    resampler: Literal["linear", "fir_kaiser"]
    default_threads: int


DEPLOYMENT_PROFILES: dict[DeploymentProfileName, ProfileSpec] = {
    "lightweight": ProfileSpec(
        name="lightweight",
        asr_model="small",
        indic_enabled=True,
        use_silero_vad=False,
        resampler="linear",
        default_threads=2,
    ),
    "balanced": ProfileSpec(
        name="balanced",
        asr_model="small",
        indic_enabled=True,
        use_silero_vad=True,
        resampler="fir_kaiser",
        default_threads=4,
    ),
    "accuracy": ProfileSpec(
        name="accuracy",
        asr_model="large-v3-turbo",
        indic_enabled=True,
        use_silero_vad=True,
        resampler="fir_kaiser",
        default_threads=4,
    ),
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return max(1, int(raw.strip()))
    except ValueError:
        return default


def get_profile_name() -> DeploymentProfileName:
    raw = (os.getenv("SOLLICUT_PROFILE") or "balanced").strip().lower()
    if raw in DEPLOYMENT_PROFILES:
        return raw  # type: ignore[return-value]
    if raw:
        logger.warning("Unknown SOLLICUT_PROFILE '%s'; falling back to 'balanced'.", raw)
    return "balanced"


def get_profile_spec() -> ProfileSpec:
    return DEPLOYMENT_PROFILES[get_profile_name()]


def get_asr_model() -> str:
    raw = os.getenv("SOLLICUT_ASR_MODEL", "").strip()
    if raw:
        return raw
    return get_profile_spec().asr_model


def get_asr_device() -> str:
    return os.getenv("SOLLICUT_ASR_DEVICE", "cpu").strip() or "cpu"


def get_asr_compute_type() -> str:
    return os.getenv("SOLLICUT_ASR_COMPUTE_TYPE", "int8").strip() or "int8"


def get_asr_threads() -> int:
    return _env_int("SOLLICUT_ASR_THREADS", get_profile_spec().default_threads)


def get_model_dir() -> Path:
    return Path(os.getenv("SOLLICUT_MODEL_DIR", str(ROOT / "models")))


def is_indic_asr_enabled() -> bool:
    return _env_bool("SOLLICUT_INDIC_ASR_ENABLED", get_profile_spec().indic_enabled)


def is_silero_vad_enabled() -> bool:
    return _env_bool("SOLLICUT_VAD_ENABLED", get_profile_spec().use_silero_vad)


def get_resampler_mode() -> Literal["linear", "fir_kaiser"]:
    raw = (os.getenv("SOLLICUT_RESAMPLER") or "").strip().lower()
    if raw in {"linear", "fir_kaiser"}:
        return raw  # type: ignore[return-value]
    return get_profile_spec().resampler


def get_indic_model_dir() -> Path:
    raw = os.getenv("SOLLICUT_INDIC_MODEL_DIR", "").strip()
    if raw:
        return Path(raw)
    return get_model_dir() / "indicconformer-ta"
