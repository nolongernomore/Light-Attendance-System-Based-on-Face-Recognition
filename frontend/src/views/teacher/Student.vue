<template>
  <div>
    <el-row justify="space-between" style="margin-bottom:16px">
      <el-space>
        <el-button type="primary" @click="openAdd">添加学生</el-button>
        <el-button type="success" @click="importVisible=true">批量导入</el-button>
      </el-space>
    </el-row>

    <el-table :data="students" border>
      <el-table-column prop="student_id" label="学号" width="120" />
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="major" label="专业" />
      <el-table-column label="人脸状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.has_face_image ? 'success' : 'info'" size="small">
            {{ row.has_face_image ? '已录入' : '未录入' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" @click="openFace(row)">录入人脸</el-button>
          <el-button size="small" type="danger" @click="deleteStudent(row.student_id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="addVisible" title="添加学生" width="400px">
      <el-form :model="form">
        <el-form-item label="学号"><el-input v-model="form.student_id" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="专业"><el-input v-model="form.major" /></el-form-item>
        <el-form-item label="性别">
          <el-radio-group v-model="form.gender">
            <el-radio value="男">男</el-radio>
            <el-radio value="女">女</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible=false">取消</el-button>
        <el-button type="primary" @click="submitAdd">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编辑学生弹窗 -->
    <el-dialog v-model="editVisible" title="编辑学生" width="400px">
      <el-form :model="editForm">
        <el-form-item label="学号"><el-input v-model="editForm.student_id" disabled /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="editForm.name" /></el-form-item>
        <el-form-item label="专业"><el-input v-model="editForm.major" /></el-form-item>
        <el-form-item label="性别">
          <el-radio-group v-model="editForm.gender">
            <el-radio value="男">男</el-radio>
            <el-radio value="女">女</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible=false">取消</el-button>
        <el-button type="primary" @click="submitEdit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入弹窗 -->
    <el-dialog v-model="importVisible" title="批量导入学生" width="400px">
      <el-upload drag :auto-upload="false" :on-change="onImportFileChange" accept=".xlsx,.xls,.csv">
        <el-icon style="font-size:48px"><Upload /></el-icon>
        <div>拖拽或点击上传 Excel/CSV 文件</div>
      </el-upload>
      <template #footer>
        <el-button @click="importVisible=false">取消</el-button>
        <el-button type="primary" @click="submitImport" :loading="importing">导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="faceVisible" :title="`录入人脸 - ${currentStudent?.name}`" width="500px">
      <el-upload
        drag
        :auto-upload="false"
        :on-change="onFaceFileChange"
        accept="image/*"
        :limit="1"
      >
        <el-icon style="font-size:48px"><Upload /></el-icon>
        <div>拖拽或点击上传人脸照片</div>
      </el-upload>
      <template #footer>
        <el-button @click="faceVisible=false">取消</el-button>
        <el-button type="primary" @click="submitFace" :loading="uploading" :disabled="!faceFile">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import request from '../../api/request'

const students = ref([])
const addVisible = ref(false)
const editVisible = ref(false)
const importVisible = ref(false)
const faceVisible = ref(false)
const importing = ref(false)
const uploading = ref(false)
const currentStudent = ref(null)
const importFile = ref(null)
const faceFile = ref(null)
const editForm = ref({})
const form = ref({ student_id: '', name: '', major: '', gender: '男' })

// 加载学生列表
async function loadStudents() {
  try {
    const res = await request.get('/api/students')
    students.value = Array.isArray(res) ? res : (res.data || [])
  } catch (error) {
    console.error('加载学生列表失败:', error)
    students.value = []
  }
}

// 打开添加弹窗
function openAdd() {
  form.value = { student_id: '', name: '', major: '', gender: '男' }
  addVisible.value = true
}

// 提交添加学生
async function submitAdd() {
  try {
    await request.post('/api/students', form.value)
    ElMessage.success('添加成功')
    addVisible.value = false
    loadStudents() 
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '添加失败')
  }
}

// 批量导入相关
function onImportFileChange(file) {
  importFile.value = file.raw
}

async function submitImport() {
  if (!importFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    await request.post('/api/students/import', fd)
    ElMessage.success('导入成功')
    importVisible.value = false
    loadStudents()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

// 编辑学生相关
function openEdit(row) {
  editForm.value = { ...row }
  editVisible.value = true
}

async function submitEdit() {
  try {
    await request.put(`/api/students/${editForm.value.student_id}`, editForm.value)
    ElMessage.success('修改成功')
    editVisible.value = false
    loadStudents()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '修改失败')
  }
}

// 补回来的：删除学生函数！
async function deleteStudent(id) {
  try {
    await request.delete(`/api/students/${id}`)
    ElMessage.success('删除成功')
    loadStudents()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '删除失败')
  }
}

// 打开人脸录入弹窗
function openFace(row) {
  currentStudent.value = row
  faceFile.value = null
  faceVisible.value = true
}

// 文件选择处理
function onFaceFileChange(file) {
  faceFile.value = file.raw
}

// 提交人脸照片
async function submitFace() {
  if (!faceFile.value) {
    ElMessage.warning('请选择照片')
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', faceFile.value)
    fd.append('student_id', currentStudent.value.student_id)

    await request.post('/api/face/enroll', fd)
    ElMessage.success('人脸录入成功')
    faceVisible.value = false
    loadStudents()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '录入失败')
  } finally {
    uploading.value = false
  }
}

onMounted(loadStudents)
</script>