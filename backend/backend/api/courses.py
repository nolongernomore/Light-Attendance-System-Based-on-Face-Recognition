from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from models.attendance import AttendanceRecord, AttendanceSession
from models.course import Course, CourseStudent
from models.student import Student
from models.user import User
from schemas.common import ok
from schemas.course import CourseCreate, CourseStudentAddRequest, CourseUpdate
from services.auth_service import create_student_account_if_missing, get_current_teacher_id, get_current_user, require_teacher
from services.course_service import ensure_course_student, get_teacher_course, remove_course_student


router = APIRouter(prefix="/courses", tags=["courses"])


def serialize_course(course: Course) -> dict:
    return {
        "id": course.id,
        "course_id": course.id,
        "course_name": course.course_name,
        "teacher_id": course.teacher_id,
        "term": course.term,
        "description": course.description,
        "status": course.status,
        "created_at": course.created_at.isoformat() if course.created_at else None,
        "updated_at": course.updated_at.isoformat() if course.updated_at else None,
    }


def serialize_course_student(student: Student, link: CourseStudent | None = None) -> dict:
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
        "source": link.source if link else None,
        "joined_at": link.joined_at.isoformat() if link and link.joined_at else None,
    }


STUDENT_ID_COLUMNS = {"student_id", "student_no", "学号"}


def normalize_cell(value):
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or None


def read_student_ids_file(file: UploadFile) -> list[str]:
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

    student_id_column = None
    for column in df.columns:
        if str(column).strip() in STUDENT_ID_COLUMNS:
            student_id_column = column
            break
    if student_id_column is None:
        raise HTTPException(status_code=400, detail="Import file must contain student_id/student_no/学号 column")

    student_ids: list[str] = []
    for value in df[student_id_column].tolist():
        student_id = normalize_cell(value)
        if student_id:
            student_ids.append(student_id)
    return student_ids


def add_existing_students_to_course(
    db: Session,
    course: Course,
    student_ids: list[str],
    teacher_id: int,
    source: str,
) -> dict:
    added_to_course = 0
    already_in_course = 0
    duplicate_count = 0
    failed: list[dict] = []
    added: list[dict] = []
    seen: set[str] = set()

    for index, raw_student_id in enumerate(student_ids, start=1):
        student_id = (raw_student_id or "").strip()
        if not student_id:
            failed.append({"index": index, "reason": "student_id is empty"})
            continue
        if student_id in seen:
            duplicate_count += 1
            continue
        seen.add(student_id)

        student = db.query(Student).filter(Student.student_id == student_id, Student.is_active == True).first()
        if not student:
            failed.append(
                {
                    "index": index,
                    "student_id": student_id,
                    "reason": "student does not exist in student library",
                }
            )
            continue

        existing_link = (
            db.query(CourseStudent)
            .filter(CourseStudent.course_id == course.id, CourseStudent.student_id == student_id)
            .first()
        )
        was_active = bool(existing_link and existing_link.enroll_status == "active")
        link = ensure_course_student(
            db,
            course.id,
            student_id,
            source=source,
            added_by_teacher_id=teacher_id,
        )
        create_student_account_if_missing(db, student_id, student.name)
        if was_active:
            already_in_course += 1
        else:
            added_to_course += 1
        added.append(serialize_course_student(student, link))

    return {
        "id": course.id,
        "course_id": course.id,
        "course_name": course.course_name,
        "input_count": len(student_ids),
        "added_to_course_count": added_to_course,
        "already_in_course_count": already_in_course,
        "duplicate_count": duplicate_count,
        "failed_count": len(failed),
        "failed": failed,
        "students": added,
    }


@router.get("")
def list_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "teacher":
        teacher_id = get_current_teacher_id(current_user)
        courses = (
            db.query(Course)
            .filter(Course.teacher_id == teacher_id, Course.status != "deleted")
            .order_by(Course.id.asc())
            .all()
        )
    else:
        links = (
            db.query(CourseStudent)
            .filter(
                CourseStudent.student_id == current_user.student_id,
                CourseStudent.enroll_status == "active",
            )
            .all()
        )
        course_ids = [link.course_id for link in links]
        courses = (
            db.query(Course)
            .filter(Course.id.in_(course_ids), Course.status != "deleted")
            .order_by(Course.id.asc())
            .all()
            if course_ids
            else []
        )
    return ok([serialize_course(course) for course in courses], "Course list")


