<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <h1>我的机构</h1>
        <p class="page-sub">查看机构状态、成员身份与邀请记录；机构主管可邀请成员并调整角色。</p>
      </div>
    </div>

  <el-card shadow="never">

    <div v-loading="loading">
      <!-- 待处理邀请提示 -->
      <el-alert
        v-if="invitations.length > 0"
        class="mb"
        type="warning"
        :closable="false"
        show-icon
      >
        <template #title>
          你有 {{ invitations.length }} 条待处理的机构邀请，请及时接受或拒绝。
        </template>
        <template #default>
          <el-button size="small" type="primary" @click="goInvitations">
            去处理
          </el-button>
        </template>
      </el-alert>

      <!-- 尚未加入机构 -->
      <el-empty v-if="!agency && !loading" description="你尚未加入任何机构">
        <template #default>
          <span class="tip-text">
            请等待机构主管邀请，或联系平台管理员创建机构并指定主管。
          </span>
        </template>
      </el-empty>

      <!-- 机构概览 -->
      <el-descriptions v-if="agency" :column="2" border class="mb">
        <el-descriptions-item label="机构名称">{{ agency.name }}</el-descriptions-item>
        <el-descriptions-item label="机构状态">
          <el-tag :type="agency.status === 'active' ? 'success' : 'info'">
            {{ agencyStatusText(agency.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="我的身份">
          {{ memberRoleText(membership?.role) }}
        </el-descriptions-item>
        <el-descriptions-item label="成员状态">
          {{ memberStatusText(membership?.status) }}
        </el-descriptions-item>
      </el-descriptions>

      <!-- 机构主管：成员管理 -->
      <el-card v-if="isManager && agency" shadow="never" class="member-card">
        <template #header>
          <div class="card-head">
            <h4 class="card-title">成员管理</h4>
            <el-button type="primary" size="small" @click="openInvite">邀请成员</el-button>
          </div>
        </template>

        <el-table :data="members" v-loading="membersLoading">
          <el-table-column prop="username" label="账号" min-width="120" />
          <el-table-column label="姓名" width="120">
            <template #default="{ row }">{{ row.real_name ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="角色" width="100">
            <template #default="{ row }">
              <el-tag :type="row.role === 'manager' ? 'warning' : 'info'">
                {{ memberRoleText(row.role) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="成员状态" width="110">
            <template #default="{ row }">
              <el-tag :type="memberStatusTag(row.status)">
                {{ memberStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="账号状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.enabled === false ? 'danger' : 'success'">
                {{ row.enabled === false ? '已禁用' : '正常' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="加入时间" min-width="160">
            <template #default="{ row }">{{ formatTime(row.joined_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <template v-if="row.status === 'invited'">
                <el-button link type="danger" @click="cancelInvite(row)">取消邀请</el-button>
              </template>
              <template v-else-if="row.status === 'active'">
                <el-button
                  v-if="row.role === 'staff'"
                  link
                  type="primary"
                  @click="promoteToManager(row)"
                >
                  提升为主管
                </el-button>
                <el-button
                  v-else
                  link
                  type="warning"
                  @click="demoteToStaff(row)"
                >
                  降为顾问
                </el-button>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 普通成员提示 -->
      <el-alert
        v-if="agency?.status === 'disabled'"
        type="warning"
        :closable="false"
        show-icon
        title="机构已停用，机构业务暂不可操作，请联系平台管理员。"
      />
      <el-alert
        v-else-if="agency && !isManager"
        type="info"
        :closable="false"
        show-icon
        title="你是机构顾问，仅可见本机构已分配给你的候选人，无权管理成员。"
      />
    </div>

    <!-- 邀请成员弹窗 -->
    <el-dialog v-model="inviteVisible" title="邀请猎头加入机构" width="min(440px, calc(100vw - 32px))">
      <el-form :model="inviteForm" label-width="90px">
        <el-form-item label="猎头账号" required>
          <el-input v-model="inviteForm.username" placeholder="填写对方平台登录账号（username）" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="inviteForm.role" style="width: 100%">
            <el-option label="顾问" value="staff" />
            <el-option label="主管" value="manager" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="inviteVisible = false">取消</el-button>
        <el-button type="primary" :loading="inviteSaving" @click="submitInvite">发送邀请</el-button>
      </template>
    </el-dialog>
  </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAgencyContext,
  listMembers,
  inviteMember,
  setMemberRole,
  cancelInvitation,
} from '@/api/agency'

const router = useRouter()

const loading = ref(false)
const membersLoading = ref(false)
const context = ref({ agency: null, membership: null, invitations: [] })
const members = ref([])

const agency = computed(() => context.value.agency)
const membership = computed(() => context.value.membership)
const invitations = computed(() => context.value.invitations || [])
const isManager = computed(
  () => agency.value?.status === 'active' && membership.value?.role === 'manager',
)

const inviteVisible = ref(false)
const inviteSaving = ref(false)
const inviteForm = reactive({ username: '', role: 'staff' })

function agencyStatusText(s) {
  return { active: '运营中', disabled: '已停用' }[s] || s
}
function memberRoleText(r) {
  return { manager: '主管', staff: '顾问' }[r] || r
}
function memberStatusText(s) {
  return { invited: '待接受', active: '在职', declined: '已拒绝', cancelled: '已取消', left: '已离职' }[s] || s
}
function memberStatusTag(s) {
  return { invited: 'warning', active: 'success', left: 'info' }[s] || 'info'
}
function formatTime(t) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}

async function load() {
  loading.value = true
  try {
    context.value = await getAgencyContext()
    if (isManager.value && agency.value) {
      await loadMembers()
    }
  } catch (e) {
    ElMessage.error(e)
    context.value = { agency: null, membership: null, invitations: [] }
  } finally {
    loading.value = false
  }
}

async function loadMembers() {
  membersLoading.value = true
  try {
    members.value = await listMembers(agency.value.id)
  } catch (e) {
    ElMessage.error(e)
  } finally {
    membersLoading.value = false
  }
}

function goInvitations() {
  router.push({ name: 'AgencyInvitations' })
}

function openInvite() {
  inviteForm.username = ''
  inviteForm.role = 'staff'
  inviteVisible.value = true
}

async function submitInvite() {
  if (!inviteForm.username.trim()) {
    ElMessage.warning('请填写猎头账号')
    return
  }
  inviteSaving.value = true
  try {
    await inviteMember(agency.value.id, {
      username: inviteForm.username.trim(),
      role: inviteForm.role,
    })
    ElMessage.success('已发送邀请')
    inviteVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    inviteSaving.value = false
  }
}

async function promoteToManager(member) {
  await changeRole(member, 'manager')
}
async function demoteToStaff(member) {
  await changeRole(member, 'staff')
}

async function changeRole(member, role) {
  const label = role === 'manager' ? '主管' : '顾问'
  try {
    await ElMessageBox.confirm(
      `确定将「${member.real_name || member.username}」调整为${label}吗？`,
      '调整角色',
      { type: 'warning' },
    )
    await setMemberRole(agency.value.id, member.id, role)
    ElMessage.success('已调整')
    await load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e)
    }
  }
}

async function cancelInvite(member) {
  try {
    await ElMessageBox.confirm(
      `确定取消对「${member.real_name || member.username}」的邀请吗？`,
      '取消邀请',
      { type: 'warning' },
    )
    await cancelInvitation(agency.value.id, member.id)
    ElMessage.success('已取消邀请')
    await loadMembers()
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
.mb {
  margin-bottom: 16px;
}
.member-card {
  margin-top: 16px;
}
.tip-text {
  color: #909399;
  font-size: 13px;
}
</style>
