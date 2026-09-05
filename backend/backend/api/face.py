import base64
import mimetypes
from pathlib import Path, PurePosixPath
from time import perf_counter
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.face_image import StudentFaceImage
from models.face_template import FaceTemplate
from models.student import Student
from models.user import User
from schemas.common import ok
from services.auth_service import (
    create_student_account_if_missing,
    get_current_user,
    require_student,
    require_teacher,
)
from services.db_service import serialize_template_diagnostic
from services.face_image_service import create_face_image_with_template, deactivate_face_image
from services.face_service import (
    enroll_student_faces,
    get_face_algorithm_metadata,
    get_face_service_status,
)
from services.file_service import save_bytes_file, save_upload_file


router = APIRouter(prefix="/face", tags=["face"])
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
BATCH_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
ZIP_EXTENSIONS = {".zip"}
MAX_ZIP_FILE_COUNT = 1000
MAX_ZIP_IMAGE_BYTES = 10 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 500 * 1024 * 1024
SKIP_ZIP_FILENAMES = {".ds_store", "thumbs.db"}


def face_image_file_url(image_id: int | None) -> str | None:
    return f"{settings.API_PREFIX}/face/images/{image_id}/file" if image_id else None


def serialize_face_image(image: StudentFaceImage, include_data: bool = False) -> dict:
    static_url = f"/{image.file_path}" if image.file_path else None
    api_url = face_image_file_url(image.id)
    data = {
        "id": image.id,
        "student_id": image.student_id,
        "file_path": image.file_path,
        "url": static_url,
        "static_url": static_url,
        "api_url": api_url,
        "file_url": api_url,
        "source": image.source,
        "quality_score": image.quality_score,
        "is_active": image.is_active,
        "created_at": image.created_at.isoformat() if image.created_at else None,
        "deleted_at": image.deleted_at.isoformat() if image.deleted_at else None,
    }
    if include_data:
        data.update(face_image_data_payload(image))
    return data


def active_images(db: Session, student_id: str) -> list[StudentFaceImage]:
    return (
        db.query(StudentFaceImage)
        .filter(StudentFaceImage.student_id == student_id, StudentFaceImage.is_active == True)
        .order_by(StudentFaceImage.created_at.desc(), StudentFaceImage.id.desc())
        .all()
    )


def latest_active_image(db: Session, student_id: str) -> StudentFaceImage | None:
    images = active_images(db, student_id)
    return images[0] if images else None


def student_exists(db: Session, student_id: str) -> bool:
    return (
        db.query(Student)
        .filter(Student.student_id == student_id, Student.is_active == True)
        .first()
        is not None
    )


def authorize_student_image_access(db: Session, current_user: User, student_id: str) -> None:
    if current_user.role == "student" and current_user.student_id == student_id:
        return
    if current_user.role == "teacher" and student_exists(db, student_id):
        return
    raise HTTPException(status_code=403, detail="No permission to view this face image")


def authorize_face_image_access(db: Session, current_user: User, image: StudentFaceImage) -> None:
    authorize_student_image_access(db, current_user, image.student_id)


def resolve_face_image_file(image: StudentFaceImage) -> Path:
    stored_path = Path(image.file_path)
    path = stored_path if stored_path.is_absolute() else settings.BASE_DIR / stored_path
    try:
        resolved = path.resolve()
        resolved.relative_to(settings.UPLOAD_DIR.resolve())
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Face image file path is invalid") from exc
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="Face image file not found")
    return resolved


def face_image_file_response(image: StudentFaceImage) -> FileResponse:
    path = resolve_face_image_file(image)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=60"},
    )


def face_image_data_payload(image: StudentFaceImage) -> dict:
    path = resolve_face_image_file(image)
    media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "content_type": media_type,
        "base64": encoded,
        "data_url": f"data:{media_type};base64,{encoded}",
    }


def select_upload_file(*files: UploadFile | None) -> UploadFile:
    for upload in files:
        if upload is not None and upload.filename:
            return upload
    raise HTTPException(
        status_code=400,
        detail="Face image file is required; use multipart field file/image/photo/face_image",
    )


