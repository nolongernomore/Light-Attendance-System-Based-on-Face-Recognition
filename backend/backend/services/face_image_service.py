import json
from datetime import datetime

from sqlalchemy.orm import Session

from models.face_image import StudentFaceImage
from models.face_template import FaceTemplate
from models.student import Student


def refresh_student_face_status(db: Session, student_id: str) -> Student | None:
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        return None

    active_images = (
        db.query(StudentFaceImage)
        .filter(StudentFaceImage.student_id == student_id, StudentFaceImage.is_active == True)
        .order_by(StudentFaceImage.created_at.desc(), StudentFaceImage.id.desc())
        .all()
    )
    student.active_face_image_count = len(active_images)
    student.has_face_image = bool(active_images)
    student.latest_face_image_id = active_images[0].id if active_images else None
    student.updated_at = datetime.now()
    return student


def deactivate_active_face_images(db: Session, student_id: str) -> None:
    now = datetime.now()
    (
        db.query(FaceTemplate)
        .filter(FaceTemplate.student_id == student_id, FaceTemplate.is_active == True)
        .update({"is_active": False, "updated_at": now}, synchronize_session=False)
    )
    active_images = (
        db.query(StudentFaceImage)
        .filter(StudentFaceImage.student_id == student_id, StudentFaceImage.is_active == True)
        .all()
    )
    for image in active_images:
        deactivate_face_image(db, image)
    if active_images:
        db.flush()


def create_face_image_with_template(
    db: Session,
    student_id: str,
    image_path: str,
    embedding: list,
    source: str,
    uploaded_by_role: str,
    uploaded_by_id: int | None,
    original_filename: str | None = None,
    quality_score: float | None = 0.9,
    algorithm: str = "mock",
    algorithm_version: str = "v1",
) -> tuple[StudentFaceImage, FaceTemplate]:
    deactivate_active_face_images(db, student_id)

    face_image = StudentFaceImage(
        student_id=student_id,
        file_path=image_path,
        original_filename=original_filename,
        source=source,
        uploaded_by_role=uploaded_by_role,
        uploaded_by_id=uploaded_by_id,
        quality_score=quality_score,
        is_active=True,
    )
    db.add(face_image)
    db.flush()

    template = FaceTemplate(
        student_id=student_id,
        face_image_id=face_image.id,
        image_path=image_path,
        embedding=json.dumps(embedding),
        algorithm=algorithm,
        algorithm_version=algorithm_version,
        quality_score=quality_score,
        is_active=True,
    )
    db.add(template)
    db.flush()
    refresh_student_face_status(db, student_id)
    return face_image, template


def deactivate_face_image(db: Session, face_image: StudentFaceImage) -> None:
    face_image.is_active = False
    face_image.deleted_at = datetime.now()
    face_image.updated_at = datetime.now()
    (
        db.query(FaceTemplate)
        .filter(FaceTemplate.face_image_id == face_image.id)
        .update({"is_active": False, "updated_at": datetime.now()})
    )
    refresh_student_face_status(db, face_image.student_id)
