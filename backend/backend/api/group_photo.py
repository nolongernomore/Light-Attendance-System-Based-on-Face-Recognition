from collections import Counter
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.emotion import EmotionRecord
from models.group_photo_record import GroupPhotoRecord, GroupPhotoRecordStudent
from models.student import Student
from models.user import User
from schemas.common import ok
from services.auth_service import get_current_teacher_id, require_teacher
from services.course_service import get_teacher_course
from services.db_service import build_face_database
from services.emotion_service import EMOTION_CN, analyze_emotion
from services.face_service import recognize_group_photo
from services.file_service import build_upload_path, relative_upload_path, save_upload_file


router = APIRouter(prefix="/group-photo", tags=["group-photo"])
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
FACE_CROP_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def resolve_backend_path(image_path: str) -> Path:
    path = Path(image_path)
    return path if path.is_absolute() else settings.BASE_DIR / path


def serialize_emotion_result(
    emotion: str | None,
    confidence: float | None,
    error_code: str | None,
    message: str | None,
) -> dict | None:
    if not emotion and confidence is None and not error_code and not message:
        return None
    return {
        "success": error_code is None,
        "emotion": emotion,
        "emotion_cn": EMOTION_CN.get(emotion, emotion) if emotion else None,
        "confidence": confidence,
        "error_code": error_code,
        "message": message,
    }


def parse_emotion_summary(value: str | None) -> dict:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_group_face_crop(photo_path: str, bbox: list[int] | tuple[int, ...] | None, index: int) -> str:
    if not bbox or len(bbox) != 4:
        return photo_path

    source_path = resolve_backend_path(photo_path)
    try:
        from service.face_service import utils as face_utils

        image = face_utils.load_image(source_path)
        crop = face_utils.crop_face(image, tuple(int(value) for value in bbox), pad_ratio=0.15)
        if crop.size == 0:
            return photo_path
        target = build_upload_path(
            settings.GROUP_PHOTOS_DIR,
            f"group_face_{index}",
            ".jpg",
            FACE_CROP_EXTENSIONS,
        )
        if not face_utils.imwrite_unicode(target, crop):
            return photo_path
        return relative_upload_path(target)
    except Exception:
        return photo_path


def enrich_faces_with_emotion(photo_path: str, faces: list[dict]) -> tuple[list[dict], dict, int, int]:
    enriched: list[dict] = []
    counter: Counter[str] = Counter()
    analyzed_count = 0
    failed_count = 0

    for index, face in enumerate(faces, start=1):
        item = dict(face)
        crop_path = save_group_face_crop(photo_path, item.get("bbox"), index)
        emotion_result = analyze_emotion(crop_path)
        item["face_crop_path"] = crop_path
        item["emotion"] = emotion_result
        if emotion_result.get("success"):
            analyzed_count += 1
            emotion = emotion_result.get("emotion")
            if emotion:
                counter[emotion] += 1
        else:
            failed_count += 1
        enriched.append(item)

    return enriched, dict(counter), analyzed_count, failed_count


