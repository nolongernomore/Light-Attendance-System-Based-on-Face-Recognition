"""
人脸识别服务全局配置
模块负责人: C
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ["TF_USE_LEGACY_KERAS"] = "1"

# ---------------------------------------------------------------------------
# 路径配置
# ---------------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[2]          # d:/content_security/backend
SERVICE_ROOT = Path(__file__).resolve().parent              # service/face_service
DATA_ROOT = BACKEND_ROOT / "data"                           # 由 B 创建/共享
ANNOTATED_DIR = DATA_ROOT / "annotated"                     # 标注图输出目录
ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# DeepFace 模型配置
# ---------------------------------------------------------------------------
# DeepFace 支持的 backbone: VGG-Face, Facenet, Facenet512, OpenFace,
#                           DeepFace, DeepID, ArcFace, Dlib, SFace, GhostFaceNet
# ArcFace 在亚洲人脸上综合表现最好, 512 维 embedding
MODEL_NAME = "ArcFace"
EMBEDDING_DIM = 512

# 检测器: opencv, ssd, mtcnn, retinaface, mediapipe, yolov8, yunet, fastmtcnn
# retinaface 召回率高, 合照场景必备; 单人考勤可用更轻的 yunet/opencv 提速
DETECTOR_BACKEND_GROUP = os.environ.get("FACE_DETECTOR_GROUP", "retinaface")
DETECTOR_BACKEND_SINGLE = os.environ.get("FACE_DETECTOR_SINGLE", "opencv")
DETECTOR_BACKEND_ENROLL = os.environ.get("FACE_DETECTOR_ENROLL", "retinaface")

# 距离度量: cosine, euclidean, euclidean_l2
DISTANCE_METRIC = "cosine"

# ---------------------------------------------------------------------------
# 相似度阈值 (cosine similarity, 越大越像)
# DeepFace 内部用的是距离 distance = 1 - similarity, 这里统一为相似度方便理解
# ---------------------------------------------------------------------------
# 单人考勤匹配阈值 (严格, 防止误识别)
SINGLE_FACE_SIM_THRESHOLD = 0.40
# 合照识别阈值 (略宽松, 合照分辨率/角度差异更大)
GROUP_FACE_SIM_THRESHOLD = 0.30
# 注册人脸自一致性阈值, 多张注册图相互之间应当达到此相似度, 否则丢弃异常张
ENROLL_SELF_CONSISTENCY = 0.35

# ---------------------------------------------------------------------------
# 输入约束
# ---------------------------------------------------------------------------
MIN_FACE_SIZE_SINGLE = 80          # 单人考勤要求人脸至少 80px
MIN_FACE_SIZE_GROUP = 20           # 合照场景人脸更小, 阈值放低
MAX_IMAGE_SIDE = int(os.environ.get("FACE_MAX_IMAGE_SIDE", "1600"))  # 输入图最长边超过则等比缩放, 防止显存爆掉
ENROLL_MIN_VALID_IMAGES = 1        # 注册时至少需要几张有效人脸图

# ---------------------------------------------------------------------------
# 错误码
# ---------------------------------------------------------------------------
ERR_NO_FACE = "NO_FACE"
ERR_MULTIPLE_FACE = "MULTIPLE_FACE"
ERR_UNKNOWN_FACE = "UNKNOWN_FACE"
ERR_INVALID_IMAGE = "INVALID_IMAGE"
ERR_LOW_QUALITY = "LOW_QUALITY"

# ---------------------------------------------------------------------------
# 设备 / 性能
# ---------------------------------------------------------------------------
USE_GPU = os.environ.get("FACE_USE_GPU", "1") == "1"
# 让 TensorFlow 按需申请显存, 避免一次性占满
os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
# 屏蔽 TensorFlow 启动期 INFO/WARN 日志, 输出更干净
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

# ---------------------------------------------------------------------------
# 中文字体 (绘制标注图时用)
# 按平台依次尝试, 找到第一个存在的
# ---------------------------------------------------------------------------
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def get_font_path() -> str | None:
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None
