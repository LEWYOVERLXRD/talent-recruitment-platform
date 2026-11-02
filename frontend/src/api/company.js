// 企业接口封装
import request from './request'

// 客户企业选项 GET /api/v1/companies/options
// 响应：{ id, name }[]（headhunter/admin 代建需求时选择已核验客户企业）
export function listCompanyOptions() {
  return request.get('/api/v1/companies/options')
}

export function getMyCompany() {
  return request.get('/api/v1/companies/me')
}

export function listCompanyMembers() {
  return request.get('/api/v1/companies/me/members')
}

export function listCompanyInvitations() {
  return request.get('/api/v1/companies/me/invitations')
}

export function inviteCompanyMember(username) {
  return request.post('/api/v1/companies/me/invitations', { username })
}

export function listMyCompanyInvitations() {
  return request.get('/api/v1/companies/invitations')
}

export function decideCompanyInvitation(id, accept) {
  return request.post(`/api/v1/companies/invitations/${id}/decision`, { accept })
}

export function revokeCompanyInvitation(id) {
  return request.post(`/api/v1/companies/me/invitations/${id}/revoke`)
}

// ===== 平台管理员只读企业核验 =====
// 显式 businessStatus：保留 { status, message } 以便页面区分 403/404 并清空旧数据。

export function listAdminCompanies(params) {
  return request.get('/api/v1/companies', { params, businessStatus: true })
}

export function getAdminCompany(id) {
  return request.get(`/api/v1/companies/${id}`, { businessStatus: true })
}

export function listAdminCompanyMembers(id, params) {
  return request.get(`/api/v1/companies/${id}/members`, { params, businessStatus: true })
}
