# 班级考勤系统数据库重新设计说明

## 1. 设计目标

本设计面向“内容安全实验课班级考勤系统”，重点解决以下问题：

1. 教师信息、学生信息应当作为独立主数据存在，不依赖课程、账号、考勤等业务表。
2. 教师拥有课程，课程拥有学生名单；课程下可以创建多次考勤，每次考勤可以完整记录所有学生是否参与考勤。
3. 教师和学生都能按“全部 / 某门课 / 某次考勤”查询和导出自己的相关考勤记录。
4. 学生信息需要保存是否已录入照片，并在录入或删除照片后及时更新。
5. 学生本人需要有录入照片、查看照片、删除照片的接口。
6. 学生照片库需要能清晰地参与到考勤识别流程中。

核心思路：

- `teachers` 和 `students` 是独立主表。
- 登录账号在当前代码中仍使用既有 `users` 表承载；它现在只作为认证表使用，并通过 `teacher_id` 或 `student_id` 关联教师/学生主数据。
- 课程和学生名单分离，使用 `course_students` 表表示某门课有哪些学生。
- 每次考勤创建一个 `attendance_sessions`，并为课程名单中的每个学生生成一条 `attendance_records`。
- 学生照片和人脸特征分离，照片保存到 `student_face_images`，算法特征保存到 `face_templates`。
- 考勤识别时，只使用当前课程学生名单中的有效人脸模板进行比对。

## 2. 表关系总览

```text
teachers
  1 ── N courses

students
  1 ── N course_students
  1 ── N student_face_images
  1 ── N face_templates
  1 ── N attendance_records

courses
  N ── N students，通过 course_students
  1 ── N attendance_sessions

attendance_sessions
  1 ── N attendance_records

student_face_images
  1 ── N face_templates
```

可选扩展：

```text
attendance_records
  1 ── N emotion_records

attendance_sessions
  1 ── N liveness_challenges
```

## 3. 推荐核心表

### 3.1 教师表 `teachers`

教师是独立主数据，不依赖账号表、课程表或考勤表。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 教师内部 ID |
| `teacher_no` | VARCHAR(64) | UNIQUE, NOT NULL | 教师工号或教师编号 |
| `name` | VARCHAR(64) | NOT NULL | 教师姓名 |
| `department` | VARCHAR(128) | NULL | 所属学院或部门 |
| `phone` | VARCHAR(32) | NULL | 联系方式 |
| `email` | VARCHAR(128) | NULL | 邮箱 |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | 是否启用 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| `updated_at` | DATETIME | NOT NULL | 更新时间 |

建议：

- 不直接在教师表里保存密码。
- 教师删除建议使用 `is_active = false`，不要物理删除，否则历史课程和考勤归属会丢失。

### 3.2 学生表 `students`

学生也是独立主数据，不依赖课程或考勤。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 学生内部 ID |
| `student_no` | VARCHAR(64) | UNIQUE, NOT NULL | 学号 |
| `name` | VARCHAR(64) | NOT NULL | 姓名 |
| `class_name` | VARCHAR(128) | NULL | 班级 |
| `major` | VARCHAR(128) | NULL | 专业 |
| `gender` | VARCHAR(16) | NULL | 性别 |
| `phone` | VARCHAR(32) | NULL | 联系方式 |
| `email` | VARCHAR(128) | NULL | 邮箱 |
| `has_face_image` | BOOLEAN | NOT NULL, DEFAULT FALSE | 是否已录入有效照片 |
| `active_face_image_count` | INTEGER | NOT NULL, DEFAULT 0 | 当前有效照片数量，业务上只允许 0 或 1 |
| `latest_face_image_id` | INTEGER | NULL | 最新有效照片 ID |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | 是否启用 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| `updated_at` | DATETIME | NOT NULL | 更新时间 |

建议：

- `has_face_image` 可以由 `student_face_images` 动态计算，也可以像这里一样冗余保存。为了前端列表展示更快，建议保留该字段。
- 录入或删除照片后必须在同一个事务中更新 `has_face_image`、`active_face_image_count`、`latest_face_image_id`。
- 学生照片库按“每个学生最多 1 张当前有效照片”设计；重复录入时自动停用旧照片和旧模板，以最后一次成功录入的照片为准。

