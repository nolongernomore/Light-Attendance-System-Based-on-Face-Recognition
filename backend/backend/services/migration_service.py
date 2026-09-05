from database import engine


SQLITE_COLUMNS = {
    "users": {
        "full_name": "VARCHAR",
        "teacher_id": "INTEGER",
        "is_active": "BOOLEAN DEFAULT 1",
        "last_login_at": "DATETIME",
        "updated_at": "DATETIME",
    },
    "students": {
        "major": "VARCHAR",
        "phone": "VARCHAR",
        "email": "VARCHAR",
        "has_face_image": "BOOLEAN DEFAULT 0",
        "active_face_image_count": "INTEGER DEFAULT 0",
        "latest_face_image_id": "INTEGER",
        "is_active": "BOOLEAN DEFAULT 1",
        "owner_teacher_id": "INTEGER",
    },
    "courses": {
        "term": "VARCHAR",
        "status": "VARCHAR DEFAULT 'active'",
        "updated_at": "DATETIME",
    },
    "course_students": {
        "enroll_status": "VARCHAR DEFAULT 'active'",
        "source": "VARCHAR DEFAULT 'manual'",
        "added_by_teacher_id": "INTEGER",
        "joined_at": "DATETIME",
        "removed_at": "DATETIME",
        "updated_at": "DATETIME",
    },
    "face_templates": {
        "face_image_id": "INTEGER",
        "algorithm": "VARCHAR DEFAULT 'mock'",
        "algorithm_version": "VARCHAR DEFAULT 'v1'",
        "is_active": "BOOLEAN DEFAULT 1",
        "updated_at": "DATETIME",
    },
    "liveness_challenges": {
        "session_id": "INTEGER",
        "student_id": "VARCHAR",
        "used_at": "DATETIME",
    },
    "attendance_sessions": {
        "is_closed": "BOOLEAN DEFAULT 0",
        "expected_count": "INTEGER DEFAULT 0",
        "checked_count": "INTEGER DEFAULT 0",
        "absent_count": "INTEGER DEFAULT 0",
        "failed_count": "INTEGER DEFAULT 0",
        "unknown_count": "INTEGER DEFAULT 0",
        "updated_at": "DATETIME",
    },
    "attendance_records": {
        "session_id": "INTEGER",
        "course_id": "INTEGER",
        "teacher_id": "INTEGER",
        "submit_time": "DATETIME",
        "is_checked_in": "BOOLEAN DEFAULT 0",
        "emotion_confidence": "FLOAT",
        "emotion_error_code": "VARCHAR",
        "emotion_message": "TEXT",
        "used_face_image_id": "INTEGER",
        "used_face_template_id": "INTEGER",
        "fail_reason": "VARCHAR",
        "updated_at": "DATETIME",
    },
    "activities": {
        "course_id": "INTEGER",
        "teacher_id": "INTEGER",
    },
    "activity_participants": {
        "course_id": "INTEGER",
        "teacher_id": "INTEGER",
        "face_image_id": "INTEGER",
        "face_template_id": "INTEGER",
    },
    "emotion_records": {
        "course_id": "INTEGER",
    },
    "group_photo_records": {
        "emotion_summary": "TEXT",
        "emotion_analyzed_count": "INTEGER DEFAULT 0",
        "emotion_failed_count": "INTEGER DEFAULT 0",
    },
    "group_photo_record_students": {
        "emotion": "VARCHAR",
        "emotion_confidence": "FLOAT",
        "emotion_error_code": "VARCHAR",
        "emotion_message": "TEXT",
    },
}


