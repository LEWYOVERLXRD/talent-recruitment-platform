<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <el-button link type="primary" class="back-link" @click="goBack">← 返回列表</el-button>
        <h1>推荐详情</h1>
        <p v-if="detail" class="page-sub">
          {{ detail.job_title || `需求 #${detail.job_id ?? '—'}` }} ·
          {{ detail.version != null ? `推荐 v${detail.version}` : '未记录版本' }}
        </p>
      </div>
    </div>

  <el-card shadow="never" v-loading="loading">

    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon class="mb" />

    <template v-if="detail">
      <!-- 历史待核验（仅管理员） -->
      <el-alert
        v-if="detail.historical_pending_verification"
        type="warning"
        :closable="false"
        show-icon
        title="该推荐为历史待核验记录，缺少承接主体信息，当前仅平台管理员可见。"
        class="mb"
      />

      <!-- 基本信息 -->
      <el-descriptions :column="2" border class="mb">
        <el-descriptions-item label="推荐 ID">#{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="需求">
          {{ detail.job_title || `#${detail.job_id ?? '—'}` }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTag(detail.status)" size="small">{{ statusText(detail.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="推荐版本">
          {{ detail.version != null ? `v${detail.version}` : '—' }}
        </el-descriptions-item>
        <el-descriptions-item v-if="detail.job_version != null" label="需求版本">
          v{{ detail.job_version }}
        </el-descriptions-item>
        <el-descriptions-item v-if="detail.assignment_id != null" label="承接">
          #{{ detail.assignment_id }}（轮次 {{ detail.assignment_round ?? '—' }}）
        </el-descriptions-item>
        <el-descriptions-item v-if="detail.candidate_id != null" label="候选人">
          #{{ detail.candidate_id }}
        </el-descriptions-item>
        <el-descriptions-item v-if="detail.recommended_at" label="推荐时间">
          {{ fmt(detail.recommended_at) }}
        </el-descriptions-item>
        <el-descriptions-item v-if="detail.recommended_by" label="推荐人">
          #{{ detail.recommended_by }}
        </el-descriptions-item>
      </el-descriptions>

      <!-- 交付固定快照 -->
      <template v-if="snapshot">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="以下为交付时的固定快照，不随实时档案更新；请勿与当前简历/需求混淆。"
          class="mb"
        />

        <el-descriptions :column="2" border class="mb" title="需求快照">
          <el-descriptions-item label="标题">{{ snapshot.job?.title ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="版本">v{{ snapshot.job?.version ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="部门">{{ snapshot.job?.department ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="地点">{{ snapshot.job?.location ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="薪资">
            {{ fmtSalary(snapshot.job) }}
          </el-descriptions-item>
          <el-descriptions-item label="企业">{{ snapshot.job?.company_name ?? '—' }}</el-descriptions-item>
        </el-descriptions>

        <el-descriptions :column="2" border class="mb" title="候选人快照">
          <el-descriptions-item label="姓名">{{ snapshot.candidate?.name ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ snapshot.candidate?.phone ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ snapshot.candidate?.email ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="当前公司">{{ snapshot.candidate?.current_company ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="当前职位">{{ snapshot.candidate?.current_position ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="工作年限">{{ snapshot.candidate?.years_of_experience ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="最高学历">{{ snapshot.candidate?.education ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="期望薪资">{{ snapshot.candidate?.expected_salary ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="期望地点">{{ snapshot.candidate?.expected_location ?? '—' }}</el-descriptions-item>
        </el-descriptions>

        <el-descriptions :column="2" border class="mb" title="交付信息">
          <el-descriptions-item label="承接主体">{{ snapshot.provider?.name ?? `#${snapshot.provider?.id ?? '—'}` }}</el-descriptions-item>
          <el-descriptions-item label="承接轮次">{{ snapshot.assignment?.round ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="提交时间">{{ fmt(snapshot.recommendation?.submitted_at) }}</el-descriptions-item>
          <el-descriptions-item label="推荐说明" :span="2">
            <span class="wrap">{{ snapshot.recommendation?.note || '（无）' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="共享依据">
            <span v-if="userStore.isHeadhunter || userStore.isAdmin">
              {{ detail.share_basis || '交付方已记录材料共享依据' }}
            </span>
            <span v-else>交付方已记录材料共享依据</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-descriptions v-if="snapshot.resume" :column="2" border class="mb" title="简历附件快照">
          <el-descriptions-item label="版本">v{{ snapshot.resume.version ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="文件名">{{ snapshot.resume.file_name ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ snapshot.resume.file_type ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="大小">{{ formatSize(snapshot.resume.file_size) }}</el-descriptions-item>
          <el-descriptions-item label="摘要">
            <span class="mono">{{ snapshot.resume.sha256 ?? '—' }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <div class="mb">
          <el-button v-if="snapshot.resume" type="primary" plain :loading="downloading" @click="download">
            下载简历附件
          </el-button>
        </div>

        <el-collapse class="mb">
          <el-collapse-item v-if="snapshot.job?.description" title="需求描述" name="desc">
            <pre class="block">{{ snapshot.job.description }}</pre>
          </el-collapse-item>
          <el-collapse-item v-if="snapshot.job?.requirements" title="任职要求" name="req">
            <pre class="block">{{ snapshot.job.requirements }}</pre>
          </el-collapse-item>
          <el-collapse-item v-if="snapshot.resume?.parsed_text" title="简历正文（交付快照）" name="text">
            <pre class="block">{{ snapshot.resume.parsed_text }}</pre>
          </el-collapse-item>
        </el-collapse>
      </template>

      <!-- 准备区（草稿，猎头可操作，管理员只读） -->
      <template v-else-if="detail.can_edit || userStore.isAdmin">
        <el-alert
          v-if="!userStore.isHeadhunter"
          type="info"
          :closable="false"
          show-icon
          title="该推荐尚处准备阶段，仅负责猎头可编辑与提交。"
          class="mb"
        />

        <el-descriptions :column="2" border class="mb">
          <el-descriptions-item label="准备阶段">
            <el-tag :type="statusTag(detail.status)" size="small">{{ statusText(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="当前简历版本">
            {{ detail.resume_id != null ? `#${detail.resume_id}` : '未选择' }}
          </el-descriptions-item>
          <el-descriptions-item label="沟通依据">
            {{ detail.preparation_communication_id != null ? `#${detail.preparation_communication_id}` : '未选择' }}
          </el-descriptions-item>
          <el-descriptions-item label="推荐说明" :span="2">
            <span class="wrap">{{ detail.recommendation_note || '（无）' }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="canOperate" class="prep-card">
          <el-form label-width="110px" v-loading="optionsLoading" :disabled="mutationBusy">
            <el-form-item label="简历版本">
              <el-select v-model="prep.resume_id" clearable filterable placeholder="选择固定简历版本" style="width: 100%">
                <el-option
                  v-for="r in resumeOptions"
                  :key="r.id"
                  :label="`v${r.version} · ${r.original_name || '未知'}`"
                  :value="r.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="沟通依据">
              <el-select v-model="prep.communication_id" clearable filterable placeholder="选择沟通记录（可清除）" style="width: 100%">
                <el-option
                  v-for="c in communicationOptions"
                  :key="c.id"
                  :label="`#${c.id} · ${commTypeText(c.comm_type)} · ${formatShort(c.communicated_at)}`"
                  :value="c.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="推荐说明">
              <el-input v-model="prep.recommendation_note" type="textarea" :rows="4" maxlength="10000" show-word-limit />
            </el-form-item>
          </el-form>

          <div class="actions">
            <el-button type="primary" plain :loading="saving" :disabled="mutationBusy" @click="savePrep">保存准备</el-button>
            <el-button
              v-if="detail.status === 'pending_contact'"
              type="warning"
              plain
              :loading="staging"
              :disabled="mutationBusy"
              @click="stage('contacted')"
            >
              标记已沟通
            </el-button>
            <el-button
              v-if="detail.status === 'contacted'"
              type="warning"
              plain
              :loading="staging"
              :disabled="mutationBusy"
              @click="stage('pending_recommend')"
            >
              进入待推荐
            </el-button>
            <el-button v-if="canRefresh" plain :loading="refreshing" :disabled="mutationBusy" @click="refreshContext">
              刷新准备上下文
            </el-button>
          </div>

          <el-divider content-position="left">一次性交付</el-divider>
          <el-form label-width="110px" :disabled="mutationBusy">
            <el-form-item label="共享依据" required>
              <el-input v-model="submitForm.share_basis" type="textarea" :rows="3" maxlength="5000" show-word-limit
                placeholder="记录候选人同意向客户共享材料的依据" />
            </el-form-item>
            <el-form-item label="确认时间" required>
              <el-date-picker v-model="submitForm.share_confirmed_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss"
                placeholder="选择确认时间" style="width: 100%" />
            </el-form-item>
          </el-form>
          <el-button type="success" :loading="submitting" :disabled="mutationBusy || detail.status !== 'pending_recommend'" @click="submit">
            提交交付快照
          </el-button>
          <span v-if="detail.status !== 'pending_recommend'" class="sub">
            需先推进到「待推荐」阶段后方可提交。
          </span>
        </div>
      </template>

      <!-- 固定交付历史（无准备区）提示 -->
      <el-alert
        v-if="!detail.can_edit && !detail.historical_pending_verification && !snapshot && !userStore.isAdmin"
        type="info"
        :closable="false"
        show-icon
        title="该推荐为固定交付历史，仅展示交付快照，不可再编辑。"
        class="mb"
      />

      <!-- 反馈区（交付后展示） -->
      <template v-if="snapshot">
        <el-divider content-position="left">客户反馈</el-divider>

        <el-table :data="feedbacks" v-loading="feedbackLoading" border stripe class="mb">
          <el-table-column label="类型" width="110">
            <template #default="{ row }">{{ feedbackTypeText(row.feedback_type) }}</template>
          </el-table-column>
          <el-table-column label="结论" width="110">
            <template #default="{ row }">{{ conclusionText(row.conclusion) }}</template>
          </el-table-column>
          <el-table-column label="状态变更" width="180">
            <template #default="{ row }">{{ statusText(row.from_status) }} → {{ statusText(row.to_status) }}</template>
          </el-table-column>
          <el-table-column label="内容" min-width="200">
            <template #default="{ row }"><span class="wrap">{{ row.content }}</span></template>
          </el-table-column>
          <el-table-column label="时间" width="160">
            <template #default="{ row }">{{ fmt(row.created_at) }}</template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-if="feedbackTotal > feedbackSize"
          class="pager"
          layout="prev, pager, next, total"
          :total="feedbackTotal"
          :page-size="feedbackSize"
          :current-page="feedbackPage"
          @current-change="onFeedbackPage"
        />

        <div v-if="canFeedback" class="feedback-form">
          <el-alert class="mb" type="info" :closable="false" title="招聘流程通过仅表示本次流程通过，不代表入职、签约或结算；终态只能追加备注。" />
          <el-form label-width="110px">
            <el-form-item label="反馈类型" required>
              <el-radio-group v-model="feedbackForm.feedback_type">
                <el-radio-button value="recommendation">推荐反馈</el-radio-button>
                <el-radio-button value="interview">面试反馈</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="结论" required>
              <el-select v-model="feedbackForm.conclusion" placeholder="选择结论" style="width: 100%">
                <el-option
                  v-for="o in conclusionOptions"
                  :key="o.value"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="说明" required>
              <el-input v-model="feedbackForm.content" type="textarea" :rows="3" maxlength="5000" show-word-limit />
            </el-form-item>
          </el-form>
          <el-button type="primary" :loading="feedbackSaving" @click="submitFeedback">提交反馈</el-button>
        </div>

        <!-- 企业端面试题生成与回看 -->
        <template v-if="userStore.role === 'recruiter'">
          <el-divider content-position="left">AI 面试题</el-divider>

          <div class="iq-toolbar mb">
            <div>
              <span class="sub">基于固定交付快照生成结构化面试题（已过滤常见手机/座机/邮箱并移除简历文件名）；历史题组永久保留供回看。</span>
            </div>
            <el-button
              v-if="canGenerateQuestions"
              type="primary"
              plain
              :loading="iqState.questionGenerating"
              :disabled="iqState.questionGenerating || iqState.questionLoading"
              @click="handleGenerateQuestions"
            >
              生成面试题
            </el-button>
            <el-tag v-else type="info" size="small">
              仅「已接收」或「面试中」状态可生成新题组
            </el-tag>
          </div>

          <el-alert
            v-if="iqState.questionError"
            :title="iqState.questionError"
            type="error"
            show-icon
            closable
            class="mb"
            @close="iqState.questionError = ''"
          />

          <div v-loading="iqState.questionLoading || iqState.questionGenerating">
            <el-empty
              v-if="!iqState.questionLoading && !iqState.questionGenerating && iqState.questionSets.length === 0"
              description="暂无面试题组，可在已接收或面试中状态点击「生成面试题」"
              :image-size="64"
            />

            <el-card
              v-for="qset in iqState.questionSets"
              :key="qset.id"
              shadow="never"
              class="iq-set-card mb"
            >
              <template #header>
                <div class="card-head">
                  <div class="head-left">
                    <strong>题组 #{{ qset.id }}</strong>
                    <el-tag size="small" :type="statusTag(qset.recommendation_status)">
                      {{ statusText(qset.recommendation_status) }} · v{{ qset.recommendation_version }}
                    </el-tag>
                    <el-tag size="small" type="info">模型: {{ qset.model_used }}</el-tag>
                    <span class="sub">{{ fmt(qset.created_at) }}</span>
                  </div>
                  <el-button size="small" plain @click="copyQuestionSet(qset)">复制题组</el-button>
                </div>
              </template>

              <p class="sub mb" v-if="qset.input_summary">
                输入摘要：{{ qset.input_summary.job?.title || '岗位' }} /
                {{ qset.input_summary.candidate_profile?.current_position || '候选人' }}
                （已过滤常见联系方式：{{ qset.input_summary.contact_fields_removed ? '是' : '否' }}）
              </p>

              <div v-for="(item, idx) in qset.questions" :key="idx" class="iq-item">
                <div class="iq-q"><strong>Q{{ idx + 1 }}. {{ item.question }}</strong></div>
                <div class="iq-meta"><strong>考察目的：</strong>{{ item.purpose }}</div>
                <div class="iq-meta">
                  <strong>参考要点：</strong>
                  <ul class="iq-points">
                    <li v-for="(pt, pIdx) in item.key_points" :key="pIdx">{{ pt }}</li>
                  </ul>
                </div>
              </div>
            </el-card>
          </div>
        </template>
      </template>
    </template>
  </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import {
  getRecommendation,
  updateRecommendation,
  stageRecommendation,
  refreshRecommendationContext,
  submitRecommendation,
  listFeedbacks,
  addFeedback,
  downloadRecommendationResume,
  listInterviewQuestions,
  generateInterviewQuestions,
} from '@/api/recommendation'
import { allResumeVersions } from '@/api/resume'
import { listCommunications } from '@/api/communication'
import { listAssignments } from '@/api/assignment'
import {
  createInterviewQuestionState,
  createInterviewQuestionController,
} from './interviewQuestionState'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

let active = true
let loadSeq = 0
let feedbackSeq = 0

const loading = ref(false)
const loadError = ref('')
const detail = ref(null)
const currentAssignment = ref(null)

const downloading = ref(false)
const saving = ref(false)
const staging = ref(false)
const refreshing = ref(false)
const submitting = ref(false)

const optionsLoading = ref(false)
const resumeOptions = ref([])
const communicationOptions = ref([])

const prep = reactive({ resume_id: null, communication_id: null, recommendation_note: '' })
const submitForm = reactive({ share_basis: '', share_confirmed_at: '' })

const feedbackLoading = ref(false)
const feedbacks = ref([])
const feedbackPage = ref(1)
const feedbackSize = ref(20)
const feedbackTotal = ref(0)
const feedbackSaving = ref(false)
const feedbackForm = reactive({ feedback_type: 'recommendation', conclusion: '', content: '' })

const iqState = reactive(createInterviewQuestionState())
const iqController = createInterviewQuestionController(iqState)

const snapshot = computed(() => detail.value?.delivery_snapshot || null)
// 猎头且草稿才可操作准备/提交（管理员只读）
const canOperate = computed(() => userStore.isHeadhunter && detail.value?.can_edit === true)
const canRefresh = computed(() => canOperate.value && currentAssignment.value && (
  currentAssignment.value.job_version !== detail.value.job_version ||
  currentAssignment.value.round_no !== detail.value.assignment_round
))
const mutationBusy = computed(() => saving.value || staging.value || refreshing.value || submitting.value || loading.value)
// 客户对本企业已交付推荐可反馈
const canFeedback = computed(() => userStore.role === 'recruiter' && detail.value?.can_feedback === true)
const canGenerateQuestions = computed(() => (
  userStore.role === 'recruiter'
  && Boolean(detail.value?.delivery_snapshot)
  && ['accepted', 'interviewing'].includes(detail.value?.status)
))

const conclusionOptions = computed(() => {
  const options = [{ value: 'note', label: '备注' }]
  const status = detail.value?.status
  const type = feedbackForm.feedback_type
  if (status === 'recommended' && type === 'recommendation') {
    options.unshift({ value: 'accepted', label: '接收' }, { value: 'rejected', label: '拒收' })
  } else if (status === 'accepted') {
    options.unshift(type === 'interview'
      ? { value: 'interviewing', label: '进入面试' }
      : { value: 'rejected', label: '拒收' })
  } else if (status === 'interviewing' && type === 'interview') {
    options.unshift({ value: 'passed', label: '面试通过' }, { value: 'rejected', label: '面试未通过' })
  }
  return options
})
watch(conclusionOptions, (options) => {
  if (!options.some((option) => option.value === feedbackForm.conclusion)) feedbackForm.conclusion = ''
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
  }[s] || s || '—'
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
function feedbackTypeText(t) {
  return { recommendation: '推荐反馈', interview: '面试反馈' }[t] || t
}
function conclusionText(c) {
  return { accepted: '接收', rejected: '拒收/未通过', interviewing: '进入面试', passed: '面试通过', note: '备注' }[c] || c
}
function commTypeText(t) {
  return { call: '电话', wechat: '微信', email: '邮件', other: '其他' }[t] || t
}
function fmt(t) {
  return t ? String(t).replace('T', ' ').slice(0, 19) : '—'
}
function formatShort(t) {
  return fmt(t).slice(0, 16)
}
function formatSize(n) {
  if (n == null) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
function fmtSalary(job) {
  if (job?.salary_min == null && job?.salary_max == null) return '—'
  return `${job.salary_min ?? '?'} ~ ${job.salary_max ?? '?'}`
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
  if ([403, 404].includes(error.status)) {
    detail.value = null
    resumeOptions.value = []
    communicationOptions.value = []
    feedbacks.value = []
    feedbackTotal.value = 0
    loadError.value = error.message || error
    router.push({ name: 'Recommendations' })
  }
}

async function load() {
  const seq = ++loadSeq
  ++feedbackSeq
  loading.value = true
  loadError.value = ''
  detail.value = null
  currentAssignment.value = null
  resumeOptions.value = []
  communicationOptions.value = []
  Object.assign(feedbackForm, { feedback_type: 'recommendation', conclusion: '', content: '' })
  feedbacks.value = []
  feedbackTotal.value = 0
  iqController.resetForRecommendation(route.params.id)
  try {
    const data = await getRecommendation(route.params.id)
    if (!active || seq !== loadSeq) return
    detail.value = data
    resetPrepFromDetail()
    if (data?.can_edit && userStore.isHeadhunter) {
      optionsLoading.value = true
      await Promise.all([loadResumeOptions(data.candidate_id, seq), loadCommunicationOptions(data.candidate_id, seq)])
      if (!active || seq !== loadSeq || !detail.value) return
      const assignments = await listAssignments()
      if (!active || seq !== loadSeq || !detail.value) return
      currentAssignment.value = assignments.find((assignment) => assignment.id === data.assignment_id) || null
      optionsLoading.value = false
    }
    if (data?.delivery_snapshot) {
      await loadFeedbackPage()
      if (!active || seq !== loadSeq) return
      if (userStore.role === 'recruiter') {
        await loadInterviewQuestions(data.id)
      }
    }
  } catch (e) {
    if (!active || seq !== loadSeq) return
    detail.value = null
    loadError.value = e.message || e
    if ([403, 404].includes(e.status)) {
      ElMessage.error(e.message || e)
      router.push({ name: 'Recommendations' })
    }
  } finally {
    if (active && seq === loadSeq) loading.value = false
  }
}

function resetPrepFromDetail() {
  prep.resume_id = detail.value?.resume_id ?? null
  prep.communication_id = detail.value?.preparation_communication_id ?? null
  prep.recommendation_note = detail.value?.recommendation_note ?? ''
  submitForm.share_basis = ''
  submitForm.share_confirmed_at = nowIso()
}

async function loadResumeOptions(candidateId, seq) {
  try {
    const data = await allResumeVersions(candidateId)
    if (active && seq === loadSeq) resumeOptions.value = data
  } catch (e) {
    if (!active || seq !== loadSeq) return
    reportError(e)
    resumeOptions.value = []
  }
}

async function loadCommunicationOptions(candidateId, seq) {
  const items = []
  try {
    for (let p = 1; ; p++) {
      const data = await listCommunications(candidateId, { page: p, size: 100 })
      if (!active || seq !== loadSeq) return
      items.push(...(data.items || []))
      if (items.length >= data.total || (data.items || []).length === 0) break
      if (p > 50) break
    }
    if (active && seq === loadSeq) communicationOptions.value = items
  } catch (e) {
    if (!active || seq !== loadSeq) return
    reportError(e)
    communicationOptions.value = []
  }
}

async function savePrep() {
  if (mutationBusy.value || !canOperate.value) return
  saving.value = true
  try {
    await updateRecommendation(detail.value.id, {
      expected_version: detail.value.version,
      resume_id: prep.resume_id ?? null,
      communication_id: prep.communication_id ?? null,
      recommendation_note: prep.recommendation_note || null,
    })
    if (!active) return
    ElMessage.success('已保存准备信息')
    await load()
  } catch (e) {
    reportError(e)
    await load()
  } finally {
    saving.value = false
  }
}

async function stage(status) {
  if (mutationBusy.value || !canOperate.value) return
  if (!prep.communication_id) {
    ElMessage.warning('请先选择沟通依据')
    return
  }
  staging.value = true
  try {
    await stageRecommendation(detail.value.id, {
      expected_version: detail.value.version,
      status,
      communication_id: prep.communication_id,
    })
    if (!active) return
    ElMessage.success(status === 'contacted' ? '已标记为已沟通' : '已进入待推荐')
    await load()
  } catch (e) {
    reportError(e)
    await load()
  } finally {
    staging.value = false
  }
}

async function refreshContext() {
  if (mutationBusy.value || !canRefresh.value) return
  try {
    await ElMessageBox.confirm('刷新将清空已选简历、沟通依据、推荐说明和共享信息，需要重新准备。是否继续？', '确认刷新上下文', {
      type: 'warning',
      confirmButtonText: '刷新',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  refreshing.value = true
  try {
    await refreshRecommendationContext(detail.value.id, {
      expected_version: detail.value.version,
      job_version: currentAssignment.value.job_version,
      assignment_round: currentAssignment.value.round_no,
    })
    if (!active) return
    ElMessage.success('上下文已刷新，请重新准备')
    await load()
  } catch (e) {
    reportError(e)
    await load()
  } finally {
    refreshing.value = false
  }
}

async function submit() {
  if (mutationBusy.value || !canOperate.value) return
  if (!submitForm.share_basis || !submitForm.share_basis.trim()) {
    ElMessage.warning('请填写材料共享依据')
    return
  }
  if (!submitForm.share_confirmed_at) {
    ElMessage.warning('请选择确认时间')
    return
  }
  submitting.value = true
  try {
    await submitRecommendation(detail.value.id, {
      expected_version: detail.value.version,
      share_basis: submitForm.share_basis,
      share_confirmed_at: withLocalTimezone(submitForm.share_confirmed_at),
    })
    if (!active) return
    ElMessage.success('已交付固定快照')
    await load()
  } catch (e) {
    reportError(e)
    await load()
  } finally {
    submitting.value = false
  }
}

async function download() {
  if (downloading.value) return
  downloading.value = true
  try {
    await downloadRecommendationResume(detail.value.id, snapshot.value.resume?.file_name || undefined)
  } catch (e) {
    reportError(e)
  } finally {
    downloading.value = false
  }
}

async function loadFeedbackPage() {
  const seq = ++feedbackSeq
  feedbackLoading.value = true
  try {
    const data = await listFeedbacks(detail.value.id, { page: feedbackPage.value, size: feedbackSize.value })
    if (!active || seq !== feedbackSeq) return
    feedbacks.value = data.items || []
    feedbackTotal.value = data.total || 0
  } catch (e) {
    if (!active || seq !== feedbackSeq) return
    reportError(e)
    feedbacks.value = []
    feedbackTotal.value = 0
  } finally {
    if (active && seq === feedbackSeq) feedbackLoading.value = false
  }
}

function onFeedbackPage(p) {
  feedbackPage.value = p
  loadFeedbackPage()
}

async function submitFeedback() {
  if (feedbackSaving.value || !canFeedback.value) return
  if (!feedbackForm.conclusion) {
    ElMessage.warning('请选择结论')
    return
  }
  if (!feedbackForm.content || !feedbackForm.content.trim()) {
    ElMessage.warning('请填写说明')
    return
  }
  if (feedbackForm.conclusion === 'rejected' && feedbackForm.content.trim().length < 20) {
    ElMessage.warning('拒收/未通过理由至少 20 个字符')
    return
  }
  feedbackSaving.value = true
  try {
    await addFeedback(detail.value.id, {
      expected_version: detail.value.version,
      conclusion: feedbackForm.conclusion,
      feedback_type: feedbackForm.feedback_type,
      content: feedbackForm.content,
    })
    if (!active) return
    ElMessage.success('已提交反馈')
    feedbackForm.conclusion = ''
    feedbackForm.content = ''
    feedbackPage.value = 1
    await load()
  } catch (e) {
    reportError(e)
    await load()
  } finally {
    feedbackSaving.value = false
  }
}

function goBack() {
  router.push({ name: 'Recommendations' })
}

async function loadInterviewQuestions(recId) {
  if (!recId || userStore.role !== 'recruiter') return
  await iqController.loadList(recId, listInterviewQuestions)
}

async function handleGenerateQuestions() {
  if (!canGenerateQuestions.value || !detail.value?.id) return
  await iqController.generate(
    detail.value.id,
    detail.value.version,
    generateInterviewQuestions,
    {
      onSuccess: (msg) => ElMessage.success(msg),
      onError: (msg) => ElMessage.error(msg),
    },
  )
}

async function copyQuestionSet(qset) {
  const lines = (qset.questions || []).map((item, idx) => {
    const pts = (item.key_points || []).map((pt) => `   - ${pt}`).join('\n')
    return `${idx + 1}. ${item.question}\n考察目的：${item.purpose}\n参考要点：\n${pts}`
  })
  const text = `【面试题组 #${qset.id} | 模型：${qset.model_used}】\n\n${lines.join('\n\n')}`
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制题组到剪贴板')
  } catch {
    ElMessage.warning('当前环境不支持自动剪贴板写入，请手动复制')
  }
}

watch(() => route.params.id, () => {
  feedbackPage.value = 1
  load()
}, { immediate: true })
onBeforeUnmount(() => { active = false; ++loadSeq; ++feedbackSeq; iqController.dispose() })
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
.card-title {
  margin: 0;
  font-size: 16px;
  color: #303133;
}
.mb {
  margin-bottom: 12px;
}
.prep-card {
  border: 1px dashed #d9ecff;
  background: #f7fbff;
  padding: 16px;
  border-radius: 6px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 0 16px;
}
.feedback-form {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 16px;
  background: #fafafa;
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
.mono {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  word-break: break-all;
}
.wrap {
  white-space: pre-wrap;
  word-break: break-word;
}
.sub {
  color: #909399;
  font-size: 12px;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.iq-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.iq-set-card {
  background: #fcfcfd;
}
.iq-item {
  padding: 10px 0;
  border-top: 1px solid #f0f2f5;
}
.iq-item:first-of-type {
  border-top: none;
  padding-top: 0;
}
.iq-q {
  margin-bottom: 4px;
  color: #303133;
}
.iq-meta {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}
.iq-points {
  margin: 4px 0 0 18px;
  padding: 0;
}
@media (max-width: 640px) {
  .card-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
}
</style>
