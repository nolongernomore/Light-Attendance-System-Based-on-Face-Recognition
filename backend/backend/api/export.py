from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.activity import Activity, ActivityParticipant
from models.attendance import AttendanceRecord, AttendanceSession
from models.course import Course
from models.emotion import EmotionRecord
from models.group_photo_record import GroupPhotoRecord, GroupPhotoRecordStudent
from models.user import User
from services.auth_service import get_current_teacher_id, require_student, require_teacher
from services.course_service import get_teacher_course


router = APIRouter(prefix="/export", tags=["export"])


def make_excel(rows: list[dict], filename: str) -> Path:
    settings.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = settings.EXPORTS_DIR / filename
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)
    return path


def attendance_rows(db: Session, records: list[AttendanceRecord]) -> list[dict]:
    course_ids = {record.course_id for record in records if record.course_id is not None}
    session_ids = {record.session_id for record in records if record.session_id is not None}
    courses = {
        course.id: course
        for course in db.query(Course).filter(Course.id.in_(course_ids)).all()
    } if course_ids else {}
    sessions = {
        session.id: session
        for session in db.query(AttendanceSession).filter(AttendanceSession.id.in_(session_ids)).all()
    } if session_ids else {}

    return [
        {
            "course_name": courses[record.course_id].course_name if record.course_id in courses else None,
            "session_title": sessions[record.session_id].title if record.session_id in sessions else None,
            "session_start_time": sessions[record.session_id].start_time if record.session_id in sessions else None,
            "session_end_time": sessions[record.session_id].end_time if record.session_id in sessions else None,
            "student_id": record.student_id,
            "name": record.name,
            "course_id": record.course_id,
            "session_id": record.session_id,
            "status": record.status,
            "is_checked_in": record.is_checked_in,
            "checkin_time": record.checkin_time,
            "submit_time": record.submit_time,
            "liveness_passed": record.liveness_passed,
            "liveness_score": record.liveness_score,
            "face_score": record.face_score,
            "emotion": record.emotion,
            "emotion_confidence": record.emotion_confidence,
            "emotion_error_code": record.emotion_error_code,
            "emotion_message": record.emotion_message,
            "fail_reason": record.fail_reason,
            "capture_file": record.image_path,
            "used_face_image_id": record.used_face_image_id,
            "used_face_template_id": record.used_face_template_id,
        }
        for record in records
    ]


def group_photo_record_rows(
    records: list[GroupPhotoRecord],
    students: list[GroupPhotoRecordStudent],
) -> list[dict]:
    students_by_record: dict[int, list[GroupPhotoRecordStudent]] = {}
    for student in students:
        students_by_record.setdefault(student.record_id, []).append(student)

    rows: list[dict] = []
    for record in records:
        record_students = students_by_record.get(record.id, [])
        if not record_students:
            rows.append(
                {
                    "record_id": record.id,
                    "activity_name": record.activity_name,
                    "activity_date": record.activity_date,
                    "created_at": record.created_at,
                    "teacher_id": record.teacher_id,
                    "course_id": record.course_id,
                    "total_faces": record.total_faces,
                    "matched_count": record.matched_count,
                    "unknown_count": record.unknown_count,
                    "emotion_summary": record.emotion_summary,
                    "emotion_analyzed_count": record.emotion_analyzed_count,
                    "emotion_failed_count": record.emotion_failed_count,
                    "student_id": None,
                    "name": None,
                    "class_name": None,
                    "major": None,
                    "face_score": None,
                    "emotion": None,
                    "emotion_confidence": None,
                    "emotion_error_code": None,
                    "emotion_message": None,
                }
            )
            continue

        for student in record_students:
            rows.append(
                {
                    "record_id": record.id,
                    "activity_name": record.activity_name,
                    "activity_date": record.activity_date,
                    "created_at": record.created_at,
                    "teacher_id": record.teacher_id,
                    "course_id": record.course_id,
                    "total_faces": record.total_faces,
                    "matched_count": record.matched_count,
                    "unknown_count": record.unknown_count,
                    "emotion_summary": record.emotion_summary,
                    "emotion_analyzed_count": record.emotion_analyzed_count,
                    "emotion_failed_count": record.emotion_failed_count,
                    "student_id": student.student_id,
                    "name": student.name,
                    "class_name": student.class_name,
                    "major": student.major,
                    "face_score": student.face_score,
                    "emotion": student.emotion,
                    "emotion_confidence": student.emotion_confidence,
                    "emotion_error_code": student.emotion_error_code,
                    "emotion_message": student.emotion_message,
                }
            )
    return rows


