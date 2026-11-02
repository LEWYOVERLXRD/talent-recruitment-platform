<template>
  <div class="app-page">
    <div class="page-head">
      <div>
        <h1>邀请处理</h1>
        <p class="page-sub">接受邀请后将以机构成员身份参与协作；拒绝不影响现有账号。</p>
      </div>
    </div>

    <el-card shadow="never">
    <div v-loading="loading">
      <el-empty v-if="!loading && invitations.length === 0" description="暂无待处理的机构邀请" />

      <div v-for="inv in invitations" :key="inv.id" class="invite-item">
        <div class="invite-info">
          <div class="invite-title">
            邀请你加入机构（ID：{{ inv.agency_id }}）
            <el-tag size="small" :type="inv.role === 'manager' ? 'warning' : 'info'">
              {{ inv.role === 'manager' ? '主管' : '顾问' }}
            </el-tag>
          </div>
          <div class="invite-sub">状态：待处理</div>
        </div>
        <div class="invite-actions">
          <el-button type="primary" :loading="decidingId === inv.id" @click="decide(inv, true)">
            接受
          </el-button>
          <el-button :disabled="decidingId === inv.id" @click="decide(inv, false)">
            拒绝
          </el-button>
        </div>
      </div>
    </div>
  </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAgencyContext, decideInvitation } from '@/api/agency'

const loading = ref(false)
const invitations = ref([])
const decidingId = ref(null)

async function load() {
  loading.value = true
  try {
    const ctx = await getAgencyContext()
    invitations.value = ctx.invitations || []
  } catch (e) {
    ElMessage.error(e)
  } finally {
    loading.value = false
  }
}

async function decide(inv, accept) {
  if (!accept) {
    try {
      await ElMessageBox.confirm(
        `确定拒绝该机构（ID：${inv.agency_id}）的邀请吗？`,
        '拒绝邀请',
        { type: 'warning' },
      )
    } catch (e) {
      return
    }
  }

  decidingId.value = inv.id
  try {
    await decideInvitation(inv.agency_id, inv.id, accept)
    ElMessage.success(accept ? '已加入机构' : '已拒绝邀请')
    await load()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    decidingId.value = null
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
.invite-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  margin-bottom: 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}
.invite-title {
  font-size: 14px;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}
.invite-sub {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}
.invite-actions {
  display: flex;
  gap: 8px;
}
</style>
