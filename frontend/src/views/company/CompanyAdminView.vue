<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <h1>企业核验</h1>
        <p class="page-sub">
          只读查看客户企业及招聘成员归属。成员数包含禁用账号；启用主管为 0 时提示账号缺口，不代表企业未认证。
        </p>
      </div>
      <span class="readonly-tag">只读查看</span>
    </div>

    <el-card shadow="never">
      <div class="filter-bar">
        <el-input
          v-model="listQuery.keyword"
          class="filter-keyword"
          placeholder="搜索企业名称"
          clearable
          maxlength="100"
          aria-label="搜索企业名称"
          @keyup.enter="search"
          @clear="search"
        />
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </div>

      <el-alert
        v-if="listError"
        class="mb"
        type="error"
        :closable="false"
        show-icon
        :title="listError"
      />

      <div class="table-wrap">
        <el-table :data="rows" v-loading="loading" row-key="id">
          <el-table-column label="客户企业" min-width="200">
            <template #default="{ row }">
              <span class="cell-main">{{ row.name }}</span>
              <span class="cell-sub">企业 #{{ row.id }} · 创建于 {{ formatDate(row.created_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="招聘成员" width="110">
            <template #default="{ row }">{{ row.member_count }} 人</template>
          </el-table-column>
          <el-table-column label="主管账号" width="110">
            <template #default="{ row }">{{ row.manager_count }} 人</template>
          </el-table-column>
          <el-table-column label="启用主管" min-width="150">
            <template #default="{ row }">
              <el-tag
                v-if="row.enabled_manager_count === 0"
                type="warning"
                size="small"
              >
                缺少启用主管
              </el-tag>
              <el-tag v-else type="success" size="small">
                {{ row.enabled_manager_count }} 人
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="查看" width="110" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openMembers(row)">查看成员</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty
              v-if="!loading && !listError"
              description="没有符合条件的企业"
            />
          </template>
        </el-table>
      </div>

      <div class="list-summary">
        共 {{ total }} 家企业 · 成员与主管数量仅统计企业招聘方
      </div>

      <el-pagination
        v-if="total > listQuery.size"
        class="pager"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="listQuery.size"
        v-model:current-page="listQuery.page"
        @current-change="loadCompanies"
      />
    </el-card>

    <el-drawer
      v-model="drawerVisible"
      size="min(580px, 100vw)"
      :title="drawerTitle"
      @close="handleDrawerClosed"
    >
      <div v-if="activeCompany" class="drawer-body">
        <div class="drawer-head">
          <h3>{{ activeCompany.name }}</h3>
          <p class="muted">企业 #{{ activeCompany.id }}</p>
        </div>

        <el-alert
          v-if="summaryError"
          class="mb"
          type="error"
          :closable="false"
          show-icon
          :title="summaryError"
        />

        <div v-if="summary" class="summary-grid" aria-label="企业摘要">
          <div class="summary-cell">
            <strong>{{ summary.member_count }}</strong>
            <span>招聘成员</span>
          </div>
          <div class="summary-cell">
            <strong>{{ summary.manager_count }}</strong>
            <span>主管账号</span>
          </div>
          <div class="summary-cell" :class="{ alert: summary.enabled_manager_count === 0 }">
            <strong>{{ summary.enabled_manager_count }}</strong>
            <span>启用主管</span>
          </div>
        </div>

        <el-alert
          v-if="summary && summary.enabled_manager_count === 0"
          class="mb"
          type="warning"
          :closable="false"
          show-icon
          title="该企业缺少启用主管，成员邀请与需求授权等主管操作暂无法处理；已启用员工仍可按权限反馈。"
        />

        <div class="filter-bar member-filter">
          <el-input
            v-model="memberQuery.keyword"
            placeholder="搜索用户名或姓名"
            clearable
            maxlength="100"
            aria-label="搜索企业成员"
            @keyup.enter="searchMembers"
            @clear="searchMembers"
          />
          <el-select
            v-model="memberQuery.company_role"
            placeholder="全部角色"
            clearable
            aria-label="筛选企业角色"
            @change="searchMembers"
          >
            <el-option label="主管" value="manager" />
            <el-option label="普通员工" value="staff" />
          </el-select>
          <el-select
            v-model="memberQuery.enabled"
            placeholder="全部状态"
            clearable
            aria-label="筛选账号状态"
            @change="searchMembers"
          >
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </div>

        <el-alert
          v-if="memberError"
          class="mb"
          type="error"
          :closable="false"
          show-icon
          :title="memberError"
        />

        <div class="table-wrap">
          <el-table :data="members" v-loading="membersLoading" row-key="id">
            <el-table-column label="成员" min-width="150">
              <template #default="{ row }">
                <span class="cell-main">{{ row.real_name || row.username }}</span>
                <span class="cell-sub">{{ row.username }}</span>
              </template>
            </el-table-column>
            <el-table-column label="企业角色" width="105">
              <template #default="{ row }">
                {{ row.company_role === 'manager' ? '主管' : '普通员工' }}
              </template>
            </el-table-column>
            <el-table-column label="账号状态" width="95">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                  {{ row.enabled ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" min-width="130">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <template #empty>
              <el-empty
                v-if="!membersLoading && !memberError"
                description="没有符合条件的成员"
              />
            </template>
          </el-table>
        </div>

        <div class="list-summary">共 {{ memberTotal }} 名招聘成员</div>

        <el-pagination
          v-if="memberTotal > memberQuery.size"
          class="pager"
          background
          layout="total, prev, pager, next"
          :total="memberTotal"
          :page-size="memberQuery.size"
          v-model:current-page="memberQuery.page"
          @current-change="loadMembers"
        />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAdminCompany,
  listAdminCompanies,
  listAdminCompanyMembers,
} from '@/api/company'

const listQuery = reactive({ page: 1, size: 20, keyword: '' })
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const listError = ref('')
let listSeq = 0

const drawerVisible = ref(false)
const activeCompany = ref(null)
const summary = ref(null)
const summaryLoading = ref(false)
const summaryError = ref('')
const members = ref([])
const memberTotal = ref(0)
const membersLoading = ref(false)
const memberError = ref('')
const memberQuery = reactive({ page: 1, size: 20, keyword: '', company_role: '', enabled: '' })
let summarySeq = 0
let memberSeq = 0

const drawerTitle = computed(() =>
  activeCompany.value ? `企业成员 · ${activeCompany.value.name}` : '企业成员',
)

function formatDate(value) {
  return value ? String(value).replace('T', ' ').slice(0, 10) : '-'
}

function buildListParams() {
  const params = { page: listQuery.page, size: listQuery.size }
  const keyword = listQuery.keyword.trim()
  if (keyword) params.keyword = keyword
  return params
}

async function loadCompanies() {
  const seq = ++listSeq
  loading.value = true
  listError.value = ''
  try {
    const data = await listAdminCompanies(buildListParams())
    if (seq !== listSeq) return
    rows.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    if (seq !== listSeq) return
    if ([403, 404].includes(error.status)) closeInaccessibleCompany(error)
    rows.value = []
    total.value = 0
    listError.value = error.message || '企业列表加载失败'
    if (![403, 404].includes(error.status)) {
      ElMessage.error(listError.value)
    }
  } finally {
    if (seq === listSeq) loading.value = false
  }
}

function search() {
  listQuery.page = 1
  loadCompanies()
}

function resetSearch() {
  listQuery.keyword = ''
  listQuery.page = 1
  loadCompanies()
}

function resetMemberQuery() {
  memberQuery.page = 1
  memberQuery.keyword = ''
  memberQuery.company_role = ''
  memberQuery.enabled = ''
}

async function loadSummary(companyId, seq) {
  summaryLoading.value = true
  summaryError.value = ''
  try {
    const data = await getAdminCompany(companyId)
    if (seq !== summarySeq || activeCompany.value?.id !== companyId) return
    summary.value = data
  } catch (error) {
    if (seq !== summarySeq || activeCompany.value?.id !== companyId) return
    if ([403, 404].includes(error.status)) {
      closeInaccessibleCompany(error)
      return
    }
    summary.value = null
    summaryError.value = error.message || '企业摘要加载失败'
    if (![403, 404].includes(error.status)) {
      ElMessage.error(summaryError.value)
    }
  } finally {
    if (seq === summarySeq) summaryLoading.value = false
  }
}

function buildMemberParams() {
  const params = { page: memberQuery.page, size: memberQuery.size }
  const keyword = memberQuery.keyword.trim()
  if (keyword) params.keyword = keyword
  if (memberQuery.company_role) params.company_role = memberQuery.company_role
  if (memberQuery.enabled !== '' && memberQuery.enabled != null) {
    params.enabled = memberQuery.enabled
  }
  return params
}

async function loadMembers() {
  const companyId = activeCompany.value?.id
  if (!companyId) return
  const seq = ++memberSeq
  membersLoading.value = true
  memberError.value = ''
  try {
    const data = await listAdminCompanyMembers(companyId, buildMemberParams())
    if (seq !== memberSeq || activeCompany.value?.id !== companyId) return
    members.value = data.items || []
    memberTotal.value = data.total || 0
  } catch (error) {
    if (seq !== memberSeq || activeCompany.value?.id !== companyId) return
    if ([403, 404].includes(error.status)) {
      closeInaccessibleCompany(error)
      return
    }
    members.value = []
    memberTotal.value = 0
    memberError.value = error.message || '企业成员加载失败'
    if (![403, 404].includes(error.status)) {
      ElMessage.error(memberError.value)
    }
  } finally {
    if (seq === memberSeq) membersLoading.value = false
  }
}

function searchMembers() {
  memberQuery.page = 1
  loadMembers()
}

async function openMembers(row) {
  const seq = ++summarySeq
  ++memberSeq
  activeCompany.value = row
  drawerVisible.value = true
  summary.value = null
  summaryLoading.value = false
  summaryError.value = ''
  members.value = []
  memberTotal.value = 0
  membersLoading.value = false
  memberError.value = ''
  resetMemberQuery()
  await Promise.all([loadSummary(row.id, seq), loadMembers()])
}

function handleDrawerClosed() {
  ++summarySeq
  ++memberSeq
  activeCompany.value = null
  summary.value = null
  summaryError.value = ''
  members.value = []
  memberTotal.value = 0
  memberError.value = ''
  summaryLoading.value = false
  membersLoading.value = false
}

function closeInaccessibleCompany(error) {
  drawerVisible.value = false
  handleDrawerClosed()
  ElMessage.error(error.message || '企业不存在或无权访问')
}

onMounted(loadCompanies)
</script>

<style scoped>
.readonly-tag {
  flex: none;
  padding: 5px 10px;
  border: 1px solid #dce5ef;
  border-radius: 4px;
  background: #edf2f8;
  color: #506780;
  font-size: 12px;
}

.filter-keyword {
  width: min(320px, 100%);
}

.mb {
  margin-bottom: 14px;
}

.table-wrap {
  width: 100%;
  overflow-x: auto;
}

.cell-main {
  display: block;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.cell-sub {
  display: block;
  margin-top: 2px;
  color: var(--app-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.list-summary {
  margin-top: 12px;
  color: var(--app-muted);
  font-size: 12px;
}

.drawer-body {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.drawer-head h3 {
  margin: 0;
  font-size: 20px;
  overflow-wrap: anywhere;
}

.drawer-head p {
  margin: 2px 0 16px;
  font-size: 12px;
}

.summary-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 28px;
  margin-bottom: 16px;
  padding: 16px 18px;
  background: #f2f6fa;
  border-radius: 8px;
}

.summary-cell strong {
  display: block;
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
}

.summary-cell span {
  color: var(--app-muted);
  font-size: 12px;
}

.summary-cell.alert strong {
  color: var(--app-warning);
}

.member-filter {
  padding-top: 4px;
}

.member-filter .el-input {
  width: min(220px, 100%);
}

.member-filter .el-select {
  width: 130px;
}

@media (max-width: 800px) {
  .filter-keyword,
  .member-filter .el-input,
  .member-filter .el-select {
    width: 100%;
  }

  .summary-grid {
    gap: 18px;
    padding: 14px;
  }

  .summary-cell {
    min-width: 84px;
  }
}
</style>
