// 私有沟通记录（候选人沟通）接口封装
import request from './request'

// 分页列表 GET /api/v1/candidates/{candidateId}/communications?page=&size=
// 响应：{ total, items: CommunicationOut[] }
export function listCommunications(candidateId, params) {
  return request.get(`/api/v1/candidates/${candidateId}/communications`, {
    params,
    businessStatus: true,
  })
}

// 追加沟通 POST /api/v1/candidates/{candidateId}/communications
// 请求体：{ job_id?, comm_type, content, result?, communicated_at, follow_up_at? }
export function addCommunication(candidateId, payload) {
  return request.post(`/api/v1/candidates/${candidateId}/communications`, payload, {
    businessStatus: true,
  })
}

// 沟通详情 GET /api/v1/communications/{id}
export function getCommunication(id) {
  return request.get(`/api/v1/communications/${id}`, { businessStatus: true })
}