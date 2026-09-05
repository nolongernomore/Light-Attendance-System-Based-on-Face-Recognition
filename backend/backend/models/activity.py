from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text

from database import Base


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, index=True, nullable=True)
    teacher_id = Column(Integer, index=True, nullable=True)
    activity_name = Column(String, nullable=False)
    activity_date = Column(Date, default=date.today, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class GroupPhoto(Base):
    __tablename__ = "group_photos"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, index=True, nullable=False)
    photo_path = Column(String, nullable=False)
    annotated_image_path = Column(String, nullable=True)
    total_faces = Column(Integer, default=0, nullable=False)
    matched_count = Column(Integer, default=0, nullable=False)
    unknown_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class ActivityParticipant(Base):
    __tablename__ = "activity_participants"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, index=True, nullable=False)
    student_id = Column(String, index=True, nullable=True)
    name = Column(String, nullable=True)
    course_id = Column(Integer, index=True, nullable=True)
    teacher_id = Column(Integer, index=True, nullable=True)
    face_image_id = Column(Integer, nullable=True)
    face_template_id = Column(Integer, nullable=True)
    face_score = Column(Float, nullable=True)
    emotion = Column(String, nullable=True)
    bbox = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