### 3.3 登录账号表 `users`

账号表只负责登录认证，教师和学生的真实信息分别存放在 `teachers`、`students`。当前项目为了兼容已有代码和本地数据库，继续使用原表名 `users`；从设计语义上看，它等价于认证账号表。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 账号 ID |
| `username` | VARCHAR(64) | UNIQUE, NOT NULL | 登录用户名 |
| `password_hash` | VARCHAR(255) | NOT NULL | 密码哈希 |
| `role` | VARCHAR(16) | NOT NULL | `teacher` 或 `student` |
| `teacher_id` | INTEGER | FK, NULL | 教师账号关联教师 |
| `student_id` | INTEGER | FK, NULL | 学生账号关联学生 |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | 是否启用 |
| `last_login_at` | DATETIME | NULL | 最近登录时间 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| `updated_at` | DATETIME | NOT NULL | 更新时间 |

约束建议：

- `role = 'teacher'` 时必须有 `teacher_id`，且 `student_id` 为空。
- `role = 'student'` 时必须有 `student_id`，且 `teacher_id` 为空。
- 可用代码层校验，也可用数据库 `CHECK` 约束实现。

### 3.4 课程表 `courses`

一门课程属于一个教师。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 课程 ID |
| `teacher_id` | INTEGER | FK, NOT NULL | 所属教师 |
| `course_code` | VARCHAR(64) | NULL | 课程编号 |
| `course_name` | VARCHAR(128) | NOT NULL | 课程名称 |
| `term` | VARCHAR(64) | NULL | 学期，如 `2026春` |
| `description` | TEXT | NULL | 课程说明 |
| `status` | VARCHAR(16) | NOT NULL, DEFAULT `active` | `active`、`archived` |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| `updated_at` | DATETIME | NOT NULL | 更新时间 |

索引建议：

- `idx_courses_teacher_id`
- `idx_courses_teacher_term`

### 3.5 课程学生名单表 `course_students`

课程和学生是多对多关系。学生可以属于多门课，一门课也有多个学生。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 关系 ID |
| `course_id` | INTEGER | FK, NOT NULL | 课程 ID |
| `student_id` | INTEGER | FK, NOT NULL | 学生 ID |
| `enroll_status` | VARCHAR(16) | NOT NULL, DEFAULT `active` | `active`、`removed` |
| `source` | VARCHAR(32) | NOT NULL, DEFAULT `manual` | 加入来源：`manual`、`xlsx_import` |
| `added_by_teacher_id` | INTEGER | FK, NULL | 执行添加的教师 |
| `joined_at` | DATETIME | NOT NULL | 加入课程时间 |
| `removed_at` | DATETIME | NULL | 移出课程时间 |
| `updated_at` | DATETIME | NOT NULL | 更新时间 |

约束建议：

- `UNIQUE(course_id, student_id) WHERE enroll_status = 'active'`

设计原因：

- 不把学生直接挂在教师下面，而是通过课程名单关联。
- 课程名单只能引用已经存在于 `students` 学生库的学生；选择已有学生、手输学号、Excel 导入学号本质上都是写入 `course_students`。
- `students` 负责学生主数据，`course_students` 只负责“这门课有哪些学生”。
- 历史考勤记录依旧保留，即使学生后来从课程中移出。

## 4. 考勤相关表

### 4.1 考勤场次表 `attendance_sessions`

教师在某门课下发起一次考勤，就创建一条场次记录。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 考勤场次 ID |
| `course_id` | INTEGER | FK, NOT NULL | 所属课程 |
| `teacher_id` | INTEGER | FK, NOT NULL | 发起教师，冗余保存便于查询 |
| `title` | VARCHAR(128) | NOT NULL | 考勤标题 |
| `start_time` | DATETIME | NOT NULL | 考勤开始时间 |
| `end_time` | DATETIME | NULL | 考勤结束时间 |
| `is_closed` | BOOLEAN | NOT NULL, DEFAULT FALSE | 是否已结束 |
| `status` | VARCHAR(16) | NOT NULL, DEFAULT `active` | `active`、`closed`、`cancelled` |
| `expected_count` | INTEGER | NOT NULL, DEFAULT 0 | 应考勤人数 |
| `checked_count` | INTEGER | NOT NULL, DEFAULT 0 | 已成功考勤人数 |
| `absent_count` | INTEGER | NOT NULL, DEFAULT 0 | 缺勤人数 |
| `failed_count` | INTEGER | NOT NULL, DEFAULT 0 | 活体或识别失败人数 |
| `unknown_count` | INTEGER | NOT NULL, DEFAULT 0 | 未匹配身份次数 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| `updated_at` | DATETIME | NOT NULL | 更新时间 |

