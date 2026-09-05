<template>
  <el-container style="height:100vh">
    <el-aside width="200px" style="background:#304156">
      <div style="color:#fff;padding:20px;font-size:16px;font-weight:bold">考勤系统</div>
        <el-menu
          :default-active="route.path"
          router
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409EFF"
        >
          <el-menu-item index="/teacher/courses">课堂管理</el-menu-item>
          <el-menu-item index="/teacher/sessions">考勤场次</el-menu-item>
          <el-menu-item index="/teacher/student">学生管理</el-menu-item>
          <el-menu-item index="/teacher/group-photo">合照识别</el-menu-item>
          <el-menu-item index="/teacher/records">考勤记录</el-menu-item>
        </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display:flex;align-items:center;justify-content:flex-end;border-bottom:1px solid #eee">
        <span style="margin-right:12px">{{ username }}</span>
        <el-button size="small" @click="logout">退出</el-button>
      </el-header>
      <el-main><router-view :key="route.path" /></el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRouter, useRoute } from 'vue-router'
const router = useRouter()
const route = useRoute()
const username = localStorage.getItem('username')
function logout() {
  localStorage.clear()
  router.push('/login')
}
</script>
