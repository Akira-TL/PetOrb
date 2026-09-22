from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ImageSize(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ImagePoint(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class DetectorDetection(BaseModel):
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    points: list[ImagePoint] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def validate_distinct_points(self) -> "DetectorDetection":
        if len({(point.x, point.y) for point in self.points}) != 4:
            raise ValueError("detection points must contain four distinct coordinates")
        return self


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
    def validate_points_fit_image(self) -> "DetectorResponse":
        for detection in self.detections:
            for point in detection.points:
                if point.x > self.image.width or point.y > self.image.height:
                    raise ValueError("detection point exceeds original image dimensions")
        return self


class PetOrbDetection(BaseModel):
    label: str
    display_label: str
    confidence: float
    points: list[ImagePoint] = Field(min_length=4, max_length=4)


class PetOrbDetectResult(BaseModel):
    status: str = "completed"
    image: ImageSize
    detections: list[PetOrbDetection]
