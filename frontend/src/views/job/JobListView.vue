<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <h1>{{ userStore.isJobseeker ? '岗位浏览' : '招聘需求' }}</h1>
        <p class="page-sub">{{ userStore.isJobseeker ? '浏览当前开放的招聘岗位，查看要求并选择简历投递。' : '查看需求版本、确认态与来源；客户企业发布与猎头代建的需求在此统一管理。' }}</p>
      </div>
      <div class="page-actions">
      <el-button v-if="!userStore.isJobseeker" type="primary" @click="openCreate">新建需求</el-button>
      </div>
    </div>

    <el-card shadow="never">
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

    <el-table :data="rows" v-loading="loading">
      <el-table-column prop="title" label="需求名称" min-width="180" />
      <el-table-column prop="client_company_name" label="客户企业" width="140" />
      <el-table-column label="版本" width="70">
        <template #default="{ row }">v{{ row.version ?? 1 }}</template>
      </el-table-column>
      <el-table-column label="确认态" width="110">
        <template #default="{ row }">
          <el-tag :type="confirmTag(row)">{{ confirmText(row) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="!userStore.isJobseeker" label="来源" width="100">
        <template #default="{ row }">{{ sourceText(row.source) }}</template>
      </el-table-column>
      <el-table-column v-if="userStore.isJobseeker" label="负责猎头" min-width="180">
        <template #default="{ row }">{{ (row.receivers || []).map(item => item.provider_kind === 'agency' ? `${item.headhunter_name}（${item.provider_name}）` : item.headhunter_name).join('、') }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="location" label="地点" width="110" />
      <el-table-column label="薪资(K)" width="120">
        <template #default="{ row }">{{ row.salary_min ?? '-' }} - {{ row.salary_max ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row)">详情</el-button>
          <el-button v-if="canEditJob(row)" link type="primary" @click="openEdit(row)">编辑</el-button>
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
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑招聘需求' : '新建招聘需求'" width="min(640px, 94vw)">
      <el-form :model="form" label-width="110px">
        <el-form-item label="需求名称" required>
          <el-input v-model="form.title" placeholder="请填写需求/岗位名称" />
        </el-form-item>
        <el-form-item v-if="!editingId && showClientCompany" label="客户企业" required>
          <el-select v-model="form.client_company_id" filterable placeholder="选择已核验客户企业" style="width: 100%">
            <el-option v-for="c in companyOptions" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
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
        <el-form-item v-if="!editingId" label="原始岗位资料">
          <el-input type="textarea" v-model="form.job_profile_content" :rows="3" placeholder="选填；留空时由职责/要求自动生成" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { listJobs, createJob, updateJob } from '@/api/job'
import { listCompanyOptions } from '@/api/company'

const router = useRouter()
const userStore = useUserStore()

// headhunter / admin 代建需求时必须选择客户企业；招聘方由账号企业自动归属
const showClientCompany = userStore.role === 'headhunter' || userStore.role === 'admin'

function canEditJob(row) {
  if (row.status === 'closed') return false
  if (userStore.isAdmin) return true
  if (userStore.role === 'recruiter') {
    if (userStore.user?.company_id == null || row.client_company_id !== userStore.user.company_id) return false
    return row.ever_confirmed_at == null || userStore.isClientManager
  }
  return userStore.role === 'headhunter' && row.ever_confirmed_at == null && row.created_by === userStore.user?.id
}

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, size: 20, status: '', keyword: '' })

const companyOptions = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const editingVersion = ref(null)

const emptyForm = () => ({
  title: '',
  client_company_id: undefined,
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
  job_profile_content: '',
})
const form = reactive(emptyForm())

function statusText(s) {
  return { open: '寻访中', suspended: '暂停', closed: '已关闭' }[s] || s
}
function statusTag(s) {
  return { open: 'success', suspended: 'warning', closed: 'info' }[s] || 'info'
}
function confirmText(row) {
  if (row.confirmed_at) return '已确认'
  return row.ever_confirmed_at ? '待重新确认' : '未确认'
}
function confirmTag(row) {
  if (row.confirmed_at) return 'success'
  return row.ever_confirmed_at ? 'warning' : 'info'
}
function sourceText(s) {
  return { client_published: '企业发布', headhunter_created: '猎头代建' }[s] || s
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

async function loadCompanies() {
  if (!showClientCompany) return
  try {
    companyOptions.value = await listCompanyOptions()
  } catch (e) {
    ElMessage.error(e)
  }
}

function goDetail(row) {
  router.push({ name: 'JobDetail', params: { id: row.id } })
}

function openCreate() {
  editingId.value = null
  editingVersion.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  editingVersion.value = row.version
  Object.assign(form, {
    title: row.title,
    client_company_id: undefined,
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
    job_profile_content: '',
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.title || !form.title.trim()) {
    ElMessage.warning('请填写需求名称')
    return
  }
  if (!editingId.value && showClientCompany && !form.client_company_id) {
    ElMessage.warning('请选择已核验的客户企业')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      const data = {
        expected_version: editingVersion.value,
        title: form.title.trim(),
        department: form.department || null,
        description: form.description || null,
        requirements: form.requirements || null,
        salary_min: form.salary_min ?? null,
        salary_max: form.salary_max ?? null,
        location: form.location || null,
        contact_person: form.contact_person || null,
        contact_info: form.contact_info || null,
        hiring_count: form.hiring_count ?? null,
        priority: form.priority || null,
      }
      const updated = await updateJob(editingId.value, data)
      if ((updated.version ?? editingVersion.value) > editingVersion.value) {
        ElMessage.warning('招聘条件已变更，需求版本已更新，需重新确认并逐主体重新邀请')
      } else {
        ElMessage.success('已更新')
      }
    } else {
      const data = {
        title: form.title.trim(),
        department: form.department || undefined,
        description: form.description || undefined,
        requirements: form.requirements || undefined,
        salary_min: form.salary_min ?? undefined,
        salary_max: form.salary_max ?? undefined,
        location: form.location || undefined,
        hiring_count: form.hiring_count ?? undefined,
        priority: form.priority || undefined,
        contact_person: form.contact_person || undefined,
        contact_info: form.contact_info || undefined,
        job_profile_content: form.job_profile_content || undefined,
      }
      if (showClientCompany) data.client_company_id = form.client_company_id
      await createJob(data)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e)
    if (editingId.value) dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  load()
  loadCompanies()
})
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
@media (max-width: 640px) {
  .filter-bar { flex-wrap: wrap; }
}
</style>
