import logging
import shutil
from uuid import uuid4
from pathlib import Path

from config import settings


logger = logging.getLogger(__name__)
FACE_SERVICE_ERROR = "FACE_SERVICE_ERROR"


try:
    from service.face_service import (
        EMBEDDING_DIM as c_embedding_dim,
        MODEL_NAME as c_model_name,
        enroll_student_faces as c_enroll_student_faces,
        recognize_group_photo as c_recognize_group_photo,
        recognize_single_face as c_recognize_single_face,
        warmup as c_warmup,
    )
    C_FACE_SERVICE_AVAILABLE = True
    C_FACE_SERVICE_IMPORT_ERROR = None
except Exception as exc:
    c_enroll_student_faces = None
    c_recognize_group_photo = None
    c_recognize_single_face = None
    c_warmup = None
    c_embedding_dim = None
    c_model_name = None
    C_FACE_SERVICE_AVAILABLE = False
    C_FACE_SERVICE_IMPORT_ERROR = exc


def get_face_algorithm_metadata() -> dict:
    if C_FACE_SERVICE_AVAILABLE:
        model_name = c_model_name or "ArcFace"
        return {
            "algorithm": f"deepface-{model_name}",
            "algorithm_version": "c-face-service-v1",
        }
    return {
        "algorithm": "mock",
        "algorithm_version": "v1",
    }


def get_face_service_status() -> dict:
    metadata = get_face_algorithm_metadata()
    return {
        "available": C_FACE_SERVICE_AVAILABLE,
        "mode": "c_module" if C_FACE_SERVICE_AVAILABLE else "mock",
        "algorithm": metadata["algorithm"],
        "algorithm_version": metadata["algorithm_version"],
        "model_name": c_model_name,
        "expected_embedding_dim": c_embedding_dim,
        "import_error": str(C_FACE_SERVICE_IMPORT_ERROR) if C_FACE_SERVICE_IMPORT_ERROR else None,
        "install_hint": None
        if C_FACE_SERVICE_AVAILABLE
        else "Install backend/requirements-c.txt to enable C face recognition service.",
    }


def _first_meta(person: dict, key: str):
    values = person.get(key) or []
    return values[0] if values else None


def _attach_match_metadata(result: dict, face_database: list[dict]) -> dict:
    student_id = result.get("student_id")
    if not student_id:
        return result

    for person in face_database:
        if person.get("student_id") == student_id:
            result.setdefault("template_id", _first_meta(person, "template_ids"))
            result.setdefault("face_image_id", _first_meta(person, "face_image_ids"))
            break
    return result


def _normalize_single_result(result: dict, image_path: str, face_database: list[dict]) -> dict:
    result = dict(result)
    error_code = result.get("error_code")
    matched = bool(result.get("matched")) and error_code is None

    result.setdefault("success", error_code is None)
    result["matched"] = matched
    result.setdefault("student_id", None)
    result.setdefault("name", None)
    result.setdefault("score", 0)
    result.setdefault("bbox", None)
    result.setdefault("face_crop_path", image_path)
    result = _attach_match_metadata(result, face_database)
    result.setdefault("template_id", None)
    result.setdefault("face_image_id", None)
    return result


def _publish_annotated_image(path: str | None) -> str | None:
    if not path:
        return None

    source = Path(path)
    if not source.exists():
        return path

    try:
        source.resolve().relative_to(settings.UPLOAD_DIR.resolve())
        return source.relative_to(settings.BASE_DIR).as_posix()
    except ValueError:
        pass

    settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix or ".jpg"
    target = settings.RESULTS_DIR / f"group_annotated_{uuid4().hex[:8]}{suffix}"
    shutil.copy2(source, target)
    return target.relative_to(settings.BASE_DIR).as_posix()


