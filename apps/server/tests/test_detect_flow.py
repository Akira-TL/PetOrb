from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi.testclient import TestClient

from petorb_server.main import create_app
from petorb_server.settings import Settings

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"petorb-test-jpeg" + b"\xff\xd9"


class DetectorHandler(BaseHTTPRequestHandler):
    response_status = 200
    response_body = {
        "request_id": "detector-request",
        "image": {"width": 1280, "height": 720},
        "detections": [
            {
                "label": "tartar_suspected",
                "confidence": 0.87,
                "bbox": {"x1": 412, "y1": 203, "x2": 690, "y2": 461},
            }
        ],
        "model": {"name": "test-detector", "version": "1"},
        "latency_ms": 12,
    }

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/v1/detect":
            self.send_error(404)
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        assert b'name="image"' in body
        assert b"image/jpeg" in body
        assert JPEG_BYTES in body
        marker = b'name="request_id"\r\n\r\n'
        request_id = None
        if marker in body:
            request_id = body.split(marker, 1)[1].split(b"\r\n", 1)[0].decode()

        response_body = dict(type(self).response_body)
        if request_id is not None:
            response_body["request_id"] = request_id
        payload = json.dumps(response_body).encode()
        self.send_response(type(self).response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def detector_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), DetectorHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def make_client(detector_url: str) -> TestClient:
    settings = Settings(detector_url=detector_url, cors_origins=["http://localhost:3000"])
    return TestClient(create_app(settings))


def test_jpeg_flows_through_real_detector_http_boundary() -> None:
    server = detector_server()
    try:
        DetectorHandler.response_status = 200
        DetectorHandler.response_body = {
            "request_id": "detector-request",
            "image": {"width": 1280, "height": 720},
            "detections": [
                {
                    "label": "tartar_suspected",
                    "confidence": 0.87,
                    "bbox": {"x1": 412, "y1": 203, "x2": 690, "y2": 461},
                }
            ],
            "model": {"name": "test-detector", "version": "1"},
            "latency_ms": 12,
        }
        detector_url = f"http://127.0.0.1:{server.server_port}"
        with make_client(detector_url) as client:
            response = client.post(
                "/api/detect",
                files={"image": ("oral.jpg", JPEG_BYTES, "image/jpeg")},
            )

        assert response.status_code == 200
        assert response.json() == {
            "status": "completed",
            "image": {"width": 1280, "height": 720},
            "detections": [
                {
                    "label": "tartar_suspected",
                    "display_label": "疑似牙结石",
                    "confidence": 0.87,
                    "bbox": {"x1": 412, "y1": 203, "x2": 690, "y2": 461},
                }
            ],
        }
    finally:
        server.shutdown()
        server.server_close()


def test_empty_detections_are_a_successful_result() -> None:
    server = detector_server()
    try:
        DetectorHandler.response_status = 200
        DetectorHandler.response_body = {
            "request_id": "detector-empty",
            "image": {"width": 1280, "height": 720},
            "detections": [],
            "model": {"name": "test-detector", "version": "1"},
            "latency_ms": 8,
        }
        with make_client(f"http://127.0.0.1:{server.server_port}") as client:
            response = client.post(
                "/api/detect",
                files={"image": ("oral.jpg", JPEG_BYTES, "image/jpeg")},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["detections"] == []
    finally:
        server.shutdown()
        server.server_close()


def test_invalid_detector_bbox_fails_without_fake_result() -> None:
    server = detector_server()
    try:
        DetectorHandler.response_status = 200
        DetectorHandler.response_body = {
            "request_id": "detector-bad-bbox",
            "image": {"width": 1280, "height": 720},
            "detections": [
                {
                    "label": "tartar_suspected",
                    "confidence": 0.9,
                    "bbox": {"x1": 20, "y1": 20, "x2": 1500, "y2": 300},
                }
            ],
            "model": {"name": "test-detector", "version": "1"},
            "latency_ms": 9,
        }
        with make_client(f"http://127.0.0.1:{server.server_port}") as client:
            response = client.post(
                "/api/detect",
                files={"image": ("oral.jpg", JPEG_BYTES, "image/jpeg")},
            )
        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "DETECTOR_ERROR"
        assert "bbox" in response.json()["detail"]["message"]
    finally:
        server.shutdown()
        server.server_close()


def test_detector_http_error_is_visible() -> None:
    server = detector_server()
    try:
        DetectorHandler.response_status = 503
        DetectorHandler.response_body = {
            "error": {"code": "MODEL_NOT_READY", "message": "model loading"}
        }
        with make_client(f"http://127.0.0.1:{server.server_port}") as client:
            response = client.post(
                "/api/detect",
                files={"image": ("oral.jpg", JPEG_BYTES, "image/jpeg")},
            )
        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "DETECTOR_ERROR"
        assert "503" in response.json()["detail"]["message"]
    finally:
        server.shutdown()
        server.server_close()


def test_mismatched_detector_request_id_is_rejected() -> None:
    class MismatchHandler(DetectorHandler):
        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path != "/v1/detect":
                self.send_error(404)
                return
            size = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(size)
            payload = json.dumps(
                {
                    "request_id": "wrong-request-id",
                    "image": {"width": 1280, "height": 720},
                    "detections": [],
                    "model": {"name": "test-detector", "version": "1"},
                    "latency_ms": 4,
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), MismatchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with make_client(f"http://127.0.0.1:{server.server_port}") as client:
            response = client.post(
                "/api/detect",
                files={"image": ("oral.jpg", JPEG_BYTES, "image/jpeg")},
            )
        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "DETECTOR_ERROR"
        assert "request_id" in response.json()["detail"]["message"]
    finally:
        server.shutdown()
        server.server_close()
