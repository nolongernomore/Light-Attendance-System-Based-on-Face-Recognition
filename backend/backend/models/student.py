from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    class_name = Column(String, nullable=True)
    major = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    has_face_image = Column(Boolean, default=False, nullable=False)
    active_face_image_count = Column(Integer, default=0, nullable=False)
    latest_face_image_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    owner_teacher_id = Column(Integer, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
