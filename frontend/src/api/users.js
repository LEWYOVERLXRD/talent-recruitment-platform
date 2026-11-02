import request from './request'

export function listUsers(params) {
  return request.get('/api/v1/users', { params })
}

export function setUserStatus(userId, enabled) {
  return request.patch(`/api/v1/users/${userId}/status`, { enabled })
}
