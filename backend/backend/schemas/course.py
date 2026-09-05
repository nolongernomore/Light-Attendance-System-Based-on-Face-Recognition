from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    course_name: str = Field(..., examples=["Content Security Lab"])
    term: str | None = None
    description: str | None = None


class CourseUpdate(BaseModel):
    course_name: str | None = None
    term: str | None = None
    description: str | None = None
    status: str | None = None


class CourseStudentAddRequest(BaseModel):
    student_ids: list[str] = Field(..., min_length=1, examples=[["20260001", "20260002"]])
