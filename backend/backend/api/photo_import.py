from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse

from schemas.common import ok
from services.course_service import resolve_teacher_course
from services.auth_service import require_teacher
from services.photo_import_service import import_photos


router = APIRouter(tags=["photo-import"])


IMPORT_PAGE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>照片库一键导入</title>
  <style>
    body {
      margin: 0;
      font-family: Arial, "Microsoft YaHei", sans-serif;
      color: #1f2937;
      background: #f5f7fb;
    }
    main {
      max-width: 920px;
      margin: 40px auto;
      padding: 0 20px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 28px;
    }
    p {
      line-height: 1.7;
      color: #4b5563;
    }
    .panel {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 24px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    }
    label {
      display: block;
      margin: 16px 0 8px;
      font-weight: 700;
    }
    input[type="text"] {
      width: 100%;
      box-sizing: border-box;
      padding: 12px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      font-size: 15px;
    }
    .checks {
      display: flex;
      gap: 20px;
      flex-wrap: wrap;
      margin: 18px 0;
    }
    .checks label {
      margin: 0;
      font-weight: 400;
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 12px 18px;
      font-size: 15px;
      cursor: pointer;
      color: #fff;
      background: #2563eb;
    }
    button.secondary {
      background: #475569;
      margin-left: 8px;
    }
    .auth-row {
      display: grid;
      grid-template-columns: 1fr 1fr auto auto;
      gap: 10px;
      align-items: end;
      margin: 16px 0 20px;
    }
    .auth-row label {
      margin: 0;
    }
    .auth-row input {
      margin-top: 8px;
    }
    .status {
      margin: 12px 0;
      color: #2563eb;
      font-weight: 700;
    }
    pre {
      margin-top: 20px;
      padding: 16px;
      overflow: auto;
      border-radius: 8px;
      color: #d1fae5;
      background: #111827;
      min-height: 180px;
      white-space: pre-wrap;
    }
    code {
      background: #e5e7eb;
      border-radius: 4px;
      padding: 2px 5px;
    }
  </style>
</head>
<body>
  <main>
    <h1>照片库一键导入</h1>
    <p>
      这个页面在 B 后端上运行。文件夹路径必须是运行后端这台电脑上的路径，
      图片文件名格式建议为 <code>学号-姓名-专业-性别.jpg</code>。
    </p>
    <section class="panel">
      <div class="auth-row">
        <label>教师账号
          <input id="username" type="text" value="teacher" />
        </label>
        <label>密码
          <input id="password" type="password" value="123456" />
        </label>
        <button onclick="login()">登录</button>
        <button class="secondary" onclick="logout()">退出</button>
      </div>
      <div id="loginStatus" class="status">未登录</div>

      <label for="folderPath">照片库文件夹路径</label>
      <input id="folderPath" type="text" placeholder="例如 D:\\photo_library 或 C:\\Users\\ASUS\\Desktop\\photos" />

      <label for="courseId">课堂ID（可留空，默认导入到当前教师的第一个课堂）</label>
      <input id="courseId" type="text" placeholder="例如 1" />

      <div class="checks">
        <label><input id="dryRun" type="checkbox" checked /> 仅预览，不写入数据库</label>
        <label><input id="replaceTemplates" type="checkbox" /> 覆盖已有学生人脸模板</label>
      </div>

      <button onclick="submitImport()">执行</button>
      <button class="secondary" onclick="fillExample()">填入示例</button>

      <pre id="output">等待操作...</pre>
    </section>
  </main>

  <script>
    function token() {
      return localStorage.getItem("attendance_token")
    }

    function setStatus(text) {
      document.getElementById("loginStatus").textContent = text
    }

    async function login() {
      const username = document.getElementById("username").value.trim()
      const password = document.getElementById("password").value
      const output = document.getElementById("output")

      try {
        const response = await fetch("/api/auth/login", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({username, password})
        })
        const result = await response.json()
        if (!response.ok || !result.success) {
          output.textContent = JSON.stringify(result, null, 2)
          setStatus("登录失败")
          return
        }
        localStorage.setItem("attendance_token", result.data.access_token)
        setStatus("已登录：" + result.data.user.username + " / " + result.data.user.role)
        output.textContent = "登录成功，现在可以执行导入。"
      } catch (error) {
        output.textContent = "登录请求失败：" + error
      }
    }

    function logout() {
      localStorage.removeItem("attendance_token")
      setStatus("未登录")
      document.getElementById("output").textContent = "已退出。"
    }

    function fillExample() {
      document.getElementById("folderPath").value = "D:\\\\photo_library"
    }

    async function submitImport() {
      const output = document.getElementById("output")
      const folderPath = document.getElementById("folderPath").value.trim()
      const courseId = document.getElementById("courseId").value.trim()
      const dryRun = document.getElementById("dryRun").checked
      const replaceTemplates = document.getElementById("replaceTemplates").checked

      if (!folderPath) {
        output.textContent = "请先填写照片库文件夹路径。"
        return
      }
      if (!token()) {
        output.textContent = "请先使用教师账号登录。"
        return
      }

      output.textContent = "正在执行，请稍等..."

      const form = new FormData()
      form.append("folder_path", folderPath)
      if (courseId) {
        form.append("course_id", courseId)
      }
      form.append("dry_run", dryRun ? "true" : "false")
      form.append("replace_templates", replaceTemplates ? "true" : "false")

      try {
        const response = await fetch("/api/admin/import-photos", {
          method: "POST",
          headers: {
            "Authorization": "Bearer " + token()
          },
          body: form
        })
        const result = await response.json()
        output.textContent = JSON.stringify(result, null, 2)
      } catch (error) {
        output.textContent = "请求失败：" + error
      }
    }

    if (token()) {
      setStatus("已保存登录状态，可以直接执行导入")
    }
  </script>
</body>
</html>
"""


@router.get("/admin/import-photos", response_class=HTMLResponse)
def import_photos_page():
    return HTMLResponse(IMPORT_PAGE)


@router.post("/api/admin/import-photos")
def import_photos_api(
    folder_path: str = Form(...),
    course_id: int | None = Form(None),
    dry_run: bool = Form(False),
    replace_templates: bool = Form(False),
    current_user=Depends(require_teacher),
):
    folder = Path(folder_path).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"照片库文件夹不存在: {folder}")

    from database import SessionLocal

    db = SessionLocal()
    try:
        course = resolve_teacher_course(db, current_user, course_id)
    finally:
        db.close()

    result = import_photos(
        folder,
        replace_templates=replace_templates,
        dry_run=dry_run,
        teacher_id=current_user.id,
        course_id=course.id,
    )
    return ok(result, "照片库导入完成" if not dry_run else "照片库预览完成")
