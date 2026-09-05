from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.photo_import_service import import_photos


def main() -> None:
    parser = argparse.ArgumentParser(description="批量导入以 学号-姓名-专业-性别 命名的学生照片库")
    parser.add_argument("folder", help="照片库文件夹路径")
    parser.add_argument("--teacher-id", type=int, default=None, help="所属教师用户ID")
    parser.add_argument("--dry-run", action="store_true", help="只预览解析结果，不写数据库、不复制文件")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        raise SystemExit(f"照片库文件夹不存在: {folder}")

    result = import_photos(
        folder,
        dry_run=args.dry_run,
        teacher_id=args.teacher_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
