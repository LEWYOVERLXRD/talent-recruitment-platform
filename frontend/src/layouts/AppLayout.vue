<template>
  <div class="app-shell" @keydown.esc="menuOpen = false">
    <div v-if="menuOpen" class="nav-scrim" @click="menuOpen = false" />

    <aside
      ref="sidebar"
      class="app-sidebar"
      :class="{ open: menuOpen }"
      :inert="isMobile && !menuOpen"
      :role="isMobile && menuOpen ? 'dialog' : undefined"
      :aria-modal="isMobile && menuOpen ? 'true' : undefined"
      aria-label="平台导航"
      @keydown.tab="trapNavigationFocus"
    >
      <button v-if="isMobile" class="nav-close" type="button" @click="menuOpen = false">关闭导航</button>
      <router-link class="brand" :to="{ name: 'Home' }" @click="menuOpen = false">
        <span class="brand-mark" aria-hidden="true">
          <el-icon><Connection /></el-icon>
        </span>
        <span class="brand-text">
          智能招聘平台
          <small>{{ workspaceLabel }}</small>
        </span>
      </router-link>

      <p class="nav-label">业务工作区</p>
      <nav class="nav-list">
        <button
          v-for="item in visibleMenus"
          :key="item.key"
          type="button"
          class="nav-item"
          :class="{ active: isActive(item) }"
          :aria-current="isActive(item) ? 'page' : undefined"
          @click="navigate(item)"
        >
          <el-icon><component :is="iconFor(item.key)" /></el-icon>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="nav-foot">
        <strong>从需求承接到推荐反馈</strong>
        让每一次交付都有清晰依据
      </div>
    </aside>

    <div class="app-workspace" :inert="isMobile && menuOpen">
      <Header :title="pageTitle" :menu-open="menuOpen" @toggle="menuOpen = !menuOpen" />
      <main class="app-content">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowRight,
  Briefcase,
  Connection,
  Document,
  Grid,
  OfficeBuilding,
  Promotion,
  Search,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import Header from '@/views/common/Header.vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const menuOpen = ref(false)
const sidebar = ref(null)
const viewport = window.matchMedia('(max-width: 800px)')
const isMobile = ref(viewport.matches)
let previousFocus = null

function syncViewport(event) {
  isMobile.value = event.matches
  if (!event.matches) menuOpen.value = false
}
viewport.addEventListener('change', syncViewport)
onBeforeUnmount(() => viewport.removeEventListener('change', syncViewport))

watch(menuOpen, async (open) => {
  if (open && isMobile.value) previousFocus = document.activeElement
  await nextTick()
  if (open && isMobile.value) sidebar.value?.querySelector('button')?.focus()
  else if (previousFocus?.isConnected) previousFocus.focus()
})

function trapNavigationFocus(event) {
  if (!isMobile.value || !menuOpen.value) return
  const items = [...sidebar.value.querySelectorAll('a[href], button:not(:disabled)')]
    .filter((element) => element.getClientRects().length)
  const first = items[0]
  const last = items.at(-1)
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last?.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}

const MENU_ROUTES = {
  dashboard: 'Home',
  jobs: 'Jobs',
  resume: 'JobseekerResume',
  applications: 'Applications',
  assignments: 'Assignments',
  agency: 'Agency',
  agencies: 'Agencies',
  candidates: 'Candidates',
  company: 'Company',
  companies: 'Companies',
  recommendations: 'Recommendations',
  users: 'Users',
}

const DETAIL_ROUTES = {
  jobs: ['JobDetail'],
  assignments: ['AssignmentDetail'],
  candidates: ['CandidateDetail'],
  recommendations: ['RecommendationDetail'],
}

const MENU_ICONS = {
  dashboard: Grid,
  jobs: Briefcase,
  assignments: Search,
  agency: UserFilled,
  agencies: OfficeBuilding,
  candidates: User,
  company: UserFilled,
  companies: OfficeBuilding,
  recommendations: Promotion,
  users: Document,
}

