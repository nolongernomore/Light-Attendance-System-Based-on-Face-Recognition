from pathlib import Path
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, HTTPException, Depends, File, Form, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from api.face import ZIP_EXTENSIONS, process_zip_import
from models.course import CourseStudent
from models.face_image import StudentFaceImage
from models.face_template import FaceTemplate
from models.student import Student
from models.user import User
from schemas.admin import AdminStudentDeleteRequest, AdminStudentListRequest
from schemas.common import ok


router = APIRouter(prefix="/admin", tags=["admin"])
ADMIN_PASSWORD = "123456"


def verify_admin_password(password: str) -> None:
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid admin password")


def serialize_admin_student(student: Student) -> dict:
    return {
        "id": student.id,
        "student_id": student.student_id,
        "name": student.name,
        "class_name": student.class_name,
        "major": student.major,
        "gender": student.gender,
        "phone": student.phone,
        "email": student.email,
        "has_face_image": student.has_face_image,
        "active_face_image_count": student.active_face_image_count,
        "is_active": student.is_active,
        "created_at": student.created_at.isoformat() if student.created_at else None,
        "updated_at": student.updated_at.isoformat() if student.updated_at else None,
    }


@router.post("/students/list")
def admin_list_students(
    payload: AdminStudentListRequest,
    db: Session = Depends(get_db),
):
    verify_admin_password(payload.admin_password)
    students = db.query(Student).order_by(Student.student_id.asc()).all()
    return ok(
        {
            "count": len(students),
            "students": [serialize_admin_student(student) for student in students],
        },
        "Admin student list",
    )


@router.post("/students/delete")
def admin_delete_students(
    payload: AdminStudentDeleteRequest,
    db: Session = Depends(get_db),
):
    verify_admin_password(payload.admin_password)

    if payload.delete_all:
        student_ids = [row[0] for row in db.query(Student.student_id).all()]
    else:
        student_ids = sorted({student_id.strip() for student_id in payload.student_ids if student_id.strip()})

    if not student_ids:
        if payload.delete_all:
            return ok(
                {
                    "delete_all": True,
                    "requested_count": 0,
                    "deleted_student_count": 0,
                    "missing_student_ids": [],
                },
                "No students to delete",
            )
        raise HTTPException(status_code=400, detail="No students selected")

    existing_ids = sorted({
        row[0]
        for row in db.query(Student.student_id).filter(Student.student_id.in_(student_ids)).all()
    })
    missing_ids = [student_id for student_id in student_ids if student_id not in existing_ids]

    if not existing_ids:
        return ok(
            {
                "requested_count": len(student_ids),
                "deleted_student_count": 0,
                "missing_student_ids": missing_ids,
            },
            "No matching students to delete",
        )

    course_link_count = (
        db.query(CourseStudent)
        .filter(CourseStudent.student_id.in_(existing_ids))
        .delete(synchronize_session=False)
    )
    face_template_count = (
        db.query(FaceTemplate)
        .filter(FaceTemplate.student_id.in_(existing_ids))
        .delete(synchronize_session=False)
    )
    face_image_count = (
        db.query(StudentFaceImage)
        .filter(StudentFaceImage.student_id.in_(existing_ids))
        .delete(synchronize_session=False)
    )
    user_count = (
        db.query(User)
        .filter(
            User.role == "student",
            or_(User.student_id.in_(existing_ids), User.username.in_(existing_ids)),
        )
        .delete(synchronize_session=False)
    )
    student_count = (
        db.query(Student)
        .filter(Student.student_id.in_(existing_ids))
        .delete(synchronize_session=False)
    )
    db.commit()

    return ok(
        {
            "delete_all": payload.delete_all,
            "requested_count": len(student_ids),
            "deleted_student_count": student_count,
            "deleted_course_link_count": course_link_count,
            "deleted_face_template_count": face_template_count,
            "deleted_face_image_count": face_image_count,
            "deleted_student_user_count": user_count,
            "missing_student_ids": missing_ids,
        },
        "Students deleted by admin",
    )


@router.post("/face-import", include_in_schema=False)
def admin_import_face_zip(
    admin_password: str = Form(...),
    dry_run: bool = Form(True),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    verify_admin_password(admin_password)

    zip_filename = file.filename or ""
    if Path(zip_filename).suffix.lower() not in ZIP_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Please upload a .zip file")

    try:
        file.file.seek(0)
        with ZipFile(file.file) as zip_file:
            result = process_zip_import(zip_file, zip_filename, dry_run, db)
            return ok(result, "Admin batch zip image import finished")
    except BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid zip file") from exc
    finally:
        file.file.close()
