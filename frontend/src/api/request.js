// Axios 实例：统一 baseURL、自动携带 Token、统一错误处理
import axios from 'axios'
import { useUserStore } from '@/stores/user'
import router from '@/router'

const service = axios.create({
  // 开发期走 vite 代理（/api -> http://127.0.0.1:8000）
  // 生产期通过 .env 的 VITE_API_BASE_URL 配置
  baseURL: import.meta.env.VITE_API_BASE_URL || '/',
  timeout: 10000,
})

// 请求拦截器：自动携带 Authorization: Bearer <token>
service.interceptors.request.use(
  (config) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// 响应拦截器：处理 401、提取 detail 错误信息
service.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const status = error.response?.status
    let detail = '请求失败，请稍后重试'
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      detail = '请求超时，请先刷新页面确认处理结果，再决定是否重试'
    }

    // 下载等 blob 请求失败时，后端错误体是 Blob，需读取后再取 detail
    if (error.response?.data instanceof Blob) {
      try {
        const text = await error.response.data.text()
        const parsed = JSON.parse(text)
        detail = parsed?.detail || parsed?.message || detail
      } catch {
        // 非 JSON blob，保留默认提示
      }
    } else {
      detail =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        detail
    }

    // 401：token 失效或未登录，清除状态并跳登录页
    if (status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      // 避免在登录页死循环
      if (router.currentRoute.value.name !== 'Login') {
        router.push({
          name: 'Login',
          query: { redirect: router.currentRoute.value.fullPath },
        })
      }
    }

    // 统一抛出字符串错误信息，页面层直接 message.error(err) 即可
    const message = typeof detail === 'string' ? detail : JSON.stringify(detail)
    // C 批需要按状态处理失权/冲突；既有 A/B 调用继续收到字符串。
    return Promise.reject(error.config?.businessStatus ? { status, message } : message)
  },
)

export default service
