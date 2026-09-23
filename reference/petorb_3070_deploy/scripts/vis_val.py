"""Draw GT (green) and Pred (orange) OBB on bundled val images."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "weights" / "best.pt"
DEFAULT_IMAGES = ROOT / "data" / "valid" / "images"
DEFAULT_LABELS = ROOT / "data" / "valid" / "labels"
DEFAULT_OUT = ROOT / "runs" / "val_vis"

NAMES = {0: "gingi", 1: "sarro"}
GT_COLOR = (60, 200, 60)
PRED_COLOR = (0, 140, 255)


def load_gt_obb(label_path: Path, width: int, height: int) -> list[tuple[int, np.ndarray]]:
    boxes: list[tuple[int, np.ndarray]] = []
    if not label_path.is_file():
        return boxes
    text = label_path.read_text(encoding="utf-8").strip()
    if not text:
        return boxes
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 9:
            continue
        cls_id = int(float(parts[0]))
        coords = np.array([float(x) for x in parts[1:9]], dtype=np.float32).reshape(4, 2)
        coords[:, 0] *= width
        coords[:, 1] *= height
        boxes.append((cls_id, coords.astype(np.int32)))
    return boxes


def draw_obb(image: np.ndarray, pts: np.ndarray, color: tuple[int, int, int], label: str) -> None:
    cv2.polylines(image, [pts], True, color, 3, cv2.LINE_AA)
    x, y = int(pts[:, 0].min()), int(max(0, pts[:, 1].min() - 8))
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    y0 = max(th + 6, y)
    cv2.rectangle(image, (x, y0 - th - 8), (x + tw + 8, y0 + 4), color, -1)
    cv2.putText(image, label, (x + 4, y0 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)


def add_legend(image: np.ndarray) -> np.ndarray:
    bar = np.full((56, image.shape[1], 3), 28, dtype=np.uint8)
    cv2.rectangle(bar, (16, 16), (40, 40), GT_COLOR, -1)
    cv2.putText(bar, "GT", (48, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.rectangle(bar, (140, 16), (164, 40), PRED_COLOR, -1)
    cv2.putText(bar, "Pred", (172, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    return np.vstack([bar, image])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    ap.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--device", default="0")
    args = ap.parse_args()

    model = YOLO(str(args.model))
    args.out.mkdir(parents=True, exist_ok=True)
    image_paths = sorted(
        p for p in args.images.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    results = model.predict(
        source=[str(p) for p in image_paths],
        imgsz=args.imgsz,
        conf=args.conf,
        device=args.device,
        stream=True,
        verbose=False,
    )
    n_gt = n_pred = 0
    for img_path, result in zip(image_paths, results):
        image = cv2.imread(str(img_path))
        if image is None:
            continue
        h, w = image.shape[:2]
        overlay = image.copy()
        gt_boxes = load_gt_obb(args.labels / f"{img_path.stem}.txt", w, h)
        n_gt += len(gt_boxes)
        for cls_id, pts in gt_boxes:
            draw_obb(overlay, pts, GT_COLOR, f"GT {NAMES.get(cls_id, str(cls_id))}")
        if result.obb is not None and len(result.obb):
            for pts, cls_id, conf in zip(
                result.obb.xyxyxyxy.cpu().numpy(),
                result.obb.cls.cpu().numpy().astype(int),
                result.obb.conf.cpu().numpy(),
            ):
                n_pred += 1
                draw_obb(overlay, pts.reshape(4, 2).astype(np.int32), PRED_COLOR, f"P {NAMES.get(int(cls_id), str(cls_id))} {conf:.2f}")
        cv2.imwrite(str(args.out / f"{img_path.stem}.jpg"), add_legend(overlay))
    print(f"GT={n_gt} pred={n_pred} images={len(image_paths)} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
