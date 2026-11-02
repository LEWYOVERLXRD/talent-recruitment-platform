<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <h1>{{ isHunter ? '候选人投递' : (isInternal ? '投递核验' : '我的投递') }}</h1>
        <p class="page-sub">
          {{ isHunter ? '查看自己发布岗位收到的求职者投递，筛选后再进入推荐流程。' : (isInternal ? '管理员只读核验投递记录。' : '查看岗位、客户企业和当前处理进度。') }}
        </p>
      </div>
      <el-button plain :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-card shadow="never" v-loading="loading">
      <el-table :data="rows" border stripe>
        <el-table-column label="岗位" min-width="220">
          <template #default="{ row }">
            <strong>{{ row.job_title }}</strong>
            <div v-if="row.record_kind !== 'duplicate'" class="sub">{{ row.client_company_name || '客户企业' }}</div>
          </template>
        </el-table-column>
        <el-table-column v-if="isInternal" label="候选人" min-width="150" prop="candidate_name" />
        <el-table-column label="简历" min-width="180">
          <template #default="{ row }">{{ row.record_kind === 'duplicate' ? '—' : (row.resume_name || `简历 #${row.resume_id}`) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.record_kind === 'duplicate'" type="info">重复投递</el-tag>
            <el-tag v-else :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
            <div v-if="row.visibility_message" class="sub">{{ row.visibility_message }}</div>
          </template>
        </el-table-column>
        <el-table-column v-if="isInternal" label="猎头审核" min-width="150">
          <template #default="{ row }">
            <el-tag :type="reviewTag(row.review_status)">{{ reviewText(row.review_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="isHunter" label="审核备注" min-width="220">
          <template #default="{ row }">
            <span>{{ row.review_note || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="isInternal" label="拒收原因" min-width="220">
          <template #default="{ row }">
            <span v-if="row.status === 'rejected'">{{ row.rejection_reason_note || row.rejection_reason_category || '-' }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="投递时间" min-width="170"><template #default="{ row }">{{ fmt(row.submitted_at) }}</template></el-table-column>
        <el-table-column label="最近更新" min-width="170"><template #default="{ row }">{{ fmt(row.status_updated_at) }}</template></el-table-column>
        <el-table-column v-if="isInternal" label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.record_kind !== 'duplicate'" link type="primary" @click="downloadResume(row)">下载简历</el-button>
            <template v-if="isHunter">
              <el-button v-if="row.record_kind !== 'duplicate' && row.working_candidate_id" link type="primary" @click="router.push(`/candidates/${row.working_candidate_id}`)">候选人档案</el-button>
              <el-button v-if="row.record_kind !== 'duplicate' && row.can_recommend" link type="success" @click="recommend(row)">转为推荐</el-button>
              <el-button v-if="row.record_kind !== 'duplicate' && row.review_status === 'pending'" link type="warning" @click="openReview(row)">暂不推荐</el-button>
            </template>
            <el-button v-if="isHunter && row.record_kind !== 'duplicate' && nextStatuses(row.status).length" link type="primary" @click="openUpdate(row)">推进状态</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" :description="isHunter ? '暂无自己发布岗位收到的投递' : (isInternal ? '暂无投递记录' : '暂无投递记录，去岗位浏览看看吧')" />
    </el-card>

    <el-dialog v-model="dialogVisible" title="推进投递状态" width="min(520px, 94vw)" @closed="resetDialog">
      <el-form :model="form" label-width="100px">
        <el-form-item label="候选人"><span>{{ selected?.candidate_name || '-' }}</span></el-form-item>
        <el-form-item label="目标状态" required>
          <el-select v-model="form.status" style="width: 100%">
            <el-option v-for="item in nextStatuses(selected?.status)" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.status === 'rejected'" label="拒收类别">
          <el-input v-model="form.rejection_reason_category" maxlength="50" placeholder="如：经验不匹配" />
        </el-form-item>
        <el-form-item v-if="form.status === 'rejected'" label="拒收原因" required>
          <el-input v-model="form.rejection_reason_note" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="请填写具体原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveUpdate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reviewDialogVisible" title="暂不推荐" width="min(520px, 94vw)">
      <el-form :model="reviewForm" label-width="90px">
        <el-form-item label="候选人"><span>{{ reviewSelected?.candidate_name || '-' }}</span></el-form-item>
        <el-form-item label="内部原因" required>
          <el-input v-model="reviewForm.review_note" type="textarea" :rows="4" maxlength="2000" show-word-limit placeholder="仅猎头侧可见" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">取消</el-button>
        <el-button type="warning" :loading="reviewSaving" @click="saveReview">确认暂不推荐</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { listApplications, listMyApplications, updateApplicationStatus, downloadApplicationResume, reviewApplication, createRecommendationFromApplication } from '@/api/jobseeker'
import { listAssignments } from '@/api/assignment'

const userStore = useUserStore()
const router = useRouter()
const isHunter = computed(() => userStore.role === 'headhunter')
const isInternal = computed(() => isHunter.value || userStore.role === 'admin')
const rows = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const selected = ref(null)
const form = reactive({ status: '', rejection_reason_category: '', rejection_reason_note: '' })
const reviewDialogVisible = ref(false)
const reviewSaving = ref(false)
const reviewSelected = ref(null)
const reviewForm = reactive({ review_note: '' })
const assignments = ref([])

const STATUS_LABELS = {
  submitted: '已投递', screening: '筛选中', interview: '面试中', offer: '已发 Offer', rejected: '未通过', withdrawn: '已撤回',
}
const STATUS_TYPES = { submitted: 'info', screening: 'warning', interview: 'warning', offer: 'success', rejected: 'danger', withdrawn: 'info' }
const REVIEW_LABELS = { pending: '待筛选', not_recommended: '暂不推荐', recommendation_draft: '推荐准备中', recommended: '已推荐', legacy_unrouted: '历史待分流' }
const REVIEW_TYPES = { pending: 'warning', not_recommended: 'info', recommendation_draft: 'primary', recommended: 'success', legacy_unrouted: 'info' }
const NEXT = {
  submitted: [{ value: 'screening', label: '进入筛选' }, { value: 'rejected', label: '拒收' }],
  screening: [{ value: 'interview', label: '进入面试' }, { value: 'rejected', label: '拒收' }],
  interview: [{ value: 'offer', label: '发出 Offer' }, { value: 'rejected', label: '拒收' }],
}

function statusText(status) { return STATUS_LABELS[status] || status || '-' }
function statusTag(status) { return STATUS_TYPES[status] || 'info' }
function nextStatuses(status) { return NEXT[status] || [] }
function reviewText(status) { return REVIEW_LABELS[status] || status || '-' }
function reviewTag(status) { return REVIEW_TYPES[status] || 'info' }
function fmt(value) { return value ? String(value).replace('T', ' ').slice(0, 19) : '-' }

async function downloadResume(row) {
  try {
    await downloadApplicationResume(row.id, row.resume_name || undefined)
  } catch (error) {
    ElMessage.error(error.message || '简历下载失败')
  }
}

async function load() {
  loading.value = true
  try {
    if (isInternal.value) {
      const result = await Promise.all([listApplications(), isHunter.value ? listAssignments() : Promise.resolve([])])
      rows.value = result[0]
      assignments.value = result[1] || []
    } else {
      rows.value = await listMyApplications()
    }
  } catch (error) {
    ElMessage.error(error.message || '投递记录加载失败')
  } finally {
    loading.value = false
  }
}

function openReview(row) {
  reviewSelected.value = row
  reviewForm.review_note = ''
  reviewDialogVisible.value = true
}

async function saveReview() {
  if (!reviewSelected.value || !reviewForm.review_note.trim()) {
    ElMessage.warning('请填写内部原因')
    return
  }
  reviewSaving.value = true
  try {
    await reviewApplication(reviewSelected.value.id, { decision: 'not_recommended', review_note: reviewForm.review_note })
    ElMessage.success('已记录为暂不推荐')
    reviewDialogVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error(error.message || '审核记录失败')
  } finally {
    reviewSaving.value = false
  }
}

async function recommend(row) {
  const match = assignments.value.find((item) => item.id === row.assignment_id && item.status === 'active' && item.has_current_authorization)
  if (!match) {
    ElMessage.warning('当前需求没有可用的有效承接，请先确认承接权限')
    return
  }
  try {
    const recommendation = await createRecommendationFromApplication(row.id, { assignment_id: match.id })
    ElMessage.success('已创建推荐草稿，请进入推荐交付继续准备')
    await load()
    router.push(`/recommendations/${recommendation.id}`)
  } catch (error) {
    ElMessage.error(error.message || '创建推荐草稿失败')
  }
}

function openUpdate(row) {
  selected.value = row
  Object.assign(form, { status: nextStatuses(row.status)[0]?.value || '', rejection_reason_category: '', rejection_reason_note: '' })
  dialogVisible.value = true
}

function resetDialog() {
  selected.value = null
  Object.assign(form, { status: '', rejection_reason_category: '', rejection_reason_note: '' })
}

async function saveUpdate() {
  if (!selected.value || !form.status) return
  if (form.status === 'rejected' && !form.rejection_reason_note.trim()) {
    ElMessage.warning('拒收时必须填写原因')
    return
  }
  saving.value = true
  try {
    await updateApplicationStatus(selected.value.id, {
      status: form.status,
      rejection_reason_category: form.rejection_reason_category || null,
      rejection_reason_note: form.rejection_reason_note || null,
    })
    ElMessage.success('投递状态已更新')
    dialogVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error(error.message || '投递状态更新失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.sub { color: #687587; font-size: 12px; margin-top: 4px; }
.muted { color: #8a98a9; }
</style>
