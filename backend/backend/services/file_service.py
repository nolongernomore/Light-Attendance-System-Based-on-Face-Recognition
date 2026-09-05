from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile


def build_upload_path(
    target_dir: Path,
    prefix: str,
    suffix: str,
    allowed_extensions: set[str] | None = None,
) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = suffix.lower() or ".bin"
    if allowed_extensions and suffix not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise HTTPException(status_code=400, detail=f"Unsupported file extension, allowed: {allowed}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}_{uuid4().hex[:8]}{suffix}"
    return target_dir / filename


def relative_upload_path(target_path: Path) -> str:
    return target_path.relative_to(target_path.parent.parent.parent).as_posix()


def save_upload_file(
    file: UploadFile,
    target_dir: Path,
    prefix: str,
    allowed_extensions: set[str] | None = None,
) -> str:
    suffix = Path(file.filename or "").suffix.lower() or ".bin"
    target_path = build_upload_path(target_dir, prefix, suffix, allowed_extensions)

    try:
        with target_path.open("wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                buffer.write(chunk)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"File save failed: {exc}") from exc
    finally:
        file.file.close()

    return relative_upload_path(target_path)


def save_bytes_file(
    content: bytes,
    target_dir: Path,
    prefix: str,
    suffix: str,
    allowed_extensions: set[str] | None = None,
) -> str:
    target_path = build_upload_path(target_dir, prefix, suffix, allowed_extensions)

    try:
        target_path.write_bytes(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"File save failed: {exc}") from exc

    return relative_upload_path(target_path)