const visibleMenus = computed(() => userStore.menus.filter((item) => item.done !== false))
const pageTitle = computed(() => route.meta.title || '工作台')
const workspaceLabel = computed(() => {
  if (userStore.isAdmin) return '平台核验与运营'
  if (userStore.isHeadhunter) return '猎头业务协作工作台'
  if (userStore.user?.role === 'recruiter') return '客户招聘协作工作台'
  return '自助求职服务'
})

function iconFor(key) {
  return MENU_ICONS[key] || ArrowRight
}

function isActive(item) {
  const target = MENU_ROUTES[item.key]
  if (!target) return false
  if (route.name === target) return true
  return (DETAIL_ROUTES[item.key] || []).includes(route.name)
}

function navigate(item) {
  const target = MENU_ROUTES[item.key]
  if (!target) return
  menuOpen.value = false
  if (route.name !== target) router.push({ name: target })
}

watch(
  () => route.fullPath,
  () => {
    menuOpen.value = false
  },
)
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: var(--app-canvas);
}

.app-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 20;
  width: 224px;
  display: flex;
  flex-direction: column;
  background: var(--app-nav);
  color: #dce5f2;
  overflow-y: auto;
}

.nav-close {
  align-self: flex-end;
  margin: 12px 12px 0;
  min-height: 44px;
  padding: 8px 12px;
  border: 1px solid #52677f;
  border-radius: 6px;
  background: transparent;
  color: #fff;
  font: inherit;
  cursor: pointer;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 26px 20px 22px;
  color: #fff;
  text-decoration: none;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex: none;
  border-radius: 9px;
  background: #2a756f;
  color: #fff;
}

.brand-text {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.brand-text small {
  display: block;
  margin-top: 1px;
  color: #b3c2d6;
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0;
}

.nav-label {
  margin: 0;
  padding: 12px 24px 8px;
  color: #b3c2d6;
  font-size: 12px;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: calc(100% - 24px);
  min-height: 44px;
  margin: 0 12px;
  padding: 10px 12px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #cbd8e8;
  font: inherit;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}

.nav-item:hover {
  background: var(--app-nav-hover);
  color: #fff;
}

.nav-item.active {
  background: var(--app-nav-active);
  color: #fff;
  box-shadow: inset 3px 0 #60baad;
}

.nav-item .el-icon {
  font-size: 18px;
  flex: none;
}

.nav-foot {
  margin-top: auto;
  padding: 22px 24px;
  border-top: 1px solid #31445c;
  color: #b3c2d6;
  font-size: 12px;
  line-height: 1.6;
}

.nav-foot strong {
  display: block;
  margin-bottom: 2px;
  color: #e8eff7;
  font-size: 13px;
  font-weight: 500;
}

.app-workspace {
  margin-left: 224px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-content {
  flex: 1;
  width: 100%;
  max-width: 1540px;
  margin: 0 auto;
  padding: 30px 32px 42px;
}

.nav-scrim {
  display: none;
}

@media (max-width: 1150px) {
  .app-sidebar {
    width: 204px;
  }

  .app-workspace {
    margin-left: 204px;
  }

  .app-content {
    padding: 24px 24px 36px;
  }
}

@media (max-width: 800px) {
  .app-sidebar {
    width: 224px;
    transform: translateX(-100%);
  }

  .app-sidebar.open {
    transform: translateX(0);
  }

  .app-workspace {
    margin-left: 0;
  }

  .app-content {
    padding: 20px 16px 32px;
  }

  .nav-scrim {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 19;
    background: rgba(19, 40, 60, 0.42);
  }
}

@media (prefers-reduced-motion: no-preference) {
  .app-sidebar {
    transition: transform 0.18s ease;
  }

  .nav-item {
    transition: background-color 0.15s ease, color 0.15s ease;
  }
}
</style>
