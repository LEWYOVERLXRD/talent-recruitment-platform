<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <h1>企业成员</h1>
        <p class="page-sub">查看本企业招聘成员与邀请记录；待入企账号可在此接受或拒绝主管发来的邀请。</p>
      </div>
      <div class="page-actions">
        <el-tag v-if="company" :type="isManager ? 'warning' : 'info'">
          {{ isManager ? '企业主管' : '普通员工' }}
        </el-tag>
      </div>
    </div>

  <el-card shadow="never" v-loading="loading">

    <el-alert
      v-if="!company"
      class="section"
      type="info"
      :closable="false"
      title="当前账号尚未加入企业。接受企业主管发来的邀请后，即可处理本企业的招聘需求和推荐反馈。"
    />

    <template v-if="!loading">
      <el-descriptions v-if="company" :column="isNarrow ? 1 : 2" border class="section">
        <el-descriptions-item label="企业名称">{{ company.name }}</el-descriptions-item>
        <el-descriptions-item label="当前身份">{{ isManager ? '企业主管' : '普通员工' }}</el-descriptions-item>
      </el-descriptions>

      <section v-if="company && isManager" class="section">
        <div class="section-head">
          <h4>企业成员</h4>
          <el-button type="primary" @click="inviteVisible = true">邀请员工</el-button>
        </div>
        <el-table v-if="!isNarrow" :data="members" v-loading="membersLoading">
          <el-table-column prop="username" label="用户名" min-width="140" />
          <el-table-column label="姓名" min-width="120">
            <template #default="{ row }">{{ row.real_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="企业角色" width="110">
            <template #default="{ row }">{{ row.company_role === 'manager' ? '主管' : '普通员工' }}</template>
          </el-table-column>
          <el-table-column label="账号状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '禁用' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div v-else class="record-list" v-loading="membersLoading">
          <article v-for="member in members" :key="member.id" class="record-row">
            <div class="record-main"><strong>{{ member.real_name || member.username }}</strong><span>{{ member.username }}</span></div>
            <div class="record-meta"><span>{{ member.company_role === 'manager' ? '主管' : '普通员工' }}</span><el-tag :type="member.enabled ? 'success' : 'info'" size="small">{{ member.enabled ? '启用' : '禁用' }}</el-tag></div>
          </article>
          <el-empty v-if="!membersLoading && !members.length" description="暂无成员" />
        </div>

        <div class="section-head invitation-head">
          <h4>邀请记录</h4>
          <el-button :icon="Refresh" circle aria-label="刷新邀请记录" @click="loadInvitations" />
        </div>
        <el-table v-if="!isNarrow" :data="invitations" v-loading="invitationsLoading" border>
          <el-table-column prop="username" label="受邀账号" min-width="140" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }"><el-tag :type="statusTag(row.status)" size="small">{{ statusText(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="有效期至" min-width="170">
            <template #default="{ row }">{{ formatTime(row.expires_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button v-if="row.status === 'pending'" link type="danger" @click="revoke(row)">撤销</el-button>
              <span v-else class="muted">-</span>
            </template>
          </el-table-column>
        </el-table>
        <div v-else class="record-list" v-loading="invitationsLoading">
          <article v-for="invitation in invitations" :key="invitation.id" class="record-row">
            <div class="record-main"><strong>{{ invitation.username }}</strong><el-tag :type="statusTag(invitation.status)" size="small">{{ statusText(invitation.status) }}</el-tag></div>
            <div class="record-meta"><span>有效期至 {{ formatTime(invitation.expires_at) }}</span><el-button v-if="invitation.status === 'pending'" link type="danger" @click="revoke(invitation)">撤销</el-button></div>
          </article>
          <el-empty v-if="!invitationsLoading && !invitations.length" description="暂无邀请记录" />
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <h4>收到的企业邀请</h4>
          <el-button :icon="Refresh" circle aria-label="刷新收到的企业邀请" @click="loadMyInvitations" />
        </div>
        <el-table v-if="!isNarrow" :data="myInvitations" v-loading="myInvitationsLoading" border>
          <el-table-column prop="company_name" label="邀请企业" min-width="160" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }"><el-tag :type="statusTag(row.status)" size="small">{{ statusText(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="有效期至" min-width="170">
            <template #default="{ row }">{{ formatTime(row.expires_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <template v-if="row.status === 'pending'">
                <el-button v-if="!company" link type="primary" :disabled="acting" @click="decide(row, true)">接受</el-button>
                <el-button link :disabled="acting" @click="decide(row, false)">拒绝</el-button>
              </template>
              <span v-else class="muted">-</span>
            </template>
          </el-table-column>
          <template #empty><el-empty description="暂无企业邀请" /></template>
        </el-table>
        <div v-else class="record-list" v-loading="myInvitationsLoading">
          <article v-for="invitation in myInvitations" :key="invitation.id" class="record-row">
            <div class="record-main"><strong>{{ invitation.company_name }}</strong><el-tag :type="statusTag(invitation.status)" size="small">{{ statusText(invitation.status) }}</el-tag></div>
            <div class="record-meta"><span>有效期至 {{ formatTime(invitation.expires_at) }}</span></div>
            <div v-if="invitation.status === 'pending'" class="record-actions">
              <el-button v-if="!company" type="primary" size="small" :disabled="acting" @click="decide(invitation, true)">接受</el-button>
              <el-button size="small" :disabled="acting" @click="decide(invitation, false)">拒绝</el-button>
            </div>
          </article>
          <el-empty v-if="!myInvitationsLoading && !myInvitations.length" description="暂无企业邀请" />
        </div>
      </section>
    </template>

    <el-dialog v-model="inviteVisible" title="邀请招聘员工" width="min(440px, calc(100vw - 32px))">
      <el-form @submit.prevent="sendInvite">
        <el-form-item label="员工用户名" required>
          <el-input v-model="inviteUsername" maxlength="50" placeholder="填写对方注册时使用的用户名" @keyup.enter="sendInvite" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="inviteVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="sendInvite">发送邀请</el-button>
      </template>
    </el-dialog>
  </el-card>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
  decideCompanyInvitation,
  getMyCompany,
  inviteCompanyMember,
  listCompanyInvitations,
  listCompanyMembers,
  listMyCompanyInvitations,
  revokeCompanyInvitation,
} from '@/api/company'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const membersLoading = ref(false)
const invitationsLoading = ref(false)
const myInvitationsLoading = ref(false)
const saving = ref(false)
const acting = ref(false)
const isNarrow = ref(window.matchMedia('(max-width: 640px)').matches)
const company = ref(null)
const members = ref([])
const invitations = ref([])
const myInvitations = ref([])
const inviteVisible = ref(false)
const inviteUsername = ref('')
const isManager = computed(() => userStore.user?.company_role === 'manager')

