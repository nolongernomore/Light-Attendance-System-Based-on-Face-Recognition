<template>
  <div style="max-width:600px;margin:0 auto;padding:20px">
    <el-card>
      <template #header>我的人脸照片</template>

      <el-skeleton :loading="loading" animated>
        <template #default>
          <div v-if="status">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="录入状态">
                <el-tag :type="status.has_face_image ? 'success' : 'info'">
                  {{ status.has_face_image ? '已录入' : '未录入' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="录入时间" v-if="status.enrolled_at">
                {{ status.enrolled_at }}
              </el-descriptions-item>
            </el-descriptions>

            <div v-if="status.has_face_image && faceImage" style="margin-top:20px;text-align:center">
              <h4>当前照片</h4>
              <img :src="faceImage" style="max-width:100%;max-height:400px;border:1px solid #ddd;border-radius:4px" />
              <div style="margin-top:12px">
                <el-button type="danger" size="small" @click="deleteFace">删除照片</el-button>
              </div>
            </div>

            <el-empty v-else-if="!status.has_face_image" description="您还未录入人脸照片" />
          </div>
        </template>
      </el-skeleton>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../../api/request'

const loading = ref(true)
const status = ref(null)
const faceImage = ref(null)
const imageId = ref(null)

async function loadStatus() {
  try {
    const response = await request.get('/api/face/my-status')
    console.log('照片状态响应:', response)
    status.value = response.data || response
    if (status.value.has_face_image) {
      await loadImage()
    }
  } catch (e) {
    console.error('加载状态失败:', e)
    console.error('错误详情:', e.response?.data)
    ElMessage.error(e.response?.data?.message || '加载状态失败')
  } finally {
    loading.value = false
  }
}

async function loadImage() {
  try {
    const response = await request.get('/api/face/my-image')
    console.log('照片数据响应:', response)
    if (response.data?.image?.data_url) {
      faceImage.value = response.data.image.data_url
      imageId.value = response.data.image.id
      console.log('照片加载成功')
    } else {
      console.error('响应中没有找到 data_url，响应结构:', response)
      ElMessage.warning('照片数据格式异常')
    }
  } catch (e) {
    console.error('加载照片失败:', e)
    console.error('错误详情:', e.response?.data)
    ElMessage.error(e.response?.data?.message || '加载照片失败')
  }
}

async function deleteFace() {
  if (!imageId.value) {
    ElMessage.warning('没有可删除的照片')
    return
  }
  try {
    await ElMessageBox.confirm('确定要删除人脸照片吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await request.delete(`/api/face/my-images/${imageId.value}`)
    ElMessage.success('删除成功')
    faceImage.value = null
    imageId.value = null
    status.value.has_face_image = false
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.message || '删除失败')
    }
  }
}

onMounted(loadStatus)
</script>
