from __future__ import annotations

import os
import time
from pathlib import Path
from threading import Lock
from uuid import uuid4

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .preview_crop import crop_region, find_valid_region

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL = ROOT / "reference" / "petorb_3070_deploy" / "weights" / "best.pt"
MODEL_PATH = Path(os.getenv("PETORB_MODEL", str(DEFAULT_MODEL))).expanduser().resolve()
DEVICE = os.getenv("PETORB_DEVICE", "0")
IMGSZ = int(os.getenv("PETORB_IMGSZ", "640"))
CONF = float(os.getenv("PETORB_CONF", "0.15"))
CROP_VALID = os.getenv("PETORB_CROP_VALID_PREVIEW", "1").lower() not in {"0", "false", "no"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MODEL_VERSION = "yolo11m-obb-petorb-3070-2026-09-23"

app = FastAPI(title="PetOrb Oral Detector", version="1.0.0")
_model = None
_model_lock = Lock()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                if not MODEL_PATH.is_file():
                    raise RuntimeError(f"model weight not found: {MODEL_PATH}")
                from ultralytics import YOLO

                _model = YOLO(str(MODEL_PATH))
    return _model


def decode_jpeg(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("image cannot be decoded")
    return image


def clamp(value: float, lower: int, upper: int) -> int:
    return max(lower, min(int(round(value)), upper))


def extract_detections(result, ox: int, oy: int, width: int, height: int) -> list[dict]:
    obb = getattr(result, "obb", None)
    if obb is None or len(obb) == 0:
        return []

    xy = obb.xyxyxyxy.cpu().numpy()
    cls = obb.cls.cpu().numpy()
    conf = obb.conf.cpu().numpy()
    names = getattr(result, "names", None) or {0: "gingi", 1: "sarro"}
    detections: list[dict] = []

    for index in range(len(xy)):
        class_id = int(cls[index])
        if isinstance(names, dict):
            label = str(names.get(class_id, class_id))
        else:
            label = str(names[class_id]) if 0 <= class_id < len(names) else str(class_id)
        if label not in {"gingi", "sarro"}:
            continue

        points = np.asarray(xy[index]).reshape(-1, 2)
        if len(points) != 4:
            continue
        shifted = [(float(p[0]) + ox, float(p[1]) + oy) for p in points]
        detections.append(
            {
                "label": label,
                "confidence": float(conf[index]),
                "bbox": {
                    "x1": clamp(shifted[0][0], 0, width),
                    "y1": clamp(shifted[0][1], 0, height),
                    "x2": clamp(shifted[1][0], 0, width),
                    "y2": clamp(shifted[1][1], 0, height),
                    "x3": clamp(shifted[2][0], 0, width),
                    "y3": clamp(shifted[2][1], 0, height),
                    "x4": clamp(shifted[3][0], 0, width),
                    "y4": clamp(shifted[3][1], 0, height),
                },
            }
        )
    return detections


@app.get("/")
def root() -> dict[str, object]:
    return {
        "service": "petorb-oral-detector",
        "routes": ["GET /health", "POST /v1/detect"],
        "labels": ["gingi", "sarro"],
    }


@app.get("/health")
def health() -> dict[str, str]:
    if not MODEL_PATH.is_file():
        raise HTTPException(status_code=503, detail={"code": "MODEL_NOT_READY", "message": str(MODEL_PATH)})
    return {"status": "ok", "model": "petorb-oral-detector", "version": MODEL_VERSION}


@app.post("/v1/detect")
def detect(
    image: UploadFile = File(...),
    request_id: str | None = Form(default=None),
) -> dict[str, object]:
    if image.content_type not in {"image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=415, detail={"code": "UNSUPPORTED_MEDIA_TYPE", "message": "JPEG required"})
    data = image.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail={"code": "IMAGE_TOO_LARGE", "message": "image exceeds 5 MB"})
    if not data:
        raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE", "message": "empty image"})

    try:
        full = decode_jpeg(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE", "message": str(exc)}) from exc

    height, width = full.shape[:2]
    region = find_valid_region(full) if CROP_VALID else None
    detect_image = crop_region(full, region) if region else full
    ox, oy = (region[0], region[1]) if region else (0, 0)

    try:
        model = get_model()
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"code": "MODEL_NOT_READY", "message": str(exc)}) from exc

    started = time.perf_counter()
    try:
        result = model.predict(
            source=detect_image,
            imgsz=IMGSZ,
            conf=CONF,
            device=DEVICE,
            verbose=False,
        )[0]
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "INFERENCE_ERROR", "message": str(exc)}) from exc
    latency_ms = int(round((time.perf_counter() - started) * 1000))

    return {
        "request_id": request_id or str(uuid4()),
        "image": {"width": width, "height": height},
        "detections": extract_detections(result, ox, oy, width, height),
        "model": {"name": "petorb-oral-detector", "version": MODEL_VERSION},
        "latency_ms": latency_ms,
    }
