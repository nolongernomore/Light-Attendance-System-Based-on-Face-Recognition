"""
DeepFace 引擎封装: 模型预热、检测、特征提取
模块负责人: C

对外只暴露三个底层方法, 业务层 (recognition.py) 在这之上组合 enroll/recognize 等流程。
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np

from . import config
from . import utils

logger = logging.getLogger("face_service.core")


class FaceEngine:
    """
    DeepFace 引擎单例。
    第一次调用时加载模型 (ArcFace + RetinaFace), 后续复用。
    """

    _instance: "FaceEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._warmed_up = False
        self._deepface = None        # 延迟 import, 启动期不阻塞
        self._gpu_checked = False

    # ------------------------------------------------------------------
    # 内部: 延迟导入 + 预热
    # ------------------------------------------------------------------
    def _lazy_import(self):
        if self._deepface is not None:
            return
        # 导入前先做 GPU 检查 (只查一次)
        if not self._gpu_checked:
            self._check_gpu()
            self._gpu_checked = True
        from deepface import DeepFace  # noqa: WPS433  延迟导入是有意为之
        self._deepface = DeepFace

    def _check_gpu(self):
        if not config.USE_GPU:
            logger.info("FACE_USE_GPU=0, 强制走 CPU")
            return
        try:
            import tensorflow as tf
            gpus = tf.config.list_physical_devices("GPU")
            if gpus:
                logger.info("检测到 %d 个 GPU: %s", len(gpus), [g.name for g in gpus])
                for g in gpus:
                    try:
                        tf.config.experimental.set_memory_growth(g, True)
                    except RuntimeError:
                        pass
            else:
                logger.warning("未检测到 GPU, 将使用 CPU 推理")
        except ImportError:
            logger.warning("tensorflow 未安装, 跳过 GPU 检查")

    def warmup(self):
        """
        预热: 走一次空跑触发模型下载 / 编译。
        建议 B 在 FastAPI startup 钩子里调用一次, 避免首个请求超时。
        """
        if self._warmed_up:
            return
        self._lazy_import()
        # 用一张内存里的纯色图触发: 不依赖磁盘文件, 不依赖外网
        dummy = np.full((160, 160, 3), 128, dtype=np.uint8)
        try:
            self._deepface.represent(
                img_path=dummy,
                model_name=config.MODEL_NAME,
                detector_backend="skip",   # 预热时跳过检测器, 节省时间
                enforce_detection=False,
                align=False,
            )
            logger.info("DeepFace 预热完成: model=%s", config.MODEL_NAME)
        except Exception as exc:                                            # noqa: BLE001
            logger.warning("DeepFace 预热失败 (首次仍会成功加载): %s", exc)
        self._warmed_up = True

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------
    def detect_faces(
        self,
        img: np.ndarray,
        detector_backend: str = config.DETECTOR_BACKEND_GROUP,
    ) -> list[dict]:
        """
        多人检测。返回 list[ {"bbox":(x1,y1,x2,y2), "confidence":float, "face": ndarray} ]

        face 是 DeepFace 已经做过对齐+归一化 (0-1 float) 的人脸 patch。
        """
        self._lazy_import()
        try:
            results = self._deepface.extract_faces(
                img_path=img,
                detector_backend=detector_backend,
                enforce_detection=False,
                align=True,
            )
        except Exception as exc:                                            # noqa: BLE001
            logger.warning("人脸检测失败: %s", exc)
            return []

        faces: list[dict] = []
        for r in results:
            area = r.get("facial_area") or {}
            bbox = utils.facial_area_to_xyxy(area)
            # DeepFace 在没检测到人脸时也可能返回整图作为 "face", 用置信度过滤
            conf = float(r.get("confidence", 0.0))
            if conf <= 0.0:
                continue
            faces.append({
                "bbox": bbox,
                "confidence": conf,
                "face": r.get("face"),
            })
        return faces

    def embed_image(
        self,
        img: np.ndarray | str | Path,
        detector_backend: str = config.DETECTOR_BACKEND_SINGLE,
        enforce_detection: bool = True,
    ) -> list[dict]:
        """
        对一张图提取所有人脸的 embedding。
        返回 list[ {"embedding": np.ndarray(512), "bbox":(x1,y1,x2,y2), "confidence":float} ]
        """
        self._lazy_import()
        try:
            results = self._deepface.represent(
                img_path=img,
                model_name=config.MODEL_NAME,
                detector_backend=detector_backend,
                enforce_detection=enforce_detection,
                align=True,
            )
        except Exception as exc:                                            # noqa: BLE001
            logger.info("represent 失败: %s", exc)
            return []

        out: list[dict] = []
        for r in results:
            emb = np.asarray(r.get("embedding", []), dtype=np.float32)
            if emb.size == 0:
                continue
            area = r.get("facial_area") or {}
            bbox = utils.facial_area_to_xyxy(area)
            conf = float(r.get("face_confidence", 1.0))
            out.append({
                "embedding": emb,
                "bbox": bbox,
                "confidence": conf,
            })
        return out

    def embed_face_patch(self, face_patch: np.ndarray) -> np.ndarray | None:
        """
        对已经裁好的人脸 patch (BGR ndarray) 直接提 embedding, 跳过检测器。
        合照场景批量调用更快。
        """
        self._lazy_import()
        try:
            results = self._deepface.represent(
                img_path=face_patch,
                model_name=config.MODEL_NAME,
                detector_backend="skip",
                enforce_detection=False,
                align=False,
            )
        except Exception as exc:                                            # noqa: BLE001
            logger.info("embed_face_patch 失败: %s", exc)
            return None
        if not results:
            return None
        emb = np.asarray(results[0].get("embedding", []), dtype=np.float32)
        return emb if emb.size > 0 else None


def get_engine() -> FaceEngine:
    """业务层统一入口, 不要直接 new FaceEngine。"""
    return FaceEngine()
