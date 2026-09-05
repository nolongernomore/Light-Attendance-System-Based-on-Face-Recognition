# 内容安全班级考勤系统

FastAPI 后端项目，面向班级课程考勤场景，支持教师/学生登录、学生库、课程名单、人脸照片录入、单人考勤、合照识别、情绪统计和 Excel 导出。

## 项目结构

```text
backend/                         后端服务源码
backend/requirements.txt         统一依赖清单
docs/API.md                      API 联调速查
docs/DATABASE_DESIGN.md          数据库结构说明
```

## 快速启动

```powershell
cd backend
conda create -n attendance-backend python=3.11 -y
conda activate attendance-backend
python -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

如果旧环境里已经装过 TensorFlow/DeepFace，建议强制重装一次，避免残缺包、Keras 版本串线，或 `pkg_resources` 兼容问题：

```powershell
python -m pip install --no-cache-dir --force-reinstall -r requirements.txt
python -c "import tensorflow as tf; print(tf.__version__); print(hasattr(tf, 'config'))"
```

第二条命令应输出 `2.15.1` 和 `True`。

常用地址：

```text
Swagger:        http://127.0.0.1:8000/docs
健康检查:       http://127.0.0.1:8000/api/health
学生后台管理:   http://127.0.0.1:8000/tools/admin-students
照片库后台导入: http://127.0.0.1:8000/tools/admin-face-import
```

默认教师账号：

```text
username: teacher
password: 123456
```

学生账号在创建或导入学生时自动生成，用户名和默认密码均为学号。

## 主要流程

1. 教师登录并创建课程。
2. 创建或导入学生库。
3. 将学生加入课程名单。
4. 录入学生人脸照片，或通过后台批量导入照片库。
5. 教师创建考勤场次。
6. 学生登录后查看进行中的考勤并上传采集图片。
7. 教师查看考勤、合照、情绪统计并按需导出 Excel。

## 数据与提交

本地运行会生成以下数据文件或目录，已在 `.gitignore` 中排除：

```text
backend/attendance.db
backend/uploads/
backend/data/annotated/
__pycache__/
```

提交前确认 `git status --short` 中没有运行时数据即可。数据库文件不存在时，后端首次启动会自动建表并初始化默认教师账号。
