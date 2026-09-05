<template>
  <div>
    <el-form inline style="margin-bottom:16px">
      <el-form-item label="课程ID">
        <el-input-number v-model="filters.course_id" :min="1" style="width:100px" />
      </el-form-item>
      <el-form-item label="学号">
        <el-input v-model="filters.student_id" placeholder="输入学号" clearable />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="loadRecords">查询</el-button>
        <el-button type="success" @click="exportRecords">导出Excel</el-button>
      </el-form-item>
    </el-form>

    <el-card v-if="records.length > 0" style="margin-bottom:20px">
      <template #header>情绪统计</template>
      <el-row :gutter="20">
        <el-col :span="12">
          <div ref="emotionChartRef" style="width:100%;height:300px"></div>
        </el-col>
        <el-col :span="12">
          <el-row :gutter="20" style="margin-bottom:20px">
            <el-col :span="12">
              <el-statistic title="总记录数" :value="records.length" />
            </el-col>
            <el-col :span="12">
              <el-statistic title="有情绪数据" :value="records.filter(r => r.emotion).length" />
            </el-col>
          </el-row>
          <el-table :data="emotionStats" border size="small" style="margin-top:20px">
            <el-table-column prop="emotion" label="情绪" />
            <el-table-column prop="count" label="人次" />
            <el-table-column prop="percentage" label="占比">
              <template #default="{ row }">{{ row.percentage }}%</template>
            </el-table-column>
          </el-table>
        </el-col>
      </el-row>
    </el-card>

    <el-table :data="records" border>
      <el-table-column prop="student_id" label="学号" width="120" />
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="checkin_time" label="考勤时间" width="160" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="emotion" label="情绪" width="80" />
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import request from '../../api/request'
import * as echarts from 'echarts'

const records = ref([])
const filters = ref({ course_id: 1, student_id: '' })
const emotionChartRef = ref(null)
let emotionChartInstance = null

const emotionMap = {
  happy: '高兴',
  sad: '悲伤',
  angry: '愤怒',
  neutral: '平静',
  surprise: '惊讶',
  fear: '恐惧',
  disgust: '厌恶'
}

const emotionStats = computed(() => {
  const statsMap = {}
  let total = 0
  records.value.forEach(r => {
    if (r.emotion) {
      const emotionCn = emotionMap[r.emotion] || r.emotion
      statsMap[emotionCn] = (statsMap[emotionCn] || 0) + 1
      total++
    }
  })
  return Object.entries(statsMap).map(([emotion, count]) => ({
    emotion,
    count,
    percentage: ((count / total) * 100).toFixed(1)
  })).sort((a, b) => b.count - a.count)
})

function initEmotionChart() {
  if (!emotionChartRef.value || emotionStats.value.length === 0) return

  if (emotionChartInstance) {
    emotionChartInstance.dispose()
  }

  emotionChartInstance = echarts.init(emotionChartRef.value)
  emotionChartInstance.setOption({
    title: { text: '情绪分布', left: 'center' },
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: '60%',
      data: emotionStats.value.map(s => ({ name: s.emotion, value: s.count })),
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  })
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

async function loadRecords() {
  const params = { course_id: filters.value.course_id || 1 }
  if (filters.value.student_id) params.student_id = filters.value.student_id
  try {
    const res = await request.get('/api/attendance/records', { params })
    records.value = Array.isArray(res) ? res : (res.data || [])
    nextTick(() => {
      initEmotionChart()
    })
  } catch (e) {
    records.value = []
  }
}

async function exportRecords() {
  const params = { course_id: filters.value.course_id || 1 }
  if (filters.value.student_id) params.student_id = filters.value.student_id
  try {
    const response = await request.get('/api/export/attendance', {
      params,
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `考勤记录_课程${params.course_id}_${new Date().toLocaleDateString('zh-CN')}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败')
  }
}

onMounted(loadRecords)
</script>
