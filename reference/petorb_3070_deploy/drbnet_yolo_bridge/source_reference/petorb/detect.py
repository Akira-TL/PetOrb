"""Run OBB detection. Default: bundled val images. Saves boxes on images."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "weights" / "best.pt"
DEFAULT_SOURCE = ROOT / "data" / "valid" / "images"


def main() -> int:
    ap = argparse.ArgumentParser(description="YOLO11m-OBB detect (no API)")
    ap.add_argument("source", nargs="?", default=str(DEFAULT_SOURCE), help="image file or folder")
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--device", default="0")
    args = ap.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.model)
    results = model.predict(
        source=args.source,
        imgsz=args.imgsz,
        conf=args.conf,
        device=args.device,
        save=True,
        project=str(ROOT / "runs"),
        name="detect",
        exist_ok=True,
        verbose=True,
    )
    n = 0
    for r in results:
        n += 0 if r.obb is None else len(r.obb)
        print(f"{Path(r.path).name}: {0 if r.obb is None else len(r.obb)} boxes")
    print(f"total boxes={n}")
    print(f"saved -> {ROOT / 'runs' / 'detect'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
