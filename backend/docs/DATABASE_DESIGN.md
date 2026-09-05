# 数据库结构说明

## 基本信息

- 数据库：SQLite
- 默认文件：`backend/attendance.db`
- 建表方式：应用启动时执行 `Base.metadata.create_all()`，随后由 `services/migration_service.py` 补齐旧库字段和索引。
- 运行时文件：图片、导出文件和标注图不进数据库主体，只保存路径，实际文件位于 `backend/uploads/` 和 `backend/data/annotated/`。

数据库不存在时，首次启动会自动创建表，并初始化：

- 默认教师资料：`teachers.teacher_no = teacher`
- 默认教师账号：`users.username = teacher`
- 默认课程：`courses.course_name = Default Course`

## 关系总览

```text
teachers 1 -- N courses
teachers 1 -- N users

students 1 -- N users
students 1 -- N course_students
students 1 -- N student_face_images
students 1 -- N face_templates
students 1 -- N attendance_records

courses 1 -- N course_students
courses 1 -- N attendance_sessions
courses 1 -- N attendance_records

attendance_sessions 1 -- N attendance_records
group_photo_records 1 -- N group_photo_record_students
```

当前代码大量使用业务学号 `students.student_id` 作为学生关联键；课程和教师使用内部 `id`。

## 核心主数据

### `teachers`

教师主数据。

| 字段 | 说明 |
| --- | --- |
| `id` | 教师内部 ID |
| `teacher_no` | 教师编号，唯一 |
| `name` | 教师姓名 |
| `department` / `phone` / `email` | 可选资料 |
| `is_active` | 是否启用 |
| `created_at` / `updated_at` | 创建和更新时间 |

### `students`

学生主数据。

| 字段 | 说明 |
| --- | --- |
| `id` | 学生内部 ID |
| `student_id` | 学号，唯一，业务关联键 |
| `name` | 姓名 |
| `class_name` / `major` / `gender` | 班级、专业、性别 |
| `phone` / `email` | 联系方式 |
| `has_face_image` | 是否有有效照片 |
| `active_face_image_count` | 当前有效照片数 |
| `latest_face_image_id` | 最新有效照片 ID |
| `owner_teacher_id` | 创建或维护该学生的教师 |
| `is_active` | 是否启用 |
| `created_at` / `updated_at` | 创建和更新时间 |

### `users`

登录账号表。教师账号通过 `teacher_id` 关联教师，学生账号通过 `student_id` 关联学号。

| 字段 | 说明 |
| --- | --- |
| `id` | 账号 ID |
| `username` | 登录名，唯一 |
| `password_hash` | 密码哈希 |
| `role` | `teacher` 或 `student` |
| `full_name` | 展示姓名 |
| `teacher_id` | 教师账号关联 |
| `student_id` | 学生账号关联 |
| `is_active` | 是否启用 |
| `last_login_at` | 最近登录时间 |
| `created_at` / `updated_at` | 创建和更新时间 |

## 课程与名单

### `courses`

课程表，一门课程属于一个教师。

| 字段 | 说明 |
| --- | --- |
| `id` | 课程 ID |
| `course_name` | 课程名称 |
| `teacher_id` | 所属教师 |
| `term` | 学期 |
| `description` | 课程说明 |
| `status` | `active` / `deleted` 等状态 |
| `created_at` / `updated_at` | 创建和更新时间 |

### `course_students`

课程名单表，只记录“某课程包含哪些已有学生”。

| 字段 | 说明 |
| --- | --- |
| `id` | 关系 ID |
| `course_id` | 课程 ID |
| `student_id` | 学号 |
| `enroll_status` | `active` 或 `removed` |
| `source` | `manual`、`student_import` 等来源 |
| `added_by_teacher_id` | 添加操作教师 |
| `joined_at` / `removed_at` | 加入和移出时间 |
| `created_at` / `updated_at` | 创建和更新时间 |

唯一约束保证同一课程同一学号最多只有一条 active 名单关系。

## 照片与人脸模板

### `student_face_images`

学生照片元数据，文件本体保存在 `backend/uploads/enroll/`。

| 字段 | 说明 |
| --- | --- |
| `id` | 照片 ID |
| `student_id` | 学号 |
| `file_path` | 文件路径 |
| `file_hash` | 文件哈希 |
| `original_filename` | 原始文件名 |
| `source` | 上传来源 |
| `uploaded_by_role` / `uploaded_by_id` | 上传者信息 |
| `quality_score` | 质量分 |
| `is_active` | 是否有效 |
| `deleted_at` | 软删除时间 |
| `created_at` / `updated_at` | 创建和更新时间 |

### `face_templates`

人脸特征模板。识别时只使用 active 模板。

| 字段 | 说明 |
| --- | --- |
| `id` | 模板 ID |
| `student_id` | 学号 |
| `face_image_id` | 来源照片 ID |
| `image_path` | 来源图片路径 |
| `embedding` | 特征向量序列化内容 |
| `algorithm` | 算法名称，如 `mock` 或 `deepface-ArcFace` |
| `algorithm_version` | 算法版本 |
| `quality_score` | 模板质量分 |
| `is_active` | 是否有效 |
| `created_at` / `updated_at` | 创建和更新时间 |

