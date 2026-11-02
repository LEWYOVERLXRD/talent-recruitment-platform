<template>
  <div class="skill-panel">
    <div class="panel-bar">
      <el-select
        v-model="selectedResumeId"
        placeholder="选择简历版本"
        style="width: min(320px, 100%)"
        :disabled="extracting || saving"
        filterable
        @change="onSelectResume"
      >
        <el-option
          v-for="r in resumeVersions"
          :key="r.id"
          :label="`v${r.version} · ${r.original_name || '未知'}`"
          :value="r.id"
        />
      </el-select>
      <el-button plain :disabled="extracting || saving" @click="refresh">刷新</el-button>
      <el-button
        v-if="canMutate && skills && skills.skill_revision != null"
        type="primary"
        plain
        :loading="extracting"
        :disabled="!canChange"
        @click="doExtract"
      >
        重新抽取技能
      </el-button>
      <el-button v-if="canMutate" type="primary" :disabled="!canChange" @click="openAdd">新增技能</el-button>
    </div>
    <el-alert v-if="selectedResume && selectedResume.parse_status !== 'success'" class="mb"
      title="请先在简历版本中成功解析正文，再抽取或核对技能。" type="info" :closable="false" />

    <template v-if="skills">
      <div class="meta-row">
        <span>技能修订号：v{{ skills.skill_revision }}</span>
        <el-tag :type="statusTag(skills.extraction_status)" size="small">
          抽取状态：{{ statusText(skills.extraction_status) }}
        </el-tag>
      </div>
      <el-alert
        v-if="skills.extraction_status === 'failed'"
        :title="`技能抽取失败：${skills.extraction_error || '未知原因'}（不影响已有人工技能）`"
        type="warning"
        :closable="false"
        show-icon
        class="mb"
      />

      <el-table :data="skills.items" v-loading="skillsLoading" border stripe>
        <el-table-column label="技能名" min-width="140">
          <template #default="{ row }">{{ row.name }}</template>
        </el-table-column>
        <el-table-column label="类别" width="120">
          <template #default="{ row }">{{ row.category ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="原文证据" min-width="220">
          <template #default="{ row }">
            <span class="evidence">{{ row.evidence }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="reviewTag(row.review_status)" size="small">
              {{ reviewText(row.review_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源模型" width="150">
          <template #default="{ row }">{{ row.model_used ?? '人工' }}</template>
        </el-table-column>
        <el-table-column label="抽取/核对" min-width="190">
          <template #default="{ row }">
            <div>抽取：{{ row.extracted_at ?? '—' }}</div>
            <div>核对：{{ row.reviewed_by != null ? `#${row.reviewed_by}` : '—' }} / {{ row.reviewed_at ?? '—' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="canMutate && row.review_status !== 'confirmed'"
              link
              type="success"
              :disabled="!canChange"
              @click="openReview(row, 'confirmed')"
            >
              确认
            </el-button>
            <el-button
              v-if="canMutate && row.review_status !== 'rejected'"
              link
              type="danger"
              :disabled="!canChange"
              @click="openReview(row, 'rejected')"
            >
              拒绝
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="!skillsLoading && skills.items.length === 0"
        description="暂无技能记录（空结果也可能是成功的抽取）"
      />
    </template>
    <el-empty v-else-if="!skillsLoading" description="请选择简历版本查看技能" />

    <!-- 新增技能弹窗 -->
    <el-dialog v-model="addVisible" title="人工新增技能" width="min(560px, calc(100vw - 32px))">
      <el-form :model="addForm" label-width="90px">
        <el-form-item label="技能名" required>
          <el-input v-model="addForm.name" maxlength="100" />
        </el-form-item>
        <el-form-item label="类别">
          <el-input v-model="addForm.category" maxlength="50" placeholder="可选" />
        </el-form-item>
        <el-form-item label="原文证据" required>
          <el-input
            v-model="addForm.evidence"
            type="textarea"
            :rows="3"
            maxlength="5000"
            placeholder="必须来自当前版本正文的连续原文，后端会校验"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitAdd">保存</el-button>
      </template>
    </el-dialog>

    <!-- 核对技能弹窗 -->
    <el-dialog
      v-model="reviewVisible"
      :title="`${reviewForm.target === 'confirmed' ? '确认' : '拒绝'}技能：${reviewForm.name}`"
      width="min(560px, calc(100vw - 32px))"
    >
      <el-form label-width="90px">
        <el-form-item label="修正证据">
          <el-input
            v-model="reviewForm.evidence"
            type="textarea"
            :rows="3"
            maxlength="5000"
            placeholder="可选：修正后的原文证据"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitReview">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  allResumeVersions,
  getResumeSkills,
  extractSkills,
  addSkill,
  reviewSkill,
} from '@/api/resume'

const props = defineProps({
  candidate: { type: Object, required: true },
  canMutate: { type: Boolean, default: false },
  initialResumeId: { type: Number, default: null },
})
const emit = defineEmits(['access-lost'])
let active = true
let sequence = 0

const resumeVersions = ref([])
const selectedResumeId = ref(null)
const skills = ref(null)
const skillsLoading = ref(false)
const extracting = ref(false)
const saving = ref(false)
const selectedResume = computed(() => resumeVersions.value.find(r => r.id === selectedResumeId.value))
const canChange = computed(() => props.canMutate && skills.value && !skillsLoading.value &&
  !saving.value && !extracting.value && selectedResume.value?.parse_status === 'success')

const addVisible = ref(false)
const addForm = reactive({ name: '', category: '', evidence: '' })
const reviewVisible = ref(false)
const reviewForm = reactive({ relationId: null, name: '', target: 'confirmed', evidence: '' })

function statusText(s) {
  return { pending: '待抽取', success: '已抽取', failed: '抽取失败' }[s] || s || '-'
}
function statusTag(s) {
  return { pending: 'info', success: 'success', failed: 'danger' }[s] || 'info'
}
function reviewText(s) {
  return { unreviewed: '待核对', confirmed: '已确认', rejected: '已拒绝' }[s] || s || '-'
}
function reviewTag(s) {
  return { unreviewed: 'warning', confirmed: 'success', rejected: 'danger' }[s] || 'info'
}

function reportError(error) {
  if (!active) return
  ElMessage.error(error.message || error)
  if ([401, 403, 404].includes(error.status)) {
    skills.value = null
    resumeVersions.value = []
    addVisible.value = reviewVisible.value = false
    emit('access-lost')
  }
}

async function loadVersions() {
  try {
    const data = await allResumeVersions(props.candidate.id)
    if (active) resumeVersions.value = data
  } catch (e) {
    reportError(e)
    resumeVersions.value = []
  }
}

async function loadSkills(id) {
  const request = ++sequence
  skills.value = null
  if (!id) {
    skills.value = null
    return
  }
  skillsLoading.value = true
  try {
    const data = await getResumeSkills(id)
    if (active && request === sequence) skills.value = data
  } catch (e) {
    if (request === sequence) reportError(e)
  } finally {
    if (active && request === sequence) skillsLoading.value = false
  }
}

async function onSelectResume(id) {
  addVisible.value = reviewVisible.value = false
  await loadSkills(id)
}

async function refresh() {
  if (saving.value || extracting.value) return
  await loadVersions()
  if (!active) return
  if (!resumeVersions.value.some(r => r.id === selectedResumeId.value)) {
    selectedResumeId.value = resumeVersions.value.find(r => r.is_primary)?.id || resumeVersions.value[0]?.id || null
  }
  await loadSkills(selectedResumeId.value)
}

async function doExtract() {
  if (!canChange.value) return
  const id = selectedResumeId.value
  extracting.value = true
  try {
    const data = await extractSkills(id, skills.value.skill_revision)
    if (!active || selectedResumeId.value !== id) return
    skills.value = data
    ElMessage.success('抽取完成')
    await loadVersions()
  } catch (e) {
    reportError(e)
    if (active && ![401, 403, 404].includes(e.status)) await loadSkills(id)
  } finally {
    extracting.value = false
  }
}

function openAdd() {
  if (!canChange.value) return
  addForm.name = ''
  addForm.category = ''
  addForm.evidence = ''
  addVisible.value = true
}

async function submitAdd() {
  if (!canChange.value) return
  if (!addForm.name.trim()) {
    ElMessage.warning('请填写技能名')
    return
  }
  if (!addForm.evidence.trim()) {
    ElMessage.warning('请填写原文证据')
    return
  }
  saving.value = true
  try {
    const data = await addSkill(selectedResumeId.value, {
      expected_skill_revision: skills.value.skill_revision,
      name: addForm.name.trim(),
      category: addForm.category.trim() || null,
      evidence: addForm.evidence,
    })
    if (!active) return
    skills.value = data
    ElMessage.success('已新增')
    addVisible.value = false
    await loadVersions()
  } catch (e) {
    reportError(e)
    addVisible.value = false
    if (active && ![401, 403, 404].includes(e.status)) await loadSkills(selectedResumeId.value)
  } finally {
    saving.value = false
  }
}

function openReview(row, target) {
  if (!canChange.value) return
  reviewForm.relationId = row.id
  reviewForm.name = row.name
  reviewForm.target = target
  reviewForm.evidence = ''
  reviewVisible.value = true
}

async function submitReview() {
  if (!canChange.value) return
  saving.value = true
  try {
    const data = await reviewSkill(selectedResumeId.value, reviewForm.relationId, {
      expected_skill_revision: skills.value.skill_revision,
      review_status: reviewForm.target,
      evidence: reviewForm.evidence.trim() || null,
    })
    if (!active) return
    skills.value = data
    ElMessage.success('已核对')
    reviewVisible.value = false
    await loadVersions()
  } catch (e) {
    reportError(e)
    reviewVisible.value = false
    if (active && ![401, 403, 404].includes(e.status)) await loadSkills(selectedResumeId.value)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  selectedResumeId.value = props.initialResumeId
  return refresh()
})
defineExpose({ refresh })
onBeforeUnmount(() => { active = false; ++sequence })

watch(
  () => props.initialResumeId,
  async (id) => {
    if (id && id !== selectedResumeId.value) {
      selectedResumeId.value = id
      await loadSkills(id)
    }
  },
)
</script>

<style scoped>
.panel-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.meta-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  color: #606266;
  flex-wrap: wrap;
  font-size: 13px;
}
.mb {
  margin-bottom: 12px;
}
.evidence {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