建议：

- 创建考勤场次时，读取 `course_students` 中 `active` 的学生名单。
- 同时为每个学生创建一条 `attendance_records`，初始状态为 `pending`。
- 考勤结束时，将仍为 `pending` 的记录改为 `absent`，并更新统计人数。

### 4.2 学生考勤明细表 `attendance_records`

该表是查询和导出的核心表。每次考勤中，每个学生都应有一条记录。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 明细 ID |
| `session_id` | INTEGER | FK, NOT NULL | 考勤场次 |
| `course_id` | INTEGER | FK, NOT NULL | 课程 ID，冗余保存便于查询 |
| `teacher_id` | INTEGER | FK, NOT NULL | 教师 ID，冗余保存便于查询 |
| `student_id` | INTEGER | FK, NOT NULL | 学生 ID |
| `status` | VARCHAR(16) | NOT NULL, DEFAULT `pending` | 考勤状态 |
| `is_checked_in` | BOOLEAN | NOT NULL, DEFAULT FALSE | 是否完成有效考勤 |
| `checkin_time` | DATETIME | NULL | 学生成功考勤时间 |
| `submit_time` | DATETIME | NULL | 文件提交时间 |
| `liveness_passed` | BOOLEAN | NULL | 活体是否通过 |
| `liveness_score` | FLOAT | NULL | 活体分数 |
| `face_score` | FLOAT | NULL | 人脸匹配分数 |
| `emotion` | VARCHAR(32) | NULL | 当次识别到的情绪 |
| `capture_file_path` | VARCHAR(255) | NULL | 考勤提交文件路径 |
| `used_face_image_id` | INTEGER | FK, NULL | 匹配到的照片 ID |
| `used_face_template_id` | INTEGER | FK, NULL | 匹配到的模板 ID |
| `fail_reason` | VARCHAR(255) | NULL | 失败原因 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| `updated_at` | DATETIME | NOT NULL | 更新时间 |

状态建议：

| 状态 | 说明 |
| --- | --- |
| `pending` | 考勤进行中，学生尚未提交 |
| `present` | 正常考勤成功 |
| `late` | 迟到但识别成功 |
| `absent` | 考勤结束后仍未提交 |
| `failed` | 已提交但活体或识别失败 |
| `unknown` | 识别到人脸但无法匹配学生 |
| `cancelled` | 本次场次取消 |

约束建议：

- `UNIQUE(session_id, student_id)`，保证一次考勤中每个学生只有一条结果。

索引建议：

- `idx_attendance_records_teacher_course`
- `idx_attendance_records_student_course`
- `idx_attendance_records_session`
- `idx_attendance_records_checkin_time`

## 5. 照片库与人脸特征表

### 5.1 学生照片表 `student_face_images`

保存学生上传或教师导入的照片元数据。图片文件本身仍存储在磁盘或对象存储中，数据库只保存路径和元信息。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 照片 ID |
| `student_id` | INTEGER | FK, NOT NULL | 所属学生 |
| `file_path` | VARCHAR(255) | NOT NULL | 文件保存路径 |
| `file_hash` | VARCHAR(64) | NULL | 文件哈希，用于去重 |
| `original_filename` | VARCHAR(255) | NULL | 原始文件名 |
| `source` | VARCHAR(32) | NOT NULL | `student_upload`、`teacher_upload`、`batch_import` |
| `uploaded_by_role` | VARCHAR(16) | NOT NULL | 上传者角色 |
| `uploaded_by_id` | INTEGER | NULL | 上传者 ID |
| `quality_score` | FLOAT | NULL | 照片质量分 |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | 是否有效 |
| `deleted_at` | DATETIME | NULL | 删除时间 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| `updated_at` | DATETIME | NOT NULL | 更新时间 |

