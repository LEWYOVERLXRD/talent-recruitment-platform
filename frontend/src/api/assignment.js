// 需求承接（定向邀请/承接/机构负责人）接口封装
import request from './request'

// 服务主体选项 GET /api/v1/service-providers
// 响应：{ kind: individual/agency, target_id, display_name }[]
export function listServiceProviders() {
  return request.get('/api/v1/service-providers')
}

// 我的需求承接 GET /api/v1/assignments
// 响应：AssignmentListItem[]
export function listAssignments() {
  return request.get('/api/v1/assignments')
}

// 承接详情 GET /api/v1/assignments/{id}
export function getAssignment(id) {
  return request.get(`/api/v1/assignments/${id}`)
}

// 操作历史 GET /api/v1/assignments/{id}/events
// 响应：AssignmentEventOut[]
export function getAssignmentEvents(id) {
  return request.get(`/api/v1/assignments/${id}/events`)
}

// 接受邀请 POST /api/v1/assignments/{id}/accept
// 请求体：{ expected_round, reason? }
export function acceptAssignment(id, expectedRound) {
  return request.post(`/api/v1/assignments/${id}/accept`, {
    expected_round: expectedRound,
  })
}

// 拒绝邀请 POST /api/v1/assignments/{id}/decline
// 请求体：{ expected_round, reason }（拒绝必填原因）
export function declineAssignment(id, expectedRound, reason) {
  return request.post(`/api/v1/assignments/${id}/decline`, {
    expected_round: expectedRound,
    reason,
  })
}

// 撤销邀请/终止承接 POST /api/v1/assignments/{id}/cancel
// 请求体：{ expected_round, reason }（必填原因）
export function cancelAssignment(id, expectedRound, reason) {
  return request.post(`/api/v1/assignments/${id}/cancel`, {
    expected_round: expectedRound,
    reason,
  })
}

// 确认完成 POST /api/v1/assignments/{id}/complete
// 请求体：{ expected_round, reason }（必填原因）
export function completeAssignment(id, expectedRound, reason) {
  return request.post(`/api/v1/assignments/${id}/complete`, {
    expected_round: expectedRound,
    reason,
  })
}

// 机构主管分配负责人 POST /api/v1/assignments/{id}/owner
// 请求体：{ expected_round, expected_owner_user_id, owner_user_id }
export function transferOwner(id, payload) {
  return request.post(`/api/v1/assignments/${id}/owner`, payload)
}