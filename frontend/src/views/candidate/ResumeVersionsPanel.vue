<template>
  <div class="resume-panel">
    <div v-if="canMutate" class="panel-bar">
      <el-upload
        :disabled="uploading"
        :show-file-list="false"
        accept=".pdf,.docx,.txt"
        :before-upload="beforeUpload"
        :http-request="doUpload"
      >
        <el-button type="primary" :loading="uploading">上传新版本</el-button>
      </el-upload>
      <span class="hint">支持 PDF / DOCX / UTF-8 TXT，单文件 ≤ 10 MiB</span>
    </div>
    <el-button class="mb" plain :loading="loading" @click="load">刷新版本</el-button>

    <el-table :data="rows.slice((page - 1) * 20, page * 20)" v-loading="loading" border stripe>
      <el-table-column label="版本" width="80">
        <template #default="{ row }">
          v{{ row.version }}
          <el-tag v-if="row.is_primary" type="success" size="small" class="ml">主</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="原始文件名" min-width="180">
        <template #default="{ row }">
          <span class="file-name">{{ row.original_name ?? '未知' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="类型/大小" width="130">
        <template #default="{ row }">
          {{ (row.file_type ?? '未知').toUpperCase() }} / {{ formatSize(row.file_size) }}
        </template>
      </el-table-column>
      <el-table-column label="解析状态" width="110">
        <template #default="{ row }">
          <el-tag :type="parseTag(row.parse_status)" size="small">
            {{ parseText(row.parse_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="技能抽取" width="110">
        <template #default="{ row }">
          <el-tag :type="parseTag(row.extraction_status)" size="small">
            {{ extractionText(row.extraction_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="上传时间" width="150">
        <template #default="{ row }">{{ fmt(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openText(row)">正文/解析</el-button>
          <el-button v-if="canMutate" link type="warning" @click="openSkills(row)">技能核对</el-button>
          <el-button
            v-if="canMutate && !row.is_primary"
            link
            type="success"
            :loading="row._setting"
            :disabled="setting"
            @click="setPrimary(row)"
          >
            设为主
          </el-button>
          <el-button link :loading="row._downloading" @click="download(row)">下载</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-if="rows.length > 20" v-model:current-page="page" :page-size="20"
      :total="rows.length" layout="prev, pager, next" />

    <el-empty v-if="!loading && rows.length === 0" description="暂无简历版本" />

    <!-- 正文/解析弹窗 -->
    <el-dialog
      v-model="textVisible"
      :title="`正文 · v${detail?.version ?? ''}`"
      width="min(720px, calc(100vw - 32px))"
      top="6vh"
    >
      <div v-loading="textLoading" class="text-body">
        <el-alert
          v-if="detail && detail.parse_status === 'failed'"
          :title="`解析失败：${detail.parse_error || '未知原因'}`"
          type="error"
          :closable="false"
          show-icon
          class="mb"
        />
        <template v-if="detail && detail.parse_status === 'success'">
          <pre class="parsed-text">{{ detail.parsed_text }}</pre>
          <div class="frozen-tip">正文解析成功后已冻结，修正正文需上传新版本。</div>
        </template>
        <el-empty
          v-else-if="detail && detail.parse_status !== 'failed'"
          description="尚未解析正文"
        />
      </div>
      <template #footer>
        <el-button @click="textVisible = false">关闭</el-button>
        <el-button
          v-if="canMutate && detail && detail.parse_status !== 'success'"
          type="primary"
          :loading="textLoading"
          @click="doParse(detail)"
        >
          {{ detail.parse_status === 'failed' ? '重试解析' : '解析正文' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import {
  uploadResume,
  allResumeVersions,
  getResume,
  parseResume,
  setPrimaryResume,
  downloadResume,
} from '@/api/resume'

const props = defineProps({
  candidate: { type: Object, required: true },
  canMutate: { type: Boolean, default: false },
})
const emit = defineEmits(['open-skills', 'access-lost'])

const loading = ref(false)
const uploading = ref(false)
const rows = ref([])
const page = ref(1)
const setting = ref(false)
let active = true
let loadSequence = 0
let textSequence = 0

const textVisible = ref(false)
const textLoading = ref(false)
const detail = ref(null)

function reportError(error) {
  if (!active) return
  ElMessage.error(error.message || error)
  if ([401, 403, 404].includes(error.status)) {
    rows.value = []
    detail.value = null
    textVisible.value = false
    emit('access-lost')
  }
}

function parseText(s) {
  return { pending: '待解析', success: '已解析', failed: '解析失败' }[s] || s || '-'
}
function extractionText(s) {
  return { pending: '待抽取', success: '已抽取', failed: '抽取失败' }[s] || s || '-'
}
function parseTag(s) {
  return { pending: 'info', success: 'success', failed: 'danger' }[s] || 'info'
}
function fmt(t) {
  return t ? String(t).replace('T', ' ').slice(0, 19) : '未知'
}
function formatSize(n) {
  if (n == null) return '未知'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

async function load() {
  const sequence = ++loadSequence
  loading.value = true
  try {
    const data = await allResumeVersions(props.candidate.id)
    if (!active || sequence !== loadSequence) return
    rows.value = data.map((r) => ({ ...r, _setting: false, _downloading: false }))
    page.value = Math.min(page.value, Math.max(1, Math.ceil(rows.value.length / 20)))
  } catch (e) {
    if (!active || sequence !== loadSequence) return
    reportError(e)
    rows.value = []
  } finally {
    if (active && sequence === loadSequence) loading.value = false
  }
}

function beforeUpload(file) {
  const name = (file.name || '').toLowerCase()
  const okType = /\.(pdf|docx|txt)$/.test(name)
  if (!okType) {
    ElMessage.warning('仅支持 PDF、DOCX、UTF-8 TXT 文件')
    return false
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('单文件不能超过 10 MiB')
    return false
  }
  return true
}

async function doUpload({ file }) {
  if (uploading.value) return
  uploading.value = true
  try {
    await uploadResume(props.candidate.id, file)
    if (!active) return
    ElMessage.success('上传成功')
    await load()
  } catch (e) {
    reportError(e)
  } finally {
    uploading.value = false
  }
}

async function openText(row) {
  const sequence = ++textSequence
  textVisible.value = true
  textLoading.value = true
  detail.value = null
  try {
    const data = await getResume(row.id)
    if (active && sequence === textSequence) detail.value = data
  } catch (e) {
    if (sequence === textSequence) reportError(e)
  } finally {
    if (active && sequence === textSequence) textLoading.value = false
  }
}

async function doParse(row) {
  if (textLoading.value) return
  textLoading.value = true
  const sequence = ++textSequence
  try {
    const d = await parseResume(row.id)
    if (!active || sequence !== textSequence) return
    detail.value = d
    ElMessage.success('解析完成')
    await load()
  } catch (e) {
    if (!active || sequence !== textSequence) return
    reportError(e)
    if (![401, 403, 404].includes(e.status)) {
      const data = await getResume(row.id).catch(reportError)
      if (active && sequence === textSequence && data) detail.value = data
      await load()
    }
  } finally {
    textLoading.value = false
  }
}

async function setPrimary(row) {
  if (setting.value) return
  setting.value = true
  const currentPrimary = rows.value.find((r) => r.is_primary)
  row._setting = true
  try {
    await setPrimaryResume(row.id, currentPrimary ? currentPrimary.id : null)
    ElMessage.success('已切换主简历')
    await load()
  } catch (e) {
    reportError(e)
    await load()
  } finally {
    row._setting = false
    setting.value = false
  }
}

async function download(row) {
  if (row._downloading) return
  row._downloading = true
  try {
    await downloadResume(row.id, row.original_name || undefined)
  } catch (e) {
    reportError(e)
  } finally {
    row._downloading = false
  }
}

function openSkills(row) {
  emit('open-skills', row.id)
}

onMounted(load)
defineExpose({ refresh: load })
onBeforeUnmount(() => { active = false; ++loadSequence; ++textSequence })
</script>

<style scoped>
.panel-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.ml {
  margin-left: 6px;
}
.file-name {
  word-break: break-all;
}
.text-body {
  min-height: 160px;
}
.mb {
  margin-bottom: 12px;
}
.parsed-text {
  margin: 0;
  max-height: 46vh;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.7;
}
.frozen-tip {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}
</style>
