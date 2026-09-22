from __future__ import annotations

import json
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .detector import DetectorError, detect_image
from .schemas import PetOrbDetectResult
from .settings import Settings
from .streaming import CameraStreamHub


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    app = FastAPI(title="PetOrb Server", version="0.1.0")
    app.state.settings = app_settings
    camera_hub = CameraStreamHub(app_settings)
    app.state.camera_hub = camera_hub
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/stream/status")
    async def stream_status() -> dict[str, object]:
        return camera_hub.status_snapshot()

    @app.websocket("/ws/camera/source")
    async def camera_source(websocket: WebSocket) -> None:
        await websocket.accept()
        if not await camera_hub.attach_source():
            await websocket.close(code=1013, reason="camera source already connected")
            return
        try:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                text = message.get("text")
                data = message.get("bytes")
                if text is not None:
                    try:
                        payload = json.loads(text)
                        if not isinstance(payload, dict):
                            raise ValueError("camera control message must be a JSON object")
                        await camera_hub.configure_source(payload)
                    except Exception as exc:
                        await websocket.send_json({"type": "stream_error", "message": str(exc)})
                elif data is not None:
                    await camera_hub.feed_encoded(data)
        except WebSocketDisconnect:
            pass
        finally:
            await camera_hub.detach_source()

    @app.websocket("/ws/camera/view")
    async def camera_view(websocket: WebSocket) -> None:
        try:
            await camera_hub.serve_viewer(websocket)
        except WebSocketDisconnect:
            pass


    @app.post("/api/detect", response_model=PetOrbDetectResult)
    async def detect(image: UploadFile = File(...)) -> PetOrbDetectResult:
        if image.content_type != "image/jpeg":
            raise HTTPException(
                status_code=415,
                detail={"code": "UNSUPPORTED_MEDIA_TYPE", "message": "image must be JPEG"},
            )
        image_bytes = await image.read(app_settings.max_image_bytes + 1)
        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_IMAGE", "message": "image is empty"},
            )
        if len(image_bytes) > app_settings.max_image_bytes:
            raise HTTPException(
                status_code=413,
                detail={"code": "IMAGE_TOO_LARGE", "message": "image exceeds configured size limit"},
            )
        request_id = str(uuid4())
        try:
            return await detect_image(
                image_bytes=image_bytes,
                filename=image.filename or "image.jpg",
                request_id=request_id,
                settings=app_settings,
            )
        except DetectorError as exc:
            raise HTTPException(
                status_code=502,
                detail={"code": "DETECTOR_ERROR", "message": str(exc)},
            ) from exc

    return app


app = create_app()
