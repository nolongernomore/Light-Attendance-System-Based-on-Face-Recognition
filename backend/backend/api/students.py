from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models.course import CourseStudent
from models.face_image import StudentFaceImage
from models.student import Student
from models.user import User
from schemas.common import ok
from schemas.student import StudentCreate, StudentUpdate
from services.auth_service import create_student_account_if_missing, get_current_teacher_id, require_teacher
from services.course_service import get_teacher_course


router = APIRouter(prefix="/students", tags=["students"])


COLUMN_ALIASES = {
    "student_id": "student_id",
    "student_no": "student_id",
    "学号": "student_id",
    "name": "name",
    "姓名": "name",
    "class_name": "class_name",
    "班级": "class_name",
    "major": "major",
    "专业": "major",
    "gender": "gender",
    "性别": "gender",
    "phone": "phone",
    "手机号": "phone",
    "email": "email",
    "邮箱": "email",
}


def latest_face_image_map(db: Session, student_ids: list[str]) -> dict[str, StudentFaceImage]:
    if not student_ids:
        return {}
    images = (
        db.query(StudentFaceImage)
        .filter(StudentFaceImage.student_id.in_(student_ids), StudentFaceImage.is_active == True)
        .order_by(StudentFaceImage.student_id.asc(), StudentFaceImage.created_at.desc(), StudentFaceImage.id.desc())
        .all()
    )
    result: dict[str, StudentFaceImage] = {}
    for image in images:
        result.setdefault(image.student_id, image)
    return result


def serialize_student(
    student: Student,
    course_id: int | None = None,
    face_image: StudentFaceImage | None = None,
) -> dict:
    latest_image_id = student.latest_face_image_id or (face_image.id if face_image else None)
    latest_image_path = face_image.file_path if face_image else None
    latest_image_static_url = f"/{latest_image_path}" if latest_image_path else None
    latest_image_api_url = f"/api/face/images/{latest_image_id}/file" if latest_image_id else None
    return {
        "id": student.id,
        "student_id": student.student_id,
        "name": student.name,
        "class_name": student.class_name,
        "major": student.major,
        "gender": student.gender,
        "phone": student.phone,
        "email": student.email,
        "course_id": course_id,
        "has_face_image": student.has_face_image,
        "active_face_image_count": student.active_face_image_count,
        "latest_face_image_id": latest_image_id,
        "latest_face_image_path": latest_image_path,
        "latest_face_image_url": latest_image_static_url,
        "latest_face_image_static_url": latest_image_static_url,
        "latest_face_image_api_url": latest_image_api_url,
        "latest_face_image_file_url": latest_image_api_url,
        "default_username": student.student_id,
        "default_password": student.student_id,
        "created_at": student.created_at.isoformat() if student.created_at else None,
        "updated_at": student.updated_at.isoformat() if student.updated_at else None,
    }


def normalize_cell(value):
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or None


