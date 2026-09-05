import json

from models.course import CourseStudent
from models.face_template import FaceTemplate
from models.student import Student


def parse_embedding(value: str | None) -> list:
    try:
        embedding = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return embedding if isinstance(embedding, list) else []


def embedding_dimension(embedding: list) -> int:
    return len(embedding) if isinstance(embedding, list) else 0


def serialize_template_diagnostic(template: FaceTemplate) -> dict:
    embedding = parse_embedding(template.embedding)
    return {
        "template_id": template.id,
        "face_image_id": template.face_image_id,
        "image_path": template.image_path,
        "algorithm": template.algorithm,
        "algorithm_version": template.algorithm_version,
        "embedding_dimension": embedding_dimension(embedding),
        "quality_score": template.quality_score,
        "is_active": template.is_active,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


def build_face_database(db, course_id: int | None = None) -> list[dict]:
    query = db.query(Student).filter(Student.is_active == True)
    if course_id is not None:
        links = (
            db.query(CourseStudent)
            .filter(CourseStudent.course_id == course_id, CourseStudent.enroll_status == "active")
            .all()
        )
        student_ids = [link.student_id for link in links]
        if not student_ids:
            return []
        query = query.filter(Student.student_id.in_(student_ids))

    students = query.all()
    templates = db.query(FaceTemplate).filter(FaceTemplate.is_active == True).all()
    template_map: dict[str, list[list]] = {}
    template_id_map: dict[str, list[int]] = {}
    image_id_map: dict[str, list[int | None]] = {}
    template_diagnostics_map: dict[str, list[dict]] = {}
    for template in templates:
        embedding = parse_embedding(template.embedding)
        template_map.setdefault(template.student_id, []).append(embedding)
        template_id_map.setdefault(template.student_id, []).append(template.id)
        image_id_map.setdefault(template.student_id, []).append(template.face_image_id)
        template_diagnostics_map.setdefault(template.student_id, []).append(serialize_template_diagnostic(template))

    return [
        {
            "student_id": student.student_id,
            "name": student.name,
            "embeddings": template_map.get(student.student_id, []),
            "template_ids": template_id_map.get(student.student_id, []),
            "face_image_ids": image_id_map.get(student.student_id, []),
            "template_diagnostics": template_diagnostics_map.get(student.student_id, []),
        }
        for student in students
        if template_map.get(student.student_id)
    ]


def build_student_face_database(db, student_id: str) -> list[dict]:
    student = (
        db.query(Student)
        .filter(Student.student_id == student_id, Student.is_active == True)
        .first()
    )
    if not student:
        return []

    templates = (
        db.query(FaceTemplate)
        .filter(FaceTemplate.student_id == student_id, FaceTemplate.is_active == True)
        .all()
    )
    if not templates:
        return []

    return [
        {
            "student_id": student.student_id,
            "name": student.name,
            "embeddings": [parse_embedding(template.embedding) for template in templates],
            "template_ids": [template.id for template in templates],
            "face_image_ids": [template.face_image_id for template in templates],
            "template_diagnostics": [serialize_template_diagnostic(template) for template in templates],
        }
    ]
