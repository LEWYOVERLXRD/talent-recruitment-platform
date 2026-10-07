<template>
  <el-container class="home">
    <el-aside width="220px" class="aside">
      <div class="logo">智能招聘平台</div>
      <el-menu :default-active="activeMenu" class="menu" @select="handleSelect">
        <el-menu-item
          v-for="item in userStore.menus"
          :key="item.key"
          :index="item.key"
        >
          <span>{{ item.label }}</span>
          <el-tag v-if="item.done === false" size="small" type="info" class="menu-tag">
            开发中
          </el-tag>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">工作台</div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-icon><UserFilled /></el-icon>
              <span class="username">{{ userStore.displayName || '未登录' }}</span>
              <el-tag size="small" class="role-tag">{{ userStore.roleLabel }}</el-tag>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <el-card shadow="never">
          <template #header>
            <h3 class="card-title">当前登录用户信息</h3>
          </template>

          <el-descriptions :column="2" border>
            <el-descriptions-item label="用户 ID">{{ userStore.user?.id ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="用户名">{{ userStore.user?.username ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="真实姓名">{{ userStore.user?.real_name ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="身份">{{ userStore.roleLabel || '-' }}</el-descriptions-item>
            <el-descriptions-item label="邮箱">{{ userStore.user?.email ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="手机号">{{ userStore.user?.phone ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="所属企业">
              {{ userStore.user?.company_name ?? '（未归属企业）' }}
            </el-descriptions-item>
            <el-descriptions-item label="企业内角色">
              {{ userStore.companyRoleLabel || '-' }}
            </el-descriptions-item>
          </el-descriptions>

          <div class="tips">
            <el-alert type="info" :closable="false" show-icon>
              <template #title>
                <span v-if="userStore.isAdmin">
                  你当前是平台管理员，可管理全部用户与企业账号状态。
                </span>
                <span v-else-if="userStore.isManager">
                  你当前是「{{ userStore.user?.company_name }}」的企业主管，可管理本企业员工的账号状态。
                </span>
                <span v-else-if="userStore.user?.role === 'recruiter'">
                  你当前是「{{ userStore.user?.company_name }}」的普通员工，可处理本企业招聘业务。
                </span>
                <span v-else>
                  登录/注册模块前后端联调已完成，左侧菜单已按你的身份区分。后续业务功能（岗位、候选人、简历、AI 匹配等）将在后续阶段开发。
                </span>
              </template>
            </el-alert>
          </div>
        </el-card>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled, ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

// 默认选中菜单：地址是 /jobs 时选中“招聘需求”，否则回到“工作台”
const activeMenu = ref(
  router.currentRoute.value.path === '/jobs' ? 'jobs' : 'dashboard',
)

// 已完成（done）的菜单路由表：key -> 路由名
const MENU_ROUTES = { jobs: 'Jobs' }

function handleSelect(key) {
  const target = MENU_ROUTES[key]
  if (target) {
    if (router.currentRoute.value.name !== target) {
      router.push({ name: target })
    }
    return
  }
  if (key !== 'dashboard') {
    ElMessage.info('该模块正在开发中')
  }
}

function handleCommand(cmd) {
  if (cmd === 'logout') {
    handleLogout()
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      type: 'warning',
    })
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push({ name: 'Login' })
  } catch (e) {
    // 用户取消
  }
}
</script>

<style scoped>
.home {
  min-height: 100vh;
  background: #f5f7fa;
}

.aside {
  background: #fff;
  border-right: 1px solid #ebeef5;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  border-bottom: 1px solid #ebeef5;
}

.menu {
  border-right: none;
}

.menu-tag {
  margin-left: 8px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  padding: 0 24px;
  height: 60px;
}

.header-left {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #606266;
}

.username {
  font-size: 14px;
}

.role-tag {
  color: #409eff;
  border-color: #d9ecff;
  background: #ecf5ff;
}

.main {
  padding: 24px;
}

.card-title {
  margin: 0;
  font-size: 16px;
  color: #303133;
}

.tips {
  margin-top: 20px;
}
</style>