<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <el-button link type="primary" class="back-link" @click="goBack">← 返回列表</el-button>
        <h1>{{ candidate?.name || '候选人详情' }}</h1>
        <p v-if="candidate" class="page-sub">
          {{ candidate.current_company || '未填写当前公司' }} ·
          {{ candidate.current_position || '未填写当前职位' }} ·
          负责人 {{ candidate.owner_username || '待管理员核验' }}
        </p>
      </div>
      <div v-if="candidate" class="page-actions">
        <el-button v-if="canEdit" type="primary" plain @click="openEdit">编辑资料</el-button>
        <el-button v-if="canTransfer" type="warning" plain @click="openTransfer">转派负责人</el-button>
      </div>
    </div>

  <el-card shadow="never" v-loading="loading">

    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon />
    <template v-if="candidate">
      <el-descriptions :column="2" border class="mb">
        <el-descriptions-item label="姓名">{{ candidate.name }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ candidate.gender ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="手机号">{{ candidate.phone ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ candidate.email ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="当前公司">{{ candidate.current_company ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="当前职位">{{ candidate.current_position ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="工作年限">
          {{ candidate.years_of_experience ?? '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="最高学历">{{ candidate.education ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="期望薪资">{{ candidate.expected_salary ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="期望工作地">{{ candidate.expected_location ?? '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-descriptions :column="2" border class="mb">
        <el-descriptions-item label="归属类型">
          <el-tag :type="ownershipTag" size="small">{{ ownershipText }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="所属机构">
          {{ candidate.agency_id ?? '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="负责人">
          {{ candidate.owner_username ?? '待管理员核验' }}
        </el-descriptions-item>
        <el-descriptions-item label="来源">{{ sourceText }}</el-descriptions-item>
        <el-descriptions-item label="建档时间">{{ formatTime(candidate.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatTime(candidate.updated_at) }}</el-descriptions-item>
      </el-descriptions>

      <el-alert
        v-if="!candidate.owner_username"
        type="info"
        :closable="false"
        show-icon
        title="该候选人为历史异常记录，负责人待平台管理员核验，当前不视为公共数据。"
      />

      <el-tabs v-model="activeTab" class="mt" @tab-change="refreshPanel">
        <el-tab-pane label="简历版本" name="resumes" lazy>
          <ResumeVersionsPanel
            ref="resumesPanel"
            :key="`r-${candidate.id}`"
            :candidate="candidate"
            :can-mutate="canMutate"
            @access-lost="load"
            @open-skills="showSkills"
          />
        </el-tab-pane>
        <el-tab-pane label="技能核对" name="skills" lazy>
          <SkillReviewPanel
            ref="skillsPanel"
            :key="`s-${candidate.id}`"
            :candidate="candidate"
            :can-mutate="canMutate"
            :initial-resume-id="skillsResumeId"
            @access-lost="load"
          />
        </el-tab-pane>
        <el-tab-pane label="匹配记录" name="matches" lazy>
          <MatchPanel
            ref="matchesPanel"
            :key="`m-${candidate.id}`"
            :candidate="candidate"
            :can-generate="canGenerateMatch"
            @access-lost="load"
          />
        </el-tab-pane>
        <el-tab-pane label="沟通记录" name="communications" lazy>
          <CommunicationPanel
            ref="communicationsPanel"
            :key="`c-${candidate.id}`"
            :candidate="candidate"
            @access-lost="load"
          />
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- 编辑资料弹窗 -->
    <el-dialog v-model="editVisible" title="编辑候选人资料" width="min(620px, calc(100vw - 32px))">
      <el-form :model="editForm" label-width="110px">
        <el-form-item label="姓名" required>
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="性别"><el-input v-model="editForm.gender" /></el-form-item>
        <el-form-item label="手机号"><el-input v-model="editForm.phone" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="editForm.email" /></el-form-item>
        <el-form-item label="当前公司"><el-input v-model="editForm.current_company" /></el-form-item>
        <el-form-item label="当前职位"><el-input v-model="editForm.current_position" /></el-form-item>
        <el-form-item label="工作年限">
          <el-input-number v-model="editForm.years_of_experience" :min="0" />
        </el-form-item>
        <el-form-item label="最高学历"><el-input v-model="editForm.education" /></el-form-item>
        <el-form-item label="期望薪资"><el-input v-model="editForm.expected_salary" /></el-form-item>
        <el-form-item label="期望工作地"><el-input v-model="editForm.expected_location" /></el-form-item>
        <el-form-item label="来源">
          <el-select v-model="editForm.source" style="width: 100%">
            <el-option label="手动录入" value="manual" />
            <el-option label="自助投递" value="self_apply" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 转派弹窗 -->
    <el-dialog v-model="transferVisible" title="转派负责人" width="min(440px, calc(100vw - 32px))">
      <el-form label-width="110px">
        <el-form-item label="新负责人" required>
          <el-select v-model="transferUserId" placeholder="选择同机构有效成员" style="width: 100%">
            <el-option
              v-for="m in transferableMembers"
              :key="m.id"
              :label="`${m.real_name || m.username}（${m.username}）`"
              :value="m.user_id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTransfer">确认转派</el-button>
      </template>
    </el-dialog>
  </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getCandidate, updateCandidate, transferCandidate } from '@/api/candidate'
import { getAgencyContext, listMembers } from '@/api/agency'
import ResumeVersionsPanel from './ResumeVersionsPanel.vue'
import SkillReviewPanel from './SkillReviewPanel.vue'
import MatchPanel from './MatchPanel.vue'
import CommunicationPanel from './CommunicationPanel.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isAdmin = computed(() => userStore.role === 'admin')

const loading = ref(false)
const loadError = ref('')
const candidate = ref(null)
const context = ref({ agency: null, membership: null, invitations: [] })
const activeTab = ref('resumes')
const skillsResumeId = ref(null)
const resumesPanel = ref(null)
const skillsPanel = ref(null)
const matchesPanel = ref(null)
const communicationsPanel = ref(null)
let loadSequence = 0

const editVisible = ref(false)
const transferVisible = ref(false)
const saving = ref(false)
const members = ref([])
const transferUserId = ref(null)

const ownershipText = computed(() => {
  if (candidate.value?.provider_kind === 'agency') return '机构候选人'
  if (candidate.value?.provider_kind === 'individual') return '个人档案'
  return '待管理员核验'
})
const ownershipTag = computed(() => {
  if (candidate.value?.provider_kind === 'agency') return 'warning'
  if (candidate.value?.provider_kind === 'individual') return 'success'
  return 'info'
})
const sourceText = computed(() =>
  ({ manual: '手动录入', self_apply: '自助投递' }[candidate.value?.source] ||
    candidate.value?.source ||
    '-'),
)

// 当前用户是否该候选人负责人
const isOwner = computed(
  () => candidate.value?.owner_user_id != null &&
    candidate.value.owner_user_id === userStore.user?.id,
)
// 当前用户是否该候选人所属机构的主管
const isAgencyManager = computed(
  () =>
    candidate.value?.agency_id != null &&
    context.value.agency?.status === 'active' &&
    context.value.membership?.status === 'active' &&
    context.value.membership?.role === 'manager' &&
    context.value.membership?.agency_id === candidate.value.agency_id,
)
const canEdit = computed(() => isAdmin.value || isOwner.value || isAgencyManager.value)
// 简历/技能等私密材料的操作权限：负责人、机构主管或管理员
const canMutate = computed(() => isAdmin.value || isOwner.value || isAgencyManager.value)
// 生成匹配仅猎头具备（管理员只核验，不代猎头生成）
const canGenerateMatch = computed(() => canMutate.value && userStore.isHeadhunter)
// 转派仅面向机构候选人，且由该机构主管或管理员执行
const canTransfer = computed(
  () => candidate.value?.agency_id != null && (isAdmin.value || isAgencyManager.value),
)
// 可转派的同机构有效成员
const transferableMembers = computed(() =>
  members.value.filter((m) => m.status === 'active' && m.enabled === true),
)

const editForm = reactive({})

function formatTime(t) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}

async function load() {
  const sequence = ++loadSequence
  loading.value = true
  loadError.value = ''
  candidate.value = null
  members.value = []
  context.value = { agency: null, membership: null, invitations: [] }
  editVisible.value = false
  transferVisible.value = false
  try {
    const id = Number(route.params.id)
    const data = await getCandidate(id)
    const ctx = await getAgencyContext().catch(() => ({ agency: null, membership: null, invitations: [] }))
    if (sequence !== loadSequence) return
    candidate.value = data
    context.value = ctx
    if (canTransfer.value) {
      await loadMembers()
    }
  } catch (e) {
    if (sequence !== loadSequence) return
    candidate.value = null
    loadError.value = e
    ElMessage.error(e)
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function loadMembers() {
  const sequence = loadSequence
  try {
    const data = await listMembers(candidate.value.agency_id)
    if (sequence === loadSequence) members.value = data
  } catch (e) {
    ElMessage.error(e)
  }
}

function goBack() {
  router.push({ name: 'Candidates' })
}

function showSkills(resumeId) {
  skillsResumeId.value = resumeId
  activeTab.value = 'skills'
}

async function refreshPanel(name) {
  await nextTick()
  const panel = { resumes: resumesPanel, skills: skillsPanel, matches: matchesPanel, communications: communicationsPanel }[name]
  await panel?.value?.refresh()
}

function openEdit() {
  Object.assign(editForm, {
    name: candidate.value.name,
    gender: candidate.value.gender ?? '',
    phone: candidate.value.phone ?? '',
    email: candidate.value.email ?? '',
    current_company: candidate.value.current_company ?? '',
    current_position: candidate.value.current_position ?? '',
    years_of_experience: candidate.value.years_of_experience,
    education: candidate.value.education ?? '',
    expected_salary: candidate.value.expected_salary ?? '',
    expected_location: candidate.value.expected_location ?? '',
    source: candidate.value.source || 'manual',
  })
  editVisible.value = true
}

async function saveEdit() {
  if (!editForm.name) {
    ElMessage.warning('请填写姓名')
    return
  }
  saving.value = true
  try {
    await updateCandidate(candidate.value.id, editForm)
    ElMessage.success('已更新')
    editVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    saving.value = false
  }
}

function openTransfer() {
  transferUserId.value = null
  transferVisible.value = true
}

async function saveTransfer() {
  if (!transferUserId.value) {
    ElMessage.warning('请选择新负责人')
    return
  }
  saving.value = true
  try {
    await transferCandidate(candidate.value.id, transferUserId.value)
    ElMessage.success('已转派')
    transferVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    saving.value = false
  }
}

watch(
  () => [route.params.id, userStore.user?.id, userStore.role],
  () => {
    // 切换候选人时重置子面板状态，避免旧数据残留
    activeTab.value = 'resumes'
    skillsResumeId.value = null
    load()
  },
  { immediate: true },
)
onBeforeUnmount(() => { ++loadSequence })
</script>

<style scoped>
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.head-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.head-actions {
  display: flex;
  gap: 8px;
}
.card-title {
  margin: 0;
  font-size: 16px;
  color: #303133;
}
.mb {
  margin-bottom: 16px;
}
.mt {
  margin-top: 16px;
}
@media (max-width: 640px) {
  .card-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
  .card-title {
    white-space: nowrap;
  }
}
</style>
