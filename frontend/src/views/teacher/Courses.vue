<template>
  <div>
    <el-row justify="space-between" style="margin-bottom:16px">
      <el-button type="primary" @click="openAdd">创建课堂</el-button>
    </el-row>

    <el-table :data="courses" border>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="course_name" label="课程名称" />
      <el-table-column prop="description" label="描述" />
      <el-table-column label="操作" width="400">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="info" @click="openStudents(row)">学生管理</el-button>
          <el-button size="small" type="success" @click="startSession(row.id)">启动考勤</el-button>
          <el-button size="small" type="danger" @click="deleteCourse(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="addVisible" title="创建课堂" width="400px">
      <el-form :model="form">
        <el-form-item label="课程名称"><el-input v-model="form.course_name" /></el-form-item>
        <el-form-item label="学期"><el-input v-model="form.term" placeholder="如：2026春" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible=false">取消</el-button>
        <el-button type="primary" @click="submitAdd">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编辑课堂弹窗 -->
    <el-dialog v-model="editVisible" title="编辑课堂" width="400px">
      <el-form :model="editForm">
        <el-form-item label="课程名称"><el-input v-model="editForm.course_name" /></el-form-item>
        <el-form-item label="学期"><el-input v-model="editForm.term" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="editForm.description" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible=false">取消</el-button>
        <el-button type="primary" @click="submitEdit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="sessionVisible" title="启动考勤" width="400px">
      <el-form :model="sessionForm">
        <el-form-item label="考勤标题"><el-input v-model="sessionForm.title" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sessionVisible=false">取消</el-button>
        <el-button type="primary" @click="submitSession">启动</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="studentsVisible" :title="`学生管理 - ${currentCourse?.course_name}`" width="700px">
      <el-row justify="space-between" style="margin-bottom:12px">
        <el-space>
          <el-button size="small" type="primary" @click="addStudentVisible=true">添加学生</el-button>
          <el-button size="small" type="success" @click="importStudentVisible=true">批量导入</el-button>
        </el-space>
      </el-row>
      <el-table :data="courseStudents" border max-height="400">
        <el-table-column prop="student_id" label="学号" width="120" />
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="major" label="专业" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="removeStudent(row.student_id)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="addStudentVisible" title="添加学生到课程" width="400px">
      <el-input v-model="studentIds" type="textarea" :rows="4" placeholder="输入学号，每行一个" />
      <template #footer>
        <el-button @click="addStudentVisible=false">取消</el-button>
        <el-button type="primary" @click="submitAddStudents">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importStudentVisible" title="批量导入学生到课程" width="400px">
      <el-upload drag :auto-upload="false" :on-change="onStudentFileChange" accept=".xlsx,.xls,.csv">
        <el-icon style="font-size:48px"><Upload /></el-icon>
        <div>拖拽或点击上传 Excel/CSV 文件</div>
      </el-upload>
      <template #footer>
        <el-button @click="importStudentVisible=false">取消</el-button>
        <el-button type="primary" @click="submitImportStudents" :loading="importingStudents">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import request from '../../api/request'

const courses = ref([])
const addVisible = ref(false)
const editVisible = ref(false)
const sessionVisible = ref(false)
const studentsVisible = ref(false)
const addStudentVisible = ref(false)
const importStudentVisible = ref(false)
const form = ref({ course_name: '', term: '', description: '' })
const editForm = ref({})
const sessionForm = ref({ course_id: null, title: '' })
const courseStudents = ref([])
const currentCourse = ref(null)
const studentIds = ref('')
const studentFile = ref(null)
const importingStudents = ref(false)

async function loadCourses() {
  const res = await request.get('/api/courses').catch(() => ({ data: [] }))
  courses.value = Array.isArray(res) ? res : (res.data || [])
}

function openAdd() {
  form.value = { course_name: '', term: '', description: '' }
  addVisible.value = true
}

async function submitAdd() {
  try {
    await request.post('/api/courses', form.value)
    ElMessage.success('创建成功')
    addVisible.value = false
    loadCourses()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '创建失败')
  }
}

function openEdit(row) {
  editForm.value = { ...row }
  editVisible.value = true
}

async function submitEdit() {
  try {
    await request.put(`/api/courses/${editForm.value.id}`, editForm.value)
    ElMessage.success('修改成功')
    editVisible.value = false
    loadCourses()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '修改失败')
  }
}

async function deleteCourse(id) {
  try {
    await ElMessageBox.confirm('确定要删除这门课程吗？删除后无法恢复！', '警告', { type: 'error' })
    console.log('删除课程ID:', id)
    await request.delete(`/api/courses/${id}`)
    ElMessage.success('课程已删除')
    loadCourses()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除课程失败:', e.response?.data || e)
      ElMessage.error(e.response?.data?.detail || e.response?.data?.message || '删除失败')
    }
  }
}

function startSession(courseId) {
  sessionForm.value = { course_id: courseId, title: '课堂考勤' }
  sessionVisible.value = true
}

async function submitSession() {
  const res = await request.post('/api/attendance/sessions', sessionForm.value)
  ElMessage.success(`考勤已启动，session_id: ${res.data?.id || res.id}`)
  sessionVisible.value = false
}

// 学生管理相关
async function openStudents(row) {
  currentCourse.value = row
  studentsVisible.value = true
  await loadCourseStudents()
}

async function loadCourseStudents() {
  console.log('当前课程:', currentCourse.value)
  console.log('课程ID:', currentCourse.value?.id)
  if (!currentCourse.value?.id) {
    ElMessage.error('课程ID不存在')
    return
  }
  try {
    const res = await request.get(`/api/courses/${currentCourse.value.id}/students`)
    courseStudents.value = Array.isArray(res) ? res : (res.data || [])
  } catch (e) {
    console.error('加载学生列表失败:', e.response?.data || e)
    ElMessage.error(e.response?.data?.detail || e.response?.data?.message || '加载学生列表失败')
    courseStudents.value = []
  }
}

async function submitAddStudents() {
  const ids = studentIds.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (ids.length === 0) {
    ElMessage.warning('请输入学号')
    return
  }
  try {
    await request.post(`/api/courses/${currentCourse.value.id}/students`, { student_ids: ids })
    ElMessage.success('添加成功')
    addStudentVisible.value = false
    studentIds.value = ''
    await loadCourseStudents()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加失败')
  }
}

async function removeStudent(studentId) {
  try {
    await request.delete(`/api/courses/${currentCourse.value.id}/students/${studentId}`)
    ElMessage.success('移除成功')
    await loadCourseStudents()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '移除失败')
  }
}

function onStudentFileChange(file) {
  studentFile.value = file.raw
}

async function submitImportStudents() {
  if (!studentFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  importingStudents.value = true
  try {
    const fd = new FormData()
    fd.append('file', studentFile.value)
    await request.post(`/api/courses/${currentCourse.value.id}/students/import`, fd)
    ElMessage.success('导入成功')
    importStudentVisible.value = false
    await loadCourseStudents()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导入失败')
  } finally {
    importingStudents.value = false
  }
}

onMounted(loadCourses)
</script>
