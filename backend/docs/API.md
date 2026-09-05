# API 联调速查

## 基本约定

- 本地地址：`http://127.0.0.1:8000`
- API 前缀：`/api`
- Swagger：`GET /docs`
- 健康检查：`GET /api/health`
- 普通业务接口使用 `Authorization: Bearer <access_token>`
- 管理员工具页使用固定管理员密码 `123456`

统一响应格式：

```json
{
  "success": true,
  "code": "OK",
  "message": "message",
  "data": {}
}
```

默认教师账号：

```text
username: teacher
password: 123456
```

学生账号在创建或导入学生时自动生成，用户名和默认密码均为学号。

## 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/login` | 登录并返回 JWT |
| GET | `/api/auth/me` | 查询当前用户 |
| POST | `/api/auth/teachers` | 教师创建新的教师账号 |

登录请求：

```json
{
  "username": "teacher",
  "password": "123456"
}
```

## 后台管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/tools/admin-students` | 学生后台管理页面 |
| GET | `/tools/admin-face-import` | 照片库 ZIP 导入页面 |
| POST | `/api/admin/students/list` | 列出学生库 |
| POST | `/api/admin/students/delete` | 删除指定学生或清空学生库 |
| POST | `/api/admin/face-import` | 后台导入照片库 ZIP |

后台请求体包含：

```json
{
  "admin_password": "123456"
}
```

删除学生会清理学生主数据、学生账号、课程名单关系、照片记录和人脸模板。历史考勤和统计类记录按接口逻辑保留或单独删除。

## 课程

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/courses` | 教师查自己的课程；学生查已加入课程 |
| POST | `/api/courses` | 教师创建课程 |
| PUT | `/api/courses/{course_id}` | 教师更新课程 |
| DELETE | `/api/courses/{course_id}` | 教师软删除课程 |
| GET | `/api/courses/{course_id}/students` | 查询课程名单 |
| POST | `/api/courses/{course_id}/students` | 将已有学生加入课程 |
| POST | `/api/courses/{course_id}/students/import` | 通过表格批量加入课程 |
| DELETE | `/api/courses/{course_id}/students/{student_id}` | 从课程名单移除学生 |

创建课程：

```json
{
  "course_name": "Content Security Lab",
  "term": "2026 Spring",
  "description": "课程说明"
}
```

加入课程只建立名单关系，不创建学生主数据。若学生不存在，需要先调用学生库接口创建或导入。

## 学生库

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/students` | 查询学生库，可用 `course_id` 和 `keyword` 筛选 |
| POST | `/api/students` | 新增或更新学生 |
| POST | `/api/students/import` | 导入 `.xlsx`、`.xls`、`.csv` 学生表 |
| PUT | `/api/students/{student_id}` | 更新学生信息 |

学生字段：

```json
{
  "student_id": "20260001",
  "name": "Zhang San",
  "class_name": "Class 1",
  "major": "Cyber Security",
  "gender": "M",
  "phone": "13800000000",
  "email": "student@example.com"
}
```

导入表支持列名：`student_id` / `student_no` / `学号`，`name` / `姓名`，`class_name` / `班级`，`major` / `专业`，`gender` / `性别`，`phone` / `手机号`，`email` / `邮箱`。