建议：

- 删除照片建议软删除：`is_active = false`，保留历史记录，避免历史考勤记录中的 `used_face_image_id` 失效。
- 如果学生删除的是最后一张有效照片，要同步更新 `students.has_face_image = false`。

### 5.2 人脸模板表 `face_templates`

保存算法生成的人脸特征。这样后续替换算法时，可以按版本重新生成模板。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 模板 ID |
| `student_id` | INTEGER | FK, NOT NULL | 所属学生 |
| `face_image_id` | INTEGER | FK, NOT NULL | 来源照片 |
| `embedding` | TEXT / BLOB | NOT NULL | 人脸特征向量 |
| `algorithm` | VARCHAR(64) | NOT NULL | 算法名称 |
| `algorithm_version` | VARCHAR(64) | NOT NULL | 算法版本 |
| `quality_score` | FLOAT | NULL | 特征质量 |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | 是否有效 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| `updated_at` | DATETIME | NOT NULL | 更新时间 |

建议：

- 识别时只使用 `is_active = true` 的模板。
- 删除照片时，该照片对应的模板也要置为无效。
- 如果算法升级，不要覆盖旧模板，可以创建新版本模板，方便回滚和对比准确率。

## 6. 活体、情绪和合照扩展表

### 6.1 活体挑战表 `liveness_challenges`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 挑战 ID |
| `challenge_id` | VARCHAR(64) | UNIQUE, NOT NULL | 前端使用的挑战字符串 |
| `session_id` | INTEGER | FK, NOT NULL | 所属考勤场次 |
| `student_id` | INTEGER | FK, NULL | 可选，指定学生 |
| `actions` | TEXT | NOT NULL | 活体动作 JSON |
| `expire_at` | DATETIME | NOT NULL | 过期时间 |
| `used` | BOOLEAN | NOT NULL, DEFAULT FALSE | 是否已使用 |
| `used_at` | DATETIME | NULL | 使用时间 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |

### 6.2 情绪记录表 `emotion_records`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 情绪记录 ID |
| `student_id` | INTEGER | FK, NOT NULL | 学生 ID |
| `course_id` | INTEGER | FK, NULL | 课程 ID |
| `source_type` | VARCHAR(32) | NOT NULL | `attendance` 或 `group_photo` |
| `source_id` | INTEGER | NOT NULL | 来源记录 ID |
| `emotion` | VARCHAR(32) | NOT NULL | 情绪类型 |
| `confidence` | FLOAT | NULL | 置信度 |
| `record_time` | DATETIME | NOT NULL | 识别时间 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |

### 6.3 合照活动表，可继续保留

如果课程设计继续包含合照识别，建议保留：

- `activities`：活动信息。
- `group_photos`：合照文件及识别汇总。
- `activity_participants`：合照中识别出的学生名单。

建议在 `activity_participants` 中补充：

- `course_id`
- `teacher_id`
- `student_id`
- `face_image_id`
- `face_template_id`

这样后续查询“某学生参与过哪些活动”会更简单。

## 7. 推荐查询能力

### 7.1 教师查询某门课所有考勤

查询条件：

```text
teacher_id = 当前教师
course_id = 指定课程
```

查询表：

- `attendance_sessions`
- `attendance_records`
- `students`

用途：

- 查看每次考勤概览。
- 查看某门课所有学生的考勤明细。
- 导出某门课全部考勤记录。

### 7.2 教师查询某门课某次考勤

查询条件：

```text
teacher_id = 当前教师
course_id = 指定课程
session_id = 指定考勤场次
```

结果字段建议：

- 考勤标题
- 开始时间
- 结束时间
- 学号
- 姓名
- 状态
- 是否考勤
- 考勤时间
- 活体分数
- 人脸分数
- 情绪
- 失败原因

### 7.3 教师查询自己相关的所有考勤

查询条件：

```text
teacher_id = 当前教师
```

适合做教师端“全部考勤记录”页面。

### 7.4 学生查询某门课所有考勤

查询条件：

```text
student_id = 当前学生
course_id = 指定课程
```

学生只能看到自己的记录，不能看到同课其他学生记录。

