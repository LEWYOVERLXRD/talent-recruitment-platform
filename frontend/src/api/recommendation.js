// 推荐交付 / 客户反馈 接口封装
import request from './request'

// 推荐列表 GET /api/v1/recommendations?page=&size=
// 响应：{ total, items: dict[] }（item 为推荐对象 dict，随角色/状态呈现不同态）
export function listRecommendations(params) {
  return request.get('/api/v1/recommendations', { params, businessStatus: true })
}

// 创建推荐草稿 POST /api/v1/recommendations
// 请求体：{ assignment_id, candidate_id }
export function createRecommendation(payload) {
  return request.post('/api/v1/recommendations', payload, { businessStatus: true })
}

// 推荐详情 GET /api/v1/recommendations/{id}
export function getRecommendation(id) {
  return request.get(`/api/v1/recommendations/${id}`, { businessStatus: true })
}

// 准备字段更新 PATCH /api/v1/recommendations/{id}
// 请求体：{ expected_version, resume_id?, communication_id?, recommendation_note? }
export function updateRecommendation(id, payload) {
  return request.patch(`/api/v1/recommendations/${id}`, payload, { businessStatus: true })
}

// 推进准备阶段 POST /api/v1/recommendations/{id}/stage
// 请求体：{ expected_version, status: contacted|pending_recommend, communication_id }
export function stageRecommendation(id, payload) {
  return request.post(`/api/v1/recommendations/${id}/stage`, payload, { businessStatus: true })
}

// 刷新准备上下文 POST /api/v1/recommendations/{id}/refresh-context
// 请求体：{ expected_version, job_version, assignment_round }
export function refreshRecommendationContext(id, payload) {
  return request.post(`/api/v1/recommendations/${id}/refresh-context`, payload, {
    businessStatus: true,
  })
}

// 一次性交付快照 POST /api/v1/recommendations/{id}/submit
// 请求体：{ expected_version, share_basis, share_confirmed_at }
export function submitRecommendation(id, payload) {
  return request.post(`/api/v1/recommendations/${id}/submit`, payload, { businessStatus: true })
}

// 反馈历史分页 GET /api/v1/recommendations/{id}/feedbacks?page=&size=
// 响应：{ total, items: RecommendationFeedbackOut[] }
export function listFeedbacks(id, params) {
  return request.get(`/api/v1/recommendations/${id}/feedbacks`, { params, businessStatus: true })
}

// 客户追加反馈 POST /api/v1/recommendations/{id}/feedbacks
// 请求体：{ expected_version, conclusion, feedback_type, content }
export function addFeedback(id, payload) {
  return request.post(`/api/v1/recommendations/${id}/feedbacks`, payload, { businessStatus: true })
}

// 下载固定交付简历附件 GET /api/v1/recommendations/{id}/resume/download
// 返回 blob 并触发浏览器下载；文件名回退
export async function downloadRecommendationResume(id, filename) {
  const blob = await request.get(`/api/v1/recommendations/${id}/resume/download`, {
    responseType: 'blob',
    businessStatus: true,
    timeout: 60000,
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || `recommendation-${id}-resume`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}