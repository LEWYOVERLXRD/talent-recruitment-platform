// 猎头机构（Agency）接口封装
import request from './request'

// 当前用户机构上下文 GET /api/v1/agencies/context
// 响应：{ agency: AgencyOut|null, membership: MemberOut|null, invitations: MemberOut[] }
export function getAgencyContext() {
  return request.get('/api/v1/agencies/context')
}

// 平台管理员：机构分页列表 GET /api/v1/agencies?page=&size=
// 响应：{ total, items: AgencyOut[] }
export function listAgencies(params) {
  return request.get('/api/v1/agencies', { params })
}

// 平台管理员：创建机构 POST /api/v1/agencies
// 请求体：{ name, manager_user_id }
export function createAgency(data) {
  return request.post('/api/v1/agencies', data)
}

// 平台管理员：机构启停 PATCH /api/v1/agencies/{id}/status
// 请求体：{ status: "active" | "disabled" }
export function setAgencyStatus(id, status) {
  return request.patch(`/api/v1/agencies/${id}/status`, { status })
}

// 机构成员列表 GET /api/v1/agencies/{agency_id}/members
// 响应：MemberOut[]
export function listMembers(agencyId) {
  return request.get(`/api/v1/agencies/${agencyId}/members`)
}

// 邀请猎头账号加入 POST /api/v1/agencies/{agency_id}/invitations
// 请求体：{ username, role?: "manager" | "staff" }
export function inviteMember(agencyId, data) {
  return request.post(`/api/v1/agencies/${agencyId}/invitations`, data)
}

// 接受/拒绝邀请 POST /api/v1/agencies/{agency_id}/members/{member_id}/decision
// 请求体：{ accept: boolean }
export function decideInvitation(agencyId, memberId, accept) {
  return request.post(
    `/api/v1/agencies/${agencyId}/members/${memberId}/decision`,
    { accept },
  )
}

// 调整成员角色 PATCH /api/v1/agencies/{agency_id}/members/{member_id}/role
// 请求体：{ role: "manager" | "staff" }
export function setMemberRole(agencyId, memberId, role) {
  return request.patch(
    `/api/v1/agencies/${agencyId}/members/${memberId}/role`,
    { role },
  )
}

// 取消待处理邀请 POST /api/v1/agencies/{agency_id}/members/{member_id}/cancel
export function cancelInvitation(agencyId, memberId) {
  return request.post(`/api/v1/agencies/${agencyId}/members/${memberId}/cancel`)
}