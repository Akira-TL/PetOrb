"""Receive GO 3S preview JPEGs from the phone (adb reverse) and run YOLO11m-OBB."""

from __future__ import annotations

import argparse
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from preview_crop import crop_region, find_valid_region, paste_plot

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "weights" / "best.pt"

_latest_jpeg: bytes | None = None
_latest_lock = threading.Lock()
_frame_event = threading.Event()
_stats = {"frames": 0, "last_ms": 0.0}


def decode_jpeg(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


class FrameHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/frame":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(n) if n > 0 else b""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")
        if not data:
            return
        global _latest_jpeg
        with _latest_lock:
            _latest_jpeg = data
        _frame_event.set()


def detector_loop(model_path: Path, imgsz: int, conf: float, device: str, show: bool, crop_valid: bool) -> None:
    from ultralytics import YOLO

    print(f"loading {model_path}", flush=True)
    model = YOLO(str(model_path))
    print(f"crop valid preview region: {crop_valid}", flush=True)
    win = "GO3S YOLO"
    if show:
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    print("waiting for frames on http://127.0.0.1:8080/frame ...", flush=True)
    while True:
        _frame_event.wait(timeout=1.0)
        _frame_event.clear()
        with _latest_lock:
            jpeg = _latest_jpeg
        if jpeg is None:
            continue
        img = decode_jpeg(jpeg)
        if img is None:
            continue
        h, w = img.shape[:2]
        region = find_valid_region(img) if crop_valid else None
        detect_img = crop_region(img, region) if region else img
        t0 = time.perf_counter()
        results = model.predict(
            source=detect_img,
            imgsz=imgsz,
            conf=conf,
            device=device,
            verbose=False,
        )
        dt = (time.perf_counter() - t0) * 1000
        r = results[0]
        n = 0 if r.obb is None else len(r.obb)
        plotted = paste_plot(img, r.plot(), region) if region else r.plot()
        _stats["frames"] += 1
        _stats["last_ms"] = dt
        crop_txt = f"{region[0]},{region[1]} {region[2]}x{region[3]}" if region else "full"
        label = f"in={w}x{h} crop={crop_txt} boxes={n}  detect={dt:.0f}ms  frames={_stats['frames']}"
        cv2.putText(plotted, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
        print(label, flush=True)
        if show:
            cv2.imshow(win, plotted)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break


def main() -> int:
    ap = argparse.ArgumentParser(description="PC side: receive phone preview frames and run OBB detect")
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--device", default="0")
    ap.add_argument("--no-show", action="store_true")
    ap.add_argument("--no-crop", action="store_true", help="detect on the full frame, including black padding")
    args = ap.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), FrameHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    print(f"listen {args.host}:{args.port}", flush=True)
    try:
        detector_loop(
            args.model,
            args.imgsz,
            args.conf,
            args.device,
            show=not args.no_show,
            crop_valid=not args.no_crop,
        )
    except KeyboardInterrupt:
        print("stop", flush=True)
    except Exception:
        import traceback

        traceback.print_exc()
        return 1
    finally:
        httpd.shutdown()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
