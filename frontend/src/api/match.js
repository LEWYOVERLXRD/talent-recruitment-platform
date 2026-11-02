// AI 人岗匹配接口封装
import request from './request'

// 执行匹配 POST /api/v1/matches
// 请求体五项必填：{ job_id, candidate_id, resume_id, expected_job_version, expected_skill_revision }
// 每次新增一条，不覆盖历史；模型调用单独较长超时
export function runMatch(payload) {
  return request.post('/api/v1/matches', payload, { timeout: 90000, businessStatus: true })
}

// 匹配结果分页列表 GET /api/v1/matches
// 可选 { candidate_id, job_id, page, size }；响应 { total, items: MatchSummary[] }
export function listMatches(params) {
  return request.get('/api/v1/matches', { params, businessStatus: true })
}

// 匹配结果详情 GET /api/v1/matches/{id} -> MatchAnalysisOut（含 input_snapshot）
export function getMatch(id) {
  return request.get(`/api/v1/matches/${id}`, { businessStatus: true })
}
