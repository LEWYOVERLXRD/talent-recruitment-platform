<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <h1>机构管理</h1>
        <p class="page-sub">管理猎头机构的启用状态与首任主管；机构成员协作由机构主管在“我的机构”中处理。</p>
      </div>
      <div class="page-actions">
        <el-button type="primary" @click="openCreate">创建机构</el-button>
      </div>
    </div>

    <el-card shadow="never">
    <el-table :data="rows" v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="机构名称" min-width="180" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status === 'active' ? '运营中' : '已停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'active'"
            link
            type="danger"
            @click="toggleStatus(row, 'disabled')"
          >
            停用
          </el-button>
          <el-button v-else link type="success" @click="toggleStatus(row, 'active')">
            恢复
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      background
      layout="total, prev, pager, next"
      :total="total"
      :page-size="query.size"
      v-model:current-page="query.page"
      @current-change="load"
    />

    <!-- 创建机构弹窗 -->
    <el-dialog v-model="dialogVisible" title="创建机构" width="min(440px, calc(100vw - 32px))">
      <el-form :model="form" label-width="130px">
        <el-form-item label="机构名称" required>
          <el-input v-model="form.name" placeholder="请填写机构名称" />
        </el-form-item>
        <el-form-item label="首任主管用户 ID" required>
          <el-input-number v-model="form.manager_user_id" :min="1" style="width: 100%" />
          <div class="form-tip">填写平台已核验的有效猎头账号 ID</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">创建</el-button>
      </template>
    </el-dialog>
  </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listAgencies, createAgency, setAgencyStatus } from '@/api/agency'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, size: 20 })

const dialogVisible = ref(false)
const saving = ref(false)
const form = reactive({ name: '', manager_user_id: undefined })

async function load() {
  loading.value = true
  try {
    const data = await listAgencies({ page: query.page, size: query.size })
    rows.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error(e)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.name = ''
  form.manager_user_id = undefined
  dialogVisible.value = true
}

async function save() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写机构名称')
    return
  }
  if (!form.manager_user_id) {
    ElMessage.warning('请填写首任主管用户 ID')
    return
  }
  saving.value = true
  try {
    await createAgency({ name: form.name.trim(), manager_user_id: form.manager_user_id })
    ElMessage.success('已创建机构')
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    saving.value = false
  }
}

async function toggleStatus(row, status) {
  const action = status === 'active' ? '恢复' : '停用'
  try {
    await ElMessageBox.confirm(`确定${action}机构「${row.name}」吗？`, action, {
      type: 'warning',
    })
    await setAgencyStatus(row.id, status)
    ElMessage.success(`已${action}`)
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e)
    }
  }
}

onMounted(load)
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
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.form-tip {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}
</style>
