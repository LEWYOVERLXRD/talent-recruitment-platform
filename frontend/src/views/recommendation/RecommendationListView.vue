<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <h1>{{ title }}</h1>
        <p class="page-sub">{{ hint }}</p>
      </div>
      <div class="page-actions">
        <el-button v-if="userStore.isHeadhunter" type="primary" @click="openCreate">新建推荐</el-button>
      </div>
    </div>

    <el-card shadow="never" v-loading="loading">
    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon class="mb" />

    <template v-if="!loadError">
      <el-table :data="rows" @row-click="openDetail">
        <el-table-column label="ID" width="80">
          <template #default="{ row }">#{{ row.id }}</template>
        </el-table-column>
        <el-table-column label="需求" min-width="160">
          <template #default="{ row }">
            <span v-if="row.job_title">{{ row.job_title }}</span>
            <span v-else class="sub">需求 #{{ row.job_id ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.historical_pending_verification" type="warning" size="small">历史待核验</el-tag>
            <el-tag v-else :type="statusTag(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="80">
          <template #default="{ row }">
            {{ row.version != null ? `v${row.version}` : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="推荐时间" width="160">
          <template #default="{ row }">{{ fmt(row.recommended_at) }}</template>
        </el-table-column>
        <el-table-column label="角色提示" min-width="140">
          <template #default="{ row }">
            <el-tag v-if="row.can_edit" type="success" size="small">草稿可编辑</el-tag>
            <el-tag v-else-if="row.can_feedback" type="warning" size="small">待反馈</el-tag>
            <span v-else class="sub">只读</span>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > size"
        class="pager"
        layout="prev, pager, next, total"
        :total="total"
        :page-size="size"
        :current-page="page"
        @current-change="onPage"
      />
      <el-empty v-if="!loading && rows.length === 0" description="暂无推荐记录" />
    </template>

    <!-- 新建推荐弹窗（仅猎头） -->
    <el-dialog v-model="createVisible" title="新建推荐" width="min(560px, calc(100vw - 32px))">
      <el-form label-width="110px" v-loading="optionsLoading">
        <el-form-item label="有效承接" required>
          <el-select v-model="form.assignment_id" filterable placeholder="选择承接" style="width: 100%" @change="onAssignmentChange">
            <el-option
              v-for="a in assignmentOptions"
              :key="a.id"
              :label="`${a.client_company_name || '客户企业'} · ${a.job_title || a.job_snapshot?.title || '岗位'}（承接 #${a.id}，v${a.job_version}）`"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="候选人" required>
          <el-select v-model="form.candidate_id" filterable placeholder="选择权限内候选人" style="width: 100%">
            <el-option
              v-for="c in candidateOptions"
              :key="c.id"
              :label="`${c.name}（#${c.id}）`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="gen-tip">仅能从当前有效承接与权限内候选人发起草稿；已有生命周期的承接/候选人组合会提示冲突。</div>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { listRecommendations, createRecommendation } from '@/api/recommendation'
import { listAssignments } from '@/api/assignment'
import { listCandidates } from '@/api/candidate'

const router = useRouter()
const userStore = useUserStore()

let active = true
let listSequence = 0

const loading = ref(false)
const loadError = ref('')
const rows = ref([])
const page = ref(1)
const size = ref(20)
const total = ref(0)

const createVisible = ref(false)
const creating = ref(false)
const optionsLoading = ref(false)
const assignmentOptions = ref([])
const candidateOptions = ref([])
const form = reactive({ assignment_id: null, candidate_id: null })

const title = computed(() => {
  if (userStore.isAdmin) return '推荐核验'
  if (userStore.isHeadhunter) return '推荐交付'
  return '推荐反馈'
})
const hint = computed(() => {
  if (userStore.isAdmin) return '管理员只读核验：此处含历史待核验记录，不代猎头交付、不代客户写反馈。'
  if (userStore.isHeadhunter) return '从有效承接发起推荐草稿，准备完成后一次性交付固定快照。'
  return '此处仅展示本企业已交付的固定快照，可接收/拒收并追加面试反馈。'
})

function statusText(s) {
  return {
    pending_contact: '待沟通',
    contacted: '已沟通',
    pending_recommend: '待推荐',
    recommended: '已推荐',
    accepted: '已接收',
    interviewing: '面试中',
    passed: '已通过',
    rejected: '已拒收/未通过',
  }[s] || s
}
function statusTag(s) {
  return {
    pending_contact: 'info',
    contacted: 'info',
    pending_recommend: 'warning',
    recommended: 'primary',
    accepted: 'success',
    interviewing: 'warning',
    passed: 'success',
    rejected: 'danger',
  }[s] || 'info'
}
function fmt(t) {
  return t ? String(t).replace('T', ' ').slice(0, 19) : '—'
}

function reportError(error) {
  if (!active) return
  ElMessage.error(error.message || error)
  if ([401, 403, 404].includes(error.status)) {
    rows.value = []
    total.value = 0
    loadError.value = error.message || error
  }
}

async function load() {
  const seq = ++listSequence
  loading.value = true
  loadError.value = ''
  try {
    const data = await listRecommendations({ page: page.value, size: size.value })
    if (!active || seq !== listSequence) return
    rows.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    if (!active || seq !== listSequence) return
    reportError(e)
    rows.value = []
    total.value = 0
  } finally {
    if (active && seq === listSequence) loading.value = false
  }
}

function onPage(p) {
  page.value = p
  load()
}

function openDetail(row) {
  router.push({ name: 'RecommendationDetail', params: { id: row.id } })
}

async function loadAssignmentOptions() {
  try {
    const assignments = await listAssignments()
    if (!active) return
    assignmentOptions.value = (assignments || []).filter(
      (a) => a.status === 'active' && a.has_current_authorization,
    )
  } catch (e) {
    reportError(e)
    assignmentOptions.value = []
  }
}

async function loadAllCandidates() {
  const items = []
  for (let p = 1; ; p++) {
    const data = await listCandidates({ page: p, size: 100 })
    items.push(...(data.items || []))
    if (items.length >= data.total || (data.items || []).length === 0) break
    if (p > 50) break
  }
  return items
}

async function onAssignmentChange(id) {
  form.candidate_id = null
  candidateOptions.value = []
  const assignment = assignmentOptions.value.find((a) => a.id === id)
  if (!assignment) return
  try {
    const all = await loadAllCandidates()
    if (!active) return
    candidateOptions.value = all.filter((c) => c.provider_id === assignment.provider_id)
  } catch (e) {
    reportError(e)
    candidateOptions.value = []
  }
}

async function openCreate() {
  if (!userStore.isHeadhunter) return
  form.assignment_id = null
  form.candidate_id = null
  candidateOptions.value = []
  createVisible.value = true
  optionsLoading.value = true
  await loadAssignmentOptions()
  optionsLoading.value = false
}

async function submitCreate() {
  if (creating.value || !userStore.isHeadhunter) return
  if (!form.assignment_id) {
    ElMessage.warning('请选择有效承接')
    return
  }
  if (!form.candidate_id) {
    ElMessage.warning('请选择候选人')
    return
  }
  creating.value = true
  try {
    const created = await createRecommendation({
      assignment_id: form.assignment_id,
      candidate_id: form.candidate_id,
    })
    if (!active) return
    ElMessage.success('已创建推荐草稿')
    createVisible.value = false
    if (created?.id) {
      router.push({ name: 'RecommendationDetail', params: { id: created.id } })
    } else {
      page.value = 1
      await load()
    }
  } catch (e) {
    reportError(e)
    createVisible.value = false
    page.value = 1
    await load()
  } finally {
    creating.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => { active = false; ++listSequence })
</script>

<style scoped>
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-title {
  margin: 0;
  font-size: 16px;
  color: #303133;
}
.mb {
  margin-bottom: 12px;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.sub {
  color: #909399;
  font-size: 12px;
}
.gen-tip {
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
</style>