## 人脸照片

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/face/service-status` | 人脸服务状态 |
| POST | `/api/face/enroll` | 教师给学生录入照片 |
| GET | `/api/face/status/{student_id}` | 查询学生照片状态 |
| GET | `/api/face/diagnostics/{student_id}` | 教师诊断学生模板 |
| GET | `/api/face/students/{student_id}/images` | 教师查学生有效照片列表 |
| GET | `/api/face/students/{student_id}/image` | 教师查学生最新有效照片 JSON |
| GET | `/api/face/students/{student_id}/image/file` | 教师查学生最新照片文件 |
| GET | `/api/face/images/{image_id}/file` | 按图片 ID 获取照片文件 |
| POST | `/api/face/enroll-me` | 学生本人上传照片 |
| GET | `/api/face/my-status` | 学生查本人照片状态 |
| GET | `/api/face/my-diagnostics` | 学生查本人模板诊断 |
| GET | `/api/face/my-image` | 学生查本人最新照片 JSON |
| GET | `/api/face/my-image/file` | 学生查本人最新照片文件 |
| GET | `/api/face/my-images` | 学生查本人有效照片列表 |
| DELETE | `/api/face/my-images/{image_id}` | 学生软删除本人照片 |

照片录入使用 `multipart/form-data`：

```text
student_id: 20260001
file: jpg/jpeg/png
```

同一学生再次成功录入时，旧照片和旧模板会被停用，只保留最新有效照片。

照片库 ZIP 导入文件名格式：

```text
学号-姓名-专业-性别.jpg
```

ZIP 导入支持 `.jpg`、`.jpeg`、`.png`、`.bmp`、`.webp`，用于后台批量建学生和录入照片。

## 考勤

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/attendance/sessions` | 教师创建考勤场次 |
| GET | `/api/attendance/sessions` | 教师查询场次 |
| GET | `/api/attendance/sessions/active` | 教师查询进行中场次 |
| GET | `/api/attendance/my-sessions/active` | 学生查询自己可参加的进行中场次 |
| POST | `/api/attendance/sessions/{session_id}/close` | 教师关闭场次，未签到记录转缺勤 |
| DELETE | `/api/attendance/sessions/{session_id}` | 教师删除场次及其明细 |
| POST | `/api/attendance/checkin` | 学生提交考勤 |
| GET | `/api/attendance/records` | 教师查询考勤明细 |
| GET | `/api/attendance/my-records` | 学生查询本人考勤 |

创建场次：

```json
{
  "course_id": 1,
  "title": "第 1 次课堂考勤"
}
```

`course_id` 可不传，不传时使用当前教师默认课程。创建场次时会读取课程 active 名单，并为每名学生生成一条 `pending` 考勤记录。

学生提交考勤使用 `multipart/form-data`：

```text
session_id: 1
file: jpg/jpeg/png/webm/mp4/mov/avi
liveness_passed: true
liveness_score: 0.98
liveness_status: passed
liveness_error_code:
liveness_message:
```

考勤状态：`pending`、`present`、`late`、`absent`、`failed`、`unknown`。

## 合照识别

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/group-photo/recognize` | 教师上传合照并识别 |
| GET | `/api/group-photo/records` | 查询合照识别记录 |
| GET | `/api/group-photo/records/{record_id}` | 查询记录详情 |
| DELETE | `/api/group-photo/records/{record_id}` | 删除记录及明细 |
| GET | `/api/group-photo/records/export` | 导出合照记录 |
| GET | `/api/group-photo/activities` | 兼容旧前端，等价于 records |
| GET | `/api/group-photo/{record_id}` | 兼容旧前端，等价于 records detail |
| DELETE | `/api/group-photo/{record_id}` | 兼容旧前端，等价于 records delete |

上传合照使用 `multipart/form-data`：

```text
file: jpg/jpeg/png
course_id: 1
activity_name: 活动名称
activity_date: 2026-05-21
description: 备注
```

传入 `course_id` 时只用该课程学生库做匹配；不传时使用教师可见的全局学生库。

## 统计与导出

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/stats/attendance` | 考勤统计，可按 `course_id` 筛选 |
| GET | `/api/stats/activity-frequency` | 活动参与频次 |
| GET | `/api/stats/emotion` | 情绪统计 |
| GET | `/api/export/attendance` | 教师导出考勤 |
| GET | `/api/export/my-attendance` | 学生导出本人考勤 |
| GET | `/api/export/activity` | 导出活动参与 |
| GET | `/api/export/group-photo-records` | 导出合照记录 |
| GET | `/api/export/emotion` | 导出情绪记录 |

常用筛选参数：`course_id`、`session_id`、`student_id`。

## 推荐联调顺序

1. `POST /api/auth/login` 教师登录。
2. `POST /api/courses` 创建课程，或使用默认课程。
3. `POST /api/students` / `POST /api/students/import` 建学生库。
4. `POST /api/courses/{course_id}/students` 将学生加入课程。
5. `POST /api/face/enroll` 或后台 ZIP 导入录入照片。
6. `POST /api/attendance/sessions` 创建考勤。
7. 学生登录后调用 `GET /api/attendance/my-sessions/active`。
8. 学生调用 `POST /api/attendance/checkin` 提交考勤。
9. 教师调用 `GET /api/attendance/records`、统计和导出接口。
