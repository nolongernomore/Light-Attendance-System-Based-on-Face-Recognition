import os
from pathlib import Path


class Settings:
    APP_NAME = "内容安全班级考勤系统后端"
    API_PREFIX = "/api"
    DATABASE_URL = "sqlite:///./attendance.db"
    SECRET_KEY = "change-this-secret-key-before-production"
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8
    DEFAULT_TEACHER_USERNAME = "teacher"
    DEFAULT_TEACHER_PASSWORD = "123456"
    CHECKIN_FACE_TIMEOUT_SECONDS = float(os.environ.get("CHECKIN_FACE_TIMEOUT_SECONDS", "30"))

    BASE_DIR = Path(__file__).resolve().parent
    UPLOAD_DIR = BASE_DIR / "uploads"
    ENROLL_DIR = UPLOAD_DIR / "enroll"
    CHECKIN_DIR = UPLOAD_DIR / "checkin"
    FACES_DIR = UPLOAD_DIR / "faces"
    GROUP_PHOTOS_DIR = UPLOAD_DIR / "group_photos"
    RESULTS_DIR = UPLOAD_DIR / "results"
    EXPORTS_DIR = UPLOAD_DIR / "exports"

    ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


settings = Settings()


def ensure_upload_dirs() -> None:
    for path in [
        settings.ENROLL_DIR,
        settings.CHECKIN_DIR,
        settings.FACES_DIR,
        settings.GROUP_PHOTOS_DIR,
        settings.RESULTS_DIR,
        settings.EXPORTS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
