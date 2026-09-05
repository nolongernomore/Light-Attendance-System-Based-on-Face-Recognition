"""
人脸识别业务层: 注册 / 单人考勤识别 / 合照识别 / 标注绘制
模块负责人: C

对外接口完全与方案一设计文档对齐:
    enroll_student_faces(student_id, image_paths) -> dict
    recognize_single_face(image_path, face_database) -> dict
    recognize_group_photo(image_path, face_database) -> dict
    draw_recognition_result(image_path, faces, save_path=None) -> str
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import numpy as np

from . import config
from . import utils
from .core_engine import get_engine

logger = logging.getLogger("face_service.recognition")


# ---------------------------------------------------------------------------
# 1. 学生人脸注册
# ---------------------------------------------------------------------------
def enroll_student_faces(student_id: str, image_paths: Sequence[str]) -> dict:
    """
    遍历学生上传的注册照, 提取每张图的人脸特征, 返回可入库的 embeddings。

    传入: image_paths - 通常是 3-5 张
    丢弃: 无人脸 / 多人脸 / 人脸过小 / 与其他注册图差异过大的照片

    返回示例:
        {
            "success": True,
            "student_id": "20260001",
            "valid_count": 4,
            "invalid_count": 1,
            "embeddings": [[0.12, ...], ...],   # 已 L2 归一化, 可直接入库
            "details": [
                {"path": "1.jpg", "ok": True,  "reason": null},
                {"path": "2.jpg", "ok": False, "reason": "NO_FACE"},
                ...
            ],
            "message": "人脸录入成功"
        }
    """
    engine = get_engine()
    results: list[dict] = []
    embeddings: list[np.ndarray] = []

    for path in image_paths:
        item = {"path": str(path), "ok": False, "reason": None}
        try:
            img = utils.load_image(path)
        except ValueError:
            item["reason"] = config.ERR_INVALID_IMAGE
            results.append(item)
            continue

        faces = engine.embed_image(
            img,
            detector_backend=config.DETECTOR_BACKEND_ENROLL,
            enforce_detection=True,
        )

        if not faces:
            item["reason"] = config.ERR_NO_FACE
            results.append(item)
            continue

        if len(faces) > 1:
            item["reason"] = config.ERR_MULTIPLE_FACE
            results.append(item)
            continue

        face = faces[0]
        if utils.bbox_size(face["bbox"]) < config.MIN_FACE_SIZE_SINGLE:
            item["reason"] = config.ERR_LOW_QUALITY
            results.append(item)
            continue

        emb = utils.l2_normalize(face["embedding"])
        embeddings.append(emb)
        item["ok"] = True
        results.append(item)

    # 自一致性检查: 注册图之间应当相互相似, 剔除离群点
    if len(embeddings) >= 3:
        keep_mask = _self_consistency_filter(embeddings)
        if not all(keep_mask):
            new_embs = []
            keep_iter = iter(keep_mask)
            for r in results:
                if r["ok"]:
                    keep = next(keep_iter)
                    if keep:
                        new_embs.append(embeddings[len(new_embs)])
                    else:
                        r["ok"] = False
                        r["reason"] = config.ERR_LOW_QUALITY
            embeddings = new_embs

    valid = len(embeddings)
    invalid = len(results) - valid
    success = valid >= config.ENROLL_MIN_VALID_IMAGES

    return {
        "success": success,
        "student_id": student_id,
        "valid_count": valid,
        "invalid_count": invalid,
        "embeddings": [utils.embedding_to_list(e) for e in embeddings],
        "details": results,
        "message": "人脸录入成功" if success else "有效人脸图不足, 请重新上传",
    }


def _self_consistency_filter(embeddings: list[np.ndarray]) -> list[bool]:
    """
    用每个 emb 到其他 emb 的平均相似度判断是否离群。
    平均相似度低于阈值的判为离群。
    """
    n = len(embeddings)
    keep = [True] * n
    if n < 3:
        return keep
    sims = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(i + 1, n):
            s = utils.cosine_similarity(embeddings[i], embeddings[j])
            sims[i, j] = sims[j, i] = s
    for i in range(n):
        avg = (sims[i].sum()) / (n - 1)
        if avg < config.ENROLL_SELF_CONSISTENCY:
            keep[i] = False
    # 至少留一张, 否则全部判错
    if not any(keep):
        keep[int(np.argmax(sims.sum(axis=1)))] = True
    return keep


# ---------------------------------------------------------------------------
# 2. 单人考勤识别
# ---------------------------------------------------------------------------
def recognize_single_face(image_path: str, face_database: Sequence[dict]) -> dict:
    """
    考勤场景: 输入单张人脸图, 在 face_database 中找最相似的学生。

    face_database 由 B 从数据库组装:
        [
            {"student_id": "20260001", "name": "张三", "embeddings": [[...], ...]},
            ...
        ]

    返回示例 (与设计文档对齐):
        {
            "matched": True,
            "student_id": "20260001",
            "name": "张三",
            "score": 0.76,
            "bbox": [120, 80, 180, 160],
            "error_code": null
        }
    """
    base = {
        "matched": False,
        "student_id": None,
        "name": None,
        "score": 0.0,
        "bbox": None,
        "error_code": None,
    }

    try:
        img = utils.load_image(image_path)
    except ValueError:
        base["error_code"] = config.ERR_INVALID_IMAGE
        return base

    engine = get_engine()
    faces = engine.embed_image(
        img,
        detector_backend=config.DETECTOR_BACKEND_SINGLE,
        enforce_detection=True,
    )

    if not faces:
        base["error_code"] = config.ERR_NO_FACE
        return base

    if len(faces) > 1:
        base["error_code"] = config.ERR_MULTIPLE_FACE
        # 多人时仍返回最大那张的 bbox, 方便前端提示
        biggest = max(faces, key=lambda f: utils.bbox_size(f["bbox"]))
        base["bbox"] = list(biggest["bbox"])
        return base

    face = faces[0]
    if utils.bbox_size(face["bbox"]) < config.MIN_FACE_SIZE_SINGLE:
        base["error_code"] = config.ERR_LOW_QUALITY
        base["bbox"] = list(face["bbox"])
        return base

    emb = utils.l2_normalize(face["embedding"])
    match = utils.best_match(emb, face_database, config.SINGLE_FACE_SIM_THRESHOLD)

    base["matched"] = match["matched"]
    base["student_id"] = match["student_id"]
    base["name"] = match["name"]
    base["score"] = match["score"]
    base["bbox"] = list(face["bbox"])
    base["error_code"] = match["error_code"]
    return base


# ---------------------------------------------------------------------------
# 3. 合照多人识别
# ---------------------------------------------------------------------------
def recognize_group_photo(image_path: str, face_database: Sequence[dict]) -> dict:
    """
    合照场景: 检测所有人脸, 逐个匹配学生, 输出名单 + 标注图。

    返回示例 (与设计文档对齐):
        {
            "success": True,
            "total_faces": 12,
            "matched_count": 10,
            "unknown_count": 2,
            "faces": [
                {"matched": True,  "student_id": "20260001", "name": "张三",
                 "score": 0.76, "bbox": [120, 80, 180, 160]},
                ...
            ],
            "annotated_image": "data/annotated/annot_xxx.jpg",
            "error_code": null
        }
    """
    out = {
        "success": False,
        "total_faces": 0,
        "matched_count": 0,
        "unknown_count": 0,
        "faces": [],
        "annotated_image": None,
        "error_code": None,
    }

    try:
        img = utils.load_image(image_path)
    except ValueError:
        out["error_code"] = config.ERR_INVALID_IMAGE
        return out

    engine = get_engine()

    # 第 1 步: 检测所有人脸
    detections = engine.detect_faces(img, detector_backend=config.DETECTOR_BACKEND_GROUP)

    # 过滤过小人脸
    detections = [d for d in detections if utils.bbox_size(d["bbox"]) >= config.MIN_FACE_SIZE_GROUP]

    if not detections:
        out["error_code"] = config.ERR_NO_FACE
        # 即便没识别到人脸也保存原图作为标注图, 方便排查
        out["annotated_image"] = _save_annotated(img, [], prefix="group")
        return out

    # 第 2 步: 逐个人脸提特征 + 匹配
    face_results: list[dict] = []
    for det in detections:
        crop = utils.crop_face(img, det["bbox"])
        if crop.size == 0:
            continue
        emb = engine.embed_face_patch(crop)
        if emb is None:
            continue
        emb = utils.l2_normalize(emb)
        match = utils.best_match(emb, face_database, config.GROUP_FACE_SIM_THRESHOLD)
        face_results.append({
            "matched": match["matched"],
            "student_id": match["student_id"],
            "name": match["name"],
            "score": match["score"],
            "bbox": list(det["bbox"]),
        })

    # 同一学生出现多次时只保留 score 最高那次, 防止把同一人识别成"参与了 N 次"
    face_results = _dedupe_by_student(face_results)

    matched_count = sum(1 for f in face_results if f["matched"])
    unknown_count = len(face_results) - matched_count

    # 第 3 步: 画标注图
    annot_path = _save_annotated(img, face_results, prefix="group")

    out.update({
        "success": True,
        "total_faces": len(face_results),
        "matched_count": matched_count,
        "unknown_count": unknown_count,
        "faces": face_results,
        "annotated_image": annot_path,
    })
    return out


def _dedupe_by_student(faces: list[dict]) -> list[dict]:
    """
    合照里同一学号被识别成多张人脸 (识别错误) 时, 只保留 score 最高那张, 其余降级为 unknown。
    避免活动参与统计被刷高。
    """
    best_for: dict[str, int] = {}      # student_id -> idx
    for i, f in enumerate(faces):
        if not f["matched"]:
            continue
        sid = f["student_id"]
        if sid not in best_for or faces[best_for[sid]]["score"] < f["score"]:
            best_for[sid] = i

    keep_idx = set(best_for.values())
    out = []
    for i, f in enumerate(faces):
        if f["matched"] and i not in keep_idx:
            out.append({
                **f,
                "matched": False,
                "student_id": None,
                "name": None,
                "error_code": config.ERR_UNKNOWN_FACE,
            })
        else:
            out.append(f)
    return out


# ---------------------------------------------------------------------------
# 4. 标注图生成 (供 B/A 单独调用)
# ---------------------------------------------------------------------------
def draw_recognition_result(
    image_path: str,
    faces: list[dict],
    save_path: str | None = None,
) -> str:
    """
    根据已有的识别结果重画一张标注图。
    用于 B 想要把数据库里历史合照重新生成预览图的场景。
    """
    img = utils.load_image(image_path)
    annotated = utils.draw_face_boxes(img, faces)
    target = Path(save_path) if save_path else utils.make_annotated_path("annot")
    utils.imwrite_unicode(target, annotated)
    return str(target)


def _save_annotated(img: np.ndarray, faces: list[dict], prefix: str) -> str:
    annotated = utils.draw_face_boxes(img, faces) if faces else img.copy()
    target = utils.make_annotated_path(prefix)
    utils.imwrite_unicode(target, annotated)
    return str(target)
