<template>
  <div style="max-width:600px;margin:0 auto;padding:20px">
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>摄像头考勤</span>
          <el-tag style="margin-left:12px" :type="statusType">{{ statusText }}</el-tag>
        </div>
        <div v-if="sessionInfo" style="margin-top:8px;font-size:14px;color:#606266">
          当前考勤：{{ sessionInfo.title }} ({{ sessionInfo.course_name }})
        </div>
      </template>

      <div style="text-align:center;position:relative">
        <div v-if="flashColor" :style="{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: flashColor,
          opacity: 0.3,
          pointerEvents: 'none',
          zIndex: 10
        }"></div>
        <video ref="videoRef" autoplay style="width:100%;max-width:480px;border:1px solid #ddd;border-radius:4px"></video>
        <canvas ref="canvasRef" width="480" height="360" style="display:none"></canvas>
      </div>

      <el-alert v-if="currentAction" :title="`请完成动作：${currentAction}`" type="warning" show-icon style="margin-top:12px" />
      <el-alert v-if="stabilizing" title="请保持稳定，即将抓拍..." type="info" show-icon style="margin-top:12px" />
      <el-progress v-if="detecting" :percentage="progress" style="margin-top:12px" />

      <div style="margin-top:16px;text-align:center">
        <el-button v-if="!streaming" type="primary" @click="startCamera">开启摄像头</el-button>
        <el-button v-else @click="stopCamera">关闭摄像头</el-button>
      </div>

      <div v-if="capturedImage" style="margin-top:16px;text-align:center">
        <h4 style="margin-bottom:8px">抓拍照片</h4>
        <img :src="capturedImage" style="max-width:100%;border:1px solid #ddd;border-radius:4px" />
      </div>

      <el-result v-if="checkinResult" :icon="checkinResult.success ? 'success' : 'error'"
        :title="checkinResult.message" style="padding:20px 0">
        <template #extra v-if="checkinResult.emotion">
          <el-tag type="success">情绪：{{ checkinResult.emotion }}</el-tag>
          <el-tag v-if="checkinResult.emotionConfidence" type="info" style="margin-left:8px">
            置信度：{{ (checkinResult.emotionConfidence * 100).toFixed(1) }}%
          </el-tag>
        </template>
      </el-result>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as faceapi from 'face-api.js'
import request from '../../api/request'

const videoRef = ref()
const canvasRef = ref()
const streaming = ref(false)
const detecting = ref(false)
const currentAction = ref('')
const progress = ref(0)
const stabilizing = ref(false)
const flashColor = ref('')
const checkinResult = ref(null)
const sessionId = ref(null)
const sessionInfo = ref(null)
const modelsLoaded = ref(false)
const capturedImage = ref(null)
let stream = null
let detectionInterval = null

const statusText = computed(() => {
  if (!streaming.value) return '未开启'
  if (detecting.value) return '检测中'
  return '就绪'
})
const statusType = computed(() => {
  if (!streaming.value) return 'info'
  if (detecting.value) return 'warning'
  return 'success'
})

// 加载 face-api 模型
async function loadModels() {
  if (modelsLoaded.value) return
  try {
    await Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri('/models'),
      faceapi.nets.faceLandmark68Net.loadFromUri('/models')
    ])
    modelsLoaded.value = true
  } catch (e) {
    ElMessage.error('模型加载失败，请刷新页面重试')
  }
}

onMounted(loadModels)

// 随机生成活体动作
function generateAction() {
  const actions = ['张嘴', '摇头']
  return actions[Math.floor(Math.random() * actions.length)]
}

// 开启摄像头
async function startCamera() {
  if (!modelsLoaded.value) {
    ElMessage.warning('模型加载中，请稍候')
    return
  }
  checkinResult.value = null
  capturedImage.value = null
  stabilizing.value = false
  try {
    const res = await request.get('/api/attendance/my-sessions/active')
    const sessions = Array.isArray(res) ? res : (res.data || [])
    if (!sessions || sessions.length === 0) {
      ElMessage.warning('当前没有进行中的考勤')
      return
    }
    const session = sessions[0]
    sessionId.value = session.id
    sessionInfo.value = session
  } catch {
    ElMessage.warning('无法获取考勤状态')
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true })
    videoRef.value.srcObject = stream
    streaming.value = true
    currentAction.value = generateAction()
    startDetection()
  } catch {
    ElMessage.error('无法访问摄像头')
  }
}

