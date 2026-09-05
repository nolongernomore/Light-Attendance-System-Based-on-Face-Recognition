"""
工具函数: 图像 IO、相似度计算、bbox 处理、中文绘图
模块负责人: C
"""
from __future__ import annotations

import base64
import time
import uuid
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import config


# ---------------------------------------------------------------------------
# 图像 IO
# ---------------------------------------------------------------------------
def imread_unicode(path: str | Path) -> np.ndarray | None:
    """
    cv2.imread 在 Windows 下遇中文路径会返回 None, 这里走 numpy 兜底。
    返回 BGR ndarray, 失败返回 None。
    """
    p = str(path)
    try:
        with open(p, "rb") as f:
            buf = np.frombuffer(f.read(), dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except (OSError, ValueError):
        return None


def imwrite_unicode(path: str | Path, img: np.ndarray) -> bool:
    """中文路径安全的 imwrite。"""
    p = str(path)
    ext = Path(p).suffix or ".jpg"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        return False
    try:
        with open(p, "wb") as f:
            f.write(buf.tobytes())
        return True
    except OSError:
        return False


def shrink_if_too_large(img: np.ndarray, max_side: int = config.MAX_IMAGE_SIDE) -> np.ndarray:
    """长边超 max_side 时等比缩放, 防止 GPU 显存爆掉。"""
    h, w = img.shape[:2]
    side = max(h, w)
    if side <= max_side:
        return img
    scale = max_side / side
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def load_image(path: str | Path) -> np.ndarray:
    """读图 + 缩放, 失败抛 ValueError。"""
    img = imread_unicode(path)
    if img is None:
        raise ValueError(f"无法读取图片: {path}")
    return shrink_if_too_large(img)


# ---------------------------------------------------------------------------
# 相似度
# ---------------------------------------------------------------------------
def l2_normalize(vec: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(vec)
    if n < 1e-12:
        return vec
    return vec / n


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32).ravel()
    b = np.asarray(b, dtype=np.float32).ravel()
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def best_match(
    embedding: np.ndarray,
    database: Sequence[dict],
    threshold: float,
) -> dict:
    """
    在 database 中找与 embedding 最相似的学生。

    database 元素结构 (由 B 组装传入):
        {
            "student_id": str,
            "name": str,
            "embeddings": list[list[float]]  # 一个学生可有多张注册图
        }

    返回 {"matched", "student_id", "name", "score", "error_code"}
    """
    best_score = -1.0
    best_item: dict | None = None

    for item in database:
        embs = item.get("embeddings") or []
        for emb in embs:
            score = cosine_similarity(embedding, np.asarray(emb))
            if score > best_score:
                best_score = score
                best_item = item

    if best_item is not None and best_score >= threshold:
        return {
            "matched": True,
            "student_id": best_item.get("student_id"),
            "name": best_item.get("name"),
            "score": round(best_score, 4),
            "error_code": None,
        }
    return {
        "matched": False,
        "student_id": None,
        "name": None,
        "score": round(max(best_score, 0.0), 4),
        "error_code": config.ERR_UNKNOWN_FACE,
    }


# ---------------------------------------------------------------------------
# bbox / facial_area
# ---------------------------------------------------------------------------
def facial_area_to_xyxy(area: dict) -> tuple[int, int, int, int]:
    """DeepFace 返回的 facial_area 是 {x,y,w,h}, 这里转成 (x1,y1,x2,y2)。"""
    x = int(area.get("x", 0))
    y = int(area.get("y", 0))
    w = int(area.get("w", 0))
    h = int(area.get("h", 0))
    return x, y, x + w, y + h


def bbox_size(bbox: tuple[int, int, int, int]) -> int:
    """返回 bbox 短边长度, 用于过滤过小的人脸。"""
    x1, y1, x2, y2 = bbox
    return min(x2 - x1, y2 - y1)


def crop_face(img: np.ndarray, bbox: tuple[int, int, int, int], pad_ratio: float = 0.1) -> np.ndarray:
    """按 bbox 截取人脸, 周围加 pad 防止裁掉下巴/额头。"""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    bw = x2 - x1
    bh = y2 - y1
    px = int(bw * pad_ratio)
    py = int(bh * pad_ratio)
    x1 = max(0, x1 - px)
    y1 = max(0, y1 - py)
    x2 = min(w, x2 + px)
    y2 = min(h, y2 + py)
    return img[y1:y2, x1:x2].copy()


# ---------------------------------------------------------------------------
# 标注绘制 (支持中文)
# ---------------------------------------------------------------------------
_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}


def _get_font(size: int) -> ImageFont.ImageFont:
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    font_path = config.get_font_path()
    if font_path is None:
        font = ImageFont.load_default()
    else:
        font = ImageFont.truetype(font_path, size=size)
    _FONT_CACHE[size] = font
    return font


def draw_face_boxes(
    img: np.ndarray,
    faces: list[dict],
    font_size: int = 22,
) -> np.ndarray:
    """
    在图上绘制 bbox + 标签。faces 元素结构:
        {
            "bbox": [x1,y1,x2,y2],
            "matched": bool,
            "name": str | None,
            "student_id": str | None,
            "score": float,
        }
    匹配成功用绿色, 未知用红色。
    """
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    font = _get_font(font_size)

    for f in faces:
        x1, y1, x2, y2 = f["bbox"]
        matched = f.get("matched", False)
        color = (60, 200, 80) if matched else (220, 60, 60)

        draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=3)

        if matched:
            label = f"{f.get('name') or f.get('student_id') or 'matched'} {f.get('score', 0):.2f}"
        else:
            label = "unknown"

        try:
            tb = draw.textbbox((0, 0), label, font=font)
            tw = tb[2] - tb[0]
            th = tb[3] - tb[1]
        except AttributeError:
            tw, th = draw.textsize(label, font=font)
        bg_y1 = max(0, y1 - th - 6)
        draw.rectangle([(x1, bg_y1), (x1 + tw + 8, bg_y1 + th + 6)], fill=color)
        draw.text((x1 + 4, bg_y1 + 2), label, fill=(255, 255, 255), font=font)

    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


# ---------------------------------------------------------------------------
# 输出路径
# ---------------------------------------------------------------------------
def make_annotated_path(prefix: str = "annot") -> Path:
    ts = int(time.time() * 1000)
    name = f"{prefix}_{ts}_{uuid.uuid4().hex[:6]}.jpg"
    return config.ANNOTATED_DIR / name


# ---------------------------------------------------------------------------
# 嵌入序列化辅助 (方便 B 存数据库)
# ---------------------------------------------------------------------------
def embedding_to_list(emb: np.ndarray) -> list[float]:
    return [float(x) for x in np.asarray(emb).ravel()]


def embedding_to_b64(emb: np.ndarray) -> str:
    """float32 紧凑存储, 比 JSON list 小 ~3 倍, B 可选用。"""
    arr = np.asarray(emb, dtype=np.float32).tobytes()
    return base64.b64encode(arr).decode("ascii")


def embedding_from_b64(s: str, dim: int = config.EMBEDDING_DIM) -> np.ndarray:
    raw = base64.b64decode(s)
    arr = np.frombuffer(raw, dtype=np.float32)
    if arr.size != dim:
        raise ValueError(f"嵌入维度不匹配: 期望{dim}, 实际{arr.size}")
    return arr.copy()
