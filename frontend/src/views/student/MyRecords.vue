<template>
  <div style="max-width:800px;margin:0 auto;padding:20px">
    <el-card header="我的考勤记录">
      <el-table :data="records" border>
        <el-table-column label="课程" width="120">
          <template #default="{ row }">
            {{ row.course_name || `课程 ${row.course_id}` }}
          </template>
        </el-table-column>
        <el-table-column label="考勤场次" width="120">
          <template #default="{ row }">
            {{ row.session_title || `场次 ${row.session_id}` }}
          </template>
        </el-table-column>
        <el-table-column prop="checkin_time" label="考勤时间" width="160" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="情绪" width="80">
          <template #default="{ row }">
            {{ getEmotionText(row.emotion) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import request from '../../api/request'

const records = ref([])

function getEmotionText(emotion) {
  const map = {
    happy: '高兴',
    sad: '悲伤',
    angry: '愤怒',
    neutral: '平静',
    surprise: '惊讶',
    fear: '恐惧',
    disgust: '厌恶'
  }
  return map[emotion] || emotion || '-'
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

onMounted(async () => {
  try {
    const res = await request.get('/api/attendance/my-records')
    console.log('考勤记录原始响应:', res)
    records.value = Array.isArray(res) ? res : (res.data || [])
    console.log('处理后的记录:', records.value)
    if (records.value.length > 0) {
      console.log('第一条记录示例:', records.value[0])
    }
  } catch (e) {
    console.error('加载考勤记录失败:', e)
    records.value = []
  }
})
</script>
