from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from .detector import DetectorError, detect_image
from .risk import (
    NO_OBVIOUS_ABNORMALITY,
    RISK_RANK,
    detection_risk,
    highest_risk,
    overall_copy,
)
from .schemas import PetOrbDetectResult, PetOrbDetection
from .session_models import EvidenceFrame, SamplingSessionResponse, SessionFinding
from .session_store import SessionStore
from .settings import Settings


class IngestError(RuntimeError):
    def __init__(self, code: str, message: str, http_status: int):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class AnalysisError(RuntimeError):
    pass


@dataclass
class ProcessedFrame:
    id: str
    path: Path
    result: PetOrbDetectResult


class SessionService:
    def __init__(self, settings: Settings, store: SessionStore):
        self.settings = settings
        self.store = store

    async def ingest(self, images: list[UploadFile]) -> SamplingSessionResponse:
        if not images:
            raise IngestError("EMPTY_BATCH", "at least one JPEG is required", 400)
        if len(images) > 10:
            raise IngestError("TOO_MANY_IMAGES", "a batch may contain at most 10 JPEG images", 400)

        session_id = self.store.claim_ready_session()
        session_dir = self.store.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        temporary_paths: list[Path] = []
        processed: list[ProcessedFrame] = []
        try:
            staged: list[tuple[str, str, bytes, Path]] = []
            for upload in images:
                if upload.content_type != "image/jpeg":
                    raise IngestError("UNSUPPORTED_MEDIA_TYPE", "all batch items must be JPEG", 415)
                image_bytes = await upload.read(self.settings.max_image_bytes + 1)
                if not image_bytes:
                    raise IngestError("INVALID_IMAGE", "batch contains an empty image", 400)
                if len(image_bytes) > self.settings.max_image_bytes:
                    raise IngestError("IMAGE_TOO_LARGE", "batch image exceeds configured size limit", 413)
                frame_id = str(uuid4())
                frame_path = session_dir / f"{frame_id}.jpg"
                frame_path.write_bytes(image_bytes)
                temporary_paths.append(frame_path)
                staged.append((frame_id, upload.filename or "image.jpg", image_bytes, frame_path))

            self.store.set_status(session_id, "ANALYZING")
            for frame_id, filename, image_bytes, frame_path in staged:
                result = await detect_image(
                    image_bytes=image_bytes,
                    filename=filename,
                    request_id=f"{session_id}:{frame_id}",
                    settings=self.settings,
                )
                processed.append(ProcessedFrame(frame_id, frame_path, result))

            evidence_frames = self._select_evidence(processed)
            evidence_ids = {frame.id for frame in evidence_frames}
            for frame in processed:
                if frame.id not in evidence_ids:
                    frame.path.unlink(missing_ok=True)

            findings = self._aggregate_findings(evidence_frames)
            all_detections = [
                detection
                for frame in processed
                for detection in frame.result.detections
            ]
            risk_level = highest_risk(all_detections)
            overall_judgment, recommendation = overall_copy(risk_level)
            response = self.store.complete_session(
                session_id,
                sample_quality="usable",
                risk_level=risk_level,
                overall_judgment=overall_judgment,
                recommendation=recommendation,
                findings=findings,
                evidence_frames=evidence_frames,
            )
            return response
        except DetectorError as exc:
            self._cleanup(temporary_paths)
            self.store.set_status(session_id, "FAILED", str(exc))
            raise AnalysisError(str(exc)) from exc
        except IngestError as exc:
            self._cleanup(temporary_paths)
            self.store.set_status(session_id, "FAILED", str(exc))
            raise
        except Exception as exc:
            self._cleanup(temporary_paths)
            self.store.set_status(session_id, "FAILED", str(exc))
            raise

    def _select_evidence(self, processed: list[ProcessedFrame]) -> list[EvidenceFrame]:
        def score(frame: ProcessedFrame) -> tuple[int, float, int]:
            detections = frame.result.detections
            if not detections:
                return (0, 0.0, 0)
            frame_risk = highest_risk(detections)
            max_confidence = max(item.confidence for item in detections)
            return (RISK_RANK[frame_risk], max_confidence, len(detections))

        ranked = sorted(processed, key=score, reverse=True)
        has_reportable = any(score(frame)[0] > 0 for frame in ranked)
        selected = ranked[:3] if has_reportable else ranked[:1]
        return [
            EvidenceFrame(
                id=frame.id,
                url="",
                image=frame.result.image,
                detections=frame.result.detections,
            )
            for frame in selected
        ]

    def _aggregate_findings(self, evidence_frames: list[EvidenceFrame]) -> list[SessionFinding]:
        best_by_label: dict[str, tuple[PetOrbDetection, str]] = {}
        for frame in evidence_frames:
            for detection in frame.detections:
                if detection_risk(detection) == NO_OBVIOUS_ABNORMALITY:
                    continue
                previous = best_by_label.get(detection.label)
                if previous is None or detection.confidence > previous[0].confidence:
                    best_by_label[detection.label] = (detection, frame.id)
        findings = [
            SessionFinding(
                label=detection.label,
                display_label=detection.display_label,
                confidence=detection.confidence,
                evidence_frame_id=frame_id,
            )
            for detection, frame_id in best_by_label.values()
        ]
        return sorted(findings, key=lambda item: item.confidence, reverse=True)

    @staticmethod
    def _cleanup(paths: list[Path]) -> None:
        for path in paths:
            path.unlink(missing_ok=True)
