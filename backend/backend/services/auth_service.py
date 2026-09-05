import base64
import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal, get_db
from models.course import Course
from models.student import Student
from models.teacher import Teacher
from models.user import User


bearer_scheme = HTTPBearer(auto_error=False)
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return "$".join(
        [
            PASSWORD_HASH_PREFIX,
            str(PASSWORD_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        prefix, iterations, salt_b64, digest_b64 = password_hash.split("$", 3)
        if prefix != PASSWORD_HASH_PREFIX:
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            int(iterations),
        )
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def get_current_teacher_id(user: User) -> int:
    return user.teacher_id or user.id


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
        "teacher_id": user.teacher_id,
        "student_id": user.student_id,
    }


def ensure_teacher_profile(
    db: Session,
    username: str,
    full_name: str | None = None,
) -> Teacher:
    teacher = db.query(Teacher).filter(Teacher.teacher_no == username).first()
    if teacher:
        if full_name and not teacher.name:
            teacher.name = full_name
        return teacher

    teacher = Teacher(
        teacher_no=username,
        name=full_name or username,
    )
    db.add(teacher)
    db.flush()
    return teacher


def create_student_account_if_missing(db: Session, student_id: str, name: str | None = None) -> User:
    user = db.query(User).filter(User.username == student_id).first()
    if user:
        if name and not user.full_name:
            user.full_name = name
        return user

    user = User(
        username=student_id,
        password_hash=hash_password(student_id),
        role="student",
        full_name=name,
        student_id=student_id,
        is_active=True,
    )
    db.add(user)
    return user


def ensure_default_users() -> None:
    db = SessionLocal()
    try:
        teacher_profile = ensure_teacher_profile(
            db,
            settings.DEFAULT_TEACHER_USERNAME,
            "Default Teacher",
        )

        teacher_user = (
            db.query(User)
            .filter(User.username == settings.DEFAULT_TEACHER_USERNAME)
            .first()
        )
        if not teacher_user:
            teacher_user = User(
                username=settings.DEFAULT_TEACHER_USERNAME,
                password_hash=hash_password(settings.DEFAULT_TEACHER_PASSWORD),
                role="teacher",
                full_name=teacher_profile.name,
                teacher_id=teacher_profile.id,
                is_active=True,
            )
            db.add(teacher_user)
            db.flush()
        elif not teacher_user.teacher_id:
            teacher_user.teacher_id = teacher_profile.id
            if not teacher_user.full_name:
                teacher_user.full_name = teacher_profile.name

        teacher_id = get_current_teacher_id(teacher_user)
        default_course = (
            db.query(Course)
            .filter(Course.teacher_id == teacher_id, Course.course_name == "Default Course")
            .first()
        )
        if not default_course:
            db.add(
                Course(
                    course_name="Default Course",
                    teacher_id=teacher_id,
                    description="System default course",
                    status="active",
                )
            )

        for student in db.query(Student).all():
            create_student_account_if_missing(db, student.student_id, student.name)
        db.commit()
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        token = credentials.credentials.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_teacher(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher account required")
    return current_user


def require_student(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Student account required")
    return current_user
