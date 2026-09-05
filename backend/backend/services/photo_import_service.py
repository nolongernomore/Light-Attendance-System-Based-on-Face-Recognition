from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from config import ensure_upload_dirs, settings
from database import Base, SessionLocal, engine
from models.student import Student
from services.auth_service import create_student_account_if_missing
from services.face_image_service import create_face_image_with_template
from services.face_service import enroll_student_faces, get_face_algorithm_metadata


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class PhotoInfo:
    source_path: Path
    student_id: str
    name: str
    major: str | None
    gender: str | None


def parse_photo_name(path: Path) -> PhotoInfo | None:
    parts = [part.strip() for part in path.stem.replace("_", "-").split("-") if part.strip()]
    if len(parts) < 2:
        return None

    return PhotoInfo(
        source_path=path,
        student_id=parts[0],
        name=parts[1],
        major=parts[2] if len(parts) >= 3 else None,
        gender=parts[3] if len(parts) >= 4 else None,
    )


def file_hash(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def copy_photo(info: PhotoInfo) -> str:
    digest = file_hash(info.source_path)
    suffix = info.source_path.suffix.lower()
    target_name = f"student_{info.student_id}_{digest}{suffix}"
    target_path = settings.ENROLL_DIR / target_name
    if not target_path.exists():
        shutil.copy2(info.source_path, target_path)
    return target_path.relative_to(settings.BASE_DIR).as_posix()


def collect_photos(folder: Path) -> tuple[list[PhotoInfo], list[dict]]:
    photos: list[PhotoInfo] = []
    invalid_files: list[dict] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        info = parse_photo_name(path)
        if info:
            photos.append(info)
        else:
            invalid_files.append(
                {
                    "path": str(path),
                    "reason": "Filename should contain at least student_id-name",
                }
            )
    return photos, invalid_files


def import_photos(
    folder: Path,
    dry_run: bool = False,
    teacher_id: int | None = None,
) -> dict:
    ensure_upload_dirs()
    Base.metadata.create_all(bind=engine)

    photos, invalid_files = collect_photos(folder)
    grouped: dict[str, list[PhotoInfo]] = {}
    for photo in photos:
        grouped.setdefault(photo.student_id, []).append(photo)

    result = {
        "folder": str(folder),
        "students": len(grouped),
        "photos": len(photos),
        "created_students": 0,
        "updated_students": 0,
        "created_templates": 0,
        "skipped_templates": 0,
        "invalid_files": invalid_files,
        "teacher_id": teacher_id,
    }

    preview = [
        {
            "student_id": items[0].student_id,
            "name": items[0].name,
            "major": items[0].major,
            "gender": items[0].gender,
            "photo_count": len(items),
        }
        for items in grouped.values()
    ]

    if dry_run:
        result["preview"] = preview
        return result

    db = SessionLocal()
    try:
        face_metadata = get_face_algorithm_metadata()
        for student_id, items in grouped.items():
            first = items[0]
            student = db.query(Student).filter(Student.student_id == student_id).first()
            if student:
                student.name = first.name
                student.class_name = first.major
                student.major = first.major
                student.gender = first.gender
                student.is_active = True
                if teacher_id and not student.owner_teacher_id:
                    student.owner_teacher_id = teacher_id
                result["updated_students"] += 1
            else:
                student = Student(
                    student_id=student_id,
                    name=first.name,
                    class_name=first.major,
                    major=first.major,
                    gender=first.gender,
                    owner_teacher_id=teacher_id,
                    is_active=True,
                )
                db.add(student)
                result["created_students"] += 1

            create_student_account_if_missing(db, student_id, first.name)

            image_paths = [copy_photo(item) for item in items]
            enroll_result = enroll_student_faces(student_id, image_paths)
            embeddings = enroll_result.get("embeddings") or []

            if image_paths:
                embedding = embeddings[-1] if embeddings else []
                create_face_image_with_template(
                    db=db,
                    student_id=student_id,
                    image_path=image_paths[-1],
                    embedding=embedding,
                    source="batch_import",
                    uploaded_by_role="teacher" if teacher_id else "system",
                    uploaded_by_id=teacher_id,
                    original_filename=items[-1].source_path.name,
                    quality_score=0.9,
                    algorithm=face_metadata["algorithm"],
                    algorithm_version=face_metadata["algorithm_version"],
                )
                result["created_templates"] += 1

        db.commit()
    finally:
        db.close()

    result["preview"] = preview[:20]
    return result
