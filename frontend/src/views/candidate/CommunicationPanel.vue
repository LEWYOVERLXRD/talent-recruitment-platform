<template>
  <div class="comm-panel">
    <div class="panel-bar">
      <el-button v-if="canWrite" type="primary" @click="openAdd">追加沟通</el-button>
      <el-button plain @click="load">刷新</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column label="时间" width="150">
        <template #default="{ row }">{{ fmt(row.communicated_at) }}</template>
      </el-table-column>
      <el-table-column label="方式" width="90">
        <template #default="{ row }">{{ commTypeText(row.comm_type) }}</template>
      </el-table-column>
      <el-table-column label="关联需求" width="110">
        <template #default="{ row }">{{ row.job_id != null ? `#${row.job_id}` : '—' }}</template>
      </el-table-column>
      <el-table-column label="意向" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.result" :type="resultTag(row.result)" size="small">
            {{ resultText(row.result) }}
          </el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="记录人" width="100">
        <template #default="{ row }">{{ row.created_by != null ? `#${row.created_by}` : '—' }}</template>
      </el-table-column>
      <el-table-column label="沟通内容" min-width="220">
        <template #default="{ row }">
          <span class="content">{{ row.content }}</span>
        </template>
      </el-table-column>
      <el-table-column label="下次跟进" width="150">
        <template #default="{ row }">{{ fmt(row.follow_up_at) }}</template>
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
    <el-empty v-if="!loading && rows.length === 0" description="暂无沟通记录" />

    <!-- 追加沟通弹窗 -->
    <el-dialog v-model="addVisible" title="追加沟通" width="min(560px, calc(100vw - 32px))">
      <el-form label-width="90px" v-loading="optionsLoading">
        <el-form-item label="关联需求">
          <el-select v-model="form.job_id" clearable filterable placeholder="不关联需求" style="width: 100%">
            <el-option
              v-for="j in jobOptions"
              :key="j.id"
              :label="`需求 #${j.job_id}（v${j.job_version}）`"
              :value="j.job_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="沟通方式" required>
          <el-select v-model="form.comm_type" style="width: 100%">
            <el-option label="电话" value="call" />
            <el-option label="微信" value="wechat" />
            <el-option label="邮件" value="email" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="沟通内容" required>
          <el-input v-model="form.content" type="textarea" :rows="4" maxlength="10000" show-word-limit />
        </el-form-item>
        <el-form-item label="意向">
          <el-select v-model="form.result" clearable placeholder="暂不记录" style="width: 100%">
            <el-option label="有意向" value="considering" />
            <el-option label="无意向" value="not_interested" />
            <el-option label="待定" value="undecided" />
          </el-select>
        </el-form-item>
        <el-form-item label="沟通时间" required>
          <el-date-picker v-model="form.communicated_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="选择沟通时间" style="width: 100%" />
        </el-form-item>
        <el-form-item label="下次跟进">
          <el-date-picker v-model="form.follow_up_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="可选" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { listCommunications, addCommunication } from '@/api/communication'
import { listAssignments } from '@/api/assignment'

const props = defineProps({
  candidate: { type: Object, required: true },
})
const emit = defineEmits(['access-lost'])

const userStore = useUserStore()
// 猎头可写，管理员只读核验
const canWrite = computed(() => userStore.isHeadhunter)

let active = true
let listSequence = 0

const loading = ref(false)
const rows = ref([])
const page = ref(1)
const size = ref(20)
const total = ref(0)

const addVisible = ref(false)
const saving = ref(false)
const optionsLoading = ref(false)
const jobOptions = ref([])
const form = reactive({
  job_id: null,
  comm_type: 'wechat',
  content: '',
  result: null,
  communicated_at: '',
  follow_up_at: null,
})

function commTypeText(t) {
  return { call: '电话', wechat: '微信', email: '邮件', other: '其他' }[t] || t || '-'
}
function resultText(r) {
  return { considering: '有意向', not_interested: '无意向', undecided: '待定' }[r] || r
}
function resultTag(r) {
  return { considering: 'success', not_interested: 'danger', undecided: 'info' }[r] || 'info'
}
function fmt(t) {
  return t ? String(t).replace('T', ' ').slice(0, 19) : '—'
}
function nowIso() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
function withLocalTimezone(value) {
  if (!value || /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)) return value
  const offset = -new Date(value).getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  const hours = String(Math.floor(Math.abs(offset) / 60)).padStart(2, '0')
  const minutes = String(Math.abs(offset) % 60).padStart(2, '0')
  return `${value}${sign}${hours}:${minutes}`
}

function reportError(error) {
  if (!active) return
  ElMessage.error(error.message || error)
  if ([401, 403, 404].includes(error.status)) {
    rows.value = []
    total.value = 0
    jobOptions.value = []
    addVisible.value = false
    emit('access-lost')
  }
}

async function load() {
  const seq = ++listSequence
  loading.value = true
  try {
    const data = await listCommunications(props.candidate.id, { page: page.value, size: size.value })
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

async function loadJobOptions() {
  jobOptions.value = []
  try {
    const assignments = await listAssignments()
    if (!active) return
    jobOptions.value = (assignments || []).filter(
      (a) =>
        a.status === 'active' &&
        a.has_current_authorization &&
        a.provider_id === props.candidate.provider_id,
    )
  } catch (e) {
    reportError(e)
    jobOptions.value = []
  }
}

async function openAdd() {
  if (!canWrite.value) return
  Object.assign(form, {
    job_id: null,
    comm_type: 'wechat',
    content: '',
    result: null,
    communicated_at: nowIso(),
    follow_up_at: null,
  })
  addVisible.value = true
  optionsLoading.value = true
  await loadJobOptions()
  optionsLoading.value = false
}

async function submit() {
  if (saving.value || !canWrite.value) return
  if (!form.content || !form.content.trim()) {
    ElMessage.warning('请填写沟通内容')
    return
  }
  if (!form.communicated_at) {
    ElMessage.warning('请选择沟通时间')
    return
  }
  saving.value = true
  try {
    await addCommunication(props.candidate.id, {
      job_id: form.job_id ?? null,
      comm_type: form.comm_type,
      content: form.content,
      result: form.result ?? null,
      communicated_at: withLocalTimezone(form.communicated_at),
      follow_up_at: withLocalTimezone(form.follow_up_at),
    })
    if (!active) return
    ElMessage.success('已记录沟通')
    addVisible.value = false
    page.value = 1
    await load()
  } catch (e) {
    reportError(e)
  } finally {
    saving.value = false
  }
}

onMounted(load)
defineExpose({ refresh: load })
onBeforeUnmount(() => { active = false; ++listSequence })
</script>

<style scoped>
.panel-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.content {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
