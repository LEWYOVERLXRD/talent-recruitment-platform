<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <el-button link type="primary" class="back-link" @click="router.push({ name: 'Assignments' })">← 返回列表</el-button>
        <h1>{{ assignment?.job_title || assignment?.job_snapshot?.title || '任务详情' }}</h1>
        <p v-if="assignment" class="page-sub">
          {{ assignment.client_company_name || '客户企业待核验' }} ·
          {{ assignment.provider_name || '承接主体待核验' }} ·
          第 {{ assignment.round_no }} 轮 · 需求版本 v{{ assignment.job_version }}
        </p>
      </div>
      <div v-if="assignment" class="page-actions">
        <el-tag :type="asgStatusTag(assignment.status)">{{ asgStatusText(assignment.status) }}</el-tag>
        <el-tag :type="assignment.has_current_authorization ? 'success' : 'warning'">
          {{ assignment.has_current_authorization ? '授权有效' : '授权失效' }}
        </el-tag>
      </div>
    </div>

  <el-card shadow="never" v-loading="loading">

    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon />
    <template v-if="assignment">
      <div class="actions">
        <template v-if="canOperateProvider(assignment) && assignment.status === 'invited'">
          <el-button type="success" @click="actions.accept(assignment)">接受</el-button>
          <el-button type="danger" plain @click="actions.decline(assignment)">拒绝</el-button>
        </template>
        <el-button
          v-if="isClientManager && assignment.status === 'active'"
          type="success"
          @click="actions.complete(assignment)"
        >
          确认完成
        </el-button>
        <el-button v-if="canCancel(assignment)" type="danger" plain @click="actions.cancel(assignment, isClientManager)">
          {{ isClientManager ? '撤权' : '终止' }}
        </el-button>
        <el-button v-if="canTransfer" type="warning" plain @click="openOwner">
          分配负责人
        </el-button>
      </div>

      <el-descriptions :column="2" border class="mb">
        <el-descriptions-item label="需求名称">{{ assignment.job_title || assignment.job_snapshot?.title || `需求 #${assignment.job_id}` }}</el-descriptions-item>
        <el-descriptions-item label="客户企业">{{ assignment.client_company_name || '待核验' }}</el-descriptions-item>
        <el-descriptions-item label="承接主体">{{ assignment.provider_name || '待核验' }}</el-descriptions-item>
        <el-descriptions-item label="任务负责人">{{ assignment.owner_user_id ? `用户 #${assignment.owner_user_id}` : '尚未分配' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="asgStatusTag(assignment.status)">{{ asgStatusText(assignment.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="当前授权">
          <el-tag :type="assignment.has_current_authorization ? 'success' : 'warning'">
            {{ assignment.has_current_authorization ? '有效' : '失效' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="轮次">{{ assignment.round_no }}</el-descriptions-item>
        <el-descriptions-item label="任务版本">v{{ assignment.job_version }}</el-descriptions-item>
        <el-descriptions-item label="邀请时间">{{ fmt(assignment.invited_at) }}</el-descriptions-item>
        <el-descriptions-item label="接受时间">{{ fmt(assignment.accepted_at) }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ fmt(assignment.ended_at) }}</el-descriptions-item>
        <el-descriptions-item label="结束原因">{{ assignment.end_reason ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="客户联系人">{{ assignment.contact_person ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系方式">{{ assignment.contact_info ?? '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-card shadow="never" class="mb">
        <template #header><h4 class="card-title">岗位快照</h4></template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="部门">{{ assignment.job_snapshot?.department ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="地点">{{ assignment.job_snapshot?.location ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="薪资(K)">
            {{ assignment.job_snapshot?.salary_min ?? '-' }} - {{ assignment.job_snapshot?.salary_max ?? '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="招聘人数">{{ assignment.job_snapshot?.hiring_count ?? '-' }}</el-descriptions-item>
        </el-descriptions>
        <h4 class="snapshot-label">岗位职责</h4>
        <p class="para">{{ assignment.job_snapshot?.description || '（未填写）' }}</p>
        <h4 class="snapshot-label">岗位要求</h4>
        <p class="para">{{ assignment.job_snapshot?.requirements || '（未填写）' }}</p>
      </el-card>

      <el-card shadow="never">
        <template #header><h4 class="card-title">操作历史</h4></template>
        <el-timeline v-if="events.length">
          <el-timeline-item
            v-for="e in events"
            :key="e.id"
            :timestamp="fmt(e.created_at)"
            :type="eventTypeColor(e.event_type)"
          >
            <div class="event-row">
              <span class="event-type">{{ eventTypeText(e.event_type) }}</span>
              <span class="event-meta">v{{ e.job_version }} · 操作人 #{{ e.actor_id }}</span>
              <span v-if="e.reason" class="event-reason">原因：{{ e.reason }}</span>
              <span v-if="e.event_type === 'reassigned'" class="event-meta">
                负责人：#{{ e.payload?.from_owner_user_id }} → #{{ e.payload?.to_owner_user_id }}
              </span>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无操作历史" />
      </el-card>
    </template>

    <!-- 分配负责人弹窗 -->
    <el-dialog v-model="ownerVisible" title="分配任务负责人" width="min(480px, 94vw)">
      <el-form label-width="90px">
        <el-form-item label="新负责人" required>
          <el-select v-model="selectedOwner" filterable placeholder="选择同机构有效顾问/主管" style="width: 100%">
            <el-option
              v-for="m in memberOptions"
              :key="m.user_id"
              :label="`${m.real_name || m.username}（${m.role === 'manager' ? '主管' : '顾问'}）`"
              :value="m.user_id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ownerVisible = false">取消</el-button>
        <el-button type="primary" :loading="ownerSaving" @click="submitOwner">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getAssignment, getAssignmentEvents, transferOwner } from '@/api/assignment'
import { getAgencyContext, listMembers } from '@/api/agency'
import { useAssignmentActions } from '@/composables/assignmentActions'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const assignment = ref(null)
const events = ref([])
const agencyCtx = ref({ agency: null, membership: null })
const contextLoaded = ref(false)
const loadError = ref('')
let loadSequence = 0

const isClientManager = computed(() => userStore.isClientManager)
const isIndependent = computed(
  () => contextLoaded.value && userStore.isHeadhunter && agencyCtx.value.membership == null,
)
const isAgencyManager = computed(
  () =>
    userStore.isHeadhunter &&
    agencyCtx.value.agency?.status === 'active' &&
    agencyCtx.value.membership?.role === 'manager',
)

const canTransfer = computed(() => isAgencyManager.value &&
  assignment.value?.provider_kind === 'agency' && assignment.value?.has_current_authorization)

function canOperateProvider(row) {
  return (row.provider_kind === 'individual' && isIndependent.value) ||
    (row.provider_kind === 'agency' && isAgencyManager.value)
}

function canCancel(row) {
  if (row.status !== 'invited' && row.status !== 'active') return false
  if (isClientManager.value) return true
  return canOperateProvider(row)
}

function asgStatusText(s) {
  return { invited: '待接受', active: '已承接', declined: '已拒绝', cancelled: '已撤销', completed: '已完成' }[s] || s
}
function asgStatusTag(s) {
  return { invited: 'warning', active: 'success', declined: 'info', cancelled: 'danger', completed: 'success' }[s] || 'info'
}
function eventTypeText(t) {
  return { invited: '邀请', accepted: '接受', declined: '拒绝', cancelled: '撤销/终止', completed: '完成', reassigned: '转派' }[t] || t
}
function eventTypeColor(t) {
  return { accepted: 'success', declined: 'danger', cancelled: 'warning', completed: 'success', reassigned: 'primary' }[t] || 'primary'
}
function fmt(t) {
  return t ? String(t).replace('T', ' ').slice(0, 19) : '-'
}

async function load() {
  const sequence = ++loadSequence
  const id = route.params.id
  loading.value = true
  assignment.value = null
  events.value = []
  loadError.value = ''
  ownerVisible.value = false
  try {
    const [data, history] = await Promise.all([getAssignment(id), getAssignmentEvents(id)])
    if (sequence !== loadSequence) return
    assignment.value = data
    events.value = history
  } catch (e) {
    if (sequence !== loadSequence) return
    assignment.value = null
    events.value = []
    loadError.value = String(e)
    ElMessage.error(e)
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

const actions = useAssignmentActions(load)

// ===== 分配负责人 =====
const ownerVisible = ref(false)
const ownerSaving = ref(false)
const members = ref([])
const selectedOwner = ref(null)
const memberOptions = computed(() =>
  members.value.filter((m) => m.status === 'active' && m.enabled !== false),
)

async function openOwner() {
  if (!canTransfer.value) return
  selectedOwner.value = assignment.value.owner_user_id ?? null
  members.value = []
  ownerVisible.value = true
  try {
    members.value = await listMembers(agencyCtx.value.agency.id)
  } catch (e) {
    ElMessage.error(e)
  }
}

async function submitOwner() {
  if (!selectedOwner.value) {
    ElMessage.warning('请选择新负责人')
    return
  }
  ownerSaving.value = true
  try {
    await transferOwner(assignment.value.id, {
      expected_round: assignment.value.round_no,
      expected_owner_user_id: assignment.value.owner_user_id ?? null,
      owner_user_id: selectedOwner.value,
    })
    ElMessage.success('已分配负责人')
    ownerVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e)
    await load()
  } finally {
    ownerSaving.value = false
  }
}

onMounted(async () => {
  if (userStore.isHeadhunter) {
    try {
      agencyCtx.value = await getAgencyContext()
      contextLoaded.value = true
    } catch (e) {
      ElMessage.error(e)
    }
  }
  await load()
  if (route.query.action === 'owner' && canTransfer.value) await openOwner()
})
watch(() => route.params.id, load)
</script>

<style scoped>
.card-head { display: flex; align-items: center; justify-content: space-between; }
.head-left { display: flex; align-items: center; gap: 8px; }
.card-title { margin: 0; font-size: 16px; color: #303133; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.mb { margin-bottom: 16px; }
.event-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.event-type { font-weight: 600; color: #303133; }
.event-meta { color: #909399; font-size: 12px; }
.event-reason { color: #606266; font-size: 12px; }
.snapshot-label { margin: 12px 0 6px; font-size: 14px; }
.para { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; }
@media (max-width: 640px) {
  .head-left { flex-wrap: wrap; }
}
</style>
