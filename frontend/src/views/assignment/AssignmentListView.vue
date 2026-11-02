<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <h1>{{ userStore.isHeadhunter ? '我的任务' : '需求承接' }}</h1>
        <p class="page-sub">查看授权承接、需求版本与结束原因；授权失效会单独提示，不与承接状态合并。</p>
      </div>
      <div class="page-actions">
        <el-button plain @click="load">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
    <el-table :data="rows" v-loading="loading">
      <el-table-column label="需求名称" min-width="180">
        <template #default="{ row }">
          <strong>{{ row.job_title || row.job_snapshot?.title || `需求 #${row.job_id}` }}</strong>
          <div class="sub">{{ row.client_company_name || '客户企业待核验' }}</div>
        </template>
      </el-table-column>
      <el-table-column label="承接主体" min-width="160">
        <template #default="{ row }">{{ row.provider_name || '承接主体待核验' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="150">
        <template #default="{ row }">
          <el-tag :type="asgStatusTag(row.status)">{{ asgStatusText(row.status) }}</el-tag>
          <el-tag
            v-if="row.status === 'active' && !row.has_current_authorization"
            class="ml"
            type="warning"
            size="small"
          >
            授权失效
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="轮次" width="70">
        <template #default="{ row }">{{ row.round_no }}</template>
      </el-table-column>
      <el-table-column label="版本" width="80">
        <template #default="{ row }">v{{ row.job_version }}</template>
      </el-table-column>
      <el-table-column label="邀请时间" min-width="150">
        <template #default="{ row }">{{ fmt(row.invited_at) }}</template>
      </el-table-column>
      <el-table-column label="结束原因" min-width="140">
        <template #default="{ row }">{{ row.end_reason ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row)">详情</el-button>
          <template v-if="canOperateProvider(row) && row.status === 'invited'">
            <el-button link type="success" @click="actions.accept(row)">接受</el-button>
            <el-button link type="danger" @click="actions.decline(row)">拒绝</el-button>
          </template>
          <el-button
            v-if="isClientManager && row.status === 'active'"
            link
            type="success"
            @click="actions.complete(row)"
          >
            确认完成
          </el-button>
          <el-button
            v-if="canCancel(row)"
            link
            type="danger"
            @click="actions.cancel(row, isClientManager)"
          >
            {{ isClientManager ? '撤权' : '终止' }}
          </el-button>
          <el-button
            v-if="isAgencyManager && row.provider_kind === 'agency' && row.has_current_authorization"
            link
            type="warning"
            @click="goDetail(row, 'owner')"
          >
            分配负责人
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && rows.length === 0" description="暂无需求承接记录" />
  </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { listAssignments } from '@/api/assignment'
import { getAgencyContext } from '@/api/agency'
import { useAssignmentActions } from '@/composables/assignmentActions'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const rows = ref([])
const agencyCtx = ref({ agency: null, membership: null, invitations: [] })
const contextLoaded = ref(false)

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
function fmt(t) {
  return t ? String(t).replace('T', ' ').slice(0, 19) : '-'
}

async function load() {
  loading.value = true
  try {
    rows.value = await listAssignments()
  } catch (e) {
    ElMessage.error(e)
    rows.value = []
  } finally {
    loading.value = false
  }
}

function goDetail(row, action) {
  router.push({
    name: 'AssignmentDetail',
    params: { id: row.id },
    query: action ? { action } : {},
  })
}

const actions = useAssignmentActions(load)

onMounted(async () => {
  await load()
  if (userStore.isHeadhunter) {
    try {
      agencyCtx.value = await getAgencyContext()
      contextLoaded.value = true
    } catch (e) {
      ElMessage.error(e)
    }
  }
})
</script>

<style scoped>
.card-head { display: flex; align-items: center; justify-content: space-between; }
.card-title { margin: 0; font-size: 16px; color: #303133; }
.sub { margin-top: 4px; color: #687587; font-size: 12px; }
.ml { margin-left: 6px; }
</style>
