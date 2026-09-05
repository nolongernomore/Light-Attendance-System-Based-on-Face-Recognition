"""
face_service 冒烟测试 / 接口示例

直接运行: python -m service.face_service.demo_smoke_test
也可以当作 B 集成时的样例代码 copy-paste。

测试图片路径请改成本地真实路径; 默认在 service/face_service/test_images/ 下找。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from . import (
    enroll_student_faces,
    recognize_single_face,
    recognize_group_photo,
    draw_recognition_result,
    warmup,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

HERE = Path(__file__).parent
SAMPLE_DIR = HERE / "test_images"


def step_warmup():
    print("\n=== [0] 模型预热 ===")
    warmup()


def step_enroll():
    print("\n=== [1] 学生人脸注册 ===")
    enroll_imgs = sorted(SAMPLE_DIR.glob("2023302181059-安书达-网络空间安全-男.jpg"))
    if not enroll_imgs:
        print(f"⚠ 未找到注册样本, 请在 {SAMPLE_DIR} 放 zhangsan_*.jpg")
        return None
    res = enroll_student_faces("20260001", [str(p) for p in enroll_imgs])
    print(json.dumps({**res, "embeddings": f"<{len(res['embeddings'])} vectors>"},
                     ensure_ascii=False, indent=2))
    return res


def step_attendance(enroll_res):
    print("\n=== [2] 单人考勤识别 ===")
    test_img = SAMPLE_DIR / "1778341866442.jpg"
    if not test_img.exists():
        print(f"⚠ 未找到考勤样本: {test_img}")
        return
    if not enroll_res or not enroll_res["success"]:
        print("⚠ 未注册成功, 跳过考勤测试")
        return
    db = [{
        "student_id": "20260001",
        "name": "张三",
        "embeddings": enroll_res["embeddings"],
    }]
    res = recognize_single_face(str(test_img), db)
    print(json.dumps(res, ensure_ascii=False, indent=2))


def step_group(enroll_res):
    print("\n=== [3] 合照多人识别 ===")
    test_img = SAMPLE_DIR / "43B11B4EEE3F00F1B6A3B6A1BC9F9A33.jpg"
    if not test_img.exists():
        print(f"⚠ 未找到合照样本: {test_img}")
        return
    if not enroll_res or not enroll_res["success"]:
        print("⚠ 未注册成功, 仅做检测演示")
        db = []
    else:
        db = [{
            "student_id": "20260001",
            "name": "张三",
            "embeddings": enroll_res["embeddings"],
        }]
    res = recognize_group_photo(str(test_img), db)
    print(json.dumps({
        "success": res["success"],
        "total_faces": res["total_faces"],
        "matched_count": res["matched_count"],
        "unknown_count": res["unknown_count"],
        "annotated_image": res["annotated_image"],
        "faces": res["faces"][:3],   # 截取前 3 个, 避免输出太长
    }, ensure_ascii=False, indent=2))


def step_redraw():
    print("\n=== [4] 标注图重绘 (示例) ===")
    test_img = SAMPLE_DIR / "group.jpg"
    if not test_img.exists():
        return
    fake = [
        {"bbox": [50, 50, 200, 200], "matched": True,
         "name": "测试", "student_id": "00000001", "score": 0.88},
        {"bbox": [220, 60, 360, 200], "matched": False,
         "name": None, "student_id": None, "score": 0.21},
    ]
    out = draw_recognition_result(str(test_img), fake)
    print(f"已生成: {out}")


if __name__ == "__main__":
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    step_warmup()
    enroll_res = step_enroll()
    step_attendance(enroll_res)
    step_group(enroll_res)
    step_redraw()
