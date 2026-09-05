"""
face_service: 人脸识别 + 合照识别服务 (方案一 C 模块)

供 B 调用的稳定接口:
    enroll_student_faces(student_id, image_paths) -> dict
    recognize_single_face(image_path, face_database) -> dict
    recognize_group_photo(image_path, face_database) -> dict
    draw_recognition_result(image_path, faces, save_path=None) -> str
    warmup() -> None              # 建议在 FastAPI startup 钩子里调一次

存储辅助 (B 决定数据库怎么存):
    embedding_to_list / embedding_to_b64 / embedding_from_b64

face_database 入参格式:
    [
        {"student_id": "20260001", "name": "张三",
         "embeddings": [[0.12, ...], [0.34, ...]]},
        ...
    ]
"""
from .config import (
    SINGLE_FACE_SIM_THRESHOLD,
    GROUP_FACE_SIM_THRESHOLD,
    EMBEDDING_DIM,
    MODEL_NAME,
    ERR_NO_FACE,
    ERR_MULTIPLE_FACE,
    ERR_UNKNOWN_FACE,
    ERR_INVALID_IMAGE,
    ERR_LOW_QUALITY,
)
from .core_engine import get_engine
from .recognition import (
    enroll_student_faces,
    recognize_single_face,
    recognize_group_photo,
    draw_recognition_result,
)
from .utils import (
    embedding_to_list,
    embedding_to_b64,
    embedding_from_b64,
    cosine_similarity,
)


def warmup() -> None:
    """触发模型加载, 供后端启动时调用。"""
    get_engine().warmup()


__all__ = [
    "enroll_student_faces",
    "recognize_single_face",
    "recognize_group_photo",
    "draw_recognition_result",
    "warmup",
    "embedding_to_list",
    "embedding_to_b64",
    "embedding_from_b64",
    "cosine_similarity",
    "SINGLE_FACE_SIM_THRESHOLD",
    "GROUP_FACE_SIM_THRESHOLD",
    "EMBEDDING_DIM",
    "MODEL_NAME",
    "ERR_NO_FACE",
    "ERR_MULTIPLE_FACE",
    "ERR_UNKNOWN_FACE",
    "ERR_INVALID_IMAGE",
    "ERR_LOW_QUALITY",
]