### 7.5 学生查询自己所有相关考勤

查询条件：

```text
student_id = 当前学生
```

适合学生端“我的考勤”页面。

## 8. 导出 XLSX 设计建议

可以统一设计一个导出接口，也可以按角色拆分。

### 8.1 教师导出

建议接口：

```http
GET /api/attendance/export?course_id=1
GET /api/attendance/export?course_id=1&session_id=10
GET /api/attendance/export?student_id=3
```

权限：

- 教师只能导出自己课程下的记录。

导出列：

| 列名 | 来源 |
| --- | --- |
| 课程名称 | `courses.course_name` |
| 考勤标题 | `attendance_sessions.title` |
| 开始时间 | `attendance_sessions.start_time` |
| 结束时间 | `attendance_sessions.end_time` |
| 学号 | `students.student_no` |
| 姓名 | `students.name` |
| 状态 | `attendance_records.status` |
| 是否考勤 | `attendance_records.is_checked_in` |
| 考勤时间 | `attendance_records.checkin_time` |
| 活体通过 | `attendance_records.liveness_passed` |
| 活体分数 | `attendance_records.liveness_score` |
| 人脸分数 | `attendance_records.face_score` |
| 情绪 | `attendance_records.emotion` |
| 失败原因 | `attendance_records.fail_reason` |

### 8.2 学生导出

建议接口：

```http
GET /api/me/attendance/export
GET /api/me/attendance/export?course_id=1
GET /api/me/attendance/export?course_id=1&session_id=10
```

权限：

- 学生只能导出自己的考勤记录。

## 9. 学生照片 API 建议

### 9.1 学生上传本人照片

```http
POST /api/me/face-images
Content-Type: multipart/form-data
```

字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `file` | 是 | 人脸照片 |

后端处理：

1. 保存图片文件。
2. 检查图片格式和大小。
3. 检测是否有人脸，最好只允许单人脸。
4. 计算照片质量分。
5. 停用该学生已有的有效 `student_face_images` 和 `face_templates`。
6. 写入新的 `student_face_images`。
7. 调用算法生成新的 `face_templates`。
8. 更新 `students.has_face_image`、`active_face_image_count`、`latest_face_image_id`。

### 9.2 学生查看本人照片列表

```http
GET /api/me/face-images
```

只返回当前学生自己的有效照片。按当前设计，该列表最多只有 1 条。

### 9.3 学生删除本人照片

```http
DELETE /api/me/face-images/{image_id}
```

后端处理：

1. 校验该照片属于当前学生。
2. 将 `student_face_images.is_active` 改为 `false`。
3. 将该照片对应的 `face_templates.is_active` 改为 `false`。
4. 重新统计该学生有效照片数量。
5. 更新 `students.has_face_image`。

注意：

- 不建议直接删除磁盘文件和数据库记录，因为历史考勤可能引用这张照片。
- 如果确实需要物理删除，应保证历史考勤只保存识别结果，不再依赖该文件路径。

### 9.4 教师管理学生照片

建议保留教师接口：

```http
POST /api/students/{student_id}/face-images
GET /api/students/{student_id}/face-images
DELETE /api/students/{student_id}/face-images/{image_id}
```

教师只能管理自己课程名单中的学生。

## 10. 照片库如何应用到考勤

推荐流程如下：

### 10.1 录入阶段

1. 学生本人上传照片，或教师为学生上传照片。
2. 后端保存照片到 `uploads/enroll` 或对象存储。
3. 后端停用该学生旧的有效照片和模板。
4. 后端写入新的 `student_face_images`。
5. 人脸算法从照片提取 embedding。
6. 后端写入新的 `face_templates`。
7. 更新 `students.has_face_image = true`。

### 10.2 考勤开始阶段

1. 教师创建考勤场次。
2. 后端查询当前课程的 `active` 学生名单。
3. 在 `attendance_sessions` 中创建一条场次。
4. 为名单中每个学生创建一条 `attendance_records`，状态为 `pending`。
5. 后端可以预加载该课程所有学生的有效 `face_templates`，形成该场次的人脸库。

### 10.3 学生提交考勤阶段

