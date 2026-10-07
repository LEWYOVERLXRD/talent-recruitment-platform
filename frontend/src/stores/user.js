// 用户状态：token、当前用户、登录/退出动作、角色派生信息
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister, getCurrentUser as apiGetMe } from '@/api/auth'

const TOKEN_KEY = 'recruitment_token'

// 平台角色中文映射
const ROLE_LABELS = {
  admin: '平台管理员',
  recruiter: '企业招聘方',
  headhunter: '猎头',
  jobseeker: '求职者',
}

// 企业内角色中文映射
const COMPANY_ROLE_LABELS = {
  manager: '企业主管',
  staff: '普通员工',
}

// 角色菜单：按平台角色 + 企业内角色决定侧边栏可见项
// done=false 的菜单仅占位，业务模块后续阶段开发
const MENUS_BY_ROLE = {
  admin: [
    { key: 'dashboard', label: '工作台' },
    { key: 'jobs', label: '招聘需求', done: true },
    { key: 'companies', label: '企业管理', done: false },
    { key: 'users', label: '用户管理', done: false },
  ],
  recruiter: [
    { key: 'dashboard', label: '工作台' },
    { key: 'jobs', label: '招聘需求', done: true },
    { key: 'resumes', label: '简历管理', done: false },
    { key: 'applications', label: '求职投递', done: false },
  ],
  headhunter: [
    { key: 'dashboard', label: '工作台' },
    { key: 'jobs', label: '招聘需求', done: true },
    { key: 'candidates', label: '候选人管理', done: false },
  ],
  jobseeker: [
    { key: 'dashboard', label: '工作台' },
    { key: 'jobs', label: '岗位浏览', done: false },
    { key: 'resume', label: '我的简历', done: false },
    { key: 'applications', label: '我的投递', done: false },
  ],
}

export const useUserStore = defineStore('user', () => {
  // token：初始值从 localStorage 读取（刷新页面不丢失）
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  // 当前登录用户信息
  const user = ref(null)

  // 是否已登录（有 token 即认为登录）
  const isLoggedIn = computed(() => !!token.value)

  // 显示名：优先用 real_name，其次 username
  const displayName = computed(() => user.value?.real_name || user.value?.username || '')

  // 平台角色
  const role = computed(() => user.value?.role || '')

  // 平台角色中文
  const roleLabel = computed(() => ROLE_LABELS[role.value] || role.value)

  // 企业内角色中文（非招聘方为空）
  const companyRoleLabel = computed(
    () => COMPANY_ROLE_LABELS[user.value?.company_role] || '',
  )

  // 是否平台管理员
  const isAdmin = computed(() => role.value === 'admin')

  // 是否企业主管（仅本企业 staff 的管理权限）
  const isManager = computed(
    () => role.value === 'recruiter' && user.value?.company_role === 'manager',
  )

  // 当前角色可见的菜单
  const menus = computed(() => MENUS_BY_ROLE[role.value] || [])

  // 保存 token（同时写入 localStorage）
  function setToken(newToken) {
    token.value = newToken
    if (newToken) {
      localStorage.setItem(TOKEN_KEY, newToken)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  }

  // 登录：调接口拿 token，接着拉一次用户信息（角色菜单依赖它）
  async function login(loginForm) {
    const data = await apiLogin(loginForm)
    setToken(data.access_token)
    await fetchCurrentUser()
    return data
  }

  // 注册：调接口创建用户，成功后自动登录
  async function register(registerForm) {
    await apiRegister(registerForm)
    // 注册成功后自动用相同账号密码登录
    await login({
      username: registerForm.username,
      password: registerForm.password,
    })
  }

  // 拉取当前用户信息
  async function fetchCurrentUser() {
    if (!token.value) return null
    try {
      user.value = await apiGetMe()
      return user.value
    } catch (e) {
      // token 失效，清掉
      setToken('')
      user.value = null
      throw e
    }
  }

  // 退出登录：清除 token 和用户状态
  function logout() {
    setToken('')
    user.value = null
  }

  return {
    token,
    user,
    isLoggedIn,
    displayName,
    role,
    roleLabel,
    companyRoleLabel,
    isAdmin,
    isManager,
    menus,
    setToken,
    login,
    register,
    fetchCurrentUser,
    logout,
  }
})