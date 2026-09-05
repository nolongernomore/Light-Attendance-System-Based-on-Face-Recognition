from pydantic import BaseModel, Field


class AdminStudentListRequest(BaseModel):
    admin_password: str = Field(..., examples=["123456"])


class AdminStudentDeleteRequest(BaseModel):
    admin_password: str = Field(..., examples=["123456"])
    student_ids: list[str] = Field(default_factory=list, examples=[["20260001", "20260002"]])
    delete_all: bool = False
