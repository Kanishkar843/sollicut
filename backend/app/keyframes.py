"""Manual keyframe interpolation and frame transform helpers (OpenCV)."""
import math
from typing import Iterable

import cv2
import numpy as np

from .models import Keyframe


def ease(t: float, mode: str = "linear") -> float:
    t = max(0.0, min(1.0, float(t)))
    if mode == "ease_in":
        return t * t
    if mode == "ease_out":
        return 1.0 - (1.0 - t) ** 2
    if mode == "ease_in_out":
        return 0.5 * (1.0 - math.cos(math.pi * t))
    return t


def interpolate_keyframes(keyframes: Iterable[Keyframe], time_sec: float) -> dict[str, float]:
    ordered = sorted(keyframes, key=lambda k: k.time_seconds)
    if not ordered:
        return {"x": 0.0, "y": 0.0, "scale": 1.0, "rotation": 0.0, "opacity": 1.0}
    if time_sec <= ordered[0].time_seconds:
        k = ordered[0]
        return {"x": k.x, "y": k.y, "scale": k.scale, "rotation": k.rotation, "opacity": k.opacity}
    if time_sec >= ordered[-1].time_seconds:
        k = ordered[-1]
        return {"x": k.x, "y": k.y, "scale": k.scale, "rotation": k.rotation, "opacity": k.opacity}
    for prev_k, next_k in zip(ordered, ordered[1:]):
        if prev_k.time_seconds <= time_sec <= next_k.time_seconds:
            span = max(1e-6, next_k.time_seconds - prev_k.time_seconds)
            progress = ease((time_sec - prev_k.time_seconds) / span, next_k.easing)
            return {
                "x": prev_k.x + (next_k.x - prev_k.x) * progress,
                "y": prev_k.y + (next_k.y - prev_k.y) * progress,
                "scale": prev_k.scale + (next_k.scale - prev_k.scale) * progress,
                "rotation": prev_k.rotation + (next_k.rotation - prev_k.rotation) * progress,
                "opacity": prev_k.opacity + (next_k.opacity - prev_k.opacity) * progress,
            }
    k = ordered[-1]
    return {"x": k.x, "y": k.y, "scale": k.scale, "rotation": k.rotation, "opacity": k.opacity}


def apply_keyframes_to_image(frame_bgr: np.ndarray, props: dict[str, float], width: int = 720, height: int = 1280) -> np.ndarray:
    """Apply scale, rotation, normalized translation, and opacity onto studio dark backdrop."""
    if frame_bgr.shape[1] != width or frame_bgr.shape[0] != height:
        base = cv2.resize(frame_bgr, (width, height), interpolation=cv2.INTER_LINEAR)
    else:
        base = frame_bgr
    cx, cy = width / 2.0, height / 2.0
    scale = max(0.25, min(3.0, float(props.get("scale", 1.0))))
    angle = float(props.get("rotation", 0.0))
    tx = float(props.get("x", 0.0)) * (width / 2.0)
    ty = float(props.get("y", 0.0)) * (height / 2.0)
    opacity = max(0.0, min(1.0, float(props.get("opacity", 1.0))))

    mat = cv2.getRotationMatrix2D((cx, cy), -angle, scale)
    mat[0, 2] += tx
    mat[1, 2] += ty
    # Studio backdrop color #0e110f -> BGR (15, 17, 14)
    backdrop = (15, 17, 14)
    warped = cv2.warpAffine(base, mat, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=backdrop)
    if opacity < 0.999:
        bg = np.full_like(warped, backdrop, dtype=np.uint8)
        warped = cv2.addWeighted(warped, opacity, bg, 1.0 - opacity, 0.0)
    return warped