def normalize_import_table(df: pd.DataFrame, require_name: bool = True) -> pd.DataFrame:
    renamed = {}
    for column in df.columns:
        key = str(column).strip()
        if key in COLUMN_ALIASES:
            renamed[column] = COLUMN_ALIASES[key]
    df = df.rename(columns=renamed)

    required = {"student_id", "name"} if require_name else {"student_id"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Import file must contain: {', '.join(sorted(missing))}")

    available_columns = [
        column
        for column in ["student_id", "name", "class_name", "major", "gender", "phone", "email"]
        if column in df.columns
    ]
    df = df[available_columns].copy()
    df = df.where(pd.notnull(df), None)
    for column in available_columns:
        df[column] = df[column].map(normalize_cell)
    return df


def read_student_table(file: UploadFile, require_name: bool = True) -> pd.DataFrame:
    filename = file.filename or ""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if suffix in {"xlsx", "xls"}:
            df = pd.read_excel(file.file)
        elif suffix == "csv":
            df = pd.read_csv(file.file, encoding="utf-8-sig")
        else:
            raise HTTPException(status_code=400, detail="Only xlsx, xls and csv files are supported")
    except UnicodeDecodeError:
        file.file.seek(0)
        df = pd.read_csv(file.file, encoding="gbk")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read import file: {exc}") from exc
    finally:
        file.file.close()
    return normalize_import_table(df, require_name=require_name)


def upsert_student_from_row(db: Session, row, teacher_id: int) -> tuple[Student, bool]:
    student_id = row.get("student_id")
    name = row.get("name")
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if student:
        student.name = name or student.name
        student.class_name = row.get("class_name") or student.class_name
        student.major = row.get("major") or student.major
        student.gender = row.get("gender") or student.gender
        student.phone = row.get("phone") or student.phone
        student.email = row.get("email") or student.email
        student.is_active = True
        student.updated_at = datetime.now()
        return student, False

    student = Student(
        student_id=student_id,
        name=name,
        class_name=row.get("class_name"),
        major=row.get("major"),
        gender=row.get("gender"),
        phone=row.get("phone"),
        email=row.get("email"),
        owner_teacher_id=teacher_id,
        is_active=True,
    )
    db.add(student)
    return student, True


@router.get("")
def list_students(
    course_id: int | None = Query(None),
    keyword: str | None = Query(None),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    query = db.query(Student).filter(Student.is_active == True)
    resolved_course_id: int | None = None

    if course_id is not None:
        course = get_teacher_course(db, current_user, course_id)
        resolved_course_id = course.id
        links = (
            db.query(CourseStudent)
            .filter(CourseStudent.course_id == course.id, CourseStudent.enroll_status == "active")
            .all()
        )
        student_ids = [link.student_id for link in links]
        if not student_ids:
            return ok([], "Course student list")
        query = query.filter(Student.student_id.in_(student_ids))

    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Student.student_id.like(pattern),
                Student.name.like(pattern),
                Student.class_name.like(pattern),
                Student.major.like(pattern),
            )
        )

    students = query.order_by(Student.student_id.asc()).all()
    image_map = latest_face_image_map(db, [student.student_id for student in students])
    message = "Course student list" if course_id is not None else "Student library list"
    return ok(
        [serialize_student(student, resolved_course_id, image_map.get(student.student_id)) for student in students],
        message,
    )


@router.post("")
def create_student(
    payload: StudentCreate,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    existing = db.query(Student).filter(Student.student_id == payload.student_id).first()
    if existing:
        existing.name = payload.name
        existing.class_name = payload.class_name or existing.class_name
        existing.major = payload.major or existing.major
        existing.gender = payload.gender or existing.gender
        existing.phone = payload.phone or existing.phone
        existing.email = payload.email or existing.email
        existing.is_active = True
        existing.updated_at = datetime.now()
        student = existing
        created = False
    else:
        student = Student(
            student_id=payload.student_id,
            name=payload.name,
            class_name=payload.class_name,
            major=payload.major,
            gender=payload.gender,
            phone=payload.phone,
            email=payload.email,
            owner_teacher_id=teacher_id,
            is_active=True,
        )
        db.add(student)
        created = True

    create_student_account_if_missing(db, payload.student_id, payload.name)
    db.commit()
    db.refresh(student)
    return ok(
        serialize_student(student) | {"created": created},
        "Student saved to library",
    )


@router.post("/import")
def import_students(
    file: UploadFile = File(...),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    df = read_student_table(file, require_name=True)
    teacher_id = get_current_teacher_id(current_user)

    created = 0
    updated = 0
    skipped = 0
    errors = []

    for index, row in df.iterrows():
        student_id = row.get("student_id")
        name = row.get("name")
        if not student_id or not name:
            skipped += 1
            errors.append({"row": int(index) + 2, "reason": "student_id or name is empty"})
            continue

        student, was_created = upsert_student_from_row(db, row, teacher_id)
        create_student_account_if_missing(db, student.student_id, student.name)
        if was_created:
            created += 1
        else:
            updated += 1

    db.commit()
    return ok(
        {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        },
        "Students imported to library",
    )


@router.put("/{student_id}")
def update_student(
    student_id: str,
    payload: StudentUpdate,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.student_id == student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(student, key, value)
    student.updated_at = datetime.now()

    db.commit()
    db.refresh(student)
    return ok(serialize_student(student), "Student library record updated")


@router.delete("/{student_id}", include_in_schema=False)
def delete_student(
    student_id: str,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.student_id == student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    student.is_active = False
    student.updated_at = datetime.now()
    db.commit()
    return ok({"student_id": student_id}, "Student disabled in library")
