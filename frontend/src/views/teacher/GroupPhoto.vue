<template>
  <div>
    <el-form :model="form" inline style="margin-bottom:16px">
      <el-form-item label="活动名称">
        <el-input v-model="form.activity_name" placeholder="可选，默认为 Group photo recognition" />
      </el-form-item>
      <el-form-item label="活动日期">
        <el-date-picker v-model="form.activity_date" type="date" value-format="YYYY-MM-DD" placeholder="可选，默认为当天" />
      </el-form-item>
      <el-form-item label="课程ID">
        <el-input-number v-model="form.course_id" :min="1" placeholder="可选，不填则使用全局学生库" />
      </el-form-item>
      <el-form-item label="活动说明">
        <el-input v-model="form.description" placeholder="可选" />
      </el-form-item>
    </el-form>

    <el-upload
      drag
      action="#"
      :auto-upload="false"
      :on-change="onFileChange"
      accept="image/*"
      style="margin-bottom:16px"
    >
      <el-icon style="font-size:48px"><Upload /></el-icon>
      <div>拖拽或点击上传合照</div>
    </el-upload>

    <div v-if="previewUrl" style="margin-bottom:16px;text-align:center">
      <h4>上传的合照</h4>
      <img :src="previewUrl" style="max-width:100%;max-height:400px;border:1px solid #eee" />
    </div>

    <el-button type="primary" :loading="loading" @click="recognize" :disabled="!file">开始识别</el-button>

    <template v-if="historyRecords.length > 0">
      <el-divider />
      <h4>数据统计</h4>
      <el-row :gutter="20" style="margin-bottom:20px">
        <el-col :span="6">
          <el-statistic title="总活动数" :value="historyRecords.length" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="总参与人次" :value="historyRecords.reduce((sum, r) => sum + (r.recognized_student_count || 0), 0)" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="参与学生数" :value="studentStats.length" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="情绪分析总数" :value="historyRecords.reduce((sum, r) => sum + (r.emotion_analyzed_count || 0), 0)" />
        </el-col>
      </el-row>

      <el-row :gutter="20" style="margin-bottom:20px">
        <el-col :span="12">
          <h4>合照情绪分布</h4>
          <div ref="groupEmotionChartRef" style="width:100%;height:300px"></div>
        </el-col>
        <el-col :span="12">
          <h4>情绪统计表</h4>
          <el-table :data="groupEmotionStats" border size="small" max-height="300">
            <el-table-column prop="emotion" label="情绪" />
            <el-table-column prop="count" label="人次" />
            <el-table-column prop="percentage" label="占比">
              <template #default="{ row }">{{ row.percentage }}%</template>
            </el-table-column>
          </el-table>
        </el-col>
      </el-row>

      <h4>学生参与统计</h4>
      <el-table :data="studentStats" border size="small" style="margin-bottom:20px" max-height="400">
        <el-table-column prop="student_id" label="学号" width="120" />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="class_name" label="班级" width="100" />
        <el-table-column prop="major" label="专业" />
        <el-table-column prop="count" label="参与次数" width="100" sortable />
      </el-table>

      <el-row :gutter="20">
        <el-col :span="12">
          <h4>参与次数柱状图（Top 10）</h4>
          <div ref="barChartRef" style="width:100%;height:300px"></div>
        </el-col>
        <el-col :span="12">
          <h4>活动趋势折线图</h4>
          <div ref="lineChartRef" style="width:100%;height:300px"></div>
        </el-col>
      </el-row>
    </template>

    <template v-if="historyRecords.length > 0">
      <el-divider />
      <el-row justify="space-between" style="margin-bottom:12px">
        <h4>识别历史</h4>
        <el-button type="success" size="small" @click="exportRecords">导出Excel</el-button>
      </el-row>
      <el-collapse>
        <el-collapse-item v-for="record in historyRecords" :key="record.id">
          <template #title>
            <div style="display:flex;justify-content:space-between;width:100%;padding-right:20px;align-items:center">
              <span><strong>{{ record.activity_name || '合照识别' }}</strong></span>
              <div>
                <span style="margin-right:12px">识别 {{ record.recognized_student_count || 0 }} 人 | {{ record.timestamp }}</span>
                <el-button type="danger" size="small" @click.stop="deleteRecord(record.id)">删除</el-button>
              </div>
            </div>
          </template>

          <el-alert type="success" style="margin-bottom:12px" :closable="false">
            <div>总人脸数：{{ record.total_faces || 0 }} | 匹配成功：{{ record.matched_count || 0 }} | 未知人脸：{{ record.unknown_count || 0 }}</div>
            <div>识别学生数：{{ record.recognized_student_count || 0 }}</div>
            <div v-if="record.emotion_summary">
              情绪统计：
              <el-tag v-for="(count, emotion) in record.emotion_summary" :key="emotion" size="small" style="margin-left:4px">
                {{ emotion }}: {{ count }}人
              </el-tag>
            </div>
          </el-alert>

          <el-table :data="record.students || []" border size="small">
            <el-table-column prop="student_id" label="学号" width="120" />
            <el-table-column prop="name" label="姓名" width="100" />
            <el-table-column prop="major" label="专业" />
            <el-table-column prop="face_score" label="置信度" width="100">
              <template #default="{ row }">{{ (row.face_score * 100).toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column label="情绪" width="120">
              <template #default="{ row }">
                <span v-if="row.emotion">{{ row.emotion }}</span>
                <el-tag v-else-if="row.emotion_error_code" type="danger" size="small">分析失败</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-collapse-item>
      </el-collapse>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import request from '../../api/request'
