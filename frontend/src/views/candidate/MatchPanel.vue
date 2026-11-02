<template>
  <div class="match-panel">
    <div class="panel-bar">
      <el-button v-if="canGenerate" type="primary" :disabled="running || optionsLoading" @click="openGenerate">生成匹配</el-button>
      <el-button plain @click="loadMatches">刷新</el-button>
    </div>

    <el-table :data="matches" v-loading="loading" border stripe>
      <el-table-column label="需求" width="140">
        <template #default="{ row }">
          需求 #{{ row.job_id }}
          <span v-if="row.job_version != null" class="sub">v{{ row.job_version }}</span>
        </template>
      </el-table-column>
      <el-table-column label="简历版本" width="110">
        <template #default="{ row }">
          {{ row.resume_id != null ? `#${row.resume_id}` : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="执行人" width="100">
        <template #default="{ row }">{{ row.executed_by != null ? `#${row.executed_by}` : '—' }}</template>
      </el-table-column>
      <el-table-column label="时间" min-width="150">
        <template #default="{ row }">{{ fmt(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="得分" width="100">
        <template #default="{ row }">
          {{ row.match_score == null ? '未给出' : row.match_score }}
        </template>
      </el-table-column>
      <el-table-column label="模型" min-width="140">
        <template #default="{ row }">{{ row.model_used ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
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
    <el-empty v-if="!loading && matches.length === 0" description="暂无匹配记录" />

    <!-- 生成匹配弹窗 -->
    <el-dialog v-model="genVisible" title="生成匹配" width="min(560px, calc(100vw - 32px))">
      <el-form label-width="90px" v-loading="optionsLoading">
        <el-form-item label="目标需求" required>
          <el-select v-model="form.job_id" filterable placeholder="选择有效承接需求" style="width: 100%">
            <el-option
              v-for="j in jobOptions"
              :key="j.id"
              :label="`${j.title ?? `需求 #${j.id}`}（v${j.version}）`"
              :value="j.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="简历版本" required>
          <el-select v-model="form.resume_id" filterable placeholder="选择固定简历版本" style="width: 100%">
            <el-option
              v-for="r in resumeOptions"
              :key="r.id"
              :label="`v${r.version} · ${r.original_name || '未知'}（技能修订 v${r.skill_revision}）`"
              :value="r.id"
              :disabled="r.parse_status !== 'success'"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="gen-tip">
        匹配将固定当前需求版本与所选简历版本（及技能修订号）执行，结果仅作辅助分析，不自动推荐或拒收。
      </div>
      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button type="primary" :loading="running" :disabled="optionsLoading" @click="submitGenerate">执行匹配</el-button>
      </template>
    </el-dialog>

    <!-- 匹配详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      title="匹配结果详情"
      width="min(760px, calc(100vw - 32px))"
      top="5vh"
    >
      <div v-loading="detailLoading">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="本结果为辅助分析，仅供顾问判断，不自动推荐或拒收。"
          class="mb"
        />
        <template v-if="detail">
          <el-alert v-if="historicalVersion" class="mb" type="warning" :closable="false"
            :title="`当前需求已更新为 v${currentJobVersion}，此结果仍为 v${detail.job_version} 的历史分析。`" />
          <el-descriptions :column="2" border class="mb">
            <el-descriptions-item label="需求">#{{ detail.job_id }}</el-descriptions-item>
            <el-descriptions-item label="需求版本">
              {{ detail.job_version != null ? `v${detail.job_version}` : '历史版本' }}
            </el-descriptions-item>
            <el-descriptions-item label="简历版本">
              {{ detail.resume_id != null ? `#${detail.resume_id}` : '旧记录无完整输入快照' }}
            </el-descriptions-item>
            <el-descriptions-item label="得分">
              {{ detail.match_score == null ? '未给出' : detail.match_score }}
            </el-descriptions-item>
            <el-descriptions-item label="模型">{{ detail.model_used ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="执行人">
              {{ detail.executed_by != null ? `#${detail.executed_by}` : '—' }}
            </el-descriptions-item>
          </el-descriptions>

          <el-collapse class="mb">
            <el-collapse-item title="匹配点" name="matches">
              <pre class="block">{{ detail.match_points ?? '—' }}</pre>
            </el-collapse-item>
            <el-collapse-item title="不匹配点" name="mismatches">
              <pre class="block">{{ detail.mismatch_points ?? '—' }}</pre>
            </el-collapse-item>
            <el-collapse-item title="追问" name="questions">
              <pre class="block">{{ detail.questions_to_ask ?? '—' }}</pre>
            </el-collapse-item>
            <el-collapse-item title="原始分析" name="raw">
              <pre class="block">{{ detail.analysis_text ?? '—' }}</pre>
            </el-collapse-item>
            <el-collapse-item v-if="detail.input_snapshot?.system_prompt" title="完整 Prompt" name="prompt">
              <pre class="block">{{ detail.input_snapshot.system_prompt }}{{ '\n\n' }}{{ detail.input_snapshot.user_prompt }}</pre>
            </el-collapse-item>
            <el-collapse-item title="输入快照" name="snapshot">
              <pre v-if="detail.input_snapshot" class="block">{{ JSON.stringify(detail.input_snapshot, null, 2) }}</pre>
              <el-empty v-else description="旧记录无完整输入快照" :image-size="60" />
            </el-collapse-item>
          </el-collapse>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { listMatches, getMatch, runMatch } from '@/api/match'
import { listAssignments } from '@/api/assignment'
import { getJob } from '@/api/job'
import { allResumeVersions } from '@/api/resume'

const props = defineProps({
  candidate: { type: Object, required: true },
  canGenerate: { type: Boolean, default: false },
})
const emit = defineEmits(['access-lost'])
let active = true
let listSequence = 0
let detailSequence = 0
let optionSequence = 0

const loading = ref(false)
const matches = ref([])
const page = ref(1)
const size = ref(20)
const total = ref(0)

const genVisible = ref(false)
const running = ref(false)
const form = reactive({ job_id: null, resume_id: null })
const jobOptions = ref([])
const resumeOptions = ref([])
const optionsLoading = ref(false)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
const currentJobVersion = ref(null)
const historicalVersion = computed(() => detail.value?.job_version != null &&
  currentJobVersion.value != null && detail.value.job_version !== currentJobVersion.value)

function reportError(error) {
  if (!active) return
  ElMessage.error(error.message || error)
  if ([401, 403, 404].includes(error.status)) {
    matches.value = []; total.value = 0; detail.value = null
    jobOptions.value = []; resumeOptions.value = []
    genVisible.value = detailVisible.value = false
    emit('access-lost')
  }
}

function fmt(t) {
  return t ? String(t).replace('T', ' ').slice(0, 19) : '—'
}

async function loadMatches() {
  const request = ++listSequence
  loading.value = true
  try {
    const data = await listMatches({
      candidate_id: props.candidate.id,
      page: page.value,
      size: size.value,
    })
    if (!active || request !== listSequence) return
    matches.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    if (!active || request !== listSequence) return
    reportError(e)
    matches.value = []
    total.value = 0
  } finally {
    if (active && request === listSequence) loading.value = false
  }
}

function onPage(p) {
  page.value = p
  loadMatches()
}

async function loadResumeOptions() {
  try {
    const data = await allResumeVersions(props.candidate.id)
    if (active) resumeOptions.value = data
  } catch (e) {
    reportError(e)
    resumeOptions.value = []
  }
}

async function loadJobOptions() {
  jobOptions.value = []
  try {
    const assignments = await listAssignments()
    const accepted = (assignments || []).filter(
      (a) =>
        a.status === 'active' &&
        a.has_current_authorization &&
        a.provider_id === props.candidate.provider_id,
    )
    const jobs = []
    for (const a of accepted) {
      try {
        const job = await getJob(a.job_id)
        if (job.status === 'open' && job.confirmed_at && job.version === a.job_version) {
          jobs.push(job)
        }
      } catch {
        // 无权限或已失效的需求跳过
      }
    }
    if (active) jobOptions.value = jobs
  } catch (e) {
    reportError(e)
    jobOptions.value = []
  }
}

async function openGenerate() {
  if (running.value || optionsLoading.value || !props.canGenerate) return
  form.job_id = null
  form.resume_id = null
  genVisible.value = true
  await loadOptions()
}

async function loadOptions() {
  const request = ++optionSequence
  optionsLoading.value = true
  jobOptions.value = []; resumeOptions.value = []
  try {
    await Promise.all([loadJobOptions(), loadResumeOptions()])
  } finally {
    if (request === optionSequence) optionsLoading.value = false
  }
}

async function submitGenerate() {
  if (running.value || optionsLoading.value || !props.canGenerate) return
  if (!form.job_id) {
    ElMessage.warning('请选择目标需求')
    return
  }
  if (!form.resume_id) {
    ElMessage.warning('请选择简历版本')
    return
  }
  const job = jobOptions.value.find((j) => j.id === form.job_id)
  const resume = resumeOptions.value.find((r) => r.id === form.resume_id)
  if (!job || !resume) {
    ElMessage.warning('需求或简历版本已失效，请重新选择')
    return
  }
  running.value = true
  try {
    await runMatch({
      job_id: job.id,
      candidate_id: props.candidate.id,
      resume_id: resume.id,
      expected_job_version: job.version,
      expected_skill_revision: resume.skill_revision,
    })
    if (!active) return
    ElMessage.success('匹配完成')
    genVisible.value = false
    page.value = 1
    await loadMatches()
  } catch (e) {
    reportError(e)
    // 冲突/失效后刷新版本与需求上下文，重置旧选择，避免重复提交过期输入
    form.job_id = null
    form.resume_id = null
    genVisible.value = false
    await loadMatches()
  } finally {
    running.value = false
  }
}

async function openDetail(row) {
  const request = ++detailSequence
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  currentJobVersion.value = null
  try {
    const data = await getMatch(row.id)
    const job = await getJob(row.job_id).catch(() => null)
    if (!active || request !== detailSequence) return
    detail.value = data
    currentJobVersion.value = job?.version ?? null
  } catch (e) {
    if (request === detailSequence) reportError(e)
  } finally {
    if (active && request === detailSequence) detailLoading.value = false
  }
}

onMounted(loadMatches)
defineExpose({ refresh: loadMatches })
onBeforeUnmount(() => { active = false; ++listSequence; ++detailSequence; ++optionSequence })
</script>

<style scoped>
.panel-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.sub {
  color: #909399;
  font-size: 12px;
  margin-left: 4px;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.mb {
  margin-bottom: 12px;
}
.gen-tip {
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
.block {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.7;
  max-height: 40vh;
  overflow: auto;
}
</style>
