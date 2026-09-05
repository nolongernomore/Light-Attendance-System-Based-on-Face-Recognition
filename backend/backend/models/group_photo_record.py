from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text

from database import Base


class GroupPhotoRecord(Base):
    __tablename__ = "group_photo_records"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, index=True, nullable=False)
    course_id = Column(Integer, index=True, nullable=True)
    activity_name = Column(String, nullable=True)
    activity_date = Column(Date, default=date.today, nullable=True)
    description = Column(Text, nullable=True)
    photo_path = Column(String, nullable=False)
    annotated_image_path = Column(String, nullable=True)
    total_faces = Column(Integer, default=0, nullable=False)
    matched_count = Column(Integer, default=0, nullable=False)
    unknown_count = Column(Integer, default=0, nullable=False)
    recognized_student_count = Column(Integer, default=0, nullable=False)
    emotion_summary = Column(Text, nullable=True)
    emotion_analyzed_count = Column(Integer, default=0, nullable=False)
    emotion_failed_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class GroupPhotoRecordStudent(Base):
    __tablename__ = "group_photo_record_students"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, index=True, nullable=False)
    teacher_id = Column(Integer, index=True, nullable=False)
    student_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=True)
    class_name = Column(String, nullable=True)
    major = Column(String, nullable=True)
    face_score = Column(Float, nullable=True)
    face_image_id = Column(Integer, nullable=True)
    face_template_id = Column(Integer, nullable=True)
    emotion = Column(String, nullable=True)
    emotion_confidence = Column(Float, nullable=True)
    emotion_error_code = Column(String, nullable=True)
    emotion_message = Column(Text, nullable=True)
    bbox = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
