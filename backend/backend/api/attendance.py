from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.attendance import AttendanceRecord, AttendanceSession
from models.course import Course
from models.emotion import EmotionRecord
from models.student import Student
from models.user import User
from schemas.attendance import AttendanceSessionCreate
from schemas.common import ok
from services.auth_service import get_current_teacher_id, require_student, require_teacher
from services.course_service import get_active_course_student_ids, get_teacher_course, resolve_teacher_course
from services.db_service import build_student_face_database
from services.emotion_service import EMOTION_CN, analyze_emotion
from services.face_service import get_face_service_status, recognize_single_face
from services.file_service import save_upload_file


router = APIRouter(prefix="/attendance", tags=["attendance"])
CHECKIN_EXTENSIONS = {".webm", ".mp4", ".mov", ".avi", ".jpg", ".jpeg", ".png"}
CHECKED_STATUSES = {"present", "late", "success"}
CHECKIN_SUCCESS = "CHECKIN_SUCCESS"
CHECKIN_FAILED_TIMEOUT = "CHECKIN_FAILED_TIMEOUT"
CHECKIN_FAILED_RECOGNITION = "CHECKIN_FAILED_RECOGNITION"
FACE_CHECKIN_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def checkin_response(code: str, message: str, data: dict, success: bool = False) -> dict:
    return {
        "success": success,
        "code": code,
        "message": message,
        "data": data,
    }


def face_database_diagnostics(face_database: list[dict]) -> dict:
    if not face_database:
        return {
            "template_count": 0,
            "template_ids": [],
            "face_image_ids": [],
            "template_dimensions": [],
            "template_algorithms": [],
            "templates": [],
        }

    person = face_database[0]
    templates = person.get("template_diagnostics") or []
    return {
        "student_id": person.get("student_id"),
        "name": person.get("name"),
        "template_count": len(person.get("embeddings") or []),
        "template_ids": person.get("template_ids") or [],
        "face_image_ids": person.get("face_image_ids") or [],
        "template_dimensions": [item.get("embedding_dimension", 0) for item in templates],
        "template_algorithms": [item.get("algorithm") for item in templates],
        "templates": templates,
    }


def incompatible_template_message(diagnostics: dict, expected_dim: int | None) -> str | None:
    if not expected_dim:
        return None
    dimensions = diagnostics.get("template_dimensions") or []
    if dimensions and any(dimension != expected_dim for dimension in dimensions):
        return (
            f"Face template dimension does not match current face service. "
            f"expected={expected_dim}, actual={dimensions}. Please re-enroll this student's face image."
        )
    return None


def is_liveness_timeout(status: str | None, error_code: str | None) -> bool:
    values = {value.lower() for value in [status or "", error_code or ""] if value}
    return bool(values & {"timeout", "timed_out", "expired", "challenge_expired", "liveness_timeout"})


def recognize_single_face_with_timeout(image_path: str, face_database: list[dict]) -> tuple[dict, bool]:
    timeout_seconds = settings.CHECKIN_FACE_TIMEOUT_SECONDS
    if timeout_seconds <= 0:
        return recognize_single_face(image_path, face_database), False

    future = FACE_CHECKIN_EXECUTOR.submit(recognize_single_face, image_path, face_database)
    try:
        return future.result(timeout=timeout_seconds), False
    except FutureTimeoutError:
        future.cancel()
        return (
            {
                "success": False,
                "matched": False,
                "student_id": None,
                "name": None,
                "score": 0,
                "bbox": None,
                "face_crop_path": image_path,
                "template_id": None,
                "face_image_id": None,
                "error_code": "FACE_SERVICE_TIMEOUT",
                "message": f"Face recognition timed out after {timeout_seconds:g}s",
            },
            True,
        )


def refresh_session_counts(db: Session, session: AttendanceSession) -> None:
    records = db.query(AttendanceRecord).filter(AttendanceRecord.session_id == session.id).all()
    student_records = [record for record in records if record.student_id]
    session.expected_count = len(student_records)
    session.checked_count = sum(1 for record in student_records if record.status in CHECKED_STATUSES)
    session.absent_count = sum(1 for record in student_records if record.status == "absent")
    session.failed_count = sum(1 for record in records if record.status == "failed")
    session.unknown_count = sum(1 for record in records if record.status == "unknown")
    session.updated_at = datetime.now()


