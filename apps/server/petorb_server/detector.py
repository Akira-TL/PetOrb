from __future__ import annotations

import httpx
from pydantic import ValidationError

from .schemas import DetectorResponse, PetOrbDetectResult, PetOrbDetection
from .settings import Settings

LABEL_DISPLAY_NAMES = {
    "gingi": "牙龈炎 / 红龈",
    "sarro": "牙结石",
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
        code = None
        message = None
        try:
            payload = response.json()
            if isinstance(payload, dict):
                code = payload.get("code")
                message = payload.get("message")
                error = payload.get("error")
                if isinstance(error, dict):
                    code = code or error.get("code")
                    message = message or error.get("message")
                detail = payload.get("detail")
                if message is None and isinstance(detail, str):
                    message = detail
        except ValueError:
            pass
        suffix = ": ".join(part for part in (str(code) if code else None, str(message) if message else None) if part)
        if suffix:
            raise DetectorError(f"detector returned HTTP {response.status_code}: {suffix}")
        raise DetectorError(f"detector returned HTTP {response.status_code}")

    try:
        detector_result = DetectorResponse.model_validate(response.json())
    except (ValueError, ValidationError) as exc:
        raise DetectorError(f"detector returned invalid response: {exc}") from exc

    if detector_result.request_id != request_id:
        raise DetectorError("detector returned mismatched request_id")

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
