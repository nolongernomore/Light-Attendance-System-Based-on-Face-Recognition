from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    course_name = Column(String, nullable=False)
    teacher_id = Column(Integer, index=True, nullable=False)
    term = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="active", index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class CourseStudent(Base):
    __tablename__ = "course_students"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, index=True, nullable=False)
    student_id = Column(String, index=True, nullable=False)
    enroll_status = Column(String, default="active", index=True, nullable=False)
    source = Column(String, default="manual", nullable=False)
    added_by_teacher_id = Column(Integer, index=True, nullable=True)
    joined_at = Column(DateTime, default=datetime.now, nullable=False)
    removed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


Index(
    "ux_course_students_active_course_student",
    CourseStudent.course_id,
    CourseStudent.student_id,
    unique=True,
    sqlite_where=CourseStudent.enroll_status == "active",
)
