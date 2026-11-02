<template>
  <header class="topbar">
    <div class="topbar-left">
      <button
        class="menu-toggle"
        type="button"
        :aria-label="menuOpen ? '关闭导航' : '打开导航'"
        :aria-expanded="String(menuOpen)"
        @click="$emit('toggle')"
      >
        <el-icon><Menu /></el-icon>
      </button>
      <div class="crumb" aria-label="当前位置">
        <span class="crumb-root">业务工作区</span>
        <span class="crumb-sep" aria-hidden="true">/</span>
        <span class="crumb-current">{{ title }}</span>
      </div>
    </div>

    <div class="account">
      <span class="avatar" aria-hidden="true">{{ avatarText }}</span>
      <span class="account-name">{{ userStore.displayName || '未登录' }}</span>
      <span class="account-role">{{ userStore.roleLabel }}</span>
      <el-dropdown trigger="click" @command="handleCommand">
        <button class="account-more" type="button" aria-label="账号菜单">
          <el-icon><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>
              {{ userStore.user?.company_name || '未归属企业' }}
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Menu, ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

defineProps({
  title: { type: String, default: '工作台' },
  menuOpen: { type: Boolean, default: false },
})
defineEmits(['toggle'])

const router = useRouter()
const userStore = useUserStore()

const avatarText = computed(() => (userStore.displayName || '未').slice(0, 1))

async function handleCommand(command) {
  if (command !== 'logout') return
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出登录', {
      type: 'warning',
      confirmButtonText: '退出登录',
      cancelButtonText: '取消',
    })
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push({ name: 'Login' })
  } catch {
    // 用户取消
  }
}
</script>

<style scoped>
.topbar {
  height: 68px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 30px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--app-border);
}

.topbar-left,
.account {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.menu-toggle {
  display: none;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: #fff;
  color: var(--app-text);
  cursor: pointer;
}

.crumb {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  color: var(--app-muted);
  font-size: 13px;
}

.crumb-root,
.crumb-sep {
  white-space: nowrap;
}

.crumb-current {
  color: var(--app-text);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-name {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
}

.account-role {
  color: var(--app-muted);
  font-size: 12px;
  white-space: nowrap;
}

.avatar {
  width: 32px;
  height: 32px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #e5eef7;
  color: #36577d;
  font-size: 13px;
  font-weight: 600;
}

.account-more {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--app-muted);
  cursor: pointer;
}

.account-more:hover {
  background: var(--el-fill-color-light);
}

@media (max-width: 800px) {
  .topbar {
    height: 64px;
    padding: 0 16px;
  }

  .menu-toggle {
    display: inline-flex;
  }

  .account-role {
    display: none;
  }

  .crumb-root,
  .crumb-sep {
    display: none;
  }
}
</style>