// 计算 MAR (Mouth Aspect Ratio) - 张嘴检测
function calculateMAR(mouth) {
  const v1 = Math.hypot(mouth[2].x - mouth[10].x, mouth[2].y - mouth[10].y)
  const v2 = Math.hypot(mouth[4].x - mouth[8].x, mouth[4].y - mouth[8].y)
  const h = Math.hypot(mouth[0].x - mouth[6].x, mouth[0].y - mouth[6].y)
  return (v1 + v2) / (2 * h)
}

// 启动活体检测
let mouthOpenCount = 0
let noseHistory = []
let flashInterval = null

async function startDetection() {
  detecting.value = true
  progress.value = 0
  mouthOpenCount = 0
  noseHistory = []

  // 随机闪光防作弊
  const colors = ['#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF']
  flashInterval = setInterval(() => {
    flashColor.value = colors[Math.floor(Math.random() * colors.length)]
    setTimeout(() => { flashColor.value = '' }, 200)
  }, 1500)

  // 等待视频准备就绪
  await new Promise(resolve => {
    if (videoRef.value.readyState >= 2) resolve()
    else videoRef.value.onloadeddata = resolve
  })

  const detect = async () => {
    if (!streaming.value) return
    try {
      const detection = await faceapi.detectSingleFace(videoRef.value, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks()
      if (detection) {
        const landmarks = detection.landmarks.positions
        const mouth = landmarks.slice(48, 68)
        const nose = landmarks[30]

        const mar = calculateMAR(mouth)

        if (currentAction.value === '张嘴') {
          if (mar > 0.6) mouthOpenCount++
          progress.value = Math.min(mouthOpenCount * 10, 100)
          if (mouthOpenCount >= 10) {
            if (detectionInterval) cancelAnimationFrame(detectionInterval)
            stabilizing.value = true
            await new Promise(resolve => setTimeout(resolve, 1000))
            return await captureAndSubmit()
          }
        } else if (currentAction.value === '摇头') {
          noseHistory.push(nose.x)
          if (noseHistory.length > 30) noseHistory.shift()
          if (noseHistory.length >= 30) {
            const range = Math.max(...noseHistory) - Math.min(...noseHistory)
            progress.value = Math.min(range * 2, 100)
            if (range > 50) {
              if (detectionInterval) cancelAnimationFrame(detectionInterval)
              stabilizing.value = true
              await new Promise(resolve => setTimeout(resolve, 1000))
              return await captureAndSubmit()
            }
          }
        }
      }
    } catch (e) {
      console.error('检测错误:', e)
    }
    detectionInterval = requestAnimationFrame(detect)
  }
  detect()
}

// 抓拍并提交
async function captureAndSubmit() {
  detecting.value = false
  stabilizing.value = false
  if (detectionInterval) cancelAnimationFrame(detectionInterval)
  if (flashInterval) clearInterval(flashInterval)
  flashColor.value = ''

  ElMessage.success('活体识别成功！正在提交考勤...')

  try {
    const ctx = canvasRef.value.getContext('2d')
    ctx.drawImage(videoRef.value, 0, 0, 480, 360)

    // 图像预处理：自动调整亮度和对比度
    const imageData = ctx.getImageData(0, 0, 480, 360)
    const data = imageData.data

    // 计算平均亮度
    let sum = 0
    for (let i = 0; i < data.length; i += 4) {
      sum += (data[i] + data[i + 1] + data[i + 2]) / 3
    }
    const avgBrightness = sum / (data.length / 4)

    // 如果亮度过低或过高，进行调整
    if (avgBrightness < 100 || avgBrightness > 180) {
      const factor = 128 / avgBrightness
      for (let i = 0; i < data.length; i += 4) {
        data[i] = Math.min(255, data[i] * factor)
        data[i + 1] = Math.min(255, data[i + 1] * factor)
        data[i + 2] = Math.min(255, data[i + 2] * factor)
      }
      ctx.putImageData(imageData, 0, 0)
    }

    const blob = await new Promise(r => canvasRef.value.toBlob(r, 'image/jpeg', 0.9))

    capturedImage.value = URL.createObjectURL(blob)

    const fd = new FormData()
    fd.append('session_id', sessionId.value)
    fd.append('file', blob, 'checkin.jpg')
    fd.append('liveness_passed', 'true')

    const response = await request.post('/api/attendance/checkin', fd)

    if (response.success) {
      const emotionData = response.data?.emotion || response.data?.record?.emotion_result
      checkinResult.value = {
        success: true,
        message: '考勤成功',
        emotion: emotionData?.emotion_cn || emotionData?.emotion,
        emotionConfidence: emotionData?.confidence
      }
      stopCamera()
    } else {
      const reasonCode = response.data?.reason_code
      let errorMsg = '考勤失败'

      switch (reasonCode) {
        case 'LIVENESS_TIMEOUT':
          errorMsg = '活体检测超时，请重试'
          break
        case 'LIVENESS_FAILED':
          errorMsg = '活体检测未通过，请重试'
          break
        case 'FACE_NOT_ENROLLED':
          errorMsg = '未录入人脸照片，请先录入'
          break
        case 'FACE_TEMPLATE_INCOMPATIBLE':
          errorMsg = '人脸模板不兼容，请重新录入照片'
          break
        case 'FACE_SERVICE_TIMEOUT':
          errorMsg = '人脸识别服务超时，请重试'
          break
        case 'INVALID_IMAGE':
          errorMsg = '图片格式异常，请重试'
          break
        case 'NO_FACE':
          errorMsg = '未检测到人脸，请重试'
          break
        case 'MULTIPLE_FACE':
          errorMsg = '检测到多张人脸，请确保只有您一人'
          break
        case 'LOW_QUALITY':
          errorMsg = '人脸质量太低，请靠近摄像头'
          break
        case 'UNKNOWN_FACE':
          errorMsg = '人脸识别失败，请重试'
          break
        case 'FACE_SERVICE_ERROR':
          errorMsg = '人脸识别服务异常，请稍后重试'
          break
        default:
          errorMsg = '考勤失败，请重试'
      }

      checkinResult.value = {
        success: false,
        message: errorMsg
      }
      detecting.value = false
    }
  } catch (e) {
    console.error('考勤请求异常:', e.response?.data || e)
    const errorData = e.response?.data

    if (errorData && !errorData.success) {
      const reasonCode = errorData.data?.reason_code
      let errorMsg = '考勤失败'

      switch (reasonCode) {
        case 'LIVENESS_TIMEOUT':
          errorMsg = '活体检测超时，请重试'
          break
        case 'LIVENESS_FAILED':
          errorMsg = '活体检测未通过，请重试'
          break
        case 'FACE_NOT_ENROLLED':
          errorMsg = '未录入人脸照片，请先录入'
          break
        case 'FACE_TEMPLATE_INCOMPATIBLE':
          errorMsg = '人脸模板不兼容，请重新录入照片'
          break
        case 'FACE_SERVICE_TIMEOUT':
          errorMsg = '人脸识别服务超时，请重试'
          break
        case 'INVALID_IMAGE':
          errorMsg = '图片格式异常，请重试'
          break
        case 'NO_FACE':
          errorMsg = '未检测到人脸，请重试'
          break
        case 'MULTIPLE_FACE':
          errorMsg = '检测到多张人脸，请确保只有您一人'
          break
        case 'LOW_QUALITY':
          errorMsg = '人脸质量太低，请靠近摄像头'
          break
        case 'UNKNOWN_FACE':
          errorMsg = '人脸识别失败，请重试'
          break
        case 'FACE_SERVICE_ERROR':
          errorMsg = '人脸识别服务异常，请稍后重试'
          break
        default:
          errorMsg = errorData?.message || '考勤失败，请重试'
      }

      checkinResult.value = {
        success: false,
        message: errorMsg
      }
    } else {
      checkinResult.value = {
        success: false,
        message: errorData?.message || '考勤失败'
      }
    }
    detecting.value = false
  }
}

// 关闭摄像头
function stopCamera() {
  stream?.getTracks().forEach(t => t.stop())
  stream = null
  streaming.value = false
  detecting.value = false
  if (detectionInterval) cancelAnimationFrame(detectionInterval)
}

onUnmounted(stopCamera)
</script>

