"""Competition Web UI: receive phone JPEGs and serve tech (8080) + user (8081) pages.

Does not replace scripts/pc_detect_server.py. Phone still POSTs /frame on 8080.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import cv2
import numpy as np

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from preview_crop import crop_region, find_valid_region, offset_boxes, paste_plot

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "weights" / "best.pt"
WEB_DIR = ROOT / "web"
USER_DIST = WEB_DIR / "user-dist"
NAMES = {0: "gingi", 1: "sarro"}
USER_NAME = {"gingi": "口腔溃疡", "sarro": "牙结石"}

_latest_jpeg: bytes | None = None
_latest_received_ms = 0
_latest_lock = threading.Lock()
_frame_event = threading.Event()
_live_times: list[float] = []
_ai_times: list[float] = []

_state_lock = threading.Lock()
_ai_jpeg: bytes | None = None
_state: dict = {
    "image_w": 0,
    "image_h": 0,
    "live_fps": 0.0,
    "ai_fps": 0.0,
    "ai_ms": 0.0,
    "frames": 0,
    "boxes": [],
    "risk": "低",
    "risk_level": "low",
    "summary": "等待画面",
    "recommend_check": False,
    "recommend_medical": False,
    "updated_ms": 0,
}

_replay_lock = threading.Lock()
_replay: deque[dict] = deque(maxlen=48)
_replay_jpegs: dict[int, bytes] = {}
_replay_seq = 0
_last_save = 0.0


def decode_jpeg(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def encode_jpeg(img: np.ndarray, quality: int = 80) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return b""
    return buf.tobytes()


def live_fps_now() -> float:
    now = time.time()
    cutoff = now - 1.0
    while _live_times and _live_times[0] < cutoff:
        _live_times.pop(0)
    return float(len(_live_times))


def assess_risk(boxes: list[dict]) -> tuple[str, str, str, bool, bool]:
    if not boxes:
        return "低", "low", "未见明显异常", False, False
    n = len(boxes)
    max_conf = max(b["conf"] for b in boxes)
    has_sarro = any(b["cls"] == "sarro" for b in boxes)
    has_gingi = any(b["cls"] == "gingi" for b in boxes)
    if max_conf >= 0.70 or n >= 3:
        parts = []
        if has_gingi:
            parts.append("牙龈相关区域")
        if has_sarro:
            parts.append("牙结石相关区域")
        summary = "检测到" + "、".join(parts) + "，建议人工检查或就医"
        return "高", "high", summary, True, True
    if max_conf >= 0.40:
        return "中", "medium", "发现可疑区域，建议人工复查", True, False
    return "低", "low", "信号较弱，未见稳定异常", False, False


def extract_boxes(result) -> list[dict]:
    boxes: list[dict] = []
    obb = getattr(result, "obb", None)
    if obb is None or len(obb) == 0:
        return boxes
    xy = obb.xyxyxyxy.cpu().numpy()
    cls = obb.cls.cpu().numpy()
    conf = obb.conf.cpu().numpy()
    names = getattr(result, "names", None) or NAMES
    for i in range(len(xy)):
        cid = int(cls[i])
        pts = np.asarray(xy[i]).reshape(-1, 2)
        if isinstance(names, dict):
            label = names.get(cid, NAMES.get(cid, str(cid)))
        elif 0 <= cid < len(names):
            label = names[cid]
        else:
            label = NAMES.get(cid, str(cid))
        boxes.append(
            {
                "cls": str(label),
                "conf": float(conf[i]),
                "poly": [[float(p[0]), float(p[1])] for p in pts],
            }
        )
    return boxes


def class_scores(boxes: list[dict]) -> tuple[float, float]:
    tartar = 0.0
    ulcer = 0.0
    for b in boxes:
        key = str(b.get("cls", "")).lower()
        if key == "sarro":
            tartar = max(tartar, float(b["conf"]))
        elif key == "gingi":
            ulcer = max(ulcer, float(b["conf"]))
    return tartar, ulcer


def user_banner(level: str, tartar: float, ulcer: float, frames: int) -> tuple[str, str]:
    bits = []
    if ulcer > 0:
        bits.append(f"口腔溃疡 {ulcer * 100:.0f}%")
    if tartar > 0:
        bits.append(f"牙结石 {tartar * 100:.0f}%")
    detail = "、".join(bits)
    if frames <= 0:
        return "idle", "等待本次检查"
    if level == "high":
        extra = detail or "异常区域"
        return "high", f"发现疑似{extra}，建议尽快人工检查或就医"
    if level == "medium":
        extra = f"（{detail}）" if detail else ""
        return "medium", f"口腔状况需关注{extra}，建议近期复查"
    if detail:
        return "low", f"口腔状况基本平稳，当前{detail}，建议持续观察"
    return "low", "暂无异常提醒，口腔状况平稳"


def user_boxes(boxes: list[dict]) -> list[dict]:
    out = []
    for b in boxes:
        raw = str(b.get("cls", ""))
        out.append({"cls": USER_NAME.get(raw, raw), "conf": float(b["conf"])})
    return out


def user_snapshot() -> dict:
    with _state_lock:
        boxes = list(_state["boxes"])
        level = str(_state["risk_level"])
        risk = str(_state["risk"])
        summary = str(_state["summary"])
        updated = int(_state["updated_ms"])
        frames = int(_state["frames"])
    tartar, ulcer = class_scores(boxes)
    blevel, btext = user_banner(level, tartar, ulcer, frames)
    with _replay_lock:
        latest_id = _replay[-1]["id"] if _replay else None
    return {
        "banner": {"level": blevel, "text": btext},
        "scores": {
            "ulcer": {"name": "口腔溃疡", "conf": round(ulcer, 4), "found": ulcer > 0},
            "tartar": {"name": "牙结石", "conf": round(tartar, 4), "found": tartar > 0},
        },
        "risk": risk,
        "risk_level": level,
        "summary": summary,
        "updated_ms": updated,
        "frames": frames,
        "latest_replay_id": latest_id,
    }


def maybe_save_replay(ai_bytes: bytes, boxes: list[dict], risk: str, level: str) -> None:
    global _replay_seq, _last_save
    if not ai_bytes:
        return
    now = time.time()
    tartar, ulcer = class_scores(boxes)
    gap = 0.5 if level in ("medium", "high") else 0.8
    if not boxes and level == "low":
        return
    if now - _last_save < gap:
        return
    _last_save = now
    with _replay_lock:
        _replay_seq += 1
        rid = _replay_seq
        item = {
            "id": rid,
            "ts": int(now * 1000),
            "risk": risk,
            "risk_level": level,
            "tartar": round(tartar, 4),
            "ulcer": round(ulcer, 4),
            "boxes": user_boxes(boxes),
        }
        _replay.append(item)
        _replay_jpegs[rid] = ai_bytes
        keep = {x["id"] for x in _replay}
        for k in list(_replay_jpegs):
            if k not in keep:
                del _replay_jpegs[k]


class _Base(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_jpeg(self, data: bytes | None) -> None:
        if not data:
            self.send_error(404)
            return
        self._send(200, data, "image/jpeg")

    def _send_json(self, obj: dict | list) -> None:
        self._send(200, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")


class Handler(_Base):
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, (WEB_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/health":
            self._send(200, b"ok", "text/plain")
            return
        if path == "/live.jpg":
            with _latest_lock:
                data = _latest_jpeg
            self._send_jpeg(data)
            return
        if path == "/ai.jpg":
            with _state_lock:
                data = _ai_jpeg
            self._send_jpeg(data)
            return
        if path == "/api/state":
            with _state_lock:
                payload = dict(_state)
                cutoff = time.time() - 1.0
                while _ai_times and _ai_times[0] < cutoff:
                    _ai_times.pop(0)
                payload["ai_fps"] = float(len(_ai_times))
            payload["live_fps"] = round(live_fps_now(), 1)
            self._send_json(payload)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/frame":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(n) if n > 0 else b""
        self._send(200, b"ok", "text/plain")
        if not data:
            return
        global _latest_jpeg, _latest_received_ms
        with _latest_lock:
            _latest_jpeg = data
            _latest_received_ms = int(time.time() * 1000)
            _live_times.append(time.time())
        _frame_event.set()


class UserHandler(_Base):
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/user.html"):
            self._send(200, (USER_DIST / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if path.startswith("/assets/"):
            asset = (USER_DIST / path.lstrip("/")).resolve()
            if not asset.is_relative_to(USER_DIST.resolve()) or not asset.is_file():
                self.send_error(404)
                return
            content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
            self._send(200, asset.read_bytes(), content_type)
            return
        if path == "/api/live-status":
            with _latest_lock:
                received_ms = _latest_received_ms
            self._send_json({
                "connected": bool(received_ms and int(time.time() * 1000) - received_ms < 3000),
                "last_frame_ms": received_ms,
            })
            return
        if path == "/live.jpg":
            with _latest_lock:
                data = _latest_jpeg
            self._send_jpeg(data)
            return
        if path == "/api/user":
            self._send_json(user_snapshot())
            return
        if path == "/api/replay":
            with _replay_lock:
                items = list(_replay)
            items.reverse()
            self._send_json({"items": items})
            return
        if path.startswith("/replay/") and path.endswith(".jpg"):
            try:
                rid = int(path.rsplit("/", 1)[-1].removesuffix(".jpg"))
            except ValueError:
                self.send_error(404)
                return
            with _replay_lock:
                data = _replay_jpegs.get(rid)
            self._send_jpeg(data)
            return
        self.send_error(404)


def detector_loop(model_path: Path, imgsz: int, conf: float, device: str, crop_valid: bool) -> None:
    from ultralytics import YOLO

    print(f"loading {model_path}", flush=True)
    model = YOLO(str(model_path))
    print(f"crop valid preview region: {crop_valid}", flush=True)
    print("waiting for frames ...", flush=True)
    while True:
        if not _frame_event.wait(timeout=1.0):
            continue
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
        ox, oy = (region[0], region[1]) if region else (0, 0)
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
        boxes = offset_boxes(extract_boxes(r), ox, oy)
        plotted = paste_plot(img, r.plot(), region) if region else r.plot()
        ai_bytes = encode_jpeg(plotted)
        risk, level, summary, rec_check, rec_med = assess_risk(boxes)
        frames = int(_state["frames"]) + 1
        with _state_lock:
            global _ai_jpeg
            _ai_jpeg = ai_bytes
            now = time.time()
            _ai_times.append(now)
            while _ai_times and _ai_times[0] < now - 1.0:
                _ai_times.pop(0)
            _state.update(
                {
                    "image_w": int(w),
                    "image_h": int(h),
                    "ai_fps": float(len(_ai_times)),
                    "ai_ms": round(dt, 1),
                    "frames": frames,
                    "boxes": boxes,
                    "risk": risk,
                    "risk_level": level,
                    "summary": summary,
                    "recommend_check": rec_check,
                    "recommend_medical": rec_med,
                    "updated_ms": int(time.time() * 1000),
                }
            )
        maybe_save_replay(ai_bytes, boxes, risk, level)
        crop_txt = f"{region[0]},{region[1]} {region[2]}x{region[3]}" if region else "full"
        print(
            f"in={w}x{h} crop={crop_txt} boxes={len(boxes)}  detect={dt:.0f}ms  frames={frames}  risk={risk}",
            flush=True,
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="PetOrb competition web UI + YOLO receiver")
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--user-port", type=int, default=8081)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--device", default="0")
    ap.add_argument("--no-crop", action="store_true", help="detect on the full frame, including black padding")
    args = ap.parse_args()

    if not (WEB_DIR / "index.html").is_file() or not (USER_DIST / "index.html").is_file():
        print(f"missing tech page or built user app under {WEB_DIR}", flush=True)
        return 1

    if args.port == args.user_port:
        print("tech and user ports must differ", flush=True)
        return 1
    probe_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    for port in (args.port, args.user_port):
        try:
            with socket.create_connection((probe_host, port), timeout=0.3):
                print(f"port {port} is already in use", flush=True)
                return 1
        except OSError:
            pass

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"listen {args.host}:{args.port}", flush=True)

    user_httpd = ThreadingHTTPServer((args.host, args.user_port), UserHandler)
    threading.Thread(target=user_httpd.serve_forever, daemon=True).start()
    print(f"listen {args.host}:{args.user_port} user app", flush=True)
    try:
        detector_loop(args.model, args.imgsz, args.conf, args.device, crop_valid=not args.no_crop)
    except KeyboardInterrupt:
        print("stop", flush=True)
    except Exception:
        import traceback

        traceback.print_exc()
        return 1
    finally:
        httpd.shutdown()
        user_httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
