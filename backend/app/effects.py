"""Offline visual effects, cutout (U^2-Net ONNX + OpenCV GrabCut/ChromaKey), color filters, and audio DSP."""
import os
from pathlib import Path

import cv2
import numpy as np

from .storage import ROOT

FILTER_CHAINS: dict[str, str] = {
    "none": "",
    "cinematic": "eq=contrast=1.12:saturation=0.88,colorbalance=rs=-0.03:bs=0.05",
    "warm": "colorbalance=rs=0.08:gs=0.03:bs=-0.07,eq=saturation=1.1",
    "cool": "colorbalance=rs=-0.06:gs=0.01:bs=0.09,eq=saturation=0.95",
    "bw": "hue=s=0,eq=contrast=1.08",
    "vivid": "eq=contrast=1.14:saturation=1.35",
    "vintage": "colorbalance=rs=0.09:gs=0.02:bs=-0.06,eq=contrast=0.92:saturation=0.75,vignette=PI/5",
    "high_contrast": "eq=contrast=1.28:saturation=1.08",
}


def _find_u2net_model() -> Path | None:
    env_path = os.getenv("SOLLICUT_U2NET_MODEL", "").strip()
    candidates = [Path(env_path)] if env_path else []
    model_dir = Path(os.getenv("SOLLICUT_MODEL_DIR", str(ROOT / "models")))
    candidates.extend([model_dir / "u2net.onnx", model_dir / "u2netp.onnx"])
    for cand in candidates:
        if cand and cand.is_file():
            return cand
    return None


def cutout_capabilities() -> dict:
    model_path = _find_u2net_model()
    return {
        "backend": "u2net_onnx" if model_path else "opencv_grabcut",
        "u2net_ready": bool(model_path),
        "chroma_key": True,
    }


def _parse_hex_bgr(hex_color: str) -> tuple[int, int, int]:
    cleaned = hex_color.strip().lower().replace("0x", "").lstrip("#")
    if len(cleaned) != 6:
        return (0, 255, 0)
    try:
        r = int(cleaned[0:2], 16)
        g = int(cleaned[2:4], 16)
        b = int(cleaned[4:6], 16)
        return (b, g, r)
    except ValueError:
        return (0, 255, 0)


def _u2net_alpha(bgr: np.ndarray, model_path: Path) -> np.ndarray:
    import onnxruntime as ort

    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(cv2.resize(bgr, (320, 320)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    inp = np.transpose((rgb - mean) / std, (2, 0, 1))[None, ...].astype(np.float32)
    sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    out = sess.run(None, {input_name: inp})[0]
    pred = np.squeeze(out)
    pred = (pred - pred.min()) / (pred.max() - pred.min() + 1e-8)
    mask = cv2.resize((pred * 255.0).astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR)
    return mask


def _grabcut_alpha(bgr: np.ndarray) -> np.ndarray:
    h, w = bgr.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    margin_x = max(4, int(w * 0.08))
    margin_y = max(4, int(h * 0.08))
    rect = (margin_x, margin_y, max(8, w - 2 * margin_x), max(8, h - 2 * margin_y))
    try:
        cv2.grabCut(bgr, mask, rect, bgd, fgd, 3, cv2.GC_INIT_WITH_RECT)
        fg = np.where((mask == 1) | (mask == 3), 255, 0).astype(np.uint8)
    except cv2.error:
        fg = np.full((h, w), 255, dtype=np.uint8)
    if fg.max() == 0:
        # Fallback if subject touches edges evenly
        fg[margin_y : h - margin_y, margin_x : w - margin_x] = 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel)
    fg = cv2.GaussianBlur(fg, (5, 5), 0)
    return fg


def auto_cutout_image(input_path: Path, output_path: Path, mask_path: Path | None = None) -> Path:
    bgr = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Could not read image for cutout: {input_path}")
    u2net = _find_u2net_model()
    alpha = _u2net_alpha(bgr, u2net) if u2net else _grabcut_alpha(bgr)
    if mask_path is not None:
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(mask_path), alpha)
    alpha_f = (alpha.astype(np.float32) / 255.0)[..., None]
    backdrop = np.full_like(bgr, (15, 17, 14), dtype=np.uint8).astype(np.float32)
    comp = (bgr.astype(np.float32) * alpha_f + backdrop * (1.0 - alpha_f)).astype(np.uint8)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), comp)
    return output_path


def chroma_key_image(
    input_path: Path,
    output_path: Path,
    mask_path: Path | None = None,
    hex_color: str = "0x00ff00",
    similarity: float = 0.25,
) -> Path:
    bgr = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Could not read image for chroma key: {input_path}")
    key_bgr = np.array(_parse_hex_bgr(hex_color), dtype=np.float32)
    dist = np.linalg.norm(bgr.astype(np.float32) - key_bgr, axis=2) / 441.67
    thresh = max(0.01, min(0.6, float(similarity)))
    alpha = np.clip((dist - thresh) / 0.12, 0.0, 1.0)
    alpha_u8 = (alpha * 255.0).astype(np.uint8)
    if mask_path is not None:
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(mask_path), alpha_u8)
    alpha_f = alpha[..., None].astype(np.float32)
    backdrop = np.full_like(bgr, (15, 17, 14), dtype=np.uint8).astype(np.float32)
    comp = (bgr.astype(np.float32) * alpha_f + backdrop * (1.0 - alpha_f)).astype(np.uint8)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), comp)
    return output_path


def build_audio_filter_chain(
    *,
    denoise: bool = False,
    normalize: bool = False,
    voice_enhance: bool = False,
    vocal_isolation: str = "none",
) -> list[str]:
    parts: list[str] = []
    if denoise:
        parts.append("afftdn=nf=-25")
    if voice_enhance:
        parts.append("highpass=f=85,lowpass=f=11000,acompressor=threshold=-18dB:ratio=3")
    if vocal_isolation == "vocals_only":
        parts.append("highpass=f=220,lowpass=f=3600")
    elif vocal_isolation == "music_only":
        parts.append("lowpass=f=260")
    if normalize:
        parts.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    return parts
