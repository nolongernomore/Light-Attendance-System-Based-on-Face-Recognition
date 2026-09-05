<template>
  <div>
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card header="今日出勤统计">
          <div ref="barRef" style="height:300px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="情绪分布">
          <div ref="pieRef" style="height:300px"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'
import request from '../../api/request'

const barRef = ref()
const pieRef = ref()

onMounted(async () => {
  try {
    const [attendanceRes, emotionRes] = await Promise.all([
      request.get('/api/stats/attendance', { params: { course_id: 1 } }),
      request.get('/api/stats/emotion', { params: { course_id: 1 } })
    ])

    const attendance = attendanceRes.data || attendanceRes
    const emotion = emotionRes.data || emotionRes

    echarts.init(barRef.value).setOption({
      tooltip: {},
      xAxis: { data: attendance.labels || ['出勤', '缺勤', '迟到'] },
      yAxis: {},
      series: [{ type: 'bar', data: attendance.values || [0, 0, 0], itemStyle: { color: '#409EFF' } }]
    })

    echarts.init(pieRef.value).setOption({
      tooltip: { trigger: 'item' },
      series: [{ type: 'pie', radius: '60%', data: emotion.distribution || [] }]
    })
  } catch {
    echarts.init(barRef.value).setOption({
      tooltip: {},
      xAxis: { data: ['出勤', '缺勤', '迟到'] },
      yAxis: {},
      series: [{ type: 'bar', data: [0, 0, 0], itemStyle: { color: '#409EFF' } }]
    })
    echarts.init(pieRef.value).setOption({
      tooltip: { trigger: 'item' },
      series: [{ type: 'pie', radius: '60%', data: [] }]
    })
  }
})
</script>
