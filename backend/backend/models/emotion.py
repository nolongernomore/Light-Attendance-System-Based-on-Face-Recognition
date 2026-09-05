from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from database import Base


class EmotionRecord(Base):
    __tablename__ = "emotion_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, index=True, nullable=True)
    name = Column(String, nullable=True)
    course_id = Column(Integer, index=True, nullable=True)
    source_type = Column(String, nullable=False)
    source_id = Column(Integer, nullable=False)
    emotion = Column(String, nullable=False)
    confidence = Column(Float, nullable=True)
    record_time = Column(DateTime, default=datetime.now, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
