<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>班级考勤系统</h2>
      <el-form :model="form" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="账号" prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock" />
        </el-form-item>
        <el-form-item>
          <el-radio-group v-model="form.role">
            <el-radio value="teacher">教师</el-radio>
            <el-radio value="student">学生</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width:100%">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../api/request'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '', role: 'teacher' })

async function handleLogin() {
  loading.value = true
  try {
    const res = await request.post('/api/auth/login', { username: form.username, password: form.password })
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('role', form.role)
    localStorage.setItem('username', form.username)
    router.push(form.role === 'teacher' ? '/teacher' : '/student/checkin')
  } catch {
    ElMessage.error('登录失败，请检查账号密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { display:flex; justify-content:center; align-items:center; height:100vh; background:#f0f2f5; }
.login-card { width:380px; }
h2 { text-align:center; margin-bottom:24px; }
</style>
