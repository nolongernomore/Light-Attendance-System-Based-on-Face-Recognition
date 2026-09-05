# 内容安全班级考勤系统后端 API 文档

## 1. 基本信息

- 后端框架：FastAPI
- 本机地址：`http://127.0.0.1:8000`
- Radmin 地址：`http://26.6.49.51:8000`
- API 前缀：`/api`
- Swagger：`GET /docs`
- 健康检查：`GET /api/health`
- 照片库后台导入页：`GET /tools/admin-face-import`
- 学生后台管理页：`GET /tools/admin-students`

启动：

```powershell
cd C:\Users\ASUS\Desktop\content_exp_final\backend
conda activate attendance-backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

前端 baseURL：

```text
http://26.6.49.51:8000/api
```

除特别说明外，普通业务接口使用：

```http
Authorization: Bearer <access_token>
```

统一响应格式：

```json
{
  "success": true,
  "code": "OK",
  "message": "message",
  "data": {}
}
```

## 2. 认证接口

默认教师账号：

```text
username: teacher
password: 123456
```

学生账号在创建或导入学生时自动生成，用户名和默认密码均为学号。

### POST `/api/auth/login`

登录。

```json
{
  "username": "teacher",
  "password": "123456"
}
```

返回：

```json
{
  "access_token": "jwt token",
  "token_type": "bearer",
  "user": {
    "username": "teacher",
    "role": "teacher"
  }
}
```

### GET `/api/auth/me`

查询当前登录用户。

### POST `/api/auth/teachers`

教师创建新的教师账号。

```json
{
  "username": "teacher2",
  "password": "123456",
  "full_name": "王老师"
}
```

## 3. 后台管理

后台管理不使用普通教师 token，而是在请求体中提交管理员密码：

```text
admin_password: 123456
```

后台管理页面：

```text
http://127.0.0.1:8000/tools/admin-students
```

Radmin：

```text
http://26.6.49.51:8000/tools/admin-students
```

### POST `/api/admin/students/list`

查看学生库中所有学生，包含已停用学生。

```json
{
  "admin_password": "123456"
}
```

### POST `/api/admin/students/delete`

删除指定学生或一键删除全部学生。

删除会清理：

- `students`
- 学生登录账号 `users`
- 课程名单关系 `course_students`
- 学生照片记录 `student_face_images`
- 人脸模板 `face_templates`

历史考勤记录暂时保留，避免误删考勤统计。

删除选中学生：

```json
{
  "admin_password": "123456",
  "student_ids": ["20260001", "20260002"],
  "delete_all": false
}
```

一键删除全部学生：

```json
{
  "admin_password": "123456",
  "student_ids": [],
  "delete_all": true
}
```

## 4. 数据关系说明

当前核心关系：

- `teachers`：教师独立信息。
- `students`：学生独立信息，不依附任何课程。
- `users`：登录账号表，通过 `teacher_id` 或 `student_id` 关联真实身份。
- `courses`：课程表，归属于教师。
- `course_students`：课程学生名单表，只关联已有学生库学生。
- `attendance_sessions`：考勤场次表。
- `attendance_records`：考勤明细表。
- `student_face_images`：学生照片表。
- `face_templates`：人脸模板表。

详细表结构见：[DATABASE_DESIGN.md](DATABASE_DESIGN.md)

## 5. 课程接口

### GET `/api/courses`

查询课程列表。

- 教师：返回自己创建的课程。
- 学生：返回自己加入的课程。
- 课程统一使用后端自动生成的 `course_id`，老师不需要也不能手动填写课程编号。

返回课程字段：

- `course_id`
- `course_name`
- `teacher_id`
- `term`
- `description`
- `status`
- `created_at`
- `updated_at`

### POST `/api/courses`

教师创建课程。

```json
{
  "course_name": "内容安全实验课",
  "term": "2026春",
  "description": "课程说明"
}
```

### PUT `/api/courses/{course_id}`

教师修改自己的课程。

```json
{
  "course_name": "内容安全实验课",
  "term": "2026春",
  "description": "更新说明",
  "status": "active"
}
```

### GET `/api/courses/{course_id}/students`

教师查询某门课程的学生名单。

### POST `/api/courses/{course_id}/students`

教师把学生库中已有学生加入课程。该接口不会创建学生；如果学号在学生库中不存在，会进入失败列表。

```json
{
  "student_ids": ["20260001", "20260002"]
}
```

返回重点：

| 字段 | 说明 |
| --- | --- |
| `input_count` | 输入的学号数量 |
| `added_to_course_count` | 本次新加入课程的人数 |
| `already_in_course_count` | 原本已经在该课程的人数 |
| `duplicate_count` | 输入中重复的学号数量 |
| `failed_count` | 失败数量 |
| `failed` | 失败明细，例如学生库不存在 |
| `students` | 成功处理的学生名单 |

### POST `/api/courses/{course_id}/students/import`

通过 `.xlsx`、`.xls` 或 `.csv` 把学生库中已有学生加入课程。

请求类型：`multipart/form-data`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `file` | 是 | 包含 `student_id` / `student_no` / `学号` 列的表格 |

说明：该接口只建立课程名单关系，不创建学生主数据。

### DELETE `/api/courses/{course_id}/students/{student_id}`

教师从课程名单移除学生，不删除学生库主信息和历史考勤。

## 6. 学生库接口

### GET `/api/students`

教师查询学生库或某门课的学生名单。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `course_id` | 否 | 不传时查询学生库全部学生；传入时查询该课程名单 |
| `keyword` | 否 | 按学号、姓名、班级、专业模糊搜索 |

返回学生字段包含：

- `student_id`
- `name`
- `class_name`
- `major`
- `gender`
- `phone`
- `email`
- `has_face_image`
- `active_face_image_count`
- `latest_face_image_id`
- `latest_face_image_url`

### POST `/api/students`

教师新增或更新学生库主数据。该接口只维护学生库，不会加入任何课程。

```json
{
  "student_id": "20260001",
  "name": "张三",
  "class_name": "1班",
  "major": "网络空间安全",
  "gender": "男",
  "phone": "13800000000",
  "email": "student@example.com"
}
```

### POST `/api/students/import`

批量导入学生库主数据。该接口只维护学生库，不会加入任何课程。

请求类型：`multipart/form-data`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `file` | 是 | `.xlsx`、`.xls`、`.csv` |

支持列名：

```text
student_id / student_no / 学号
name / 姓名
class_name / 班级
major / 专业
gender / 性别
phone / 手机号
email / 邮箱
```

### PUT `/api/students/{student_id}`

教师修改学生库中的学生信息。

```json
{
  "name": "张三",
  "class_name": "1班",
  "major": "网络空间安全",
  "gender": "男",
  "phone": "13800000000",
  "email": "student@example.com"
}
```

说明：学生库删除统一使用后台管理 `POST /api/admin/students/delete`。

## 7. 学生照片接口

### POST `/api/face/enroll`

教师为学生库中的某个学生录入单张照片。该接口不会把学生加入课程。

请求类型：`multipart/form-data`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `student_id` | 是 | 学号 |
| `file` | 是 | 人脸照片，支持 `.jpg`、`.jpeg`、`.png` |

同一学生再次录入时，旧照片和旧模板会自动停用，只保留最后一次成功录入的照片。

### 照片库后台批量导入

照片库 ZIP 不再作为前端联调用 API。批量导入保留在后端管理员页面中，由管理员输入密码后操作：

```text
http://26.6.49.51:8000/tools/admin-face-import
```

管理员密码：

```text
123456
```

ZIP 内图片命名格式：

```text
学号-姓名-专业-性别.jpg
```

示例：

```text
20260001-张三-网络空间安全-男.jpg
20260002-李四-计算机科学与技术-女.png
```

导入规则：

- 照片库是全局学生照片库，不绑定课程。
- 如果学生库中没有该学号，会根据文件名创建学生主数据。
- 文件名必须正好包含 4 段信息：学号、姓名、专业、性别。
- 支持 `.jpg`、`.jpeg`、`.png`、`.bmp`、`.webp`。
- 后端会根据文件头识别真实图片格式；后缀是 `.png` 但内容实际是 JPG 时，也会按 JPG 保存并允许导入。
- 每个学生最多保留 1 张当前有效照片，重复上传时以最后一次成功录入为准。
- 不合规图片不会写入数据库，合规图片继续导入。

ZIP 限制：

```text
最多 1000 个文件
单张图片最大 10MB
ZIP 解压后总大小最大 500MB
```

返回重点：

| 字段 | 说明 |
| --- | --- |
| `zip_filename` | 上传的 ZIP 文件名 |
| `received_file_count` | ZIP 内参与处理的文件总数 |
| `valid_file_count` | 通过校验的图片数量 |
| `failed_file_count` | 失败文件数量 |
| `failed_files` | 失败文件明细 |
| `success_student_count` | 成功录入学生数量，按学号去重 |
| `success_students` | 成功录入学生名单，只含学号和姓名 |
| `created_student_count` | 新创建学生数量 |
| `updated_student_count` | 更新已有学生数量 |
| `created_image_count` | 成功写入照片数量 |

### GET `/api/face/status/{student_id}`

查询某个学生照片录入状态。

### POST `/api/face/enroll-me`

学生本人上传照片。

请求类型：`multipart/form-data`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `file` | 是 | 本人人脸照片 |

### GET `/api/face/my-status`

学生查询本人照片状态。

### GET `/api/face/my-image`

学生查询本人当前有效照片。

### GET `/api/face/my-images`

学生查询本人所有有效照片。按当前设计最多 1 条。

### DELETE `/api/face/my-images/{image_id}`

学生删除本人照片。删除为软删除，会同步停用对应 `face_templates`，并刷新 `students.has_face_image`。

## 8. 考勤接口

说明：后端已移除活体挑战流程。活体检测由前端完成，提交考勤时后端只接收前端给出的 `liveness_passed` 和 `liveness_score`。

### POST `/api/attendance/sessions`

教师创建考勤场次。

```json
{
  "course_id": 1,
  "title": "第1次课堂考勤"
}
```

说明：

- `course_id` 可不传，不传时使用该教师默认课程。
- 创建场次时会读取该课程的 `course_students` active 名单。
- 后端会为课程名单中每个学生生成一条 `pending` 考勤记录。
- 同一课程允许同时存在多个进行中的考勤，后端不会因为新建场次自动关闭旧场次。

### GET `/api/attendance/sessions`

教师查询自己创建的考勤场次。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `course_id` | 否 | 按课程筛选 |

### GET `/api/attendance/sessions/active`

查询当前进行中的考勤场次。前端学生端不建议使用该接口，应使用 `GET /api/attendance/my-sessions/active` 获取“和当前学生有关”的所有进行中考勤。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `course_id` | 否 | 按课程筛选 |

### GET `/api/attendance/my-sessions/active`

学生登录后查询“涉及自己且正在进行”的所有考勤场次。

权限：学生。

返回内容每一项包含：

- 考勤场次信息：`id`、`course_id`、`title`、`status`、`start_time`、`expected_count`、`checked_count`
- 课程信息：`course_name`
- 当前学生在该场次的记录：`record`

### POST `/api/attendance/sessions/{session_id}/close`

教师关闭考勤。关闭时，仍为 `pending` 的学生会自动变为 `absent`。

### DELETE `/api/attendance/sessions/{session_id}`

教师删除自己发起的某个考勤场次。删除后会同时删除该场次下的学生考勤明细，以及这些明细关联的考勤情绪记录。

权限：教师，只能删除自己发起的考勤。

### POST `/api/attendance/checkin`

学生提交考勤。

权限：学生。后端会使用当前登录学生账号的 `student_id`，只和该学生自己的有效照片模板做比对；不会在整门课的人脸库中搜索身份。

请求类型：`multipart/form-data`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `session_id` | 是 | 考勤场次 ID |
| `file` | 是 | 前端摄像头采集的图片或视频 |
| `liveness_passed` | 否 | 前端活体结果，默认 `true` |
| `liveness_score` | 否 | 前端活体分数 |

说明：

- `session_id` 必须是当前学生所属课程名单中正在进行的考勤场次。
- 如果学生已成功考勤，再次提交会直接返回已有记录。
- 如果当前学生没有有效照片，返回错误，需先录入本人照片。
- 活体失败或人脸与本人照片不匹配时，当前学生本场次记录会被更新为 `failed`，可以再次尝试。

支持上传格式：

```text
.webm .mp4 .mov .avi .jpg .jpeg .png
```

考勤状态：

```text
pending / present / late / absent / failed / unknown
```

### GET `/api/attendance/records`

教师查询考勤记录。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `student_id` | 否 | 按学号筛选 |
| `course_id` | 否 | 按课程筛选 |
| `session_id` | 否 | 按场次筛选 |

### GET `/api/attendance/my-records`

学生查询自己的考勤记录。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `course_id` | 否 | 按课程筛选 |
| `session_id` | 否 | 按场次筛选 |

## 9. 合照识别接口

### POST `/api/group-photo/recognize`

教师上传合照并识别。

请求类型：`multipart/form-data`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `activity_name` | 是 | 活动名称 |
| `activity_date` | 是 | 活动日期，格式 `YYYY-MM-DD` |
| `file` | 是 | 合照图片，支持 `.jpg`、`.jpeg`、`.png` |
| `course_id` | 否 | 课程 ID，不传时使用默认课程 |
| `description` | 否 | 活动说明 |

### GET `/api/group-photo/activities`

教师查询活动列表。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `course_id` | 否 | 按课程筛选 |

### GET `/api/group-photo/{activity_id}`

教师查询活动详情，包括合照识别结果和参与人员。

## 10. 统计接口

### GET `/api/stats/attendance`

教师查询考勤统计。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `course_id` | 否 | 按课程筛选 |

### GET `/api/stats/activity-frequency`

教师查询活动参与频次统计。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `course_id` | 否 | 按课程筛选 |

### GET `/api/stats/emotion`

教师查询情绪统计。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `course_id` | 否 | 按课程筛选 |

## 11. 导出接口

### GET `/api/export/attendance`

教师导出考勤记录为 XLSX。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `course_id` | 否 | 按课程筛选 |
| `session_id` | 否 | 按场次筛选 |
| `student_id` | 否 | 按学号筛选 |

说明：

- 教师导出某门课全部学生全部考勤记录：`GET /api/export/attendance?course_id=1`
- 也可以继续叠加 `session_id` 或 `student_id` 筛选。
- 导出列包含课程名称、考勤标题、开始时间、结束时间、学号、姓名、状态、考勤时间、活体分数、人脸分数、失败原因等。

### GET `/api/export/my-attendance`

学生导出自己的考勤记录为 XLSX。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `course_id` | 否 | 按课程筛选 |
| `session_id` | 否 | 按场次筛选 |

说明：

- 不传参数时导出当前学生涉及的全部考勤记录。
- 可按课程或具体考勤场次筛选。

### GET `/api/export/activity`

教师导出活动参与记录为 XLSX。

### GET `/api/export/emotion`

教师导出情绪记录为 XLSX。

## 12. 推荐联调流程

1. 教师登录：`POST /api/auth/login`
2. 创建或查询课程：`POST /api/courses`、`GET /api/courses`
3. 导入或创建学生库主数据：`POST /api/students/import`、`POST /api/students`
4. 把已有学生加入课程：`POST /api/courses/{course_id}/students` 或 `POST /api/courses/{course_id}/students/import`
5. 后台导入照片库 ZIP：管理员打开 `GET /tools/admin-face-import`
6. 创建考勤场次：`POST /api/attendance/sessions`
7. 学生登录后获取自己的进行中考勤：`GET /api/attendance/my-sessions/active`
8. 前端完成活体检测和摄像头采集
9. 学生提交考勤：`POST /api/attendance/checkin`
10. 教师查询记录：`GET /api/attendance/records?session_id=1`
11. 导出记录：教师 `GET /api/export/attendance?course_id=1`，学生 `GET /api/export/my-attendance`

## 13. 当前算法说明

数据库和 API 流程已经按新结构打通，但人脸识别与情绪分析仍可能处于 mock 或适配状态：

- `services/face_service.py`：人脸录入、单人人脸识别、合照识别入口。
- `services/emotion_service.py`：情绪分析入口。

后续如果接入真实算法，只需要保证这些服务函数的返回结构保持兼容即可。
