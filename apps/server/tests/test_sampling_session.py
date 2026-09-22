from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient

from petorb_server.main import create_app
from petorb_server.settings import Settings

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"petorb-session-jpeg" + b"\xff\xd9"


class SessionDetectorHandler(BaseHTTPRequestHandler):
    label = "sarro"
    confidence = 0.86
    status = 200
    call_count = 0

    def do_POST(self) -> None:  # noqa: N802
        type(self).call_count += 1
        if self.path != "/v1/detect":
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(size)
        marker = b'name="request_id"\r\n\r\n'
        request_id = body.split(marker, 1)[1].split(b"\r\n", 1)[0].decode()
        if type(self).status != 200:
            payload = json.dumps({"error": {"code": "MODEL_NOT_READY", "message": "loading"}}).encode()
            self.send_response(type(self).status)
        else:
            payload = json.dumps(
                {
                    "request_id": request_id,
                    "image": {"width": 1280, "height": 720},
                    "detections": [
                        {
                            "label": type(self).label,
                            "confidence": type(self).confidence,
                            "bbox": {"x1": 100, "y1": 120, "x2": 500, "y2": 125, "x3": 490, "y3": 420, "x4": 105, "y4": 410},
                        }
                    ],
                    "model": {"name": "session-detector", "version": "1"},
                    "latency_ms": 5,
                }
            ).encode()
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def start_detector() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), SessionDetectorHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def make_client(detector_url: str, data_dir: Path) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                detector_url=detector_url,
                data_dir=data_dir,
                cors_origins=["http://localhost:3000"],
            )
        )
    )


