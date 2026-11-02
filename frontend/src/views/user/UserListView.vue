<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <h1>用户管理</h1>
        <p class="page-sub">查看平台账号角色、企业归属与启用状态；禁用后该账号当前登录凭证将失效。</p>
      </div>
      <div class="page-actions">
        <span class="summary">共 {{ total }} 个账号</span>
      </div>
    </div>

    <el-card shadow="never">
    <div class="filter-bar">
      <el-input
        v-model="query.keyword"
        placeholder="搜索用户名或姓名"
        clearable
        class="keyword"
        @keyup.enter="search"
        @clear="search"
      />
      <el-select v-model="query.role" clearable placeholder="全部角色" class="filter-select">
        <el-option v-for="role in roles" :key="role.value" :label="role.label" :value="role.value" />
      </el-select>
      <el-select v-model="query.enabled" clearable placeholder="全部状态" class="filter-select">
        <el-option label="启用" value="true" />
        <el-option label="禁用" value="false" />
      </el-select>
      <el-button type="primary" @click="search">查询</el-button>
    </div>

    <el-table :data="rows" v-loading="loading">
      <el-table-column prop="username" label="用户名" min-width="140" />
      <el-table-column prop="real_name" label="姓名" min-width="110">
        <template #default="{ row }">{{ row.real_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="平台角色" min-width="120">
        <template #default="{ row }">{{ roleLabel(row.role) }}</template>
      </el-table-column>
      <el-table-column label="所属企业" min-width="160">
        <template #default="{ row }">{{ row.company_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="企业角色" min-width="110">
        <template #default="{ row }">{{ companyRoleLabel(row.company_role) }}</template>
      </el-table-column>
      <el-table-column label="账号状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.id !== userStore.user?.id"
            link
            :type="row.enabled ? 'danger' : 'primary'"
            :disabled="busyId === row.id"
            @click="toggleStatus(row)"
          >
            {{ row.enabled ? '禁用' : '启用' }}
          </el-button>
          <span v-else class="self-label">当前账号</span>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="没有符合条件的账号" />
      </template>
    </el-table>

    <el-pagination
      v-if="total > query.size"
      class="pager"
      background
      layout="total, prev, pager, next"
      :total="total"
      :page-size="query.size"
      v-model:current-page="query.page"
      @current-change="load"
    />
  </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { listUsers, setUserStatus } from '@/api/users'

const userStore = useUserStore()
const roles = [
  { value: 'admin', label: '平台管理员' },
  { value: 'recruiter', label: '企业招聘方' },
  { value: 'headhunter', label: '猎头' },
  { value: 'jobseeker', label: '求职者' },
]
const query = reactive({ page: 1, size: 20, keyword: '', role: '', enabled: '' })
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const busyId = ref(null)

function roleLabel(role) {
  return roles.find((item) => item.value === role)?.label || role || '-'
}

function companyRoleLabel(role) {
  return ({ manager: '企业主管', staff: '普通员工' })[role] || '-'
}

function search() {
  query.page = 1
  load()
}

async function load() {
  loading.value = true
  try {
    const data = await listUsers({
      page: query.page,
      size: query.size,
      keyword: query.keyword.trim() || undefined,
      role: query.role || undefined,
      enabled: query.enabled || undefined,
    })
    rows.value = data.items
    total.value = data.total
  } catch (error) {
    ElMessage.error(error)
  } finally {
    loading.value = false
  }
}

async function toggleStatus(row) {
  const enabled = !row.enabled
  const action = enabled ? '启用' : '禁用'
  try {
    await ElMessageBox.confirm(
      enabled ? `确认启用账号“${row.username}”吗？` : `禁用后该账号当前登录凭证将失效。确认禁用“${row.username}”吗？`,
      `${action}账号`,
      { type: enabled ? 'info' : 'warning', confirmButtonText: action, cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  busyId.value = row.id
  try {
    await setUserStatus(row.id, enabled)
    ElMessage.success(`账号已${action}`)
    await load()
  } catch (error) {
    ElMessage.error(error)
  } finally {
    busyId.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.card-title {
  margin: 0;
  font-size: 16px;
}

.summary,
.self-label {
  color: #909399;
  font-size: 13px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.keyword {
  width: min(260px, 100%);
}

.filter-select {
  width: 150px;
}

.pager {
  justify-content: flex-end;
  margin-top: 16px;
}

@media (max-width: 640px) {
  .keyword,
  .filter-select {
    width: 100%;
  }

  .filter-bar :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }
}
</style>
