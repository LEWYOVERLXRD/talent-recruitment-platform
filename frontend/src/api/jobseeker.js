import request from './request'

export function getProfile() { return request.get('/api/v1/jobseeker/profile', { businessStatus: true }) }
export function updateProfile(payload) { return request.patch('/api/v1/jobseeker/profile', payload, { businessStatus: true }) }
export function listMyResumes() { return request.get('/api/v1/jobseeker/resumes', { businessStatus: true }) }
export function uploadMyResume(file) {
  const data = new FormData()
  data.append('file', file)
  return request.post('/api/v1/jobseeker/resumes', data, { businessStatus: true, timeout: 60000 })
}
export function setMyPrimaryResume(id, expectedPrimaryId) {
  return request.post(`/api/v1/jobseeker/resumes/${id}/primary`, { expected_primary_id: expectedPrimaryId }, { businessStatus: true })
}
export function listMyApplications() { return request.get('/api/v1/applications/me', { businessStatus: true }) }
export function createApplication(payload) { return request.post('/api/v1/applications', payload, { businessStatus: true }) }
export function listApplications() { return request.get('/api/v1/applications', { businessStatus: true }) }
export function updateApplicationStatus(id, payload) { return request.patch(`/api/v1/applications/${id}/status`, payload, { businessStatus: true }) }
export function reviewApplication(id, payload) { return request.post(`/api/v1/applications/${id}/review`, payload, { businessStatus: true }) }
export function createRecommendationFromApplication(id, payload) {
  return request.post(`/api/v1/applications/${id}/recommendation`, payload, { businessStatus: true })
}
export async function downloadApplicationResume(id, filename) {
  const blob = await request.get(`/api/v1/applications/${id}/resume`, {
    responseType: 'blob',
    businessStatus: true,
    timeout: 60000,
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename || `application-${id}-resume`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
