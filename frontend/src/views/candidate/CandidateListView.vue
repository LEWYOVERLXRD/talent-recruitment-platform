<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <h1>候选人管理</h1>
        <p class="page-sub">维护候选人档案、简历版本与沟通记录；机构候选人与个人档案按归属区分。</p>
      </div>
      <div class="page-actions">
        <el-button type="primary" @click="openCreate">录入候选人</el-button>
      </div>
    </div>

    <el-card shadow="never">
    <div class="filter-bar">
      <el-input
        v-model="query.keyword"
        placeholder="按姓名/公司/职位检索"
        clearable
        style="width: 260px"
        @keyup.enter="load"
        @clear="load"
      />
      <el-button type="primary" plain @click="load">查询</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" @row-click="goDetail">
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column prop="current_company" label="当前公司" min-width="140" />
      <el-table-column prop="current_position" label="当前职位" min-width="140" />
      <el-table-column prop="education" label="学历" width="100" />
      <el-table-column label="工作年限" width="90">
        <template #default="{ row }">{{ row.years_of_experience ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="归属" width="110">
        <template #default="{ row }">
          <el-tag :type="ownershipTag(row)" size="small">
            {{ ownershipText(row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="负责人" width="120">
        <template #default="{ row }">{{ row.owner_username ?? '待管理员核验' }}</template>
      </el-table-column>
      <el-table-column label="来源" width="100">
        <template #default="{ row }">{{ sourceText(row.source) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default>
          <el-button link type="primary">查看</el-button>
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

    <!-- 录入候选人弹窗 -->
    <el-dialog v-model="dialogVisible" title="录入候选人" width="min(620px, calc(100vw - 32px))">
      <el-form :model="form" label-width="110px">
        <el-form-item v-if="isHeadhunter" label="归属" required>
          <el-radio-group v-model="form.ownership">
            <el-radio value="individual">个人档案</el-radio>
            <el-radio value="agency" :disabled="!activeAgency">本机构档案</el-radio>
          </el-radio-group>
          <div v-if="!activeAgency" class="form-tip">
            你当前不是有效机构成员，只能创建个人档案。
          </div>
        </el-form-item>
        <el-form-item v-if="isAdmin" label="负责人用户 ID" required>
          <el-input-number v-model="form.owner_user_id" :min="1" style="width: 100%" />
          <div class="form-tip">管理员创建个人档案时，必须指定有效猎头账号 ID。</div>
        </el-form-item>
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" placeholder="候选人姓名" />
        </el-form-item>
        <el-form-item label="性别">
          <el-input v-model="form.gender" placeholder="选填" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.phone" placeholder="选填" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="选填" />
        </el-form-item>
        <el-form-item label="当前公司">
          <el-input v-model="form.current_company" placeholder="选填" />
        </el-form-item>
        <el-form-item label="当前职位">
          <el-input v-model="form.current_position" placeholder="选填" />
        </el-form-item>
        <el-form-item label="工作年限">
          <el-input-number v-model="form.years_of_experience" :min="0" />
        </el-form-item>
        <el-form-item label="最高学历">
          <el-input v-model="form.education" placeholder="如：硕士" />
        </el-form-item>
        <el-form-item label="期望薪资">
          <el-input v-model="form.expected_salary" placeholder="选填" />
        </el-form-item>
        <el-form-item label="期望工作地">
          <el-input v-model="form.expected_location" placeholder="选填" />
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="form.source" style="width: 100%">
            <el-option label="手动录入" value="manual" />
            <el-option label="自助投递" value="self_apply" />
          </el-select>
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
import { listCandidates, createCandidate } from '@/api/candidate'
import { getAgencyContext } from '@/api/agency'

const router = useRouter()
const userStore = useUserStore()
const isAdmin = userStore.role === 'admin'
const isHeadhunter = userStore.role === 'headhunter'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, size: 20, keyword: '' })

// 当前猎头是否为有效机构成员（决定能否创建本机构档案）
const activeAgency = ref(false)

const dialogVisible = ref(false)
const saving = ref(false)
const emptyForm = () => ({
  ownership: 'individual',
  owner_user_id: undefined,
  name: '',
  gender: '',
  phone: '',
  email: '',
  current_company: '',
  current_position: '',
  years_of_experience: undefined,
  education: '',
  expected_salary: '',
  expected_location: '',
  source: 'manual',
})
const form = reactive(emptyForm())

function ownershipText(row) {
  if (row.provider_kind === 'agency') return '机构候选人'
  if (row.provider_kind === 'individual') return '个人档案'
  return '待管理员核验'
}
function ownershipTag(row) {
  if (row.provider_kind === 'agency') return 'warning'
  if (row.provider_kind === 'individual') return 'success'
  return 'info'
}
function sourceText(s) {
  return { manual: '手动录入', self_apply: '自助投递' }[s] || s || '-'
}

async function load() {
  loading.value = true
  try {
    const data = await listCandidates({
      page: query.page,
      size: query.size,
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

async function loadAgencyContext() {
  if (!isHeadhunter) return
  try {
    const ctx = await getAgencyContext()
    activeAgency.value = ctx.agency?.status === 'active' && ctx.membership?.status === 'active'
  } catch (e) {
    activeAgency.value = false
  }
}

function openCreate() {
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

async function save() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写候选人姓名')
    return
  }
  if (isAdmin && !form.owner_user_id) {
    ElMessage.warning('请填写负责人用户 ID')
    return
  }
  saving.value = true
  try {
    const payload = {
      ownership: isAdmin ? 'individual' : form.ownership,
      name: form.name.trim(),
      gender: form.gender || undefined,
      phone: form.phone || undefined,
      email: form.email || undefined,
      current_company: form.current_company || undefined,
      current_position: form.current_position || undefined,
      years_of_experience: form.years_of_experience ?? undefined,
      education: form.education || undefined,
      expected_salary: form.expected_salary || undefined,
      expected_location: form.expected_location || undefined,
      source: form.source,
    }
    if (isAdmin && form.owner_user_id) {
      payload.owner_user_id = form.owner_user_id
    }
    await createCandidate(payload)
    ElMessage.success('已录入候选人')
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    saving.value = false
  }
}

function goDetail(row) {
  router.push({ name: 'CandidateDetail', params: { id: row.id } })
}

onMounted(() => {
  load()
  loadAgencyContext()
})
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
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
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