def resolve_enroll_student_id(*values: str | None) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    raise HTTPException(
        status_code=400,
        detail="student_id is required; use form field student_id/student_no/studentId",
    )


def face_enrollment_failure_detail(result: dict) -> str:
    details = result.get("details") or []
    reasons: list[str] = []
    for item in details:
        reason = item.get("reason") if isinstance(item, dict) else None
        if reason and reason not in reasons:
            reasons.append(reason)

    code = result.get("error_code") or (reasons[0] if reasons else None)
    message = result.get("message") or "Face enrollment failed"
    if code and str(code) not in str(message):
        message = f"{message} ({code})"
    if reasons:
        message = f"{message}; details: {', '.join(reasons)}"
    return message


def face_diagnostics_payload(db: Session, student_id: str) -> dict:
    student = db.query(Student).filter(Student.student_id == student_id).first()
    images = active_images(db, student_id)
    latest_image = images[0] if images else None
    templates = (
        db.query(FaceTemplate)
        .filter(FaceTemplate.student_id == student_id, FaceTemplate.is_active == True)
        .order_by(FaceTemplate.created_at.desc(), FaceTemplate.id.desc())
        .all()
    )
    service_status = get_face_service_status()
    expected_dim = service_status.get("expected_embedding_dim")
    template_diagnostics = [serialize_template_diagnostic(template) for template in templates]
    for item in template_diagnostics:
        item["compatible_with_current_service"] = (
            expected_dim is None or item["embedding_dimension"] == expected_dim
        )

    return {
        "student_id": student_id,
        "student_exists": student is not None,
        "student_name": student.name if student else None,
        "has_face_image": student.has_face_image if student else bool(images),
        "active_face_image_count": len(images),
        "latest_face_image": serialize_face_image(latest_image) if latest_image else None,
        "active_template_count": len(templates),
        "templates": template_diagnostics,
        "face_service": service_status,
    }


@router.get("/service-status")
def face_service_status(
    current_user: User = Depends(require_teacher),
):
    return ok(get_face_service_status(), "Face service status")


