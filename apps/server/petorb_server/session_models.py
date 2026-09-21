from __future__ import annotations

from pydantic import BaseModel, Field

from .schemas import ImageSize, PetOrbDetection


class SessionCreateRequest(BaseModel):
    animal_id: str | None = Field(default=None, max_length=64)


class SessionFinding(BaseModel):
    label: str
    display_label: str
    confidence: float
    evidence_frame_id: str


class EvidenceFrame(BaseModel):
    id: str
    url: str
    image: ImageSize
    detections: list[PetOrbDetection]


class SamplingSessionResponse(BaseModel):
    id: str
    animal_id: str | None
    status: str
    sample_quality: str | None = None
    risk_level: str | None = None
    overall_judgment: str | None = None
    recommendation: str | None = None
    findings: list[SessionFinding] = Field(default_factory=list)
    evidence_frames: list[EvidenceFrame] = Field(default_factory=list)
    error: str | None = None
    created_at: str
