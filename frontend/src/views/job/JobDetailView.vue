<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <el-button link type="primary" class="back-link" @click="router.push({ name: 'Jobs' })">← 返回列表</el-button>
        <h1>{{ job?.title || '招聘需求详情' }}</h1>
        <p v-if="job" class="page-sub">
          {{ job.client_company_name || '未填写客户企业' }} ·
          {{ job.location || '未填写地点' }} ·
          {{ sourceText(job.source) }}
        </p>
      </div>
      <div v-if="job" class="page-actions">
        <el-tag :type="statusTag(job.status)">{{ statusText(job.status) }}</el-tag>
        <el-tag :type="confirmTag(job)">{{ confirmText(job) }}</el-tag>
        <el-tag type="info">v{{ job.version ?? 1 }}</el-tag>
      </div>
    </div>

  <el-card shadow="never" v-loading="loading">

    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon />
    <template v-if="job">
      <!-- 操作区（按角色显隐） -->
      <div class="actions">
        <el-button v-if="canEdit(job)" type="primary" plain @click="openEdit">编辑</el-button>
        <el-button v-if="isClientManager && !job.confirmed_at && job.status === 'open'" type="success" @click="doConfirm">确认需求</el-button>
        <el-button v-if="isClientManager && job.status === 'open'" type="warning" plain @click="doStatus('suspended')">暂停</el-button>
        <el-button v-if="isClientManager && job.status === 'suspended'" type="primary" plain @click="doStatus('open')">恢复</el-button>
        <el-button v-if="isClientManager && job.status !== 'closed'" type="danger" plain @click="doStatus('closed')">关闭</el-button>
        <el-button v-if="isClientManager && job.confirmed_at && job.status === 'open'" type="primary" @click="openInvite">定向邀请</el-button>
        <el-button v-if="userStore.isJobseeker && job.receivers?.length && job.status === 'open'" type="primary" @click="openApply">投递给负责猎头</el-button>
        <el-button v-if="!userStore.isJobseeker" :loading="profileLoading" plain @click="openProfile">岗位资料</el-button>
      </div>

      <el-alert
        v-if="job.ever_confirmed_at && !job.confirmed_at"
        class="mb"
        type="warning"
        :closable="false"
        show-icon
        title="招聘条件已变更，当前版本待重新确认；确认后需逐主体重新邀请。"
      />

      <el-descriptions :column="2" border class="mb">
        <el-descriptions-item label="需求名称">{{ job.title }}</el-descriptions-item>
        <el-descriptions-item label="客户企业">{{ job.client_company_name ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="部门">{{ job.department ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="工作地点">{{ job.location ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="薪资(K)">{{ job.salary_min ?? '-' }} - {{ job.salary_max ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="招聘人数">{{ job.hiring_count ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="优先级">{{ priorityText(job.priority) }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ sourceText(job.source) }}</el-descriptions-item>
        <el-descriptions-item label="客户联系人">{{ job.contact_person ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系方式">{{ job.contact_info ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="当前版本">{{ job.version ?? 1 }}</el-descriptions-item>
        <el-descriptions-item label="确认时间">{{ fmt(job.confirmed_at) }}</el-descriptions-item>
        <el-descriptions-item label="首次确认">{{ fmt(job.ever_confirmed_at) }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ fmt(job.created_at) }}</el-descriptions-item>
      </el-descriptions>

      <el-card shadow="never" class="mb">
        <template #header><h4 class="card-title">岗位职责</h4></template>
        <p class="para">{{ job.description || '（未填写）' }}</p>
      </el-card>
      <el-card shadow="never" class="mb">
        <template #header><h4 class="card-title">岗位要求</h4></template>
        <p class="para">{{ job.requirements || '（未填写）' }}</p>
      </el-card>

      <el-card v-if="!userStore.isJobseeker" shadow="never">
        <template #header><h4 class="card-title">本需求承接记录</h4></template>
        <el-table :data="assignments" border stripe empty-text="暂无可展示的承接记录">
          <el-table-column label="承接主体" min-width="160">
            <template #default="{ row }">{{ row.provider_name || `主体 #${row.provider_id}` }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="asgStatusTag(row.status)">{{ asgStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="轮次" width="70">
            <template #default="{ row }">{{ row.round_no }}</template>
          </el-table-column>
          <el-table-column label="任务版本" width="90">
            <template #default="{ row }">v{{ row.job_version }}</template>
          </el-table-column>
          <el-table-column label="当前授权" width="100">
            <template #default="{ row }">
              <el-tag :type="row.has_current_authorization ? 'success' : 'warning'">
                {{ row.has_current_authorization ? '有效' : '失效' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="邀请时间" min-width="160">
            <template #default="{ row }">{{ fmt(row.invited_at) }}</template>
          </el-table-column>
          <el-table-column label="结束原因" min-width="140">
            <template #default="{ row }">{{ row.end_reason ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="router.push({ name: 'AssignmentDetail', params: { id: row.id } })">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑招聘需求" width="min(640px, 94vw)">
      <el-form :model="editForm" label-width="110px">
        <el-form-item label="需求名称" required><el-input v-model="editForm.title" /></el-form-item>
        <el-form-item label="部门"><el-input v-model="editForm.department" /></el-form-item>
        <el-form-item label="工作地点"><el-input v-model="editForm.location" /></el-form-item>
        <el-form-item label="最低薪资(K)"><el-input-number v-model="editForm.salary_min" :min="0" /></el-form-item>
        <el-form-item label="最高薪资(K)"><el-input-number v-model="editForm.salary_max" :min="0" /></el-form-item>
        <el-form-item label="招聘人数"><el-input-number v-model="editForm.hiring_count" :min="1" /></el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="editForm.priority" clearable>
            <el-option label="高" value="high" />
            <el-option label="中" value="normal" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="客户联系人"><el-input v-model="editForm.contact_person" /></el-form-item>
        <el-form-item label="联系方式"><el-input v-model="editForm.contact_info" /></el-form-item>
        <el-form-item label="岗位职责"><el-input type="textarea" v-model="editForm.description" :rows="3" /></el-form-item>
        <el-form-item label="岗位要求"><el-input type="textarea" v-model="editForm.requirements" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 定向邀请弹窗 -->
    <el-dialog v-model="inviteVisible" title="选择定向邀请主体" width="min(560px, 94vw)">
      <el-alert type="info" :closable="false" class="mb-inline" show-icon title="仅受邀机构/独立猎头本人可处理；一条需求可邀请多家主体。" />
      <el-table :data="providers" max-height="400" v-loading="inviteLoading">
        <el-table-column label="主体类型" width="110">
          <template #default="{ row }">
            <el-tag :type="row.kind === 'agency' ? 'warning' : 'info'">
              {{ row.kind === 'agency' ? '机构' : '独立猎头' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="display_name" label="主体名称" min-width="180" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="primary" :loading="inviting" @click="doInvite(row)">邀请</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 岗位资料弹窗 -->
    <el-dialog v-model="profileVisible" title="原始岗位资料" width="min(600px, 94vw)">
      <el-descriptions v-if="profile" :column="1" border class="mb-inline">
        <el-descriptions-item label="来源类型">{{ profile.source_type }}</el-descriptions-item>
        <el-descriptions-item label="资料版本">v{{ profile.version }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ fmt(profile.submitted_at) }}</el-descriptions-item>
      </el-descriptions>
      <p class="para" v-if="profile">{{ profile.raw_content }}</p>
    </el-dialog>

    <el-dialog v-model="applyVisible" title="投递岗位" width="min(520px, 94vw)">
      <el-form label-position="top">
        <el-form-item label="选择负责猎头" required>
          <el-select v-model="applyAssignmentId" style="width: 100%" placeholder="请选择接收本次投递的猎头">
            <el-option v-for="receiver in job?.receivers || []" :key="receiver.assignment_id" :value="receiver.assignment_id" :label="receiver.provider_kind === 'agency' ? `${receiver.headhunter_name} · ${receiver.provider_name}` : receiver.headhunter_name" />
          </el-select>
        </el-form-item>
      </el-form>
      <p>投递先由所选猎头筛选，企业在猎头提交推荐后才能查看交付材料。同一岗位可以选择不同猎头投递；若该人选已被其他猎头收录，本次会保留重复投递记录，但不会重复进入筛选。</p>
      <el-alert v-if="!resumes.length" type="warning" :closable="false" show-icon title="请先在“我的简历”上传简历" />
      <el-radio-group v-else v-model="applyResumeId">
        <el-radio v-for="row in resumes" :key="row.id" :value="row.id" border class="resume-option">
          v{{ row.version }} · {{ row.original_name || `简历 #${row.id}` }}{{ row.is_primary ? '（主简历）' : '' }}
        </el-radio>
      </el-radio-group>
      <template #footer><el-button @click="applyVisible = false">取消</el-button><el-button type="primary" :loading="applying" :disabled="!applyResumeId || !applyAssignmentId" @click="apply">确认投递</el-button></template>
    </el-dialog>
  </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getJob, updateJob, confirmJob, changeJobStatus, getJobProfile, inviteProvider } from '@/api/job'
import { listMyResumes, createApplication } from '@/api/jobseeker'
import { listServiceProviders, listAssignments } from '@/api/assignment'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isClientManager = computed(() => userStore.isClientManager)
const applyVisible = ref(false)
const applying = ref(false)
const applyResumeId = ref(null)
const applyAssignmentId = ref(null)
const resumes = ref([])

const loading = ref(false)
const job = ref(null)
const assignments = ref([])
const loadError = ref('')
let loadSequence = 0

function canEdit(j) {
  if (!j || j.status === 'closed') return false
  if (userStore.isAdmin) return true
  if (userStore.role === 'recruiter') {
    if (j.client_company_id !== userStore.user?.company_id) return false
    return j.ever_confirmed_at == null || userStore.isClientManager
  }
  return userStore.role === 'headhunter' && j.ever_confirmed_at == null && j.created_by === userStore.user?.id
}

function statusText(s) {
  return { open: '寻访中', suspended: '暂停', closed: '已关闭' }[s] || s
}
function statusTag(s) {
  return { open: 'success', suspended: 'warning', closed: 'info' }[s] || 'info'
}
function confirmText(j) {
  if (j.confirmed_at) return '已确认'
  return j.ever_confirmed_at ? '待重新确认' : '未确认'
}
function confirmTag(j) {
  if (j.confirmed_at) return 'success'
  return j.ever_confirmed_at ? 'warning' : 'info'
}
function sourceText(s) {
  return { client_published: '企业发布', headhunter_created: '猎头代建' }[s] || s
}
function priorityText(p) {
  return { high: '高', normal: '中', low: '低' }[p] || (p || '-')
}
function asgStatusText(s) {
  return { invited: '待接受', active: '已承接', declined: '已拒绝', cancelled: '已撤销', completed: '已完成' }[s] || s
}
function asgStatusTag(s) {
  return { invited: 'warning', active: 'success', declined: 'info', cancelled: 'danger', completed: 'success' }[s] || 'info'
}
function fmt(t) {
  return t ? String(t).replace('T', ' ').slice(0, 19) : '-'
}

async function load() {
  const sequence = ++loadSequence
  const id = route.params.id
  loading.value = true
  job.value = null
  assignments.value = []
  loadError.value = ''
  try {
    const data = await getJob(id)
    if (sequence !== loadSequence) return
    job.value = data
    if (!userStore.isJobseeker) await loadAssignments(data.id, sequence)
  } catch (e) {
    if (sequence !== loadSequence) return
    job.value = null
    assignments.value = []
    editVisible.value = inviteVisible.value = profileVisible.value = false
    profile.value = null
    loadError.value = String(e)
    ElMessage.error(e)
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function openApply() {
  try {
    const data = await listMyResumes()
    resumes.value = data.items || []
    applyAssignmentId.value = job.value.receivers?.length === 1 ? job.value.receivers[0].assignment_id : null
    applyResumeId.value = resumes.value.find((row) => row.is_primary)?.id || resumes.value[0]?.id || null
    applyVisible.value = true
  } catch (e) { ElMessage.error(e.message || e) }
}

async function apply() {
  if (!applyResumeId.value || !applyAssignmentId.value || applying.value) return
  applying.value = true
  try {
    await createApplication({ job_id: job.value.id, resume_id: applyResumeId.value, assignment_id: applyAssignmentId.value })
    ElMessage.success('投递成功，可在“我的投递”查看进度')
    applyVisible.value = false
  } catch (e) { ElMessage.error(e.message || e) } finally { applying.value = false }
}

async function loadAssignments(jobId, sequence) {
  try {
    const all = await listAssignments()
    if (sequence === loadSequence) assignments.value = all.filter((a) => a.job_id === jobId)
  } catch (e) {
    if (sequence === loadSequence) {
      assignments.value = []
      ElMessage.error(e)
    }
  }
}

async function doConfirm() {
  try {
    await confirmJob(job.value.id, job.value.version)
    ElMessage.success('已确认需求')
    await load()
  } catch (e) {
    ElMessage.error(e)
    await load()
  }
}

async function doStatus(target) {
  const needReason = target !== 'open'
  let reason = null
  if (needReason) {
    const label = target === 'suspended' ? '暂停' : '关闭'
    try {
      const r = await ElMessageBox.prompt(`请输入${label}原因`, '变更需求状态', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputPattern: /\S+/,
        inputErrorMessage: '原因不能为空',
      })
      reason = r.value
    } catch {
      return
    }
  }
  try {
    await changeJobStatus(job.value.id, { expected_version: job.value.version, status: target, reason })
    ElMessage.success('状态已更新')
    await load()
  } catch (e) {
    ElMessage.error(e)
    await load()
  }
}

// ===== 岗位资料 =====
const profileVisible = ref(false)
const profileLoading = ref(false)
const profile = ref(null)
async function openProfile() {
  profileLoading.value = true
  try {
    profile.value = await getJobProfile(job.value.id)
    profileVisible.value = true
  } catch (e) {
    ElMessage.error(e)
  } finally {
    profileLoading.value = false
  }
}

// ===== 定向邀请 =====
const inviteVisible = ref(false)
const inviteLoading = ref(false)
const inviting = ref(false)
const providers = ref([])
async function openInvite() {
  inviteVisible.value = true
  inviteLoading.value = true
  try {
    providers.value = await listServiceProviders()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    inviteLoading.value = false
  }
}
async function doInvite(row) {
  inviting.value = true
  try {
    await inviteProvider(job.value.id, {
      provider_kind: row.kind,
      target_id: row.target_id,
      expected_version: job.value.version,
    })
    ElMessage.success('已发送邀请')
    await load()
  } catch (e) {
    ElMessage.error(e)
    await load()
  } finally {
    inviting.value = false
  }
}

// ===== 编辑 =====
const editVisible = ref(false)
const editSaving = ref(false)
const editForm = reactive({
  title: '', department: '', location: '', salary_min: undefined, salary_max: undefined,
  hiring_count: undefined, priority: '', contact_person: '', contact_info: '',
  description: '', requirements: '',
})
function openEdit() {
  Object.assign(editForm, {
    title: job.value.title,
    department: job.value.department || '',
    location: job.value.location || '',
    salary_min: job.value.salary_min,
    salary_max: job.value.salary_max,
    hiring_count: job.value.hiring_count,
    priority: job.value.priority || '',
    contact_person: job.value.contact_person || '',
    contact_info: job.value.contact_info || '',
    description: job.value.description || '',
    requirements: job.value.requirements || '',
  })
  editVisible.value = true
}
async function saveEdit() {
  if (!editForm.title || !editForm.title.trim()) {
    ElMessage.warning('请填写需求名称')
    return
  }
  const prevVersion = job.value.version
  editSaving.value = true
  try {
    const data = {
      expected_version: job.value.version,
      title: editForm.title.trim(),
      department: editForm.department || null,
      description: editForm.description || null,
      requirements: editForm.requirements || null,
      salary_min: editForm.salary_min ?? null,
      salary_max: editForm.salary_max ?? null,
      location: editForm.location || null,
      contact_person: editForm.contact_person || null,
      contact_info: editForm.contact_info || null,
      hiring_count: editForm.hiring_count ?? null,
      priority: editForm.priority || null,
    }
    const updated = await updateJob(job.value.id, data)
    if ((updated.version ?? prevVersion) > prevVersion) {
      ElMessage.warning('招聘条件已变更，需求版本已更新，需重新确认并逐主体重新邀请')
    } else {
      ElMessage.success('已更新')
    }
    editVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e)
    editVisible.value = false
    await load()
  } finally {
    editSaving.value = false
  }
}

watch(() => route.params.id, () => {
  editVisible.value = inviteVisible.value = profileVisible.value = false
  profile.value = null
  load()
}, { immediate: true })
</script>

<style scoped>
.card-head { display: flex; align-items: center; justify-content: space-between; }
.head-left { display: flex; align-items: center; gap: 8px; }
.head-tags { display: flex; gap: 8px; }
.card-title { margin: 0; font-size: 16px; color: #303133; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.mb { margin-bottom: 16px; }
.mb-inline { margin-bottom: 12px; }
.para { margin: 0; color: #606266; white-space: pre-wrap; line-height: 1.7; overflow-wrap: anywhere; }
@media (max-width: 640px) {
  .card-head { align-items: flex-start; flex-direction: column; gap: 12px; }
  .head-left { flex-wrap: wrap; }
}
</style>
