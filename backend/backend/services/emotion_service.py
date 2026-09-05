import logging
from pathlib import Path

from config import settings


logger = logging.getLogger(__name__)

EMOTION_CN = {
    "angry": "\u751f\u6c14",
    "disgust": "\u538c\u6076",
    "fear": "\u5bb3\u6015",
    "happy": "\u9ad8\u5174",
    "sad": "\u4f24\u5fc3",
    "surprise": "\u60ca\u8bb6",
    "neutral": "\u5e73\u9759",
}

EMOTION_SERVICE_ERROR = "EMOTION_SERVICE_ERROR"
EMOTION_INVALID_IMAGE = "EMOTION_INVALID_IMAGE"
EMOTION_UNAVAILABLE = "EMOTION_UNAVAILABLE"


def resolve_image_path(image_path: str | None) -> Path | None:
    if not image_path:
        return None
    path = Path(image_path)
    if path.is_absolute():
        return path
    return settings.BASE_DIR / path


def neutral_result(error_code: str | None = None, message: str | None = None) -> dict:
    return {
        "success": error_code is None,
        "emotion": "neutral",
        "emotion_cn": EMOTION_CN["neutral"],
        "confidence": 0.0,
        "error_code": error_code,
        "message": message,
    }


def normalize_confidence(value) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score > 1:
        score = score / 100.0
    return round(max(0.0, min(score, 1.0)), 4)


def analyze_emotion(face_crop_path: str) -> dict:
    """
    Analyze a face image with DeepFace and return the stable shape used by APIs.

    The C-side mood.py expects a cropped face, but the backend may pass either a
    crop path or the original captured image. DeepFace can still analyze with
    enforce_detection=False, so failures degrade to neutral instead of breaking
    attendance or group-photo flows.
    """
    path = resolve_image_path(face_crop_path)
    if not path or not path.is_file():
        logger.warning("Emotion image file not found: %s", face_crop_path)
        return neutral_result(EMOTION_INVALID_IMAGE, "Emotion image file not found")

    try:
        from deepface import DeepFace
    except ImportError:
        logger.warning("DeepFace is not installed; emotion analysis falls back to neutral")
        return neutral_result(EMOTION_UNAVAILABLE, "DeepFace is not installed")

    try:
        result = DeepFace.analyze(
            img_path=str(path),
            actions=["emotion"],
            enforce_detection=False,
            silent=True,
        )
        if isinstance(result, list):
            result = result[0] if result else {}

        emotion_scores = result.get("emotion") or {}
        if not emotion_scores:
            return neutral_result(EMOTION_SERVICE_ERROR, "DeepFace returned no emotion scores")

        dominant = result.get("dominant_emotion") or max(emotion_scores, key=emotion_scores.get)
        dominant = str(dominant).lower()
        confidence = normalize_confidence(emotion_scores.get(dominant))

        return {
            "success": True,
            "emotion": dominant,
            "emotion_cn": EMOTION_CN.get(dominant, dominant),
            "confidence": confidence,
            "error_code": None,
            "message": None,
        }
    except Exception as exc:
        logger.warning("Emotion analysis failed (%s): %s", path, exc)
        return neutral_result(EMOTION_SERVICE_ERROR, str(exc))