import * as echarts from 'echarts'

const file = ref(null)
const result = ref(null)
const loading = ref(false)
const form = ref({ activity_name: '', activity_date: '', course_id: null, description: '' })
const previewUrl = ref(null)
const historyRecords = ref([])
const studentStats = ref([])
const barChartRef = ref(null)
const lineChartRef = ref(null)
const groupEmotionChartRef = ref(null)
let barChartInstance = null
let lineChartInstance = null
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

const groupEmotionStats = computed(() => {
  const statsMap = {}
  let total = 0
  historyRecords.value.forEach(record => {
    if (record.emotion_summary) {
      Object.entries(record.emotion_summary).forEach(([emotion, count]) => {
        const emotionCn = emotionMap[emotion] || emotion
        statsMap[emotionCn] = (statsMap[emotionCn] || 0) + count
        total += count
      })
    }
  })
  return Object.entries(statsMap).map(([emotion, count]) => ({
    emotion,
    count,
    percentage: total > 0 ? ((count / total) * 100).toFixed(1) : 0
  })).sort((a, b) => b.count - a.count)
})

function calculateStats() {
  const statsMap = {}
  historyRecords.value.forEach(record => {
    (record.students || []).forEach(student => {
      if (!statsMap[student.student_id]) {
        statsMap[student.student_id] = {
          student_id: student.student_id,
          name: student.name,
          class_name: student.class_name,
          major: student.major,
          count: 0
        }
      }
      statsMap[student.student_id].count++
    })
  })
  studentStats.value = Object.values(statsMap).sort((a, b) => b.count - a.count)
  nextTick(() => {
    initCharts()
  })
}

function initCharts() {
  if (!barChartRef.value || !lineChartRef.value) return

  if (barChartInstance) barChartInstance.dispose()
  barChartInstance = echarts.init(barChartRef.value)
  const top10 = studentStats.value.slice(0, 10)
  barChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: top10.map(s => s.name),
      axisLabel: { rotate: 45 }
    },
    yAxis: { type: 'value', name: '参与次数' },
    series: [{
      type: 'bar',
      data: top10.map(s => s.count),
      itemStyle: { color: '#409EFF' }
    }]
  })

  if (lineChartInstance) lineChartInstance.dispose()
  lineChartInstance = echarts.init(lineChartRef.value)
  const sortedRecords = [...historyRecords.value].sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
  lineChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: sortedRecords.map(r => new Date(r.created_at).toLocaleDateString('zh-CN')),
      axisLabel: { rotate: 45 }
    },
    yAxis: { type: 'value', name: '参与人数' },
    series: [{
      type: 'line',
      data: sortedRecords.map(r => r.recognized_student_count || 0),
      smooth: true,
      itemStyle: { color: '#67C23A' }
    }]
  })

  if (groupEmotionChartRef.value && groupEmotionStats.value.length > 0) {
    if (emotionChartInstance) emotionChartInstance.dispose()
    emotionChartInstance = echarts.init(groupEmotionChartRef.value)
    emotionChartInstance.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: '60%',
        data: groupEmotionStats.value.map(s => ({ name: s.emotion, value: s.count })),
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
}

async function loadRecords() {
  try {
    const res = await request.get('/api/group-photo/records')
    const records = Array.isArray(res) ? res : (res.data || [])
    historyRecords.value = records.map(r => ({
      ...r,
      timestamp: new Date(r.created_at).toLocaleString('zh-CN')
    }))
    calculateStats()
  } catch (e) {
    console.error('加载历史记录失败:', e)
  }
}

async function deleteRecord(recordId) {
  try {
    await ElMessageBox.confirm('确定要删除这条活动记录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await request.delete(`/api/group-photo/records/${recordId}`)
    ElMessage.success('删除成功')
    await loadRecords()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.message || '删除失败')
    }
  }
}

async function exportRecords() {
  try {
    const response = await request.get('/api/group-photo/records/export', {
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `合照记录_${new Date().toLocaleDateString('zh-CN')}.xlsx`)
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

function onFileChange(f) {
  file.value = f.raw
  if (f.raw) {
    previewUrl.value = URL.createObjectURL(f.raw)
  }
}

async function recognize() {
  loading.value = true
  ElMessage.info('识别中，请稍候...')
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    if (form.value.activity_name) fd.append('activity_name', form.value.activity_name)
    if (form.value.activity_date) fd.append('activity_date', form.value.activity_date)
    if (form.value.course_id) fd.append('course_id', form.value.course_id)
    if (form.value.description) fd.append('description', form.value.description)

    result.value = await request.post('/api/group-photo/recognize', fd, { timeout: 60000 })

    ElMessage.success('识别成功')
    await loadRecords()
  } catch (e) {
    console.error('识别失败:', e)
    if (e.code === 'ECONNABORTED' || e.message.includes('timeout')) {
      ElMessage.warning('识别处理中，请稍后刷新页面查看结果')
      setTimeout(() => loadRecords(), 3000)
    } else {
      ElMessage.error(e.response?.data?.message || e.response?.data?.detail || '识别失败')
    }
  } finally {
    loading.value = false
  }
}
</script>