1. 学生获取活体挑战。
2. 前端采集视频或图片。
3. 后端先做活体检测。
4. 活体通过后，从提交文件中提取人脸 embedding。
5. 只在当前课程学生名单的人脸模板中做比对。
6. 如果匹配分数达到阈值，更新该学生在本场次的 `attendance_records`：
   - `status = present`
   - `is_checked_in = true`
   - `checkin_time = 当前时间`
   - `used_face_image_id`
   - `used_face_template_id`
   - `face_score`
   - `liveness_score`
7. 如果活体失败，记录为 `failed`。
8. 如果人脸无法匹配，记录为 `unknown` 或写入单独的异常记录。

### 10.4 考勤结束阶段

1. 教师关闭考勤。
2. 后端将仍为 `pending` 的学生记录改为 `absent`。
3. 更新 `attendance_sessions` 的统计字段：
   - `checked_count`
   - `absent_count`
   - `failed_count`
   - `unknown_count`
   - `end_time`
   - `is_closed = true`

## 11. 推荐 SQL DDL 草案

下面是偏 SQLite 的理想范式建表草案，后续可以继续向整数外键版本演进。当前代码为了兼容已有接口和本地旧库，保留了 `users` 作为认证表名，并继续使用 `students.student_id` 作为学号和课程名单关联键；核心关系、字段和业务流程已经按本文设计落地。

```sql
CREATE TABLE teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_no VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(64) NOT NULL,
    department VARCHAR(128),
    phone VARCHAR(32),
    email VARCHAR(128),
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_no VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(64) NOT NULL,
    class_name VARCHAR(128),
    major VARCHAR(128),
    gender VARCHAR(16),
    phone VARCHAR(32),
    email VARCHAR(128),
    has_face_image BOOLEAN NOT NULL DEFAULT 0,
    active_face_image_count INTEGER NOT NULL DEFAULT 0,
    latest_face_image_id INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE auth_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(16) NOT NULL,
    teacher_id INTEGER,
    student_id INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    last_login_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id),
    FOREIGN KEY (student_id) REFERENCES students(id),
    CHECK (
        (role = 'teacher' AND teacher_id IS NOT NULL AND student_id IS NULL)
        OR
        (role = 'student' AND student_id IS NOT NULL AND teacher_id IS NULL)
    )
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    course_code VARCHAR(64),
    course_name VARCHAR(128) NOT NULL,
    term VARCHAR(64),
    description TEXT,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id)
);

CREATE TABLE course_students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    enroll_status VARCHAR(16) NOT NULL DEFAULT 'active',
    source VARCHAR(32) NOT NULL DEFAULT 'manual',
    added_by_teacher_id INTEGER,
    joined_at DATETIME NOT NULL,
    removed_at DATETIME,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (course_id) REFERENCES courses(id),
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (added_by_teacher_id) REFERENCES teachers(id)
);

CREATE UNIQUE INDEX ux_course_students_active_course_student
ON course_students(course_id, student_id)
WHERE enroll_status = 'active';

CREATE TABLE student_face_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64),
    original_filename VARCHAR(255),
    source VARCHAR(32) NOT NULL,
    uploaded_by_role VARCHAR(16) NOT NULL,
    uploaded_by_id INTEGER,
    quality_score FLOAT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    deleted_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id)
);

CREATE TABLE face_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    face_image_id INTEGER NOT NULL,
    embedding TEXT NOT NULL,
    algorithm VARCHAR(64) NOT NULL,
    algorithm_version VARCHAR(64) NOT NULL,
    quality_score FLOAT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (face_image_id) REFERENCES student_face_images(id)
);

CREATE TABLE attendance_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    title VARCHAR(128) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    is_closed BOOLEAN NOT NULL DEFAULT 0,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    expected_count INTEGER NOT NULL DEFAULT 0,
    checked_count INTEGER NOT NULL DEFAULT 0,
    absent_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    unknown_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (course_id) REFERENCES courses(id),
    FOREIGN KEY (teacher_id) REFERENCES teachers(id)
);

CREATE TABLE attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    is_checked_in BOOLEAN NOT NULL DEFAULT 0,
    checkin_time DATETIME,
    submit_time DATETIME,
    liveness_passed BOOLEAN,
    liveness_score FLOAT,
    face_score FLOAT,
    emotion VARCHAR(32),
    capture_file_path VARCHAR(255),
    used_face_image_id INTEGER,
    used_face_template_id INTEGER,
    fail_reason VARCHAR(255),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (session_id) REFERENCES attendance_sessions(id),
    FOREIGN KEY (course_id) REFERENCES courses(id),
    FOREIGN KEY (teacher_id) REFERENCES teachers(id),
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (used_face_image_id) REFERENCES student_face_images(id),
    FOREIGN KEY (used_face_template_id) REFERENCES face_templates(id),
    UNIQUE (session_id, student_id)
);

CREATE TABLE liveness_challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id VARCHAR(64) NOT NULL UNIQUE,
    session_id INTEGER NOT NULL,
    student_id INTEGER,
    actions TEXT NOT NULL,
    expire_at DATETIME NOT NULL,
    used BOOLEAN NOT NULL DEFAULT 0,
    used_at DATETIME,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (session_id) REFERENCES attendance_sessions(id),
    FOREIGN KEY (student_id) REFERENCES students(id)
);

CREATE TABLE emotion_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER,
    source_type VARCHAR(32) NOT NULL,
    source_id INTEGER NOT NULL,
    emotion VARCHAR(32) NOT NULL,
    confidence FLOAT,
    record_time DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE INDEX idx_courses_teacher_id ON courses(teacher_id);
CREATE INDEX idx_course_students_course_id ON course_students(course_id);
CREATE INDEX idx_course_students_student_id ON course_students(student_id);
CREATE INDEX idx_face_images_student_id ON student_face_images(student_id);
CREATE INDEX idx_face_templates_student_id ON face_templates(student_id);
CREATE INDEX idx_attendance_sessions_course_id ON attendance_sessions(course_id);
CREATE INDEX idx_attendance_sessions_teacher_id ON attendance_sessions(teacher_id);
CREATE INDEX idx_attendance_records_session_id ON attendance_records(session_id);
CREATE INDEX idx_attendance_records_teacher_course ON attendance_records(teacher_id, course_id);
CREATE INDEX idx_attendance_records_student_course ON attendance_records(student_id, course_id);
```

