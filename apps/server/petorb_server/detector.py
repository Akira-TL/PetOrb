from __future__ import annotations

import httpx
from pydantic import ValidationError

from .schemas import DetectorResponse, PetOrbDetectResult, PetOrbDetection
from .settings import Settings

LABEL_DISPLAY_NAMES = {
    "tartar_suspected": "疑似牙结石",
    "gingiva_redness": "牙龈颜色异常",
    "tooth_missing": "牙齿缺失/完整性异常",
    "oral_valid": "有效口腔区域",
}


class DetectorError(RuntimeError):
    pass


async def detect_image(
    image_bytes: bytes,
    filename: str,
    request_id: str,
    settings: Settings,
) -> PetOrbDetectResult:
    url = settings.detector_url.rstrip("/") + "/v1/detect"
    try:
        async with httpx.AsyncClient(timeout=settings.detector_timeout_seconds) as client:
            response = await client.post(
                url,
                files={"image": (filename, image_bytes, "image/jpeg")},
                data={"request_id": request_id},
            )
    except httpx.HTTPError as exc:
        raise DetectorError(f"detector request failed: {exc}") from exc

    if response.status_code != 200:
        raise DetectorError(f"detector returned HTTP {response.status_code}")

    try:
        detector_result = DetectorResponse.model_validate(response.json())
    except (ValueError, ValidationError) as exc:
        raise DetectorError(f"detector returned invalid response: {exc}") from exc

    return PetOrbDetectResult(
        image=detector_result.image,
        detections=[
            PetOrbDetection(
                label=detection.label,
                display_label=LABEL_DISPLAY_NAMES.get(detection.label, detection.label),
                confidence=detection.confidence,
                bbox=detection.bbox,
            )
            for detection in detector_result.detections
        ],
    )
