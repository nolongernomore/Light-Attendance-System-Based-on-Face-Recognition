import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: () => import('../views/Login.vue') },
  {
    path: '/teacher',
    component: () => import('../views/teacher/Layout.vue'),
    redirect: '/teacher/courses',
    meta: { role: 'teacher' },
    children: [
      { path: 'courses', component: () => import('../views/teacher/Courses.vue') },
      { path: 'sessions', component: () => import('../views/teacher/Sessions.vue') },
      { path: 'student', component: () => import('../views/teacher/Student.vue') },
      { path: 'group-photo', component: () => import('../views/teacher/GroupPhoto.vue') },
      { path: 'records', component: () => import('../views/teacher/Records.vue') }
    ]
  },
  {
    path: '/student',
    component: () => import('../views/student/Layout.vue'),
    redirect: '/student/checkin',
    meta: { role: 'student' },
    children: [
      { path: 'checkin', component: () => import('../views/student/Checkin.vue') },
      { path: 'my-records', component: () => import('../views/student/MyRecords.vue') },
      { path: 'my-face', component: () => import('../views/student/MyFace.vue') }
    ]
  }
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role')
  if (to.path === '/login') return next()
  if (!token) return next('/login')
  if (to.meta.role && to.meta.role !== role) return next('/login')
  next()
})

export default router
