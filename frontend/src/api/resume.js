// 简历版本 / 正文解析 / 技能核对 接口封装
import request from './request'

// 上传简历版本 POST /api/v1/candidates/{candidateId}/resumes
// 请求 FormData，文件字段名 file。响应 ResumeSummary，新版本默认主简历
export function uploadResume(candidateId, file) {
  const fd = new FormData()
  fd.append('file', file)
  return request.post(`/api/v1/candidates/${candidateId}/resumes`, fd, {
    businessStatus: true,
    timeout: 60000,
  })
}

// 简历版本列表 GET /api/v1/candidates/{candidateId}/resumes
// 响应 { total, items: ResumeSummary[] }（按版本倒序，不含正文/文件路径）
export function listResumeVersions(candidateId, params) {
  return request.get(`/api/v1/candidates/${candidateId}/resumes`, { params, businessStatus: true })
}

export async function allResumeVersions(candidateId) {
  const items = []
  for (let page = 1; ; page++) {
    const data = await listResumeVersions(candidateId, { page, size: 100 })
    items.push(...data.items)
    if (items.length >= data.total || data.items.length === 0) return items
  }
}

// 简历详情 GET /api/v1/resumes/{id}，含可空 parsed_text
export function getResume(id) {
  return request.get(`/api/v1/resumes/${id}`, { businessStatus: true })
}

// 下载附件 GET /api/v1/resumes/{id}/download（二进制，private, no-store）
// 返回 blob 并触发浏览器下载；文件名回退用 original_name
export async function downloadResume(id, filename) {
  const blob = await request.get(`/api/v1/resumes/${id}/download`, {
    responseType: 'blob',
    businessStatus: true,
    timeout: 60000,
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || `resume-${id}`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// 设为当前主简历 POST /api/v1/resumes/{id}/primary
// 请求体 { expected_primary_id }，字段必须出现（无主才传 null）
export function setPrimaryResume(id, expectedPrimaryId) {
  return request.post(`/api/v1/resumes/${id}/primary`, {
    expected_primary_id: expectedPrimaryId,
  }, { businessStatus: true })
}

// 本地正文解析 POST /api/v1/resumes/{id}/parse
export function parseResume(id) {
  return request.post(`/api/v1/resumes/${id}/parse`, {}, { timeout: 60000, businessStatus: true })
}

// 当前简历技能 GET /api/v1/resumes/{id}/skills -> SkillsOut
export function getResumeSkills(id) {
  return request.get(`/api/v1/resumes/${id}/skills`, { businessStatus: true })
}

// AI 技能抽取 POST /api/v1/resumes/{id}/extract-skills
// 请求体 { expected_skill_revision }；模型调用单独较长超时
export function extractSkills(id, expectedSkillRevision) {
  return request.post(
    `/api/v1/resumes/${id}/extract-skills`,
    { expected_skill_revision: expectedSkillRevision },
    { timeout: 90000, businessStatus: true },
  )
}

// 人工新增技能 POST /api/v1/resumes/{id}/skills
// 请求体 { expected_skill_revision, name, category?, evidence }
export function addSkill(id, payload) {
  return request.post(`/api/v1/resumes/${id}/skills`, payload, { businessStatus: true })
}

// 人工核对技能 PATCH /api/v1/resumes/{id}/skills/{relationId}
// 请求体 { expected_skill_revision, review_status: confirmed|rejected, evidence? }
export function reviewSkill(id, relationId, payload) {
  return request.patch(`/api/v1/resumes/${id}/skills/${relationId}`, payload, { businessStatus: true })
}