def test_batch_of_ten_becomes_three_persisted_evidence_frames(tmp_path: Path) -> None:
    server = start_detector()
    try:
        SessionDetectorHandler.status = 200
        SessionDetectorHandler.label = "sarro"
        SessionDetectorHandler.confidence = 0.86
        SessionDetectorHandler.call_count = 0
        with make_client(f"http://127.0.0.1:{server.server_port}", tmp_path) as client:
            created = client.post("/api/sessions", json={"animal_id": "A023"})
            assert created.status_code == 201
            assert created.json()["status"] == "READY"

            duplicate = client.post("/api/sessions", json={"animal_id": "A024"})
            assert duplicate.status_code == 409

            response = client.post(
                "/api/ingest",
                files=[
                    ("images", (f"frame-{index}.jpg", JPEG_BYTES, "image/jpeg"))
                    for index in range(10)
                ],
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["status"] == "COMPLETED"
            assert payload["animal_id"] == "A023"
            assert payload["risk_level"] == "attention_recommended"
            assert len(payload["evidence_frames"]) == 3
            assert all(frame["detections"] for frame in payload["evidence_frames"])
            assert SessionDetectorHandler.call_count == 10

            stored = list((tmp_path / "sessions" / payload["id"]).glob("*.jpg"))
            assert len(stored) == 3

            fetched = client.get(f"/api/sessions/{payload['id']}")
            assert fetched.status_code == 200
            assert fetched.json() == payload
    finally:
        server.shutdown()
        server.server_close()


class EmptyDetectorHandler(SessionDetectorHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/detect":
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(size)
        marker = b'name="request_id"\r\n\r\n'
        request_id = body.split(marker, 1)[1].split(b"\r\n", 1)[0].decode()
        payload = json.dumps(
            {
                "request_id": request_id,
                "image": {"width": 1280, "height": 720},
                "detections": [],
                "model": {"name": "session-detector", "version": "1"},
                "latency_ms": 5,
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class FailingDetectorHandler(SessionDetectorHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/detect":
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(size)
        payload = json.dumps({"error": {"code": "MODEL_NOT_READY", "message": "loading"}}).encode()
        self.send_response(503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_handler(handler: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_empty_detections_complete_as_no_obvious_abnormality(tmp_path: Path) -> None:
    server = start_handler(EmptyDetectorHandler)
    try:
        with make_client(f"http://127.0.0.1:{server.server_port}", tmp_path) as client:
            created = client.post("/api/sessions", json={"animal_id": "A030"}).json()
            response = client.post(
                "/api/ingest",
                files=[
                    ("images", (f"frame-{index}.jpg", JPEG_BYTES, "image/jpeg"))
                    for index in range(2)
                ],
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["id"] == created["id"]
            assert payload["status"] == "COMPLETED"
            assert payload["risk_level"] == "no_obvious_abnormality"
            assert payload["findings"] == []
            assert len(payload["evidence_frames"]) == 1
            assert len(list((tmp_path / "sessions" / payload["id"]).glob("*.jpg"))) == 1
    finally:
        server.shutdown()
        server.server_close()


def test_detector_failure_marks_session_failed_and_removes_temporary_images(tmp_path: Path) -> None:
    server = start_handler(FailingDetectorHandler)
    try:
        with make_client(f"http://127.0.0.1:{server.server_port}", tmp_path) as client:
            created = client.post("/api/sessions", json={"animal_id": "A031"}).json()
            response = client.post(
                "/api/ingest",
                files=[
                    ("images", (f"frame-{index}.jpg", JPEG_BYTES, "image/jpeg"))
                    for index in range(2)
                ],
            )
            assert response.status_code == 502
            failed = client.get(f"/api/sessions/{created['id']}")
            assert failed.status_code == 200
            assert failed.json()["status"] == "FAILED"
            assert "503" in failed.json()["error"]
            session_dir = tmp_path / "sessions" / created["id"]
            assert list(session_dir.glob("*.jpg")) == []
    finally:
        server.shutdown()
        server.server_close()


def test_batch_larger_than_ten_is_rejected_without_consuming_ready_session(tmp_path: Path) -> None:
    server = start_detector()
    try:
        with make_client(f"http://127.0.0.1:{server.server_port}", tmp_path) as client:
            created = client.post("/api/sessions", json={"animal_id": "A032"}).json()
            response = client.post(
                "/api/ingest",
                files=[
                    ("images", (f"frame-{index}.jpg", JPEG_BYTES, "image/jpeg"))
                    for index in range(11)
                ],
            )
            assert response.status_code == 400
            assert response.json()["detail"]["code"] == "TOO_MANY_IMAGES"
            fetched = client.get(f"/api/sessions/{created['id']}")
            assert fetched.json()["status"] == "READY"
    finally:
        server.shutdown()
        server.server_close()


def test_high_risk_label_recommends_veterinary_review_without_treatment_prescription(tmp_path: Path) -> None:
    server = start_detector()
    try:
        SessionDetectorHandler.status = 200
        SessionDetectorHandler.label = "gingi"
        SessionDetectorHandler.confidence = 0.82
        with make_client(f"http://127.0.0.1:{server.server_port}", tmp_path) as client:
            client.post("/api/sessions", json={"animal_id": "A033"})
            response = client.post(
                "/api/ingest",
                files=[("images", ("frame.jpg", JPEG_BYTES, "image/jpeg"))],
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["risk_level"] == "veterinary_review_recommended"
            assert "宠物医院" in payload["recommendation"]
            assert "药" not in payload["recommendation"]
            assert "剂量" not in payload["recommendation"]
    finally:
        server.shutdown()
        server.server_close()


class SlowDetectorHandler(SessionDetectorHandler):
    started = threading.Event()
    release = threading.Event()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/detect":
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(size)
        marker = b'name="request_id"\r\n\r\n'
        request_id = body.split(marker, 1)[1].split(b"\r\n", 1)[0].decode()
        type(self).started.set()
        type(self).release.wait(timeout=5)
        payload = json.dumps(
            {
                "request_id": request_id,
                "image": {"width": 1280, "height": 720},
                "detections": [],
                "model": {"name": "slow-detector", "version": "1"},
                "latency_ms": 100,
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def test_concurrent_ingest_can_claim_ready_session_only_once(tmp_path: Path) -> None:
    server = start_handler(SlowDetectorHandler)
    SlowDetectorHandler.started.clear()
    SlowDetectorHandler.release.clear()
    app = create_app(
        Settings(
            detector_url=f"http://127.0.0.1:{server.server_port}",
            data_dir=tmp_path,
            cors_origins=["http://localhost:3000"],
        )
    )
    first_result: dict[str, object] = {}

    def run_first_ingest() -> None:
        with TestClient(app) as first_client:
            response = first_client.post(
                "/api/ingest",
                files=[("images", ("first.jpg", JPEG_BYTES, "image/jpeg"))],
            )
            first_result["status"] = response.status_code
            first_result["payload"] = response.json()

    try:
        with TestClient(app) as setup_client:
            setup_client.post("/api/sessions", json={"animal_id": "A034"})

        worker = threading.Thread(target=run_first_ingest, daemon=True)
        worker.start()
        assert SlowDetectorHandler.started.wait(timeout=5)

        with TestClient(app) as second_client:
            second = second_client.post(
                "/api/ingest",
                files=[("images", ("second.jpg", JPEG_BYTES, "image/jpeg"))],
            )
        assert second.status_code == 409
        assert second.json()["detail"]["code"] == "SESSION_BUSY"

        SlowDetectorHandler.release.set()
        worker.join(timeout=5)
        assert first_result["status"] == 200
        assert first_result["payload"]["status"] == "COMPLETED"
    finally:
        SlowDetectorHandler.release.set()
        server.shutdown()
        server.server_close()
