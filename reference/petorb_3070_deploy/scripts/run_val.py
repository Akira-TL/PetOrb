"""Run official Ultralytics val on the bundled valid set."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "weights" / "best.pt"
DEFAULT_DATA = ROOT / "data" / "data.yaml"


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate YOLO11m-OBB on bundled val set")
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--conf", type=float, default=0.001)
    ap.add_argument("--device", default="0")
    args = ap.parse_args()

    import os

    from ultralytics import YOLO

    os.chdir(ROOT)
    model = YOLO(str(args.model))
    metrics = model.val(
        data=str(args.data.resolve()),
        split="val",
        imgsz=args.imgsz,
        batch=args.batch,
        conf=args.conf,
        device=args.device,
        plots=True,
        project=str(ROOT / "runs"),
        name="val",
        exist_ok=True,
        workers=2,
    )
    print(
        f"P={metrics.box.mp:.3f} R={metrics.box.mr:.3f} "
        f"mAP50={metrics.box.map50:.3f} mAP50-95={metrics.box.map:.3f}"
    )
    print(f"plots -> {ROOT / 'runs' / 'val'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