## 12. 后续实现建议

### 12.1 从当前项目迁移时的建议顺序

1. 新增 `teachers` 表，把现有教师账号中的教师信息迁移过去。
2. 当前代码保留 `students.student_id` 作为业务学号和关联键，后续如需更严格范式，可再迁移为内部整数外键。
3. 当前代码保留 `users` 表作为认证表，并新增 `teacher_id`。
4. 调整 `courses`，明确 `teacher_id` 指向独立教师身份。
5. 调整 `course_students`，增加 `enroll_status`，用软移除保留历史。
6. 调整考勤逻辑：创建场次时立即为名单内所有学生创建 `attendance_records`。
7. 新增 `student_face_images`，把照片和人脸模板拆开。
8. 所有查询和导出接口统一从 `attendance_records` 读取。

### 12.2 可以补充的能力

- 考勤迟到规则：在 `attendance_sessions` 增加 `late_after_minutes`。
- 请假记录：新增 `leave_requests` 表，状态包括 `pending`、`approved`、`rejected`。
- 审计日志：新增 `audit_logs`，记录教师删除照片、修改学生、关闭考勤等关键操作。
- 文件元信息统一管理：新增 `uploaded_files` 表，统一保存上传文件路径、大小、哈希和 MIME 类型。
- 数据隐私：学生照片只给本人和有课程关系的教师访问，导出时避免导出照片路径。
- 识别阈值配置：新增 `algorithm_configs`，保存人脸相似度阈值、活体阈值、算法版本。

## 13. 结论

推荐的新设计把“人、课、名单、场次、明细、照片、模板”拆开：

- 教师和学生作为独立主数据，结构更稳定。
- 课程名单和考勤记录分离，可以保留完整历史。
- 每次考勤给每个学生生成明细，天然支持“是否考勤”和导出。
- 照片库与人脸模板分离，方便学生自助录入、删除和算法升级。
- 教师和学生查询权限可以通过 `teacher_id`、`student_id`、`course_id` 三个维度稳定控制。
