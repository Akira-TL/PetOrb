from __future__ import annotations

from uuid import uuid4

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .detector import DetectorError, detect_image
from .schemas import PetOrbDetectResult
from .session_models import SamplingSessionResponse, SessionCreateRequest
from .session_service import AnalysisError, IngestError, SessionService
from .session_store import ActiveSessionExistsError, NoActiveSessionError, SessionNotFoundError, SessionStore
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    app = FastAPI(title="PetOrb Server", version="0.1.0")
    app.state.settings = app_settings
    session_store = SessionStore(app_settings.data_dir)
    session_service = SessionService(app_settings, session_store)
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


    @app.post("/api/sessions", response_model=SamplingSessionResponse, status_code=201)
    async def create_session(payload: SessionCreateRequest = Body(default=SessionCreateRequest())) -> SamplingSessionResponse:
        try:
            return session_store.create_session(payload.animal_id)
        except ActiveSessionExistsError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "ACTIVE_SESSION_EXISTS", "message": str(exc)},
            ) from exc

    @app.get("/api/sessions/{session_id}", response_model=SamplingSessionResponse)
    async def get_session(session_id: str) -> SamplingSessionResponse:
        try:
            return session_store.get_session(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": str(exc)}) from exc

    @app.post("/api/ingest", response_model=SamplingSessionResponse)
    async def ingest(images: list[UploadFile] = File(...)) -> SamplingSessionResponse:
        try:
            return await session_service.ingest(images)
        except NoActiveSessionError as exc:
            raise HTTPException(status_code=409, detail={"code": "NO_ACTIVE_SESSION", "message": str(exc)}) from exc
        except IngestError as exc:
            raise HTTPException(
                status_code=exc.http_status,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        except AnalysisError as exc:
            raise HTTPException(
                status_code=502,
                detail={"code": "DETECTOR_ERROR", "message": str(exc)},
            ) from exc

    @app.get("/api/sessions/{session_id}/evidence/{frame_id}")
    async def get_evidence(session_id: str, frame_id: str) -> FileResponse:
        try:
            path = session_store.evidence_path(session_id, frame_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"code": "EVIDENCE_NOT_FOUND", "message": str(exc)}) from exc
        if not path.exists():
            raise HTTPException(status_code=404, detail={"code": "EVIDENCE_NOT_FOUND", "message": frame_id})
        return FileResponse(path, media_type="image/jpeg")

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
