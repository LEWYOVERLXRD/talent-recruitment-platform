// 招聘需求（Job）接口封装
import request from './request'

// 分页列表 GET /api/v1/jobs?page=1&size=20&status=&keyword=
// 响应：{ total, items: [JobOut] }
export function listJobs(params) {
  return request.get('/api/v1/jobs', { params })
}

// 详情 GET /api/v1/jobs/{id}
export function getJob(id) {
  return request.get(`/api/v1/jobs/${id}`)
}

// 创建 POST /api/v1/jobs
// 请求体：{ title, department?, description?, requirements?, salary_min?, salary_max?, location?,
//          client_company_name?...（猎头创建时传），contact_person?, contact_info?, hiring_count?, priority? }
export function createJob(data) {
  return request.post('/api/v1/jobs', data)
}

// 更新 PATCH /api/v1/jobs/{id}
export function updateJob(id, data) {
  return request.patch(`/api/v1/jobs/${id}`, data)
}