@router.post("")
def create_course(
    payload: CourseCreate,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    course = Course(
        course_name=payload.course_name,
        teacher_id=get_current_teacher_id(current_user),
        term=payload.term,
        description=payload.description,
        status="active",
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return ok(serialize_course(course), "Course created")


@router.put("/{course_id}")
def update_course(
    course_id: int,
    payload: CourseUpdate,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    course = get_teacher_course(db, current_user, course_id)
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(course, key, value)
    db.commit()
    db.refresh(course)
    return ok(serialize_course(course), "Course updated")


@router.delete("/{course_id}")
def delete_course(
    course_id: int,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    course = get_teacher_course(db, current_user, course_id)

    active_sessions = (
        db.query(AttendanceSession)
        .filter(AttendanceSession.course_id == course.id, AttendanceSession.status == "active")
        .all()
    )
    closed_session_count = 0
    marked_absent_count = 0
    now = datetime.now()
    for session in active_sessions:
        pending_records = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.session_id == session.id, AttendanceRecord.status == "pending")
            .all()
        )
        for record in pending_records:
            record.status = "absent"
            record.is_checked_in = False
            record.fail_reason = "Course deleted before check-in"
            record.updated_at = now
            marked_absent_count += 1
        session.status = "closed"
        session.is_closed = True
        session.end_time = now
        session.updated_at = now
        closed_session_count += 1

    removed_student_count = (
        db.query(CourseStudent)
        .filter(CourseStudent.course_id == course.id, CourseStudent.enroll_status == "active")
        .update(
            {
                "enroll_status": "removed",
                "removed_at": now,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )
    course.status = "deleted"
    course.updated_at = now
    db.commit()
    return ok(
        {
            "id": course.id,
            "course_id": course.id,
            "course_name": course.course_name,
            "deleted": True,
            "removed_student_count": removed_student_count,
            "closed_session_count": closed_session_count,
            "marked_absent_count": marked_absent_count,
        },
        "Course deleted",
    )


@router.post("/{course_id}/students")
def add_course_students(
    course_id: int,
    payload: CourseStudentAddRequest,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    course = get_teacher_course(db, current_user, course_id)
    teacher_id = get_current_teacher_id(current_user)
    result = add_existing_students_to_course(db, course, payload.student_ids, teacher_id, "manual")
    db.commit()
    return ok(result, "Students added to course")


@router.post("/{course_id}/students/import")
def import_course_students(
    course_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    course = get_teacher_course(db, current_user, course_id)
    teacher_id = get_current_teacher_id(current_user)
    student_ids = read_student_ids_file(file)
    result = add_existing_students_to_course(db, course, student_ids, teacher_id, "xlsx_import")
    db.commit()
    return ok(result, "Course students imported")


@router.get("/{course_id}/students")
def list_course_students(
    course_id: int,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    course = get_teacher_course(db, current_user, course_id)
    links = (
        db.query(CourseStudent)
        .filter(CourseStudent.course_id == course.id, CourseStudent.enroll_status == "active")
        .all()
    )
    student_ids = [link.student_id for link in links]
    link_map = {link.student_id: link for link in links}
    students = (
        db.query(Student)
        .filter(Student.student_id.in_(student_ids), Student.is_active == True)
        .order_by(Student.student_id.asc())
        .all()
        if student_ids
        else []
    )
    return ok(
        [serialize_course_student(student, link_map.get(student.student_id)) for student in students],
        "Course students",
    )


@router.delete("/{course_id}/students/{student_id}")
def delete_course_student(
    course_id: int,
    student_id: str,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    course = get_teacher_course(db, current_user, course_id)
    link = remove_course_student(db, course.id, student_id)
    if not link:
        raise HTTPException(status_code=404, detail="Student is not in this course")
    db.commit()
    return ok({"course_id": course.id, "student_id": student_id}, "Student removed from course")
