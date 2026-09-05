from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text

from database import Base


class LivenessChallenge(Base):
    __tablename__ = "liveness_challenges"

    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(String, unique=True, index=True, nullable=False)
    session_id = Column(Integer, index=True, nullable=True)
    student_id = Column(String, index=True, nullable=True)
    actions = Column(Text, nullable=False)
    expire_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, index=True, nullable=False)
    teacher_id = Column(Integer, index=True, nullable=False)
    title = Column(String, nullable=False)
    status = Column(String, default="active", index=True, nullable=False)
    start_time = Column(DateTime, default=datetime.now, nullable=False)
    end_time = Column(DateTime, nullable=True)
    is_closed = Column(Boolean, default=False, nullable=False)
    expected_count = Column(Integer, default=0, nullable=False)
    checked_count = Column(Integer, default=0, nullable=False)
    absent_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    unknown_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, index=True, nullable=True)
    course_id = Column(Integer, index=True, nullable=True)
    teacher_id = Column(Integer, index=True, nullable=True)
    student_id = Column(String, index=True, nullable=True)
    name = Column(String, nullable=True)
    checkin_time = Column(DateTime, nullable=True)
    submit_time = Column(DateTime, nullable=True)
    status = Column(String, default="pending", index=True, nullable=False)
    is_checked_in = Column(Boolean, default=False, nullable=False)
    liveness_passed = Column(Boolean, default=False, nullable=False)
    liveness_score = Column(Float, nullable=True)
    face_score = Column(Float, nullable=True)
    emotion = Column(String, nullable=True)
    emotion_confidence = Column(Float, nullable=True)
    emotion_error_code = Column(String, nullable=True)
    emotion_message = Column(Text, nullable=True)
    image_path = Column(String, nullable=True)
    used_face_image_id = Column(Integer, nullable=True)
    used_face_template_id = Column(Integer, nullable=True)
    fail_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


Index(
    "ix_attendance_sessions_teacher_course_status",
    AttendanceSession.teacher_id,
    AttendanceSession.course_id,
    AttendanceSession.status,
)
Index(
    "ix_attendance_records_session_student",
    AttendanceRecord.session_id,
    AttendanceRecord.student_id,
)
Index(
    "ix_attendance_records_student_status",
    AttendanceRecord.student_id,
    AttendanceRecord.status,
)
Index(
    "ix_attendance_records_teacher_course",
    AttendanceRecord.teacher_id,
    AttendanceRecord.course_id,
)
