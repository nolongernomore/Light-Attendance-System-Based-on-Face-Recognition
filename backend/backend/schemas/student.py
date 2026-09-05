from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    student_id: str = Field(..., examples=["20260001"])
    name: str = Field(..., examples=["Zhang San"])
    class_name: str | None = Field(None, examples=["Class 1"])
    major: str | None = None
    gender: str | None = None
    phone: str | None = None
    email: str | None = None


class StudentUpdate(BaseModel):
    name: str | None = None
    class_name: str | None = None
    major: str | None = None
    gender: str | None = None
    phone: str | None = None
    email: str | None = None
