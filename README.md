# 内容安全班级考勤系统

这是一个面向班级课程考勤场景的前后端项目。后端使用 FastAPI 提供课程、学生、人脸照片、考勤、合照识别、统计和导出接口；前端使用 Vue 3 + Vite，包含教师端和学生端两套页面。

## 功能概览

- 教师登录、课程管理、课程名单管理
- 学生库维护，支持手动创建和表格导入
- 学生人脸照片录入、本人照片查看和删除
- 教师创建考勤场次，学生通过摄像头活体检测后提交考勤
- 合照识别、活动记录、情绪统计和 Excel 导出
- Swagger 接口文档和本地管理工具页

## 项目结构

```text
content_exp_final/
+-- backend/
|   +-- backend/                 FastAPI 后端源码
|   |   +-- api/                 API 路由
|   |   +-- models/              SQLAlchemy 数据模型
|   |   +-- schemas/             Pydantic 请求/响应结构
|   |   +-- service/face_service 人脸识别核心服务
|   |   +-- services/            业务服务
|   |   +-- main.py              应用入口
|   |   +-- requirements.txt     后端依赖
|   +-- docs/                    API 和数据库设计文档
+-- frontend/
    +-- src/                     Vue 前端源码
    +-- public/models/           face-api.js 前端活体检测模型
    +-- package.json
    +-- vite.config.js
```

## 环境要求

- Python 3.11
- Node.js 18 或更高版本
- Windows 本地运行建议使用 PowerShell 或 Anaconda Prompt

后端依赖中包含 TensorFlow、DeepFace、RetinaFace 等包，首次安装耗时较长，建议使用独立 Python 环境。

## 后端启动

在后端源码目录启动，避免 SQLite 数据库生成到错误位置：

```powershell
cd backend\backend
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

常用入口：

```text
Swagger:        http://127.0.0.1:8000/docs
健康检查:       http://127.0.0.1:8000/api/health
学生后台管理:   http://127.0.0.1:8000/tools/admin-students
照片库后台导入: http://127.0.0.1:8000/tools/admin-face-import
```

本地开发默认教师账号：

```text
username: teacher
password: 123456
```

学生账号在创建或导入学生时自动生成，默认用户名和密码均为学号。公开部署前请修改默认密码、管理员密码和 JWT 密钥，避免使用示例配置上线。

## 前端启动

```powershell
cd frontend
npm install
npm run dev
```

开发服务默认端口为 `3000`，配置见 `frontend/vite.config.js`。前端默认请求本地后端：

```text
http://127.0.0.1:8000
```

如需连接其他后端地址，可以在 `frontend/.env.local` 中配置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

`.env.local` 属于本地配置文件，不应提交到 GitHub。

## 主要页面

教师端：

- `/teacher/courses`：课程管理、课程名单、启动考勤
- `/teacher/sessions`：考勤场次管理
- `/teacher/student`：学生库、学生导入、人脸录入
- `/teacher/group-photo`：合照识别、历史记录、统计和导出
- `/teacher/records`：考勤记录、情绪统计、Excel 导出

学生端：

- `/student/checkin`：摄像头活体检测和考勤提交
- `/student/my-records`：本人考勤记录
- `/student/my-face`：本人人脸照片状态、查看和删除

## 活体检测模型

前端活体检测使用 `face-api.js`，模型文件位于：

```text
frontend/public/models/
```

当前仓库包含以下模型文件，便于克隆后直接运行前端活体检测：

```text
tiny_face_detector_model-weights_manifest.json
tiny_face_detector_model-shard1
face_landmark_68_model-weights_manifest.json
face_landmark_68_model-shard1
```

模型来源为 `face-api.js` 官方权重目录：

```text
https://github.com/justadudewhohacks/face-api.js/tree/master/weights
```

`face-api.js` 包本身使用 MIT License。使用或再分发模型权重时，请同时遵守其来源仓库的许可要求。

## 不应提交的本地文件

项目已通过 `.gitignore` 排除常见运行文件。提交前请确认以下内容没有进入 Git：

```text
node_modules/
dist/
__pycache__/
*.pyc
*.db
backend/backend/uploads/
backend/backend_restore.tar
.env
.env.*
.claude/
.continue/
```

推荐提交前检查：

```powershell
git status --short
```

## 更多文档

- `backend/README.md`：后端启动和依赖说明
- `backend/docs/API.md`：接口说明
- `backend/docs/DATABASE_DESIGN.md`：数据库结构说明
- `frontend/项目记忆总结.md`：前端结构和业务流程
- `frontend/模型下载指南.md`：模型文件准备说明
- `frontend/前端活体检测说明.md`：前端活体检测说明
