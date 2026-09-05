from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.course import Course, CourseStudent
from models.user import User
from services.auth_service import get_current_teacher_id


def get_teacher_course(db: Session, teacher: User, course_id: int) -> Course:
    teacher_id = get_current_teacher_id(teacher)
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.teacher_id == teacher_id, Course.status != "deleted")
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or access denied")
    return course


def get_default_course(db: Session, teacher: User) -> Course:
    teacher_id = get_current_teacher_id(teacher)
    course = (
        db.query(Course)
        .filter(Course.teacher_id == teacher_id, Course.status == "active")
        .order_by(Course.id.asc())
        .first()
    )
    if not course:
        course = Course(
            course_name="Default Course",
            teacher_id=teacher_id,
            description="System default course",
            status="active",
        )
        db.add(course)
        db.commit()
        db.refresh(course)
    return course


def resolve_teacher_course(db: Session, teacher: User, course_id: int | None) -> Course:
    if course_id is None:
        return get_default_course(db, teacher)
    return get_teacher_course(db, teacher, course_id)


def ensure_course_student(
    db: Session,
    course_id: int,
    student_id: str,
    source: str = "manual",
    added_by_teacher_id: int | None = None,
) -> CourseStudent:
    link = (
        db.query(CourseStudent)
        .filter(CourseStudent.course_id == course_id, CourseStudent.student_id == student_id)
        .first()
    )
    if link:
        if link.enroll_status != "active":
            link.enroll_status = "active"
            link.removed_at = None
            link.joined_at = datetime.now()
        link.source = source or link.source
        if added_by_teacher_id is not None:
            link.added_by_teacher_id = added_by_teacher_id
        link.updated_at = datetime.now()
        return link

    link = CourseStudent(
        course_id=course_id,
        student_id=student_id,
        enroll_status="active",
        source=source,
        added_by_teacher_id=added_by_teacher_id,
    )
    db.add(link)
    return link


def remove_course_student(db: Session, course_id: int, student_id: str) -> CourseStudent | None:
    link = (
        db.query(CourseStudent)
        .filter(CourseStudent.course_id == course_id, CourseStudent.student_id == student_id)
        .first()
    )
    if not link:
        return None
    link.enroll_status = "removed"
    link.removed_at = datetime.now()
    link.updated_at = datetime.now()
    return link


def student_in_course(db: Session, course_id: int, student_id: str) -> bool:
    return (
        db.query(CourseStudent)
        .filter(
            CourseStudent.course_id == course_id,
            CourseStudent.student_id == student_id,
            CourseStudent.enroll_status == "active",
        )
        .first()
        is not None
    )


def get_active_course_student_ids(db: Session, course_id: int) -> list[str]:
    links = (
        db.query(CourseStudent)
        .filter(CourseStudent.course_id == course_id, CourseStudent.enroll_status == "active")
        .all()
    )
    return [link.student_id for link in links]
