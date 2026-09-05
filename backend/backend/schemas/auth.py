from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., examples=["teacher"])
    password: str = Field(..., examples=["123456"])


class TeacherCreate(BaseModel):
    username: str = Field(..., examples=["teacher2"])
    password: str = Field(..., examples=["123456"])
    full_name: str | None = Field(None, examples=["王老师"])