def ensure_database_schema() -> None:
    if not str(engine.url).startswith("sqlite"):
        return

    with engine.begin() as conn:
        for table_name, columns in SQLITE_COLUMNS.items():
            existing = {
                row[1]
                for row in conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
            }
            if not existing:
                continue
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    )

        conn.exec_driver_sql("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
        conn.exec_driver_sql("UPDATE students SET has_face_image = 0 WHERE has_face_image IS NULL")
        conn.exec_driver_sql(
            "UPDATE students SET active_face_image_count = 0 WHERE active_face_image_count IS NULL"
        )
        conn.exec_driver_sql("UPDATE students SET is_active = 1 WHERE is_active IS NULL")
        conn.exec_driver_sql("UPDATE courses SET status = 'active' WHERE status IS NULL")
        course_columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(courses)").fetchall()
        }
        if "course_code" in course_columns:
            try:
                conn.exec_driver_sql("ALTER TABLE courses DROP COLUMN course_code")
            except Exception:
                pass
        conn.exec_driver_sql(
            "UPDATE course_students SET enroll_status = 'active' WHERE enroll_status IS NULL"
        )
        conn.exec_driver_sql("UPDATE course_students SET source = 'manual' WHERE source IS NULL")
        conn.exec_driver_sql(
            "UPDATE course_students SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
        )
        conn.exec_driver_sql(
            """
            UPDATE course_students
            SET enroll_status = 'removed',
                removed_at = COALESCE(removed_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE enroll_status = 'active'
              AND id NOT IN (
                SELECT MAX(id)
                FROM course_students
                WHERE enroll_status = 'active'
                GROUP BY course_id, student_id
              )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_course_students_active_course_student
            ON course_students(course_id, student_id)
            WHERE enroll_status = 'active'
            """
        )
        conn.exec_driver_sql("UPDATE face_templates SET algorithm = 'mock' WHERE algorithm IS NULL")
        conn.exec_driver_sql(
            "UPDATE face_templates SET algorithm_version = 'v1' WHERE algorithm_version IS NULL"
        )
        conn.exec_driver_sql("UPDATE face_templates SET is_active = 1 WHERE is_active IS NULL")
        conn.exec_driver_sql("UPDATE attendance_sessions SET is_closed = 0 WHERE is_closed IS NULL")
        conn.exec_driver_sql(
            "UPDATE attendance_sessions SET expected_count = 0 WHERE expected_count IS NULL"
        )
        conn.exec_driver_sql(
            "UPDATE attendance_sessions SET checked_count = 0 WHERE checked_count IS NULL"
        )
        conn.exec_driver_sql(
            "UPDATE attendance_sessions SET absent_count = 0 WHERE absent_count IS NULL"
        )
        conn.exec_driver_sql(
            "UPDATE attendance_sessions SET failed_count = 0 WHERE failed_count IS NULL"
        )
        conn.exec_driver_sql(
            "UPDATE attendance_sessions SET unknown_count = 0 WHERE unknown_count IS NULL"
        )
        conn.exec_driver_sql(
            "UPDATE attendance_records SET is_checked_in = 0 WHERE is_checked_in IS NULL"
        )
        attendance_columns = {
            row[1]: row
            for row in conn.exec_driver_sql("PRAGMA table_info(attendance_records)").fetchall()
        }
        checkin_column = attendance_columns.get("checkin_time")
        if checkin_column and checkin_column[3]:
            conn.exec_driver_sql("DROP TABLE IF EXISTS attendance_records__old")
            conn.exec_driver_sql("ALTER TABLE attendance_records RENAME TO attendance_records__old")
            conn.exec_driver_sql(
                """
                CREATE TABLE attendance_records (
                    id INTEGER PRIMARY KEY,
                    session_id INTEGER,
                    course_id INTEGER,
                    teacher_id INTEGER,
                    student_id VARCHAR,
                    name VARCHAR,
                    checkin_time DATETIME,
                    submit_time DATETIME,
                    status VARCHAR NOT NULL DEFAULT 'pending',
                    is_checked_in BOOLEAN NOT NULL DEFAULT 0,
                    liveness_passed BOOLEAN NOT NULL DEFAULT 0,
                    liveness_score FLOAT,
                    face_score FLOAT,
                    emotion VARCHAR,
                    emotion_confidence FLOAT,
                    emotion_error_code VARCHAR,
                    emotion_message TEXT,
                    image_path VARCHAR,
                    used_face_image_id INTEGER,
                    used_face_template_id INTEGER,
                    fail_reason VARCHAR,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME
                )
                """
            )
            conn.exec_driver_sql(
                """
                INSERT INTO attendance_records (
                    id,
                    session_id,
                    course_id,
                    teacher_id,
                    student_id,
                    name,
                    checkin_time,
                    submit_time,
                    status,
                    is_checked_in,
                    liveness_passed,
                    liveness_score,
                    face_score,
                    emotion,
                    emotion_confidence,
                    emotion_error_code,
                    emotion_message,
                    image_path,
                    used_face_image_id,
                    used_face_template_id,
                    fail_reason,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    session_id,
                    course_id,
                    teacher_id,
                    student_id,
                    name,
                    checkin_time,
                    submit_time,
                    COALESCE(status, 'pending'),
                    COALESCE(is_checked_in, 0),
                    COALESCE(liveness_passed, 0),
                    liveness_score,
                    face_score,
                    emotion,
                    emotion_confidence,
                    emotion_error_code,
                    emotion_message,
                    image_path,
                    used_face_image_id,
                    used_face_template_id,
                    fail_reason,
                    COALESCE(created_at, CURRENT_TIMESTAMP),
                    COALESCE(updated_at, CURRENT_TIMESTAMP)
                FROM attendance_records__old
                """
            )
            conn.exec_driver_sql("DROP TABLE attendance_records__old")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_attendance_records_session_id ON attendance_records(session_id)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_attendance_records_course_id ON attendance_records(course_id)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_attendance_records_teacher_id ON attendance_records(teacher_id)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_attendance_records_student_id ON attendance_records(student_id)")

        conn.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_attendance_sessions_teacher_course_status
            ON attendance_sessions(teacher_id, course_id, status)
            """
        )
        conn.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_attendance_records_session_student
            ON attendance_records(session_id, student_id)
            """
        )
        conn.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_attendance_records_student_status
            ON attendance_records(student_id, status)
            """
        )
        conn.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_attendance_records_teacher_course
            ON attendance_records(teacher_id, course_id)
            """
        )

        face_image_columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(student_face_images)").fetchall()
        }
        face_template_columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(face_templates)").fetchall()
        }
        if face_image_columns and {"face_image_id", "image_path"}.issubset(face_template_columns):
            legacy_templates = conn.exec_driver_sql(
                """
                SELECT id, student_id, image_path, quality_score, created_at
                FROM face_templates
                WHERE is_active = 1
                  AND face_image_id IS NULL
                  AND image_path IS NOT NULL
                """
            ).fetchall()
            for template in legacy_templates:
                conn.exec_driver_sql(
                    """
                    INSERT INTO student_face_images (
                        student_id,
                        file_path,
                        source,
                        uploaded_by_role,
                        uploaded_by_id,
                        quality_score,
                        is_active,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, 'legacy_template', 'system', NULL, ?, 1, COALESCE(?, CURRENT_TIMESTAMP), CURRENT_TIMESTAMP)
                    """,
                    (template[1], template[2], template[3], template[4]),
                )
                face_image_id = conn.exec_driver_sql("SELECT last_insert_rowid()").scalar()
                conn.exec_driver_sql(
                    "UPDATE face_templates SET face_image_id = ? WHERE id = ?",
                    (face_image_id, template[0]),
                )

            conn.exec_driver_sql(
                """
                UPDATE student_face_images
                SET is_active = 0
                WHERE is_active = 1
                  AND EXISTS (
                    SELECT 1
                    FROM student_face_images AS newer
                    WHERE newer.student_id = student_face_images.student_id
                      AND newer.is_active = 1
                      AND (
                        COALESCE(newer.created_at, '1970-01-01') > COALESCE(student_face_images.created_at, '1970-01-01')
                        OR (
                          COALESCE(newer.created_at, '1970-01-01') = COALESCE(student_face_images.created_at, '1970-01-01')
                          AND newer.id > student_face_images.id
                        )
                      )
                  )
                """
            )
            conn.exec_driver_sql(
                """
                UPDATE face_templates
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE face_image_id IS NOT NULL
                  AND face_image_id NOT IN (
                    SELECT id
                    FROM student_face_images
                    WHERE is_active = 1
                  )
                """
            )
            conn.exec_driver_sql(
                """
                UPDATE face_templates
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE is_active = 1
                  AND EXISTS (
                    SELECT 1
                    FROM face_templates AS newer
                    WHERE newer.student_id = face_templates.student_id
                      AND newer.is_active = 1
                      AND (
                        COALESCE(newer.created_at, '1970-01-01') > COALESCE(face_templates.created_at, '1970-01-01')
                        OR (
                          COALESCE(newer.created_at, '1970-01-01') = COALESCE(face_templates.created_at, '1970-01-01')
                          AND newer.id > face_templates.id
                        )
                      )
                  )
                """
            )
            conn.exec_driver_sql(
                """
                UPDATE students
                SET active_face_image_count = (
                    SELECT COUNT(*)
                    FROM student_face_images
                    WHERE student_face_images.student_id = students.student_id
                      AND student_face_images.is_active = 1
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_student_face_images_one_active
                ON student_face_images(student_id)
                WHERE is_active = 1
                """
            )
            conn.exec_driver_sql(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_face_templates_one_active
                ON face_templates(student_id)
                WHERE is_active = 1
                """
            )
            conn.exec_driver_sql(
                """
                UPDATE students
                SET has_face_image = CASE WHEN active_face_image_count > 0 THEN 1 ELSE 0 END
                """
            )
            conn.exec_driver_sql(
                """
                UPDATE students
                SET latest_face_image_id = (
                    SELECT id
                    FROM student_face_images
                    WHERE student_face_images.student_id = students.student_id
                      AND student_face_images.is_active = 1
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                )
                """
            )

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS group_photo_records (
                id INTEGER PRIMARY KEY,
                teacher_id INTEGER NOT NULL,
                course_id INTEGER,
                activity_name VARCHAR,
                activity_date DATE,
                description TEXT,
                photo_path VARCHAR NOT NULL,
                annotated_image_path VARCHAR,
                total_faces INTEGER NOT NULL DEFAULT 0,
                matched_count INTEGER NOT NULL DEFAULT 0,
                unknown_count INTEGER NOT NULL DEFAULT 0,
                recognized_student_count INTEGER NOT NULL DEFAULT 0,
                emotion_summary TEXT,
                emotion_analyzed_count INTEGER NOT NULL DEFAULT 0,
                emotion_failed_count INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS group_photo_record_students (
                id INTEGER PRIMARY KEY,
                record_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                student_id VARCHAR NOT NULL,
                name VARCHAR,
                class_name VARCHAR,
                major VARCHAR,
                face_score FLOAT,
                face_image_id INTEGER,
                face_template_id INTEGER,
                emotion VARCHAR,
                emotion_confidence FLOAT,
                emotion_error_code VARCHAR,
                emotion_message TEXT,
                bbox TEXT,
                created_at DATETIME NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "UPDATE group_photo_records SET emotion_analyzed_count = 0 WHERE emotion_analyzed_count IS NULL"
        )
        conn.exec_driver_sql(
            "UPDATE group_photo_records SET emotion_failed_count = 0 WHERE emotion_failed_count IS NULL"
        )
        conn.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_group_photo_records_teacher_created
            ON group_photo_records(teacher_id, created_at)
            """
        )
        conn.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_group_photo_record_students_record
            ON group_photo_record_students(record_id)
            """
        )
