# face_service 模块

`service/face_service` 是后端内部使用的人脸识别模块，不直接挂 HTTP 路由，也不直接访问数据库。业务层通过 `services/face_service.py` 调用这里的纯函数。

## 依赖

依赖已统一到 `backend/requirements.txt`：

```powershell
cd backend
python -m pip install -r requirements.txt
```

本目录下的 `requirements.txt` 只保留兼容入口，会转向统一依赖清单。

TensorFlow/DeepFace/RetinaFace 对 Keras 大版本比较敏感，项目统一固定在 TensorFlow 2.15 系列，并限制 `setuptools` 版本以兼容 `mtcnn` 仍在使用的 `pkg_resources`。若旧环境启动时报 `tensorflow` 缺少 `config` 或缺少 `pkg_resources`，请在 `backend` 目录执行：

```powershell
python -m pip install --no-cache-dir --force-reinstall -r requirements.txt
```

## 对外函数

| 函数 | 说明 |
| --- | --- |
| `enroll_student_faces(student_id, image_paths)` | 从学生照片提取人脸特征 |
| `recognize_single_face(image_path, face_database)` | 单人考勤识别 |
| `recognize_group_photo(image_path, face_database)` | 合照多人识别 |
| `draw_recognition_result(image_path, faces, save_path=None)` | 根据识别结果生成标注图 |
| `warmup()` | 启动期预热模型 |

失败时函数返回带 `error_code` 的字典，不向业务层抛出未处理异常。

## 常见错误码

| error_code | 说明 |
| --- | --- |
| `NO_FACE` | 未检测到人脸 |
| `MULTIPLE_FACE` | 单人场景检测到多张人脸 |
| `LOW_QUALITY` | 人脸尺寸或质量不足 |
| `UNKNOWN_FACE` | 检测到人脸但未匹配到学生 |
| `INVALID_IMAGE` | 图片读取失败 |

## 边界

- 不操作数据库。
- 不处理教师/学生权限。
- 不决定 HTTP 响应格式。
- 只接收图片路径和业务层组装好的人脸库，返回可 JSON 序列化的识别结果。
