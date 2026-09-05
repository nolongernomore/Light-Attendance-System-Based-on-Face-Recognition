from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.course import Course
from models.teacher import Teacher
from models.user import User
from schemas.auth import LoginRequest, TeacherCreate
from schemas.common import ok
from services.auth_service import (
    create_access_token,
    get_current_teacher_id,
    get_current_user,
    hash_password,
    require_teacher,
    serialize_user,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username, User.is_active == True).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user.last_login_at = datetime.now()
    db.commit()

    token = create_access_token(
        {
            "sub": user.username,
            "role": user.role,
            "teacher_id": user.teacher_id,
            "student_id": user.student_id,
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return ok(
        {
            "access_token": token,
            "token_type": "bearer",
            "user": serialize_user(user),
        },
        "Login success",
    )


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return ok(serialize_user(current_user), "Current user")


@router.post("/teachers")
def create_teacher(
    payload: TeacherCreate,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    teacher = Teacher(
        teacher_no=payload.username,
        name=payload.full_name or payload.username,
    )
    db.add(teacher)
    db.flush()

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role="teacher",
        full_name=payload.full_name,
        teacher_id=teacher.id,
        is_active=True,
    )
    db.add(user)
    db.flush()

    course = Course(
        course_name="Default Course",
        teacher_id=get_current_teacher_id(user),
        description="System default course",
        status="active",
    )
    db.add(course)
    db.commit()
    db.refresh(user)
    return ok(serialize_user(user), "Teacher created")
