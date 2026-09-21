from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ImageSize(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class BoundingBox(BaseModel):
    x1: int = Field(ge=0)
    y1: int = Field(ge=0)
    x2: int = Field(gt=0)
    y2: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_order(self) -> "BoundingBox":
        if self.x1 >= self.x2 or self.y1 >= self.y2:
            raise ValueError("bbox coordinates must satisfy x1 < x2 and y1 < y2")
        return self


class DetectorDetection(BaseModel):
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox


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
    def validate_bboxes_fit_image(self) -> "DetectorResponse":
        for detection in self.detections:
            bbox = detection.bbox
            if bbox.x2 > self.image.width or bbox.y2 > self.image.height:
                raise ValueError("bbox exceeds original image dimensions")
        return self


class PetOrbDetection(BaseModel):
    label: str
    display_label: str
    confidence: float
    bbox: BoundingBox


class PetOrbDetectResult(BaseModel):
    status: str = "completed"
    image: ImageSize
    detections: list[PetOrbDetection]
