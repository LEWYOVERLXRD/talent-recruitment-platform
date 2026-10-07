// 路由配置 + 全局前置守卫
import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

// 路由按模块组织：auth（登录/注册/找回密码/协议）、home（首页）
// 后续新增模块（job/resume/application/...）时，在此处分块追加
const routes = [
  // ===== home 模块 =====
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/home/HomeView.vue'),
    meta: { requiresAuth: true, title: '首页' },
  },


    {
    path: '/header',
    name: 'Header',
    component: () => import('@/views/common/Header.vue'),
    meta: {  title: 'Header' },
  },
  // ===== auth 模块 =====
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { title: '注册' },
  },
  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('@/views/auth/ForgotPasswordView.vue'),
    meta: { title: '找回密码' },
  },
  {
    // 协议静态页：按 :type 区分《服务协议》与《隐私政策》
    path: '/agreement/:type',
    name: 'Agreement',
    component: () => import('@/views/auth/AgreementView.vue'),
    meta: { title: '协议条款' },
  },

  // ===== job 模块（招聘需求管理）=====
  {
    path: '/jobs',
    name: 'Jobs',
    component: () => import('@/views/job/JobListView.vue'),
    meta: {
      requiresAuth: true,
      roles: ['admin', 'recruiter', 'headhunter'],
      title: '招聘需求管理',
    },
  },

  {
    // 未匹配路由统一回到首页
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 已登录后无需再访问的页面（协议页不在此列，登录后也应能查看）
const AUTH_PAGES = ['Login', 'Register', 'ForgotPassword']

// 全局前置守卫：
// 1. 访问需要登录的页面时，若未登录则跳转登录页
// 2. 已登录用户访问登录/注册页，重定向到首页
// 3. 页面声明了 meta.roles 时，校验当前用户角色是否有权访问
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  // 已登录但还没拉取用户信息：拉一次（用于页面展示与角色判断）
  if (userStore.isLoggedIn && !userStore.user) {
    try {
      await userStore.fetchCurrentUser()
    } catch (e) {
      // 拉取失败（token 失效）继续往下走，下面会拦截到登录页
    }
  }

  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    return next({ name: 'Login', query: { redirect: to.fullPath } })
  }

  // 角色守卫：无权限则回到首页（不暴露被拒页面信息）
  if (to.meta.roles && !to.meta.roles.includes(userStore.role)) {
    return next({ name: 'Home' })
  }

  if (AUTH_PAGES.includes(to.name) && userStore.isLoggedIn) {
    return next({ name: 'Home' })
  }

  next()
})

// 页面标题
router.afterEach((to) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - 智能招聘平台`
  }
})

export default router