@router.get("/diagnostics/{student_id}")
def face_diagnostics(
    student_id: str,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    authorize_student_image_access(db, current_user, student_id)
    return ok(face_diagnostics_payload(db, student_id), "Face diagnostics")


@router.get("/my-diagnostics")
def my_face_diagnostics(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return ok(face_diagnostics_payload(db, current_user.student_id), "My face diagnostics")


def parse_photo_filename(filename: str) -> dict | None:
    stem = Path(filename).stem
    parts = [part.strip() for part in stem.replace("_", "-").split("-") if part.strip()]
    if len(parts) != 4:
        return None
    return {
        "student_id": parts[0],
        "name": parts[1],
        "major": parts[2],
        "gender": parts[3],
    }


def detect_image_suffix_from_header(header: bytes) -> str | None:
    if not header:
        return None
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"BM"):
        return ".bmp"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return ".webp"
    return None


def decode_zip_member_name(name: str) -> str:
    try:
        return name.encode("cp437").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def zip_member_display_name(member_name: str) -> tuple[str, str]:
    decoded = decode_zip_member_name(member_name).replace("\\", "/")
    filename = PurePosixPath(decoded).name
    return decoded, filename


def is_skipped_zip_member(member_name: str, filename: str) -> bool:
    lowered_name = member_name.replace("\\", "/").lower()
    lowered_filename = filename.lower()
    return (
        not filename
        or lowered_filename in SKIP_ZIP_FILENAMES
        or lowered_name.startswith("__macosx/")
    )


def validate_zip_member(zip_file: ZipFile, member) -> tuple[dict | None, dict | None]:
    zip_path, filename = zip_member_display_name(member.filename)
    if member.is_dir() or is_skipped_zip_member(zip_path, filename):
        return None, None

    parts = [part for part in zip_path.split("/") if part]
    if ".." in parts or zip_path.startswith("/"):
        return None, {
            "filename": filename,
            "zip_path": zip_path,
            "reason": "unsafe zip entry path",
        }

    suffix = Path(filename).suffix.lower()
    if suffix not in BATCH_IMAGE_EXTENSIONS:
        return None, {
            "filename": filename,
            "zip_path": zip_path,
            "reason": f"unsupported extension, allowed: {sorted(BATCH_IMAGE_EXTENSIONS)}",
        }

    info = parse_photo_filename(filename)
    if not info:
        return None, {
            "filename": filename,
            "zip_path": zip_path,
            "reason": "filename must be exactly student_id-name-major-gender.ext",
        }

    if member.flag_bits & 0x1:
        return None, {
            "filename": filename,
            "zip_path": zip_path,
            "student_id": info["student_id"],
            "reason": "encrypted zip entry is not supported",
        }

    if member.file_size <= 0:
        return None, {
            "filename": filename,
            "zip_path": zip_path,
            "student_id": info["student_id"],
            "reason": "empty file",
        }

    if member.file_size > MAX_ZIP_IMAGE_BYTES:
        return None, {
            "filename": filename,
            "zip_path": zip_path,
            "student_id": info["student_id"],
            "reason": f"image is too large, max {MAX_ZIP_IMAGE_BYTES // 1024 // 1024}MB",
        }

    try:
        with zip_file.open(member) as member_file:
            header = member_file.read(32)
    except (BadZipFile, RuntimeError, OSError) as exc:
        return None, {
            "filename": filename,
            "zip_path": zip_path,
            "student_id": info["student_id"],
            "reason": f"cannot read zip entry: {exc}",
        }

    detected_suffix = detect_image_suffix_from_header(header)
    if not detected_suffix:
        return None, {
            "filename": filename,
            "zip_path": zip_path,
            "student_id": info["student_id"],
            "reason": "file content is not a supported image",
        }

    info.update(
        {
            "filename": filename,
            "zip_path": zip_path,
            "suffix": detected_suffix,
            "original_suffix": suffix,
            "detected_suffix": detected_suffix,
            "extension_mismatch": suffix != detected_suffix and not (suffix == ".jpeg" and detected_suffix == ".jpg"),
            "file_size": member.file_size,
            "member": member,
        }
    )
    return info, None


def collect_zip_images(zip_file: ZipFile) -> tuple[list[dict], list[dict], int]:
    valid_entries: list[dict] = []
    failed_files: list[dict] = []
    received_file_count = 0
    total_uncompressed_size = 0

    for member in zip_file.infolist():
        zip_path, filename = zip_member_display_name(member.filename)
        if member.is_dir() or is_skipped_zip_member(zip_path, filename):
            continue

        received_file_count += 1
        if received_file_count > MAX_ZIP_FILE_COUNT:
            raise HTTPException(status_code=400, detail=f"Too many files in zip, max {MAX_ZIP_FILE_COUNT}")

        total_uncompressed_size += member.file_size
        if total_uncompressed_size > MAX_ZIP_TOTAL_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Zip uncompressed size is too large, max {MAX_ZIP_TOTAL_BYTES // 1024 // 1024}MB",
            )

        info, error = validate_zip_member(zip_file, member)
        if error:
            failed_files.append(error)
        elif info:
            valid_entries.append(info)

    return valid_entries, failed_files, received_file_count


def select_latest_entry_per_student(valid_entries: list[dict]) -> tuple[list[dict], int]:
    selected: dict[str, dict] = {}
    for info in valid_entries:
        selected[info["student_id"]] = info
    return list(selected.values()), len(valid_entries) - len(selected)


def has_compatible_active_template(db: Session, student_id: str, face_metadata: dict, expected_dim: int | None) -> bool:
    templates = (
        db.query(FaceTemplate)
        .filter(FaceTemplate.student_id == student_id, FaceTemplate.is_active == True)
        .all()
    )
    for template in templates:
        diagnostic = serialize_template_diagnostic(template)
        if template.algorithm != face_metadata["algorithm"]:
            continue
        if expected_dim is not None and diagnostic["embedding_dimension"] != expected_dim:
            continue
        return True
    return False


def upsert_student_for_image(
    db: Session,
    info: dict,
    owner_teacher_id: int | None = None,
) -> tuple[Student, bool]:
    student_id = info["student_id"]
    student = db.query(Student).filter(Student.student_id == student_id).first()
    created = False
    if student:
        student.name = info["name"]
        student.class_name = info["major"] or student.class_name
        student.major = info["major"] or student.major
        student.gender = info["gender"] or student.gender
        student.owner_teacher_id = student.owner_teacher_id or owner_teacher_id
        student.is_active = True
    else:
        student = Student(
            student_id=student_id,
            name=info["name"],
            class_name=info["major"],
            major=info["major"],
            gender=info["gender"],
            owner_teacher_id=owner_teacher_id,
            is_active=True,
        )
        db.add(student)
        created = True

    create_student_account_if_missing(db, student_id, info["name"])
    db.flush()
    return student, created


def process_zip_import(
    zip_file: ZipFile,
    zip_filename: str,
    dry_run: bool,
    db: Session,
    owner_teacher_id: int | None = None,
    uploaded_by_role: str = "admin",
    uploaded_by_id: int | None = None,
    source: str = "admin_batch_upload",
) -> dict:
    valid_entries, failed_files, received_file_count = collect_zip_images(zip_file)
    process_entries, skipped_duplicate_file_count = select_latest_entry_per_student(valid_entries)

    preview_students: dict[str, dict] = {}
    for info in valid_entries:
        item = preview_students.setdefault(
            info["student_id"],
            {
                "student_id": info["student_id"],
                "name": info["name"],
                "major": info["major"],
                "gender": info["gender"],
                "photo_count": 0,
            },
        )
        item["photo_count"] += 1

    result = {
        "zip_filename": zip_filename,
        "received_file_count": received_file_count,
        "valid_file_count": len(valid_entries),
        "failed_file_count": len(failed_files),
        "failed_files": failed_files,
        "preview_students": list(preview_students.values()),
        "selected_file_count": len(process_entries),
        "skipped_duplicate_file_count": skipped_duplicate_file_count,
        "dry_run": dry_run,
    }

    if dry_run:
        result.update(
            {
                "success_student_count": 0,
                "success_students": [],
                "created_image_count": 0,
                "processed_file_count": 0,
            }
        )
        return result

    created_students = 0
    updated_students: set[str] = set()
    created_images = 0
    processed_files = 0
    skipped_existing_compatible = 0
    success_students: dict[str, dict] = {}
    face_metadata = get_face_algorithm_metadata()
    service_status = get_face_service_status()
    expected_dim = service_status.get("expected_embedding_dim")
    started_at = perf_counter()

    for info in process_entries:
        student_id = info["student_id"]
        filename = info["filename"]
        file_started_at = perf_counter()
        try:
            if has_compatible_active_template(db, student_id, face_metadata, expected_dim):
                skipped_existing_compatible += 1
                continue

            image_bytes = zip_file.read(info["member"])
            image_path = save_bytes_file(
                image_bytes,
                settings.ENROLL_DIR,
                f"student_{student_id}",
                info["suffix"],
                BATCH_IMAGE_EXTENSIONS,
            )
            enroll_result = enroll_student_faces(student_id, [image_path])
            if not enroll_result.get("success"):
                failed_files.append(
                    {
                        "filename": filename,
                        "zip_path": info["zip_path"],
                        "student_id": student_id,
                        "reason": enroll_result.get("error_code") or "face enrollment failed",
                    }
                )
                continue

            embeddings = enroll_result.get("embeddings", [])
            embedding = embeddings[-1] if embeddings else []
            student, created = upsert_student_for_image(db, info, owner_teacher_id)
            create_face_image_with_template(
                db=db,
                student_id=student_id,
                image_path=image_path,
                embedding=embedding,
                source=source,
                uploaded_by_role=uploaded_by_role,
                uploaded_by_id=uploaded_by_id,
                original_filename=filename,
                quality_score=0.9,
                algorithm=face_metadata["algorithm"],
                algorithm_version=face_metadata["algorithm_version"],
            )
            db.commit()
            if created:
                created_students += 1
            else:
                updated_students.add(student.student_id)
            created_images += 1
            processed_files += 1

            success_students.setdefault(
                student_id,
                {
                    "student_id": student_id,
                    "name": info["name"],
                },
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            failed_files.append(
                {
                    "filename": filename,
                    "zip_path": info["zip_path"],
                    "student_id": student_id,
                    "reason": str(exc),
                    "elapsed_seconds": round(perf_counter() - file_started_at, 3),
                }
            )

    success_student_list = list(success_students.values())
    result.update(
        {
            "valid_file_count": len(valid_entries),
            "failed_file_count": len(failed_files),
            "failed_files": failed_files,
            "success_student_count": len(success_student_list),
            "success_students": success_student_list,
            "created_student_count": created_students,
            "updated_student_count": len(updated_students),
            "created_image_count": created_images,
            "processed_file_count": processed_files,
            "skipped_existing_compatible_count": skipped_existing_compatible,
            "elapsed_seconds": round(perf_counter() - started_at, 3),
        }
    )
    return result


@router.post("/enroll")
def enroll_face(
    student_id: str | None = Form(None),
    student_no: str | None = Form(None),
    student_id_camel: str | None = Form(None, alias="studentId"),
    student_no_camel: str | None = Form(None, alias="studentNo"),
    file: UploadFile | None = File(None),
    image: UploadFile | None = File(None),
    photo: UploadFile | None = File(None),
    face_image: UploadFile | None = File(None),
    face_image_camel: UploadFile | None = File(None, alias="faceImage"),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student_id = resolve_enroll_student_id(student_id, student_no, student_id_camel, student_no_camel)
    upload = select_upload_file(file, image, photo, face_image, face_image_camel)
    student = db.query(Student).filter(Student.student_id == student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    original_filename = upload.filename
    image_path = save_upload_file(upload, settings.ENROLL_DIR, f"student_{student_id}", IMAGE_EXTENSIONS)
    result = enroll_student_faces(student_id, [image_path])
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=face_enrollment_failure_detail(result))

    embeddings = result.get("embeddings", [])
    if not embeddings:
        raise HTTPException(status_code=400, detail="Face enrollment produced no embedding")
    embedding = embeddings[-1]
    face_metadata = get_face_algorithm_metadata()
    face_image, template = create_face_image_with_template(
        db=db,
        student_id=student_id,
        image_path=image_path,
        embedding=embedding,
        source="teacher_upload",
        uploaded_by_role="teacher",
        uploaded_by_id=current_user.teacher_id or current_user.id,
        original_filename=original_filename,
        quality_score=0.9,
        algorithm=face_metadata["algorithm"],
        algorithm_version=face_metadata["algorithm_version"],
    )
    db.commit()
    return ok(
        {
            "student_id": student_id,
            "image": serialize_face_image(face_image),
            "template_id": template.id,
            "algorithm_result": result,
        },
        "Face image enrolled",
    )


@router.get("/status/{student_id}")
def face_status(
    student_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    authorize_student_image_access(db, current_user, student_id)
    student = db.query(Student).filter(Student.student_id == student_id).first()
    images = active_images(db, student_id)
    latest = images[0] if images else None
    return ok(
        {
            "student_id": student_id,
            "enrolled": bool(images),
            "has_face_image": student.has_face_image if student else bool(images),
            "active_face_image_count": len(images),
            "latest_face_image_id": latest.id if latest else None,
            "image_path": latest.file_path if latest else None,
            "url": f"/{latest.file_path}" if latest else None,
            "static_url": f"/{latest.file_path}" if latest else None,
            "api_url": face_image_file_url(latest.id if latest else None),
            "file_url": face_image_file_url(latest.id if latest else None),
            "created_at": latest.created_at.isoformat() if latest else None,
        },
        "Face status",
    )


@router.get("/students/{student_id}/images")
def student_face_images(
    student_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    authorize_student_image_access(db, current_user, student_id)
    return ok([serialize_face_image(image, include_data=True) for image in active_images(db, student_id)], "Student face images")


@router.get("/students/{student_id}/image")
def student_latest_face_image(
    student_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    authorize_student_image_access(db, current_user, student_id)
    image = latest_active_image(db, student_id)
    return ok(
        {
            "student_id": student_id,
            "has_image": image is not None,
            "image": serialize_face_image(image, include_data=True) if image else None,
        },
        "Student latest face image",
    )


@router.get("/students/{student_id}/image/file")
def student_latest_face_image_file(
    student_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    authorize_student_image_access(db, current_user, student_id)
    image = latest_active_image(db, student_id)
    if not image:
        raise HTTPException(status_code=404, detail="Face image not found")
    return face_image_file_response(image)


@router.get("/images/{image_id}/file")
def face_image_file(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    image = (
        db.query(StudentFaceImage)
        .filter(StudentFaceImage.id == image_id, StudentFaceImage.is_active == True)
        .first()
    )
    if not image:
        raise HTTPException(status_code=404, detail="Face image not found")
    authorize_face_image_access(db, current_user, image)
    return face_image_file_response(image)


@router.post("/enroll-me")
def enroll_my_face(
    file: UploadFile | None = File(None),
    image: UploadFile | None = File(None),
    photo: UploadFile | None = File(None),
    face_image: UploadFile | None = File(None),
    face_image_camel: UploadFile | None = File(None, alias="faceImage"),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    student_id = current_user.student_id
    if not student_id:
        raise HTTPException(status_code=400, detail="Current account is not linked to a student")
    upload = select_upload_file(file, image, photo, face_image, face_image_camel)

    student = db.query(Student).filter(Student.student_id == student_id, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    original_filename = upload.filename
    image_path = save_upload_file(upload, settings.ENROLL_DIR, f"student_{student_id}", IMAGE_EXTENSIONS)
    result = enroll_student_faces(student_id, [image_path])
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=face_enrollment_failure_detail(result))

    embeddings = result.get("embeddings", [])
    if not embeddings:
        raise HTTPException(status_code=400, detail="Face enrollment produced no embedding")
    embedding = embeddings[-1]
    face_metadata = get_face_algorithm_metadata()
    face_image, template = create_face_image_with_template(
        db=db,
        student_id=student_id,
        image_path=image_path,
        embedding=embedding,
        source="student_upload",
        uploaded_by_role="student",
        uploaded_by_id=current_user.id,
        original_filename=original_filename,
        quality_score=0.9,
        algorithm=face_metadata["algorithm"],
        algorithm_version=face_metadata["algorithm_version"],
    )
    db.commit()
    return ok(
        {
            "student_id": student_id,
            "name": student.name,
            "image": serialize_face_image(face_image),
            "template_id": template.id,
            "algorithm_result": result,
        },
        "My face image enrolled",
    )


@router.get("/my-status")
def my_face_status(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    student_id = current_user.student_id
    student = db.query(Student).filter(Student.student_id == student_id).first()
    images = active_images(db, student_id)
    latest = images[0] if images else None
    return ok(
        {
            "student_id": student_id,
            "has_face_image": student.has_face_image if student else bool(images),
            "active_face_image_count": len(images),
            "latest_face_image_id": latest.id if latest else None,
            "latest_image_path": latest.file_path if latest else None,
            "url": f"/{latest.file_path}" if latest else None,
            "static_url": f"/{latest.file_path}" if latest else None,
            "api_url": face_image_file_url(latest.id if latest else None),
            "file_url": face_image_file_url(latest.id if latest else None),
        },
        "My face status",
    )


@router.get("/my-image")
def my_face_image(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    latest = latest_active_image(db, current_user.student_id)
    return ok(
        {
            "student_id": current_user.student_id,
            "has_image": latest is not None,
            "image": serialize_face_image(latest, include_data=True) if latest else None,
        },
        "My latest face image",
    )


@router.get("/my-image/file")
def my_face_image_file(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    image = latest_active_image(db, current_user.student_id)
    if not image:
        raise HTTPException(status_code=404, detail="Face image not found")
    return face_image_file_response(image)


@router.get("/my-images")
def my_face_images(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    images = active_images(db, current_user.student_id)
    return ok([serialize_face_image(image, include_data=True) for image in images], "My face images")


@router.delete("/my-images/{image_id}")
def delete_my_face_image(
    image_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    image = (
        db.query(StudentFaceImage)
        .filter(
            StudentFaceImage.id == image_id,
            StudentFaceImage.student_id == current_user.student_id,
            StudentFaceImage.is_active == True,
        )
        .first()
    )
    if not image:
        raise HTTPException(status_code=404, detail="Face image not found")

    deactivate_face_image(db, image)
    db.commit()
    return ok({"image_id": image_id, "student_id": current_user.student_id}, "Face image deleted")