def serialize_record(record: AttendanceRecord) -> dict:
    emotion = serialize_stored_emotion(
        record.emotion,
        record.emotion_confidence,
        record.emotion_error_code,
        record.emotion_message,
    )
    return {
        "id": record.id,
        "session_id": record.session_id,
        "course_id": record.course_id,
        "teacher_id": record.teacher_id,
        "student_id": record.student_id,
        "name": record.name,
        "status": record.status,
        "is_checked_in": record.is_checked_in,
        "checkin_time": record.checkin_time.isoformat() if record.checkin_time else None,
        "submit_time": record.submit_time.isoformat() if record.submit_time else None,
        "liveness_passed": record.liveness_passed,
        "liveness_score": record.liveness_score,
        "face_score": record.face_score,
        "emotion": record.emotion,
        "emotion_confidence": record.emotion_confidence,
        "emotion_error_code": record.emotion_error_code,
        "emotion_message": record.emotion_message,
        "emotion_result": emotion,
        "image_path": record.image_path,
        "used_face_image_id": record.used_face_image_id,
        "used_face_template_id": record.used_face_template_id,
        "fail_reason": record.fail_reason,
    }


def serialize_stored_emotion(
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


def store_attendance_emotion(
    db: Session,
    record: AttendanceRecord,
    image_path: str,
    record_time: datetime,
) -> dict:
    emotion_result = analyze_emotion(image_path)
    record.emotion = emotion_result.get("emotion")
    record.emotion_confidence = emotion_result.get("confidence")
    record.emotion_error_code = emotion_result.get("error_code")
    record.emotion_message = emotion_result.get("message")
    db.flush()
    (
        db.query(EmotionRecord)
        .filter(
            EmotionRecord.source_type == "attendance",
            EmotionRecord.source_id == record.id,
        )
        .delete(synchronize_session=False)
    )
    db.add(
        EmotionRecord(
            student_id=record.student_id,
            name=record.name,
            course_id=record.course_id,
            source_type="attendance",
            source_id=record.id,
            emotion=emotion_result.get("emotion") or "unknown",
            confidence=emotion_result.get("confidence"),
            record_time=record_time,
        )
    )
    return emotion_result


def serialize_checkin_student(student: Student | None, record: AttendanceRecord) -> dict:
    return {
        "student_id": record.student_id,
        "name": student.name if student else record.name,
        "major": student.major if student else None,
        "class_name": student.class_name if student else None,
    }


def serialize_session(session: AttendanceSession) -> dict:
    return {
        "id": session.id,
        "course_id": session.course_id,
        "teacher_id": session.teacher_id,
        "title": session.title,
        "status": session.status,
        "is_closed": session.is_closed,
        "start_time": session.start_time.isoformat() if session.start_time else None,
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "expected_count": session.expected_count,
        "checked_count": session.checked_count,
        "absent_count": session.absent_count,
        "failed_count": session.failed_count,
        "unknown_count": session.unknown_count,
    }


def serialize_student_active_session(
    session: AttendanceSession,
    record: AttendanceRecord,
    course: Course | None = None,
) -> dict:
    data = serialize_session(session)
    data.update(
        {
            "course_name": course.course_name if course else None,
            "record": serialize_record(record),
        }
    )
    return data


@router.post("/sessions")
def create_session(
    payload: AttendanceSessionCreate,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    course = resolve_teacher_course(db, current_user, payload.course_id)

    student_ids = get_active_course_student_ids(db, course.id)
    students = (
        db.query(Student)
        .filter(Student.student_id.in_(student_ids), Student.is_active == True)
        .order_by(Student.student_id.asc())
        .all()
        if student_ids
        else []
    )
    session = AttendanceSession(
        course_id=course.id,
        teacher_id=teacher_id,
        title=payload.title or f"{course.course_name} Attendance",
        status="active",
        is_closed=False,
        expected_count=len(students),
        checked_count=0,
        absent_count=0,
        failed_count=0,
        unknown_count=0,
    )
    db.add(session)
    db.flush()

    for student in students:
        db.add(
            AttendanceRecord(
                session_id=session.id,
                course_id=course.id,
                teacher_id=teacher_id,
                student_id=student.student_id,
                name=student.name,
                status="pending",
                is_checked_in=False,
                liveness_passed=False,
            )
        )

    db.commit()
    db.refresh(session)
    return ok(serialize_session(session), "Attendance session started")


@router.get("/sessions")
def list_sessions(
    course_id: int | None = Query(None),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    query = db.query(AttendanceSession).filter(AttendanceSession.teacher_id == teacher_id)
    if course_id is not None:
        get_teacher_course(db, current_user, course_id)
        query = query.filter(AttendanceSession.course_id == course_id)
    sessions = query.order_by(AttendanceSession.start_time.desc()).all()
    return ok([serialize_session(session) for session in sessions], "Attendance sessions")


@router.get("/sessions/active")
def get_active_session(
    course_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(AttendanceSession).filter(AttendanceSession.status == "active")
    if course_id is not None:
        query = query.filter(AttendanceSession.course_id == course_id)
    session = query.order_by(AttendanceSession.start_time.desc()).first()
    return ok(serialize_session(session) if session else None, "Active attendance session")


@router.get("/my-sessions/active")
def get_my_active_sessions(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    student_id = current_user.student_id
    if not student_id:
        raise HTTPException(status_code=400, detail="Current account is not linked to a student")

    rows = (
        db.query(AttendanceSession, AttendanceRecord, Course)
        .join(AttendanceRecord, AttendanceRecord.session_id == AttendanceSession.id)
        .join(Course, Course.id == AttendanceSession.course_id)
        .filter(
            AttendanceSession.status == "active",
            AttendanceSession.is_closed == False,
            AttendanceRecord.student_id == student_id,
        )
        .order_by(AttendanceSession.start_time.desc(), AttendanceSession.id.desc())
        .all()
    )
    sessions = [
        serialize_student_active_session(session, record, course)
        for session, record, course in rows
    ]
    return ok(sessions, "My active attendance sessions")


@router.post("/sessions/{session_id}/close")
def close_session(
    session_id: int,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    session = (
        db.query(AttendanceSession)
        .filter(AttendanceSession.id == session_id, AttendanceSession.teacher_id == teacher_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Attendance session not found")

    pending_records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.session_id == session.id, AttendanceRecord.status == "pending")
        .all()
    )
    for record in pending_records:
        record.status = "absent"
        record.is_checked_in = False
        record.fail_reason = "Attendance closed without check-in"
        record.updated_at = datetime.now()

    session.status = "closed"
    session.is_closed = True
    session.end_time = datetime.now()
    refresh_session_counts(db, session)
    db.commit()
    db.refresh(session)
    return ok(serialize_session(session), "Attendance session closed")


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    session = (
        db.query(AttendanceSession)
        .filter(AttendanceSession.id == session_id, AttendanceSession.teacher_id == teacher_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Attendance session not found")

    record_ids = [
        row[0]
        for row in db.query(AttendanceRecord.id)
        .filter(AttendanceRecord.session_id == session.id)
        .all()
    ]
    emotion_count = 0
    if record_ids:
        emotion_count = (
            db.query(EmotionRecord)
            .filter(
                EmotionRecord.source_type == "attendance",
                EmotionRecord.source_id.in_(record_ids),
            )
            .delete(synchronize_session=False)
        )
    record_count = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.session_id == session.id)
        .delete(synchronize_session=False)
    )
    db.delete(session)
    db.commit()
    return ok(
        {
            "session_id": session_id,
            "deleted_record_count": record_count,
            "deleted_emotion_count": emotion_count,
        },
        "Attendance session deleted",
    )


@router.post("/checkin")
def checkin(
    session_id: int = Form(...),
    file: UploadFile = File(...),
    liveness_passed: bool = Form(True),
    liveness_score: float | None = Form(None),
    liveness_status: str | None = Form(None),
    liveness_error_code: str | None = Form(None),
    liveness_message: str | None = Form(None),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    student_id = current_user.student_id
    if not student_id:
        file.file.close()
        raise HTTPException(status_code=400, detail="Current account is not linked to a student")

    session = (
        db.query(AttendanceSession)
        .filter(AttendanceSession.id == session_id, AttendanceSession.status == "active")
        .first()
    )
    if not session:
        file.file.close()
        raise HTTPException(status_code=400, detail="Attendance session not found or closed")

    record = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.session_id == session.id, AttendanceRecord.student_id == student_id)
        .first()
    )
    if not record:
        file.file.close()
        raise HTTPException(status_code=403, detail="Current student is not in this attendance session")

    student = db.query(Student).filter(Student.student_id == student_id).first()

    if record.status in CHECKED_STATUSES and record.is_checked_in:
        file.file.close()
        return checkin_response(
            CHECKIN_SUCCESS,
            "Attendance already completed",
            {
                "status": "already_checked_in",
                "checkin_time": record.checkin_time.isoformat() if record.checkin_time else None,
                "submit_time": record.submit_time.isoformat() if record.submit_time else None,
                "student": serialize_checkin_student(student, record),
                "record": serialize_record(record),
            },
            success=True,
        )

    frontend_liveness = {
        "source": "frontend",
        "passed": liveness_passed,
        "score": liveness_score,
        "status": liveness_status,
        "error_code": liveness_error_code,
        "message": liveness_message,
    }
    now = datetime.now()
    file_path = save_upload_file(file, settings.CHECKIN_DIR, "checkin", CHECKIN_EXTENSIONS)

    if not liveness_passed:
        timeout = is_liveness_timeout(liveness_status, liveness_error_code)
        code = CHECKIN_FAILED_TIMEOUT if timeout else CHECKIN_FAILED_RECOGNITION
        reason = "Frontend liveness timeout" if timeout else "Frontend liveness failed"
        if liveness_message:
            reason = f"{reason}: {liveness_message}"
        record.status = "failed"
        record.is_checked_in = False
        record.submit_time = now
        record.liveness_passed = False
        record.liveness_score = liveness_score
        record.image_path = file_path
        record.fail_reason = reason
        record.updated_at = now
        refresh_session_counts(db, session)
        db.commit()
        db.refresh(record)
        return checkin_response(
            code,
            reason,
            {
                "status": "failed",
                "failure_type": "timeout" if timeout else "recognition",
                "reason_code": "LIVENESS_TIMEOUT" if timeout else "LIVENESS_FAILED",
                "checkin_time": None,
                "submit_time": record.submit_time.isoformat() if record.submit_time else None,
                "record": serialize_record(record),
                "liveness": frontend_liveness,
            },
        )

    face_database = build_student_face_database(db, student_id)
    diagnostics = face_database_diagnostics(face_database)
    if not face_database:
        record.status = "failed"
        record.is_checked_in = False
        record.submit_time = now
        record.liveness_passed = True
        record.liveness_score = liveness_score
        record.image_path = file_path
        record.fail_reason = "Current student has no active face template"
        record.updated_at = now
        emotion_result = store_attendance_emotion(db, record, file_path, now)
        refresh_session_counts(db, session)
        db.commit()
        db.refresh(record)
        return checkin_response(
            CHECKIN_FAILED_RECOGNITION,
            "Current student has no active face template",
            {
                "status": "failed",
                "failure_type": "recognition",
                "reason_code": "FACE_NOT_ENROLLED",
                "checkin_time": None,
                "submit_time": record.submit_time.isoformat() if record.submit_time else None,
                "record": serialize_record(record),
                "liveness": frontend_liveness,
                "face_database": diagnostics,
                "face_service": get_face_service_status(),
                "emotion": emotion_result,
            },
        )

    face_service_status = get_face_service_status()
    template_message = incompatible_template_message(
        diagnostics,
        face_service_status.get("expected_embedding_dim"),
    )
    if template_message:
        record.status = "failed"
        record.is_checked_in = False
        record.submit_time = now
        record.liveness_passed = True
        record.liveness_score = liveness_score
        record.image_path = file_path
        record.fail_reason = template_message
        record.updated_at = now
        emotion_result = store_attendance_emotion(db, record, file_path, now)
        refresh_session_counts(db, session)
        db.commit()
        db.refresh(record)
        return checkin_response(
            CHECKIN_FAILED_RECOGNITION,
            template_message,
            {
                "status": "failed",
                "failure_type": "recognition",
                "reason_code": "FACE_TEMPLATE_INCOMPATIBLE",
                "checkin_time": None,
                "submit_time": record.submit_time.isoformat() if record.submit_time else None,
                "record": serialize_record(record),
                "liveness": frontend_liveness,
                "face_database": diagnostics,
                "face_service": face_service_status,
                "emotion": emotion_result,
            },
        )

    face_crop_path = file_path
    face_result, face_timeout = recognize_single_face_with_timeout(face_crop_path, face_database)
    if face_timeout:
        reason = face_result.get("message") or "Face recognition timed out"
        record.status = "failed"
        record.is_checked_in = False
        record.submit_time = now
        record.liveness_passed = True
        record.liveness_score = liveness_score
        record.face_score = face_result.get("score")
        record.image_path = file_path
        record.used_face_image_id = face_result.get("face_image_id")
        record.used_face_template_id = face_result.get("template_id")
        record.fail_reason = reason
        record.updated_at = now
        emotion_result = store_attendance_emotion(
            db,
            record,
            face_result.get("face_crop_path") or file_path,
            now,
        )
        refresh_session_counts(db, session)
        db.commit()
        db.refresh(record)
        return checkin_response(
            CHECKIN_FAILED_TIMEOUT,
            reason,
            {
                "status": "failed",
                "failure_type": "timeout",
                "reason_code": "FACE_SERVICE_TIMEOUT",
                "checkin_time": None,
                "submit_time": record.submit_time.isoformat() if record.submit_time else None,
                "record": serialize_record(record),
                "liveness": frontend_liveness,
                "face": face_result,
                "face_database": diagnostics,
                "face_service": face_service_status,
                "emotion": emotion_result,
            },
        )

    matched_student_id = face_result.get("student_id")
    if not face_result.get("matched") or matched_student_id != student_id:
        face_error_code = face_result.get("error_code")
        reason = face_result.get("message") or face_error_code or "Face does not match current student"
        record.status = "failed"
        record.is_checked_in = False
        record.submit_time = now
        record.liveness_passed = True
        record.liveness_score = liveness_score
        record.face_score = face_result.get("score")
        record.image_path = file_path
        record.used_face_image_id = face_result.get("face_image_id")
        record.used_face_template_id = face_result.get("template_id")
        record.fail_reason = reason
        record.updated_at = now
        emotion_result = store_attendance_emotion(
            db,
            record,
            face_result.get("face_crop_path") or file_path,
            now,
        )
        refresh_session_counts(db, session)
        db.commit()
        db.refresh(record)
        return checkin_response(
            CHECKIN_FAILED_RECOGNITION,
            reason,
            {
                "status": "failed",
                "failure_type": "recognition",
                "reason_code": face_error_code or "FACE_NOT_MATCHED",
                "checkin_time": None,
                "submit_time": record.submit_time.isoformat() if record.submit_time else None,
                "record": serialize_record(record),
                "liveness": frontend_liveness,
                "face": face_result,
                "face_database": diagnostics,
                "face_service": face_service_status,
                "emotion": emotion_result,
            },
        )

    record.name = face_result.get("name")
    record.status = "present"
    record.is_checked_in = True
    record.checkin_time = now
    record.submit_time = now
    record.liveness_passed = True
    record.liveness_score = liveness_score
    record.face_score = face_result.get("score")
    record.image_path = file_path
    record.used_face_image_id = face_result.get("face_image_id")
    record.used_face_template_id = face_result.get("template_id")
    record.fail_reason = None
    record.updated_at = now
    emotion_result = store_attendance_emotion(
        db,
        record,
        face_result.get("face_crop_path") or face_crop_path,
        record.checkin_time or now,
    )
    refresh_session_counts(db, session)
    db.commit()
    db.refresh(record)

    return checkin_response(
        CHECKIN_SUCCESS,
        "Attendance success",
        {
            "status": "success",
            "checkin_time": record.checkin_time.isoformat() if record.checkin_time else None,
            "submit_time": record.submit_time.isoformat() if record.submit_time else None,
            "student": serialize_checkin_student(student, record),
            "record": serialize_record(record),
            "liveness": frontend_liveness,
            "face": face_result,
            "face_database": diagnostics,
            "face_service": face_service_status,
            "emotion": emotion_result,
        },
        success=True,
    )


@router.get("/records")
def list_records(
    student_id: str | None = Query(None),
    course_id: int | None = Query(None),
    session_id: int | None = Query(None),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    teacher_id = get_current_teacher_id(current_user)
    query = db.query(AttendanceRecord).filter(AttendanceRecord.teacher_id == teacher_id)
    if student_id:
        query = query.filter(AttendanceRecord.student_id == student_id)
    if course_id:
        get_teacher_course(db, current_user, course_id)
        query = query.filter(AttendanceRecord.course_id == course_id)
    if session_id:
        query = query.filter(AttendanceRecord.session_id == session_id)
    records = query.order_by(AttendanceRecord.created_at.desc()).all()
    return ok([serialize_record(record) for record in records], "Attendance records")


@router.get("/my-records")
def my_records(
    course_id: int | None = Query(None),
    session_id: int | None = Query(None),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    query = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == current_user.student_id)
    if course_id:
        query = query.filter(AttendanceRecord.course_id == course_id)
    if session_id:
        query = query.filter(AttendanceRecord.session_id == session_id)
    records = query.order_by(AttendanceRecord.created_at.desc()).all()
    return ok([serialize_record(record) for record in records], "My attendance records")
