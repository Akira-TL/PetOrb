from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ImageSize(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class OrientedBoundingBox(BaseModel):
    x1: int = Field(ge=0)
    y1: int = Field(ge=0)
    x2: int = Field(ge=0)
    y2: int = Field(ge=0)
    x3: int = Field(ge=0)
    y3: int = Field(ge=0)
    x4: int = Field(ge=0)
    y4: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_distinct_corners(self) -> "OrientedBoundingBox":
        corners = {
            (self.x1, self.y1),
            (self.x2, self.y2),
            (self.x3, self.y3),
            (self.x4, self.y4),
        }
        if len(corners) != 4:
            raise ValueError("bbox must contain four distinct corners")
        return self

    def corners(self) -> tuple[tuple[int, int], ...]:
        return (
            (self.x1, self.y1),
            (self.x2, self.y2),
            (self.x3, self.y3),
            (self.x4, self.y4),
        )


class DetectorDetection(BaseModel):
    label: Literal["gingi", "sarro"]
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: OrientedBoundingBox


class DetectorModelInfo(BaseModel):
    name: str
    version: str


class DetectorResponse(BaseModel):
    request_id: str | None = None
    image: ImageSize
    detections: list[DetectorDetection]
    model: DetectorModelInfo
    latency_ms: int | float = Field(ge=0)

    @model_validator(mode="after")
    def validate_bbox_corners_fit_image(self) -> "DetectorResponse":
        for detection in self.detections:
            for x, y in detection.bbox.corners():
                if x > self.image.width or y > self.image.height:
                    raise ValueError("bbox corner exceeds original image dimensions")
        return self


class PetOrbDetection(BaseModel):
    label: Literal["gingi", "sarro"]
    display_label: str
    confidence: float
    bbox: OrientedBoundingBox


class PetOrbDetectResult(BaseModel):
    status: str = "completed"
    image: ImageSize
    detections: list[PetOrbDetection]