function statusText(status) {
  return ({ pending: '待处理', accepted: '已接受', declined: '已拒绝', revoked: '已撤销', expired: '已过期' })[status] || status
}
function statusTag(status) {
  return ({ pending: 'warning', accepted: 'success' })[status] || 'info'
}
function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 16) : '-'
}

async function loadMembers() {
  membersLoading.value = true
  try { members.value = await listCompanyMembers() }
  catch (error) { members.value = []; ElMessage.error(error) }
  finally { membersLoading.value = false }
}
async function loadInvitations() {
  invitationsLoading.value = true
  try { invitations.value = await listCompanyInvitations() }
  catch (error) { invitations.value = []; ElMessage.error(error) }
  finally { invitationsLoading.value = false }
}
async function loadMyInvitations() {
  myInvitationsLoading.value = true
  try { myInvitations.value = await listMyCompanyInvitations() }
  catch (error) { myInvitations.value = []; ElMessage.error(error) }
  finally { myInvitationsLoading.value = false }
}
async function load() {
  loading.value = true
  try {
    await userStore.fetchCurrentUser()
    members.value = []
    invitations.value = []
    if (!userStore.user?.company_id) company.value = null
    else company.value = await getMyCompany()
    if (company.value && isManager.value) await Promise.all([loadMembers(), loadInvitations()])
    await loadMyInvitations()
  } catch (error) {
    company.value = null
    members.value = []
    invitations.value = []
    myInvitations.value = []
    ElMessage.error(error)
  }
  finally { loading.value = false }
}

async function sendInvite() {
  const username = inviteUsername.value.trim()
  if (!username) return ElMessage.warning('请填写员工用户名')
  saving.value = true
  try {
    await inviteCompanyMember(username)
    ElMessage.success('邀请已发送，有效期7天')
    inviteVisible.value = false
    inviteUsername.value = ''
    await loadInvitations()
  } catch (error) { ElMessage.error(error) }
  finally { saving.value = false }
}

async function decide(row, accept) {
  if (acting.value) return
  acting.value = true
  try {
    await ElMessageBox.confirm(
      accept ? `接受加入“${row.company_name}”并成为普通员工？` : `拒绝“${row.company_name}”的邀请？`,
      accept ? '加入企业' : '拒绝邀请',
      { type: 'info', confirmButtonText: accept ? '确认加入' : '确认拒绝', cancelButtonText: '取消' },
    )
    await decideCompanyInvitation(row.id, accept)
    ElMessage.success(accept ? '已加入企业' : '已拒绝邀请')
    await userStore.fetchCurrentUser()
    await load()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error)
      await load()
    }
  } finally {
    acting.value = false
  }
}

async function revoke(row) {
  try {
    await ElMessageBox.confirm(`撤销发给“${row.username}”的邀请？`, '撤销邀请', {
      type: 'warning', confirmButtonText: '确认撤销', cancelButtonText: '取消',
    })
    await revokeCompanyInvitation(row.id)
    ElMessage.success('邀请已撤销')
    await loadInvitations()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error)
  }
}

onMounted(load)
const viewport = window.matchMedia('(max-width: 640px)')
function syncViewport(event) { isNarrow.value = event.matches }
viewport.addEventListener('change', syncViewport)
onBeforeUnmount(() => viewport.removeEventListener('change', syncViewport))
</script>

<style scoped>
.card-head,.section-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.card-title{margin:0;font-size:16px}
.section{margin-top:22px}
.section-head{margin-bottom:12px}
.section-head h4{margin:0;font-size:14px;font-weight:600}
.invitation-head{margin-top:24px}
.muted{color:#909399}
.record-list{border-top:1px solid #ebeef5}
.record-row{display:grid;gap:8px;padding:12px 4px;border-bottom:1px solid #ebeef5}
.record-main,.record-meta,.record-actions{display:flex;align-items:center;justify-content:space-between;gap:10px;min-width:0}
.record-main strong{overflow-wrap:anywhere}
.record-main span,.record-meta{color:#606266;font-size:13px}
.record-actions{justify-content:flex-start}
</style>