@router.get("/attendance")
def export_attendance(
    course_id: int | None = Query(None),
    session_id: int | None = Query(None),
    student_id: str | None = Query(None),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    query = db.query(AttendanceRecord).filter(AttendanceRecord.teacher_id == teacher_id)
    if course_id is not None:
        get_teacher_course(db, current_user, course_id)
        query = query.filter(AttendanceRecord.course_id == course_id)
    if session_id is not None:
        query = query.filter(AttendanceRecord.session_id == session_id)
    if student_id:
        query = query.filter(AttendanceRecord.student_id == student_id)

    records = query.order_by(AttendanceRecord.created_at.desc()).all()
    path = make_excel(attendance_rows(db, records), "attendance_records.xlsx")
    return FileResponse(path, filename=path.name)


@router.get("/my-attendance")
def export_my_attendance(
    course_id: int | None = Query(None),
    session_id: int | None = Query(None),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    query = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == current_user.student_id)
    if course_id is not None:
        query = query.filter(AttendanceRecord.course_id == course_id)
    if session_id is not None:
        query = query.filter(AttendanceRecord.session_id == session_id)

    records = query.order_by(AttendanceRecord.created_at.desc()).all()
    path = make_excel(attendance_rows(db, records), "my_attendance_records.xlsx")
    return FileResponse(path, filename=path.name)


@router.get("/activity")
def export_activity(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    teacher_activities = db.query(Activity).filter(Activity.teacher_id == teacher_id).all()
    activities = {activity.id: activity for activity in teacher_activities}
    participants = (
        db.query(ActivityParticipant)
        .filter(ActivityParticipant.activity_id.in_(list(activities.keys())))
        .all()
        if activities
        else []
    )
    rows = [
        {
            "activity_id": item.activity_id,
            "activity_name": activities[item.activity_id].activity_name if item.activity_id in activities else None,
            "activity_date": activities[item.activity_id].activity_date if item.activity_id in activities else None,
            "course_id": item.course_id,
            "student_id": item.student_id,
            "name": item.name,
            "face_score": item.face_score,
            "emotion": item.emotion,
            "face_image_id": item.face_image_id,
            "face_template_id": item.face_template_id,
        }
        for item in participants
    ]
    path = make_excel(rows, "activity_participants.xlsx")
    return FileResponse(path, filename=path.name)


@router.get("/group-photo-records")
def export_group_photo_records(
    course_id: int | None = Query(None),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    query = db.query(GroupPhotoRecord).filter(GroupPhotoRecord.teacher_id == teacher_id)
    if course_id is not None:
        get_teacher_course(db, current_user, course_id)
        query = query.filter(GroupPhotoRecord.course_id == course_id)

    records = query.order_by(GroupPhotoRecord.created_at.desc(), GroupPhotoRecord.id.desc()).all()
    record_ids = [record.id for record in records]
    students = (
        db.query(GroupPhotoRecordStudent)
        .filter(GroupPhotoRecordStudent.record_id.in_(record_ids))
        .order_by(GroupPhotoRecordStudent.record_id.desc(), GroupPhotoRecordStudent.student_id.asc())
        .all()
        if record_ids
        else []
    )
    path = make_excel(group_photo_record_rows(records, students), "group_photo_records.xlsx")
    return FileResponse(path, filename=path.name)


@router.get("/emotion")
def export_emotion(
    course_id: int | None = Query(None),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    attendance_query = db.query(AttendanceRecord).filter(AttendanceRecord.teacher_id == teacher_id)
    group_photo_query = db.query(GroupPhotoRecord).filter(GroupPhotoRecord.teacher_id == teacher_id)
    if course_id is not None:
        get_teacher_course(db, current_user, course_id)
        attendance_query = attendance_query.filter(AttendanceRecord.course_id == course_id)
        group_photo_query = group_photo_query.filter(GroupPhotoRecord.course_id == course_id)

    attendance_ids = [item.id for item in attendance_query.all()]
    group_photo_ids = [item.id for item in group_photo_query.all()]
    attendance_records = (
        db.query(EmotionRecord)
        .filter(EmotionRecord.source_type == "attendance", EmotionRecord.source_id.in_(attendance_ids))
        .all()
        if attendance_ids
        else []
    )
    group_records = (
        db.query(EmotionRecord)
        .filter(EmotionRecord.source_type == "group_photo", EmotionRecord.source_id.in_(group_photo_ids))
        .all()
        if group_photo_ids
        else []
    )
    records = sorted(
        attendance_records + group_records,
        key=lambda record: record.record_time,
        reverse=True,
    )
    rows = [
        {
            "student_id": record.student_id,
            "name": record.name,
            "course_id": record.course_id,
            "source": record.source_type,
            "source_id": record.source_id,
            "emotion": record.emotion,
            "confidence": record.confidence,
            "record_time": record.record_time,
        }
        for record in records
    ]
    path = make_excel(rows, "emotion_records.xlsx")
    return FileResponse(path, filename=path.name)
