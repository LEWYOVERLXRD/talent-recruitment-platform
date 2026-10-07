// 认证相关接口封装：注册、登录、忘记密码（密保）、获取当前用户
import request from './request'

// 注册
// POST /api/v1/auth/register
// 请求体：{ username, password, real_name?, email?, phone?, role, company_name?, security_answers }
//   - security_answers: [{ question_code, answer }] 固定 3 条且题目不重复
//   - role=recruiter 时 company_name 必填；role 不允许 admin
// 响应：UserOut（不含密码）
export function register(data) {
  return request.post('/api/v1/auth/register', data)
}

// 登录
// POST /api/v1/auth/login
// 请求体：{ username, password }
// 响应：{ access_token, token_type }
// 错误：401 用户名或密码错误；403 账号已被禁用
export function login(data) {
  return request.post('/api/v1/auth/login', data)
}

// 获取当前登录用户信息
// GET /api/v1/users/me
// 请求头：Authorization: Bearer <token>
// 响应：UserOut
export function getCurrentUser() {
  return request.get('/api/v1/users/me')
}

// 忘记密码-第一步：按账号取密保问题
// GET /api/v1/auth/security-questions?username=xxx
// 响应：{ username, questions: [{ question_code, question_text }] }
// 错误：404 账号不存在；400 该账号未设置密保
export function getSecurityQuestions(username) {
  return request.get('/api/v1/auth/security-questions', {
    params: { username },
  })
}

// 忘记密码-第二步：提交密保答案并设置新密码
// POST /api/v1/auth/password/reset
// 请求体：{ username, answers: [{ question_code, answer }], new_password }
// 错误：400 答案错误（提示剩余次数）；423 失败次数过多被锁定
export function resetPassword(data) {
  return request.post('/api/v1/auth/password/reset', data)
}