def _normalize_group_result(result: dict, image_path: str, face_database: list[dict]) -> dict:
    result = dict(result)
    faces = []
    for face in result.get("faces") or []:
        item = dict(face)
        item.setdefault("face_crop_path", image_path)
        item = _attach_match_metadata(item, face_database)
        item.setdefault("template_id", None)
        item.setdefault("face_image_id", None)
        faces.append(item)

    result["faces"] = faces
    result.setdefault("success", result.get("error_code") is None)
    result.setdefault("total_faces", len(faces))
    result.setdefault("matched_count", len([face for face in faces if face.get("matched")]))
    result.setdefault("unknown_count", result["total_faces"] - result["matched_count"])
    result["annotated_image_path"] = _publish_annotated_image(
        result.get("annotated_image_path") or result.get("annotated_image")
    )
    return result


def enroll_student_faces(student_id: str, image_paths: list[str]) -> dict:
    if not C_FACE_SERVICE_AVAILABLE:
        return {
            "success": True,
            "student_id": student_id,
            "valid_count": len(image_paths),
            "invalid_count": 0,
            "embeddings": [[0.12, -0.23, 0.45]],
            "message": f"mock face enrollment success; C module unavailable: {C_FACE_SERVICE_IMPORT_ERROR}",
            "error_code": None,
        }
    try:
        result = dict(c_enroll_student_faces(student_id, image_paths))
        result.setdefault("error_code", None)
        return result
    except Exception as exc:
        logger.exception("C face enrollment failed")
        return {
            "success": False,
            "student_id": student_id,
            "valid_count": 0,
            "invalid_count": len(image_paths),
            "embeddings": [],
            "message": f"C face enrollment failed: {exc}",
            "error_code": FACE_SERVICE_ERROR,
        }


def recognize_single_face(image_path: str, face_database: list[dict]) -> dict:
    if not C_FACE_SERVICE_AVAILABLE:
        if not face_database:
            return {
                "success": True,
                "matched": False,
                "student_id": None,
                "name": None,
                "score": 0,
                "bbox": None,
                "face_crop_path": image_path,
                "template_id": None,
                "face_image_id": None,
                "error_code": None,
            }
        first = face_database[0]
        return {
            "success": True,
            "matched": True,
            "student_id": first["student_id"],
            "name": first["name"],
            "score": 0.88,
            "bbox": [120, 80, 180, 160],
            "face_crop_path": image_path,
            "template_id": _first_meta(first, "template_ids"),
            "face_image_id": _first_meta(first, "face_image_ids"),
            "error_code": None,
        }

    try:
        result = c_recognize_single_face(image_path, face_database)
    except Exception as exc:
        logger.exception("C single face recognition failed")
        return {
            "success": False,
            "matched": False,
            "student_id": None,
            "name": None,
            "score": 0,
            "bbox": None,
            "face_crop_path": image_path,
            "template_id": None,
            "face_image_id": None,
            "error_code": FACE_SERVICE_ERROR,
            "message": f"C single face recognition failed: {exc}",
        }
    return _normalize_single_result(result, image_path, face_database)


def recognize_group_photo(image_path: str, face_database: list[dict]) -> dict:
    if not C_FACE_SERVICE_AVAILABLE:
        faces = []
        for index, person in enumerate(face_database[:10], start=1):
            faces.append(
                {
                    "matched": True,
                    "student_id": person["student_id"],
                    "name": person["name"],
                    "score": round(0.9 - index * 0.01, 2),
                    "bbox": [40 * index, 50, 40 * index + 60, 120],
                    "face_crop_path": image_path,
                    "template_id": _first_meta(person, "template_ids"),
                    "face_image_id": _first_meta(person, "face_image_ids"),
                }
            )
        return {
            "success": True,
            "total_faces": len(faces),
            "matched_count": len(faces),
            "unknown_count": 0,
            "annotated_image_path": str(Path(image_path).as_posix()),
            "faces": faces,
            "error_code": None,
        }

    try:
        result = c_recognize_group_photo(image_path, face_database)
    except Exception as exc:
        logger.exception("C group photo recognition failed")
        return {
            "success": False,
            "total_faces": 0,
            "matched_count": 0,
            "unknown_count": 0,
            "annotated_image_path": None,
            "faces": [],
            "error_code": FACE_SERVICE_ERROR,
            "message": f"C group photo recognition failed: {exc}",
        }
    return _normalize_group_result(result, image_path, face_database)


def warmup() -> None:
    if C_FACE_SERVICE_AVAILABLE:
        c_warmup()
