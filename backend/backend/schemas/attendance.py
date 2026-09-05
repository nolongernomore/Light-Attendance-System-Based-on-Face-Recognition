from pydantic import BaseModel, Field


class AttendanceSessionCreate(BaseModel):
    course_id: int | None = Field(None, examples=[1])
    title: str | None = Field(None, examples=["第1次课堂考勤"])
