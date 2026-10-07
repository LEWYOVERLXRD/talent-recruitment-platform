<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-head">
        <h3 class="card-title">招聘需求管理</h3>
        <el-button type="primary" @click="openCreate">新建需求</el-button>
      </div>
    </template>

    <div class="filter-bar">
      <el-input
        v-model="query.keyword"
        placeholder="按需求标题检索"
        clearable
        style="width: 240px"
        @keyup.enter="load"
        @clear="load"
      />
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px" @change="load">
        <el-option label="寻访中" value="open" />
        <el-option label="暂停" value="suspended" />
        <el-option label="已关闭" value="closed" />
      </el-select>
      <el-button type="primary" plain @click="load">查询</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="title" label="需求名称" min-width="180" />
      <el-table-column prop="client_company_name" label="客户企业" width="140" />
      <el-table-column prop="department" label="部门" width="120" />
      <el-table-column prop="location" label="地点" width="120" />
      <el-table-column label="薪资(K)" width="120">
        <template #default="{ row }">{{ row.salary_min ?? '-' }} - {{ row.salary_max ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="90" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
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

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑招聘需求' : '新建招聘需求'" width="560px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="需求名称" required>
          <el-input v-model="form.title" placeholder="请填写需求/岗位名称" />
        </el-form-item>
        <el-form-item v-if="isHeadhunter || isAdmin" label="客户企业">
          <el-input v-model="form.client_company_name" placeholder="猎头代客户建档时填写" />
        </el-form-item>
        <el-form-item label="部门"><el-input v-model="form.department" /></el-form-item>
        <el-form-item label="工作地点"><el-input v-model="form.location" /></el-form-item>
        <el-form-item label="最低薪资(K)"><el-input-number v-model="form.salary_min" :min="0" /></el-form-item>
        <el-form-item label="最高薪资(K)"><el-input-number v-model="form.salary_max" :min="0" /></el-form-item>
        <el-form-item label="招聘人数"><el-input-number v-model="form.hiring_count" :min="1" /></el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority" clearable placeholder="请选择">
            <el-option label="高" value="high" />
            <el-option label="中" value="normal" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="客户联系人"><el-input v-model="form.contact_person" /></el-form-item>
        <el-form-item label="联系方式"><el-input v-model="form.contact_info" /></el-form-item>
        <el-form-item label="岗位职责"><el-input type="textarea" v-model="form.description" :rows="3" /></el-form-item>
        <el-form-item label="岗位要求"><el-input type="textarea" v-model="form.requirements" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { listJobs, createJob, updateJob } from '@/api/job'

const userStore = useUserStore()
const isHeadhunter = userStore.role === 'headhunter'
const isAdmin = userStore.role === 'admin'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, size: 20, status: '', keyword: '' })

const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const emptyForm = () => ({
  title: '',
  client_company_name: '',
  department: '',
  location: '',
  salary_min: undefined,
  salary_max: undefined,
  hiring_count: undefined,
  priority: '',
  contact_person: '',
  contact_info: '',
  description: '',
  requirements: '',
})
const form = reactive(emptyForm())

function statusText(s) {
  return { open: '寻访中', suspended: '暂停', closed: '已关闭' }[s] || s
}
function statusTag(s) {
  return { open: 'success', suspended: 'warning', closed: 'info' }[s] || 'info'
}

async function load() {
  loading.value = true
  try {
    const data = await listJobs({
      page: query.page,
      size: query.size,
      status: query.status || undefined,
      keyword: query.keyword || undefined,
    })
    rows.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error(e)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    title: row.title,
    client_company_name: row.client_company_name || '',
    department: row.department || '',
    location: row.location || '',
    salary_min: row.salary_min,
    salary_max: row.salary_max,
    hiring_count: row.hiring_count,
    priority: row.priority || '',
    contact_person: row.contact_person || '',
    contact_info: row.contact_info || '',
    description: row.description || '',
    requirements: row.requirements || '',
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.title) {
    ElMessage.warning('请填写需求名称')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateJob(editingId.value, form)
      ElMessage.success('已更新')
    } else {
      await createJob(form)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    saving.value = false
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
.card-title { margin: 0; font-size: 16px; color: #303133; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.pager { margin-top: 16px; justify-content: flex-end; }
</style>