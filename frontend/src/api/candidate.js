// 候选人（Candidate）接口封装
import request from './request'

// 分页列表 GET /api/v1/candidates?keyword=&page=&size=
// 响应：{ total, items: CandidateOut[] }
export function listCandidates(params) {
  return request.get('/api/v1/candidates', { params })
}

// 详情 GET /api/v1/candidates/{id}
export function getCandidate(id) {
  return request.get(`/api/v1/candidates/${id}`)
}

// 创建 POST /api/v1/candidates
// 请求体：{ ownership?, owner_user_id?, name, gender?, phone?, email?,
//          current_company?, current_position?, years_of_experience?,
//          education?, expected_salary?, expected_location?, source? }
export function createCandidate(data) {
  return request.post('/api/v1/candidates', data)
}

// 更新 PATCH /api/v1/candidates/{id}
// 请求体：仅资料字段（name/gender/phone/email/current_company/...）
export function updateCandidate(id, data) {
  return request.patch(`/api/v1/candidates/${id}`, data)
}

// 同机构转派负责人 POST /api/v1/candidates/{id}/transfer
// 请求体：{ owner_user_id }
export function transferCandidate(id, ownerUserId) {
  return request.post(`/api/v1/candidates/${id}/transfer`, {
    owner_user_id: ownerUserId,
  })
}