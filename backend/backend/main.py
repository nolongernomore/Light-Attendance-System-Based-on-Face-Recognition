from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api import admin, auth, attendance, courses, export, face, group_photo, stats, students
from config import ensure_upload_dirs, settings
from database import Base, engine
from services.auth_service import ensure_default_users
from services.face_service import warmup
from services.migration_service import ensure_database_schema


def create_app() -> FastAPI:
    ensure_upload_dirs()
    Base.metadata.create_all(bind=engine)
    ensure_database_schema()
    ensure_default_users()

    app = FastAPI(title=settings.APP_NAME)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix=settings.API_PREFIX)
    app.include_router(admin.router, prefix=settings.API_PREFIX)
    app.include_router(courses.router, prefix=settings.API_PREFIX)
    app.include_router(students.router, prefix=settings.API_PREFIX)
    app.include_router(face.router, prefix=settings.API_PREFIX)
    app.include_router(attendance.router, prefix=settings.API_PREFIX)
    app.include_router(group_photo.router, prefix=settings.API_PREFIX)
    app.include_router(stats.router, prefix=settings.API_PREFIX)
    app.include_router(export.router, prefix=settings.API_PREFIX)
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            500: "INTERNAL_ERROR",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "code": code_map.get(exc.status_code, "ERROR"),
                "message": str(exc.detail),
                "data": None,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "code": "VALIDATION_ERROR",
                "message": "请求参数格式错误",
                "data": exc.errors(),
            },
        )

    @app.get("/api/health", tags=["health"])
    def health_check():
        return {
            "success": True,
            "code": "OK",
            "message": "backend is running",
            "data": {"app": settings.APP_NAME},
        }

    @app.get("/tools/admin-students", response_class=HTMLResponse, include_in_schema=False)
    def admin_students_page():
        return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Student Admin</title>
  <style>
    body { margin: 0; padding: 28px; font-family: Arial, "Microsoft YaHei", sans-serif; background: #f5f7fb; color: #182033; }
    main { max-width: 1100px; margin: 0 auto; }
    section { margin-top: 18px; padding: 16px; border: 1px solid #d8dee8; border-radius: 8px; background: #fff; }
    h1 { margin: 0 0 8px; font-size: 26px; }
    p { color: #5c6678; }
    input { box-sizing: border-box; padding: 9px; border: 1px solid #c8cfda; border-radius: 6px; font: inherit; }
    button { border: 0; border-radius: 6px; padding: 9px 13px; background: #1f6feb; color: #fff; font: inherit; cursor: pointer; }
    button.danger { background: #c62828; }
    button.secondary { background: #46556f; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
    .password { min-width: 260px; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }
    th, td { padding: 9px; border-bottom: 1px solid #e5e9f0; text-align: left; }
    th { background: #f2f5f9; }
    pre { min-height: 120px; overflow: auto; padding: 12px; border-radius: 8px; background: #101828; color: #eef4ff; white-space: pre-wrap; word-break: break-word; }
  </style>
</head>
<body>
  <main>
    <h1>Student Admin</h1>
    <p>Input admin password 123456 to list students, delete selected students, or delete all students.</p>

    <section>
      <div class="toolbar">
        <input id="password" class="password" type="password" placeholder="Admin password" value="123456" />
        <button id="loadBtn" type="button">Load Students</button>
        <button id="deleteSelectedBtn" type="button" class="danger">Delete Selected</button>
        <button id="deleteAllBtn" type="button" class="danger">Delete All Students</button>
      </div>
    </section>

    <section>
      <div class="toolbar">
        <label><input id="selectAll" type="checkbox" /> Select all loaded students</label>
        <span id="count">0 students</span>
      </div>
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Student ID</th>
            <th>Name</th>
            <th>Class</th>
            <th>Major</th>
            <th>Gender</th>
            <th>Active</th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </section>

    <section>
      <pre id="output">Waiting...</pre>
    </section>
  </main>

  <script>
    const passwordInput = document.querySelector("#password");
    const tbody = document.querySelector("#tbody");
    const output = document.querySelector("#output");
    const count = document.querySelector("#count");
    const selectAll = document.querySelector("#selectAll");

    function show(value) {
      output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
    }

    function password() {
      return passwordInput.value;
    }

    function selectedIds() {
      return Array.from(document.querySelectorAll(".student-check:checked")).map(item => item.value);
    }

    function renderStudents(students) {
      tbody.innerHTML = "";
      for (const student of students) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><input class="student-check" type="checkbox" value="${student.student_id}"></td>
          <td>${student.student_id || ""}</td>
          <td>${student.name || ""}</td>
          <td>${student.class_name || ""}</td>
          <td>${student.major || ""}</td>
          <td>${student.gender || ""}</td>
          <td>${student.is_active ? "yes" : "no"}</td>
        `;
        tbody.appendChild(tr);
      }
      count.textContent = `${students.length} students`;
      selectAll.checked = false;
    }

    async function postJson(url, body) {
      const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body)
      });
      const data = await response.json();
      if (!response.ok || data.success === false) {
        throw new Error(data.message || "Request failed");
      }
      return data;
    }

    async function loadStudents() {
      try {
        const data = await postJson("/api/admin/students/list", {admin_password: password()});
        renderStudents(data.data.students || []);
        show(data);
      } catch (error) {
        show(error.message);
      }
    }

    async function deleteSelected() {
      const ids = selectedIds();
      if (!ids.length) {
        show("No students selected.");
        return;
      }
      if (!confirm(`Delete ${ids.length} selected students?`)) {
        return;
      }
      try {
        const data = await postJson("/api/admin/students/delete", {
          admin_password: password(),
          student_ids: ids,
          delete_all: false
        });
        show(data);
        await loadStudents();
      } catch (error) {
        show(error.message);
      }
    }

    async function deleteAllStudents() {
      if (!confirm("Delete ALL students? This cannot be undone.")) {
        return;
      }
      if (!confirm("Confirm again: delete all students, accounts, course links, face images and templates?")) {
        return;
      }
      try {
        const data = await postJson("/api/admin/students/delete", {
          admin_password: password(),
          student_ids: [],
          delete_all: true
        });
        show(data);
        await loadStudents();
      } catch (error) {
        show(error.message);
      }
    }

    selectAll.addEventListener("change", () => {
      for (const item of document.querySelectorAll(".student-check")) {
        item.checked = selectAll.checked;
      }
    });
    document.querySelector("#loadBtn").addEventListener("click", loadStudents);
    document.querySelector("#deleteSelectedBtn").addEventListener("click", deleteSelected);
    document.querySelector("#deleteAllBtn").addEventListener("click", deleteAllStudents);
  </script>
</body>
</html>
        """

    @app.get("/tools/admin-face-import", response_class=HTMLResponse, include_in_schema=False)
    def admin_face_import_page():
        return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>照片库后台导入</title>
  <style>
    body { margin: 0; padding: 28px; font-family: Arial, "Microsoft YaHei", sans-serif; background: #f5f7fb; color: #182033; }
    main { max-width: 980px; margin: 0 auto; }
    section { margin-top: 18px; padding: 16px; border: 1px solid #d8dee8; border-radius: 8px; background: #fff; }
    h1 { margin: 0 0 8px; font-size: 26px; }
    p { color: #5c6678; line-height: 1.6; }
    label { display: block; margin: 12px 0 6px; font-weight: 600; }
    input { box-sizing: border-box; width: 100%; max-width: 520px; padding: 9px; border: 1px solid #c8cfda; border-radius: 6px; font: inherit; }
    input[type="checkbox"] { width: auto; margin-right: 8px; }
    button { border: 0; border-radius: 6px; padding: 9px 13px; background: #1f6feb; color: #fff; font: inherit; cursor: pointer; }
    button.secondary { background: #42526b; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 16px; }
    .hint { font-size: 13px; color: #687385; margin-top: 8px; }
    .password { max-width: 260px; }
    pre { min-height: 180px; overflow: auto; padding: 12px; border-radius: 8px; background: #101828; color: #eef4ff; white-space: pre-wrap; word-break: break-word; }
    @media (max-width: 720px) { body { padding: 18px; } input { max-width: none; } }
  </style>
</head>
<body>
  <main>
    <h1>照片库后台导入</h1>
    <p>管理员输入密码 123456 后，可以上传一个照片库 ZIP。照片命名格式为 <code>学号-姓名-专业-性别.jpg</code>；导入时会自动创建缺失学生账号，并且每个学生只保留最后一次成功录入的照片。</p>

    <section>
      <h2>导入设置</h2>
      <label for="password">管理员密码</label>
      <input id="password" class="password" value="123456" type="password" autocomplete="current-password" />

      <label for="zipInput">ZIP file</label>
      <input id="zipInput" type="file" accept=".zip,application/zip,application/x-zip-compressed" />
      <p class="hint" id="fileStatus">尚未选择 ZIP</p>

      <label>
        <input id="dryRun" type="checkbox" checked />
        只预检查，不写数据库
      </label>

      <div class="toolbar">
        <button id="uploadBtn" type="button">开始导入</button>
        <button id="clearBtn" type="button" class="secondary">清空结果</button>
      </div>
    </section>

    <section>
      <h2>返回结果</h2>
      <pre id="output">等待操作...</pre>
    </section>
  </main>

  <script>
    const passwordInput = document.querySelector("#password");
    const fileStatus = document.querySelector("#fileStatus");
    const output = document.querySelector("#output");
    const zipInput = document.querySelector("#zipInput");
    const dryRunInput = document.querySelector("#dryRun");
    const uploadBtn = document.querySelector("#uploadBtn");

    function setBusy(isBusy) {
      uploadBtn.disabled = isBusy;
    }

    function show(value) {
      output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
    }

    function selectedZip() {
      return zipInput.files && zipInput.files.length ? zipInput.files[0] : null;
    }

    function formatBytes(value) {
      if (value < 1024) {
        return `${value} B`;
      }
      if (value < 1024 * 1024) {
        return `${(value / 1024).toFixed(1)} KB`;
      }
      if (value < 1024 * 1024 * 1024) {
        return `${(value / 1024 / 1024).toFixed(1)} MB`;
      }
      return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`;
    }

    function updateFileStatus() {
      const file = selectedZip();
      fileStatus.textContent = file ? `已选择：${file.name} (${formatBytes(file.size)})` : "尚未选择 ZIP";
    }

    async function upload() {
      const password = passwordInput.value;
      if (!password) {
        show("请先输入管理员密码。");
        return;
      }
      const zip = selectedZip();
      if (!zip) {
        show("请先选择 ZIP 文件。");
        return;
      }

      const form = new FormData();
      form.append("admin_password", password);
      form.append("dry_run", dryRunInput.checked ? "true" : "false");
      form.append("file", zip, zip.name);

      setBusy(true);
      show(`正在导入 ${zip.name} (${formatBytes(zip.size)})...`);
      try {
        const response = await fetch("/api/admin/face-import", {
          method: "POST",
          body: form
        });
        const data = await response.json();
        show(data);
      } catch (error) {
        show(error.message);
      } finally {
        setBusy(false);
      }
    }

    zipInput.addEventListener("change", updateFileStatus);
    document.querySelector("#uploadBtn").addEventListener("click", upload);
    document.querySelector("#clearBtn").addEventListener("click", () => show("等待操作..."));
  </script>
</body>
</html>
        """

    @app.on_event("startup")
    async def warmup_face_service():
        warmup()

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=settings.APP_NAME,
            version="1.0.0",
            routes=app.routes,
        )
        # Swagger UI renders multipart arrays correctly with OpenAPI 3.0-style
        # `format: binary`; Pydantic v2 emits `contentMediaType` instead.
        for component in schema.get("components", {}).get("schemas", {}).values():
            for prop in component.get("properties", {}).values():
                items = prop.get("items")
                if isinstance(items, dict) and items.get("contentMediaType") == "application/octet-stream":
                    items.pop("contentMediaType", None)
                    items["format"] = "binary"
                if prop.get("contentMediaType") == "application/octet-stream":
                    prop.pop("contentMediaType", None)
                    prop["format"] = "binary"
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi

    return app


app = create_app()
