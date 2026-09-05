from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from database import Base


class StudentFaceImage(Base):
    __tablename__ = "student_face_images"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, index=True, nullable=False)
    file_path = Column(String, nullable=False)
    file_hash = Column(String, index=True, nullable=True)
    original_filename = Column(String, nullable=True)
    source = Column(String, nullable=False)
    uploaded_by_role = Column(String, nullable=False)
    uploaded_by_id = Column(Integer, nullable=True)
    quality_score = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, index=True, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
