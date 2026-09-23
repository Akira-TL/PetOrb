from __future__ import annotations

import cv2
import numpy as np


def _largest_blob(mask: np.ndarray) -> np.ndarray | None:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def _region_from_contour(
    contour: np.ndarray,
    w: int,
    h: int,
    pad: float = 1.08,
) -> tuple[int, int, int, int] | None:
    area = float(cv2.contourArea(contour))
    frame_area = float(w * h)
    if area < 0.04 * frame_area or area >= 0.82 * frame_area:
        return None
    (cx, cy), radius = cv2.minEnclosingCircle(contour)
    if radius < 24:
        return None
    side = max(int(radius * 2 * pad), 32)
    x = int(round(cx - side / 2.0))
    y = int(round(cy - side / 2.0))
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    ww = min(side, w - x)
    hh = min(side, h - y)
    if ww < 32 or hh < 32:
        return None
    return x, y, ww, hh


def find_valid_region(img: np.ndarray) -> tuple[int, int, int, int] | None:
    h, w = img.shape[:2]
    if h < 16 or w < 16:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    chrome = gray >= 220
    usable = gray[~chrome]
    if usable.size < 100:
        return None

    base = float(np.median(usable))
    bright_t = max(90.0, base + 35.0)
    bright = ((gray > bright_t) & (~chrome)).astype(np.uint8) * 255
    contour = _largest_blob(bright)
    if contour is not None:
        region = _region_from_contour(contour, w, h)
        if region is not None:
            return region

    _, dark_pad = cv2.threshold(gray, 12, 255, cv2.THRESH_BINARY)
    contour = _largest_blob(dark_pad)
    if contour is not None:
        return _region_from_contour(contour, w, h, pad=0.96)
    return None


def crop_region(img: np.ndarray, region: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = region
    return img[y : y + h, x : x + w]