def serialize_record_student(item: GroupPhotoRecordStudent) -> dict:
    emotion = serialize_emotion_result(
        item.emotion,
        item.emotion_confidence,
        item.emotion_error_code,
        item.emotion_message,
    )
    return {
        "id": item.id,
        "record_id": item.record_id,
        "student_id": item.student_id,
        "name": item.name,
        "class_name": item.class_name,
        "major": item.major,
        "face_score": item.face_score,
        "face_image_id": item.face_image_id,
        "face_template_id": item.face_template_id,
        "emotion": item.emotion,
        "emotion_confidence": item.emotion_confidence,
        "emotion_error_code": item.emotion_error_code,
        "emotion_message": item.emotion_message,
        "emotion_result": emotion,
        "bbox": json.loads(item.bbox) if item.bbox else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def serialize_group_photo_record(
    record: GroupPhotoRecord,
    students: list[GroupPhotoRecordStudent] | None = None,
    include_students: bool = True,
) -> dict:
    data = {
        "id": record.id,
        "teacher_id": record.teacher_id,
        "course_id": record.course_id,
        "activity_name": record.activity_name,
        "activity_date": record.activity_date.isoformat() if record.activity_date else None,
        "description": record.description,
        "photo_path": record.photo_path,
        "annotated_image_path": record.annotated_image_path,
        "total_faces": record.total_faces,
        "matched_count": record.matched_count,
        "unknown_count": record.unknown_count,
        "recognized_student_count": record.recognized_student_count,
        "emotion_summary": parse_emotion_summary(record.emotion_summary),
        "emotion_analyzed_count": record.emotion_analyzed_count,
        "emotion_failed_count": record.emotion_failed_count,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
    if include_students:
        data["students"] = [serialize_record_student(item) for item in (students or [])]
    return data


def student_map(db: Session, student_ids: set[str]) -> dict[str, Student]:
    if not student_ids:
        return {}
    return {
        student.student_id: student
        for student in db.query(Student)
        .filter(Student.student_id.in_(student_ids), Student.is_active == True)
        .all()
    }


def record_students_for_records(
    db: Session,
    record_ids: list[int],
) -> dict[int, list[GroupPhotoRecordStudent]]:
    if not record_ids:
        return {}
    rows = (
        db.query(GroupPhotoRecordStudent)
        .filter(GroupPhotoRecordStudent.record_id.in_(record_ids))
        .order_by(GroupPhotoRecordStudent.record_id.desc(), GroupPhotoRecordStudent.student_id.asc())
        .all()
    )
    grouped: dict[int, list[GroupPhotoRecordStudent]] = {}
    for row in rows:
        grouped.setdefault(row.record_id, []).append(row)
    return grouped


def save_recognized_students(
    db: Session,
    record: GroupPhotoRecord,
    faces: list[dict],
) -> list[GroupPhotoRecordStudent]:
    matched_faces = [
        face
        for face in faces
        if face.get("matched") and face.get("student_id")
    ]
    students = student_map(db, {face["student_id"] for face in matched_faces})
    saved: list[GroupPhotoRecordStudent] = []
    seen_student_ids: set[str] = set()

    for face in matched_faces:
        student_id = face["student_id"]
        if student_id in seen_student_ids:
            continue
        seen_student_ids.add(student_id)
        student = students.get(student_id)
        emotion_result = face.get("emotion") or {}
        item = GroupPhotoRecordStudent(
            record_id=record.id,
            teacher_id=record.teacher_id,
            student_id=student_id,
            name=student.name if student else face.get("name"),
            class_name=student.class_name if student else None,
            major=student.major if student else None,
            face_score=face.get("score"),
            face_image_id=face.get("face_image_id"),
            face_template_id=face.get("template_id"),
            emotion=emotion_result.get("emotion"),
            emotion_confidence=emotion_result.get("confidence"),
            emotion_error_code=emotion_result.get("error_code"),
            emotion_message=emotion_result.get("message"),
            bbox=json.dumps(face.get("bbox"), ensure_ascii=False),
        )
        db.add(item)
        db.add(
            EmotionRecord(
                student_id=student_id,
                name=item.name,
                course_id=record.course_id,
                source_type="group_photo",
                source_id=record.id,
                emotion=emotion_result.get("emotion") or "unknown",
                confidence=emotion_result.get("confidence"),
                record_time=record.created_at or datetime.now(),
            )
        )
        saved.append(item)

    record.recognized_student_count = len(saved)
    return saved


def export_group_photo_rows(records: list[GroupPhotoRecord], students_by_record: dict[int, list[GroupPhotoRecordStudent]]) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        students = students_by_record.get(record.id, [])
        if not students:
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
                    "emotion_summary": json.dumps(parse_emotion_summary(record.emotion_summary), ensure_ascii=False),
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

        for student in students:
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
                    "emotion_summary": json.dumps(parse_emotion_summary(record.emotion_summary), ensure_ascii=False),
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


@router.post("/recognize")
def recognize_photo(
    activity_name: str | None = Form(None),
    activity_date: date | None = Form(None),
    course_id: int | None = Form(None),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    if course_id is not None:
        get_teacher_course(db, current_user, course_id)

    photo_path = save_upload_file(
        file,
        settings.GROUP_PHOTOS_DIR,
        "group_record",
        IMAGE_EXTENSIONS,
    )
    recognition = recognize_group_photo(photo_path, build_face_database(db, course_id))
    if not recognition.get("success"):
        raise HTTPException(status_code=400, detail=recognition.get("error_code") or "Group photo failed")

    faces, emotion_summary, emotion_analyzed_count, emotion_failed_count = enrich_faces_with_emotion(
        photo_path,
        recognition.get("faces") or [],
    )
    recognition["faces"] = faces

    record = GroupPhotoRecord(
        teacher_id=teacher_id,
        course_id=course_id,
        activity_name=activity_name or "Group photo recognition",
        activity_date=activity_date or date.today(),
        description=description,
        photo_path=photo_path,
        annotated_image_path=recognition.get("annotated_image_path"),
        total_faces=recognition.get("total_faces", 0),
        matched_count=recognition.get("matched_count", 0),
        unknown_count=recognition.get("unknown_count", 0),
        recognized_student_count=0,
        emotion_summary=json.dumps(emotion_summary, ensure_ascii=False),
        emotion_analyzed_count=emotion_analyzed_count,
        emotion_failed_count=emotion_failed_count,
    )
    db.add(record)
    db.flush()

    saved_students = save_recognized_students(db, record, faces)
    db.commit()
    db.refresh(record)
    for item in saved_students:
        db.refresh(item)

    return ok(
        {
            "record": serialize_group_photo_record(record, saved_students),
            "recognized_students": [serialize_record_student(item) for item in saved_students],
            "recognition": {
                "total_faces": record.total_faces,
                "matched_count": record.matched_count,
                "unknown_count": record.unknown_count,
                "emotion_summary": emotion_summary,
                "emotion_analyzed_count": emotion_analyzed_count,
                "emotion_failed_count": emotion_failed_count,
                "faces": recognition.get("faces") or [],
            },
        },
        "Group photo recognized",
    )


@router.get("/records")
def list_group_photo_records(
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
    students_by_record = record_students_for_records(db, [record.id for record in records])
    return ok(
        [
            serialize_group_photo_record(record, students_by_record.get(record.id, []))
            for record in records
        ],
        "Group photo records",
    )


@router.get("/records/export")
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
    students_by_record = record_students_for_records(db, [record.id for record in records])
    rows = export_group_photo_rows(records, students_by_record)

    settings.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = settings.EXPORTS_DIR / "group_photo_records.xlsx"
    pd.DataFrame(rows).to_excel(path, index=False)
    return FileResponse(path, filename=path.name)


@router.get("/records/{record_id}")
def get_group_photo_record(
    record_id: int,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    record = (
        db.query(GroupPhotoRecord)
        .filter(
            GroupPhotoRecord.id == record_id,
            GroupPhotoRecord.teacher_id == get_current_teacher_id(current_user),
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Group photo record not found")

    students = (
        db.query(GroupPhotoRecordStudent)
        .filter(GroupPhotoRecordStudent.record_id == record.id)
        .order_by(GroupPhotoRecordStudent.student_id.asc())
        .all()
    )
    return ok(serialize_group_photo_record(record, students), "Group photo record detail")


@router.delete("/records/{record_id}")
def delete_group_photo_record(
    record_id: int,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    record = (
        db.query(GroupPhotoRecord)
        .filter(
            GroupPhotoRecord.id == record_id,
            GroupPhotoRecord.teacher_id == teacher_id,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Group photo record not found")

    student_count = (
        db.query(GroupPhotoRecordStudent)
        .filter(GroupPhotoRecordStudent.record_id == record.id)
        .delete(synchronize_session=False)
    )
    emotion_count = (
        db.query(EmotionRecord)
        .filter(
            EmotionRecord.source_type == "group_photo",
            EmotionRecord.source_id == record.id,
        )
        .delete(synchronize_session=False)
    )
    db.delete(record)
    db.commit()
    return ok(
        {
            "record_id": record_id,
            "deleted": True,
            "deleted_student_count": student_count,
            "deleted_emotion_count": emotion_count,
        },
        "Group photo record deleted",
    )


@router.get("/activities")
def list_activities(
    course_id: int | None = Query(None),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    return list_group_photo_records(course_id, current_user, db)


@router.get("/{record_id}")
def get_activity(
    record_id: int,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    return get_group_photo_record(record_id, current_user, db)


@router.delete("/{record_id}")
def delete_activity(
    record_id: int,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    return delete_group_photo_record(record_id, current_user, db)