同一学生当前只保留一张有效照片和一份有效模板；重复录入会停用旧数据。

## 考勤

### `attendance_sessions`

教师发起的一次考勤场次。

| 字段 | 说明 |
| --- | --- |
| `id` | 场次 ID |
| `course_id` | 课程 ID |
| `teacher_id` | 发起教师 |
| `title` | 考勤标题 |
| `status` | 场次状态 |
| `start_time` / `end_time` | 开始和结束时间 |
| `is_closed` | 是否关闭 |
| `expected_count` | 应签到人数 |
| `checked_count` | 成功签到人数 |
| `absent_count` | 缺勤人数 |
| `failed_count` | 失败人数 |
| `unknown_count` | 未知人数 |
| `created_at` / `updated_at` | 创建和更新时间 |

### `attendance_records`

考勤明细表。创建场次时会为课程 active 名单中的每个学生生成一条 pending 记录。

| 字段 | 说明 |
| --- | --- |
| `id` | 明细 ID |
| `session_id` | 场次 ID |
| `course_id` | 课程 ID |
| `teacher_id` | 教师 ID |
| `student_id` | 学号 |
| `name` | 学生姓名快照 |
| `status` | `pending`、`present`、`late`、`absent`、`failed`、`unknown` |
| `is_checked_in` | 是否有效签到 |
| `checkin_time` / `submit_time` | 签到成功时间和提交时间 |
| `liveness_passed` / `liveness_score` | 活体结果 |
| `face_score` | 人脸匹配分 |
| `emotion` / `emotion_confidence` | 情绪结果 |
| `emotion_error_code` / `emotion_message` | 情绪分析错误信息 |
| `image_path` | 提交图片路径 |
| `used_face_image_id` / `used_face_template_id` | 本次匹配使用的数据 |
| `fail_reason` | 失败原因 |
| `created_at` / `updated_at` | 创建和更新时间 |

### `liveness_challenges`

活体挑战历史表，保留兼容数据。当前主要活体验证由前端完成，后端在签到时接收前端结果。

## 合照与活动

### `group_photo_records`

一次合照识别记录。

| 字段 | 说明 |
| --- | --- |
| `id` | 记录 ID |
| `teacher_id` | 发起教师 |
| `course_id` | 可选课程筛选 |
| `activity_name` / `activity_date` | 活动名称和日期 |
| `description` | 备注 |
| `photo_path` | 原图路径 |
| `annotated_image_path` | 标注图路径 |
| `total_faces` / `matched_count` / `unknown_count` | 识别统计 |
| `recognized_student_count` | 识别成功学生数 |
| `emotion_summary` | 情绪汇总 JSON |
| `emotion_analyzed_count` / `emotion_failed_count` | 情绪分析统计 |
| `created_at` | 创建时间 |

### `group_photo_record_students`

合照中识别成功的学生明细。

| 字段 | 说明 |
| --- | --- |
| `id` | 明细 ID |
| `record_id` | 合照记录 ID |
| `teacher_id` | 教师 ID |
| `student_id` | 学号 |
| `name` / `class_name` / `major` | 学生信息快照 |
| `face_score` | 人脸匹配分 |
| `face_image_id` / `face_template_id` | 使用的数据 |
| `emotion` / `emotion_confidence` | 情绪结果 |
| `emotion_error_code` / `emotion_message` | 情绪错误信息 |
| `bbox` | 人脸框 JSON |
| `created_at` | 创建时间 |

### 兼容活动表

`activities`、`group_photos`、`activity_participants` 为早期活动/合照流程保留。当前合照识别主流程优先使用 `group_photo_records` 和 `group_photo_record_students`。

## 情绪流水

### `emotion_records`

统一保存单人考勤和合照识别产生的情绪结果。

| 字段 | 说明 |
| --- | --- |
| `id` | 流水 ID |
| `student_id` | 学号 |
| `name` | 姓名快照 |
| `course_id` | 课程 ID |
| `source_type` | `attendance` 或 `group_photo` |
| `source_id` | 来源业务记录 ID |
| `emotion` | 情绪类型 |
| `confidence` | 置信度 |
| `record_time` | 识别时间 |
| `created_at` | 创建时间 |

查询统计时优先聚合 `emotion_records`；展示具体考勤或合照详情时直接读取业务表中的冗余情绪字段。

## 清理原则

提交项目前可清理运行时数据，但不要删除表结构和默认账号：

- 保留 `users.teacher`
- 保留 `teachers.teacher`
- 保留 `courses.Default Course`
- 清空学生、照片、人脸模板、考勤、合照、情绪等业务数据
- 删除 `backend/uploads/` 和 `backend/data/annotated/` 下的运行时文件，保留目录和 `.gitkeep`

