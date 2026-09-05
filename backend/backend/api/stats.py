from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.activity import Activity, ActivityParticipant
from models.attendance import AttendanceRecord
from models.emotion import EmotionRecord
from models.group_photo_record import GroupPhotoRecord
from models.user import User
from schemas.common import ok
from services.auth_service import get_current_teacher_id, require_teacher
from services.course_service import get_teacher_course


router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/attendance")
def attendance_stats(
    course_id: int | None = None,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    query = db.query(AttendanceRecord).filter(AttendanceRecord.teacher_id == teacher_id)
    if course_id is not None:
        get_teacher_course(db, current_user, course_id)
        query = query.filter(AttendanceRecord.course_id == course_id)
    records = query.all()
    status_counter = Counter(record.status for record in records)
    return ok(
        {
            "total": len(records),
            "success": status_counter.get("success", 0) + status_counter.get("present", 0),
            "present": status_counter.get("present", 0),
            "pending": status_counter.get("pending", 0),
            "absent": status_counter.get("absent", 0),
            "failed": status_counter.get("failed", 0),
            "unknown": status_counter.get("unknown", 0),
            "by_status": dict(status_counter),
        },
        "Attendance stats",
    )


@router.get("/activity-frequency")
def activity_frequency(
    course_id: int | None = None,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    if course_id is not None:
        get_teacher_course(db, current_user, course_id)
    activity_query = db.query(Activity).filter(Activity.teacher_id == teacher_id)
    if course_id is not None:
        activity_query = activity_query.filter(Activity.course_id == course_id)
    activity_ids = [activity.id for activity in activity_query.all()]
    participants = (
        db.query(ActivityParticipant)
        .filter(ActivityParticipant.activity_id.in_(activity_ids))
        .all()
        if activity_ids
        else []
    )
    frequency: dict[str, dict] = {}
    for item in participants:
        key = item.student_id or "unknown"
        if key not in frequency:
            frequency[key] = {
                "student_id": item.student_id,
                "name": item.name,
                "count": 0,
            }
        frequency[key]["count"] += 1
    return ok(list(frequency.values()), "Activity frequency stats")


@router.get("/emotion")
def emotion_stats(
    course_id: int | None = None,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    record_query = db.query(AttendanceRecord).filter(AttendanceRecord.teacher_id == teacher_id)
    group_photo_query = db.query(GroupPhotoRecord).filter(GroupPhotoRecord.teacher_id == teacher_id)
    if course_id is not None:
        get_teacher_course(db, current_user, course_id)
        record_query = record_query.filter(AttendanceRecord.course_id == course_id)
        group_photo_query = group_photo_query.filter(GroupPhotoRecord.course_id == course_id)

    attendance_ids = [record.id for record in record_query.all()]
    group_photo_ids = [record.id for record in group_photo_query.all()]

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
    records = attendance_records + group_records
    emotion_counter = Counter(record.emotion for record in records)
    source_counter = Counter(record.source_type for record in records)
    return ok(
        {
            "total": len(records),
            "by_emotion": dict(emotion_counter),
            "by_source": dict(source_counter),
        },
        "Emotion stats",
    )
