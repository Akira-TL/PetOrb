from __future__ import annotations

from collections.abc import Iterable

from .schemas import PetOrbDetection

NO_OBVIOUS_ABNORMALITY = "no_obvious_abnormality"
ATTENTION_RECOMMENDED = "attention_recommended"
VETERINARY_REVIEW_RECOMMENDED = "veterinary_review_recommended"

RISK_RANK = {
    NO_OBVIOUS_ABNORMALITY: 0,
    ATTENTION_RECOMMENDED: 1,
    VETERINARY_REVIEW_RECOMMENDED: 2,
}

LABEL_RISK = {
    "sarro": ATTENTION_RECOMMENDED,
    "gingi": VETERINARY_REVIEW_RECOMMENDED,
}

MIN_REPORT_CONFIDENCE = 0.5


def detection_risk(detection: PetOrbDetection) -> str:
    if detection.confidence < MIN_REPORT_CONFIDENCE:
        return NO_OBVIOUS_ABNORMALITY
    return LABEL_RISK.get(detection.label, ATTENTION_RECOMMENDED)


def highest_risk(detections: Iterable[PetOrbDetection]) -> str:
    risk = NO_OBVIOUS_ABNORMALITY
    for detection in detections:
        candidate = detection_risk(detection)
        if RISK_RANK[candidate] > RISK_RANK[risk]:
            risk = candidate
    return risk


def overall_copy(risk_level: str) -> tuple[str, str]:
    if risk_level == VETERINARY_REVIEW_RECOMMENDED:
        return (
            "本次采样存在建议由兽医进一步评估的口腔异常迹象。",
            "建议进一步人工检查，并考虑尽快前往宠物医院由兽医进行专业评估。",
        )
    if risk_level == ATTENTION_RECOMMENDED:
        return (
            "本次采样存在需要关注的口腔异常迹象。",
            "建议安排进一步人工口腔检查并持续观察；如异常持续或加重，建议咨询宠物医生。",
        )
    return (
        "本次采样未见模型可报告的明显异常。",
        "建议继续日常观察；如出现进食异常、明显口臭、出血或疼痛表现，请进一步人工检查。",
    )
