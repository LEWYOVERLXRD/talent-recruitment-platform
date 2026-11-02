// 招聘需求（Job）接口封装
import request from './request'

// 分页列表 GET /api/v1/jobs?page=&size=&status=&keyword=
// 响应：{ total, items: [JobOut] }
export function listJobs(params) {
  return request.get('/api/v1/jobs', { params })
}

// 详情 GET /api/v1/jobs/{id}
export function getJob(id) {
  return request.get(`/api/v1/jobs/${id}`)
}

// 创建 POST /api/v1/jobs
// 请求体：{ title, department?, description?, requirements?, salary_min?, salary_max?,
//          location?, job_profile_content?, client_company_id?, contact_person?, contact_info?,
//          hiring_count?, priority? }
//   - recruiter 不能传 client_company_id（自动归属本企业）
//   - headhunter/admin 必须传 client_company_id（从 GET /companies/options 选择）
export function createJob(data) {
  return request.post('/api/v1/jobs', data)
}

// 更新 PATCH /api/v1/jobs/{id}
// 请求体必须含 expected_version + 至少一个更新字段
// 响应：JobOut（招聘条件变化会 version+1 并清空确认）
export function updateJob(id, data) {
  return request.patch(`/api/v1/jobs/${id}`, data)
}

// 客户主管确认 POST /api/v1/jobs/{id}/confirm
// 请求体：{ expected_version }
export function confirmJob(id, expectedVersion) {
  return request.post(`/api/v1/jobs/${id}/confirm`, {
    expected_version: expectedVersion,
  })
}

// 客户主管变更状态 POST /api/v1/jobs/{id}/status
// 请求体：{ expected_version, status: open/suspended/closed, reason? }
export function changeJobStatus(id, payload) {
  return request.post(`/api/v1/jobs/${id}/status`, payload)
}

// 岗位资料 GET /api/v1/jobs/{id}/profile（可能 404）
export function getJobProfile(id) {
  return request.get(`/api/v1/jobs/${id}/profile`)
}

// 定向邀请 POST /api/v1/jobs/{id}/invitations
// 请求体：{ provider_kind: individual/agency, target_id, expected_version }
export function inviteProvider(jobId, payload) {
  return request.post(`/api/v1/jobs/${jobId}/invitations`, payload)
}