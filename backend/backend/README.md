# 后端说明

本目录是 FastAPI 后端服务。项目依赖已经统一到 `requirements.txt`，不再需要分别安装 C/D 模块依赖。

## 启动

```powershell
conda create -n attendance-backend python=3.11 -y
conda activate attendance-backend
python -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

必须在 `backend` 目录下启动，否则相对路径数据库 `attendance.db` 会生成到错误位置。

## 依赖修复

如果启动时报类似 `module 'tensorflow' has no attribute 'config'` 或 `No module named 'pkg_resources'`，说明当前环境里的 TensorFlow/DeepFace 依赖处于残缺或兼容冲突状态。直接 `pip install -r requirements.txt` 可能会因为版本已满足而不重装，需要强制覆盖：

```powershell
python -m pip install --no-cache-dir --force-reinstall -r requirements.txt
python -c "import tensorflow as tf; print(tf.__version__); print(hasattr(tf, 'config'))"
```

验证命令应输出 `2.15.1` 和 `True`。

## 常用入口

```text
Swagger:        http://127.0.0.1:8000/docs
健康检查:       http://127.0.0.1:8000/api/health
学生后台管理:   http://127.0.0.1:8000/tools/admin-students
照片库后台导入: http://127.0.0.1:8000/tools/admin-face-import
```

默认教师账号：

```text
teacher / 123456
```

管理员工具密码：

```text
123456
```

## 运行时数据

```text
attendance.db              SQLite 数据库
uploads/                   上传图片、导出文件
data/annotated/            合照标注图缓存
```

这些文件是本地运行产物，提交前应保持清理状态。接口说明见 `../docs/API.md`，数据库说明见 `../docs/DATABASE_DESIGN.md`。
