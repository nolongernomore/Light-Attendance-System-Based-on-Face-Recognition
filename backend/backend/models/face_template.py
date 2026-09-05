from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from database import Base


class FaceTemplate(Base):
    __tablename__ = "face_templates"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, index=True, nullable=False)
    face_image_id = Column(Integer, index=True, nullable=True)
    image_path = Column(String, nullable=False)
    embedding = Column(Text, nullable=True)
    algorithm = Column(String, default="mock", nullable=False)
    algorithm_version = Column(String, default="v1", nullable=False)
    quality_score = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
