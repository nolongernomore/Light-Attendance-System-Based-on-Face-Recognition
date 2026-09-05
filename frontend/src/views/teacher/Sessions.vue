<template>
  <div>
    <el-alert v-if="activeSessions.length > 0" type="success" :closable="false" style="margin-bottom:16px">
      <template #title>
        当前进行中的考勤：{{ activeSessions.map(s => s.title).join('、') }}
      </template>
    </el-alert>

    <el-table :data="sessions" border @expand-change="handleExpand">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div style="padding:12px">
            <el-table :data="row.records" border size="small" v-loading="row.loading">
              <el-table-column prop="student_id" label="学号" width="120" />
              <el-table-column prop="name" label="姓名" />
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row: record }">
                  <el-tag :type="getStatusType(record.status)" size="small">
                    {{ getStatusText(record.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="checkin_time" label="考勤时间" width="160" />
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="考勤标题" />
      <el-table-column prop="course_id" label="课程ID" width="80" />
      <el-table-column prop="course_name" label="课程名称" />
      <el-table-column label="考勤情况" width="150">
        <template #default="{ row }">
          {{ row.checked_count || 0 }} / {{ row.expected_count || 0 }}
        </template>
      </el-table-column>
      <el-table-column label="开始时间" width="160">
        <template #default="{ row }">
          {{ row.start_time || row.created_at || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status === 'active' ? '进行中' : '已结束' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button v-if="row.status === 'active'" size="small" type="warning" @click="closeSession(row.id)">
            结束考勤
          </el-button>
          <el-button size="small" type="danger" @click="deleteSession(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../../api/request'

const sessions = ref([])

const activeSessions = computed(() => sessions.value.filter(s => s.status === 'active'))

async function loadSessions() {
  const res = await request.get('/api/attendance/sessions').catch(() => [])
  const list = Array.isArray(res) ? res : (res.data || [])
  for (const session of list) {
    session.records = []
    session.loading = false
    session.loaded = false
  }
  sessions.value = list
}

async function handleExpand(row, expandedRows) {
  if (!row.loaded && expandedRows.some(r => r.id === row.id)) {
    row.loading = true
    row.records = await loadSessionRecords(row.id)
    row.loaded = true
    row.loading = false
  }
}

async function loadSessionRecords(sessionId) {
  try {
    const res = await request.get(`/api/attendance/records?session_id=${sessionId}`)
    return Array.isArray(res) ? res : (res.data || [])
  } catch {
    return []
  }
}

function getStatusText(status) {
  const map = {
    pending: '待考勤',
    present: '已完成',
    absent: '缺勤',
    failed: '失败',
    unknown: '未知'
  }
  return map[status] || status
}

function getStatusType(status) {
  const map = {
    pending: 'info',
    present: 'success',
    absent: 'danger',
    failed: 'danger',
    unknown: 'info'
  }
  return map[status] || 'info'
}

async function closeSession(id) {
  try {
    await ElMessageBox.confirm('确定要结束这次考勤吗？', '提示', { type: 'warning' })
    await request.post(`/api/attendance/sessions/${id}/close`)
    ElMessage.success('考勤已结束')
    loadSessions()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function deleteSession(id) {
  try {
    await ElMessageBox.confirm('确定要删除这次考勤吗？删除后无法恢复！', '警告', { type: 'error' })
    await request.delete(`/api/attendance/sessions/${id}`)
    ElMessage.success('考勤已删除')
    loadSessions()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(loadSessions)
</script>
