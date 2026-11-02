<template>
  <div class="app-page home-page">
    <div class="page-head">
      <div>
        <h1>{{ heading }}</h1>
        <p class="page-sub">{{ subheading }}</p>
      </div>
      <div class="page-actions">
        <el-button v-for="action in actions" :key="action.name" :type="action.primary ? 'primary' : 'default'" @click="go(action.name)">
          {{ action.label }}
        </el-button>
      </div>
    </div>

    <!-- 猎头工作台 -->
    <template v-if="userStore.isHeadhunter">
      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <h2 class="card-title">招聘协作流程</h2>
            <span class="muted">从已获授权的需求开始</span>
          </div>
        </template>
        <div class="journey">
          <div class="journey-step">
            <span class="step-num">01</span>
            <strong>承接需求</strong>
            <p>接受客户定向邀请，确认当前需求版本。</p>
            <el-button link type="primary" class="link-btn" @click="go('Assignments')">查看我的任务</el-button>
          </div>
          <div class="journey-step">
            <span class="step-num">02</span>
            <strong>整理候选人</strong>
            <p>维护档案、简历版本，追加沟通记录。</p>
            <el-button link type="primary" class="link-btn" @click="go('Candidates')">进入候选人管理</el-button>
          </div>
          <div class="journey-step">
            <span class="step-num">03</span>
            <strong>核对匹配依据</strong>
            <p>在候选人详情中检查技能与人岗匹配。</p>
            <el-button link type="primary" class="link-btn" @click="go('Candidates')">查看候选人</el-button>
          </div>
          <div class="journey-step">
            <span class="step-num">04</span>
            <strong>推荐并跟进</strong>
            <p>核对交付材料，跟进客户与面试反馈。</p>
            <el-button link type="primary" class="link-btn" @click="go('Recommendations')">进入推荐交付</el-button>
          </div>
        </div>
      </el-card>

      <div class="home-grid">
        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <h2 class="card-title">我的任务</h2>
              <el-button link type="primary" @click="go('Assignments')">查看全部</el-button>
            </div>
          </template>

          <el-alert
            v-if="tasksError"
            class="mb"
            type="error"
            :closable="false"
            show-icon
            :title="tasksError"
          />

          <div v-loading="tasksLoading" class="task-list">
            <article v-for="task in tasks" :key="task.id" class="task-row">
              <div class="task-main">
                <strong>{{ task.job_snapshot?.title || `需求 #${task.job_id}` }}</strong>
                <span>需求版本 v{{ task.job_version }} · 第 {{ task.round_no }} 轮</span>
              </div>
              <div class="task-meta">
                <el-tag :type="assignmentTag(task.status)" size="small">
                  {{ assignmentText(task.status) }}
                </el-tag>
                <el-tag
                  v-if="task.status === 'active' && !task.has_current_authorization"
                  type="warning"
                  size="small"
                >
                  授权失效
                </el-tag>
                <el-button link type="primary" @click="goTask(task)">查看任务</el-button>
              </div>
            </article>

            <el-empty
              v-if="!tasksLoading && !tasks.length && !tasksError"
              description="暂无已授权的需求承接"
            >
              <el-button type="primary" plain @click="go('Assignments')">去我的任务查看</el-button>
            </el-empty>
          </div>
        </el-card>

        <div class="home-side">
          <el-card shadow="never">
            <template #header><h2 class="card-title">常用入口</h2></template>
            <div class="entry-list">
              <button type="button" class="entry-item" @click="go('Candidates')">
                <span>候选人管理<small>档案、简历、技能与沟通</small></span>
                <el-icon><ArrowRight /></el-icon>
              </button>
              <button type="button" class="entry-item" @click="go('Recommendations')">
                <span>推荐交付<small>交付材料与反馈历史</small></span>
                <el-icon><ArrowRight /></el-icon>
              </button>
              <button type="button" class="entry-item" @click="go('Applications')">
                <span>候选人投递<small>查看求职者投递并筛选推荐</small></span>
                <el-icon><ArrowRight /></el-icon>
              </button>
              <button type="button" class="entry-item" @click="go('Agency')">
                <span>我的机构<small>查看机构与成员协作</small></span>
                <el-icon><ArrowRight /></el-icon>
              </button>
            </div>
          </el-card>

          <div class="hint-panel">
            <strong>每次交付，保留当时的材料</strong>
            推荐提交后，客户查看的是固定交付材料；后续更新档案不会改写已经交付的内容。
          </div>
        </div>
      </div>
    </template>

    <!-- 管理员工作台 -->
    <template v-else-if="userStore.isAdmin">
      <div class="entry-grid">
        <el-card v-for="entry in adminEntries" :key="entry.name" shadow="never" class="entry-card">
          <button type="button" class="entry-card-btn" @click="go(entry.name)">
            <span class="entry-icon" aria-hidden="true"><el-icon><component :is="entry.icon" /></el-icon></span>
            <span class="entry-copy">
              <strong>{{ entry.title }}</strong>
              <small>{{ entry.desc }}</small>
            </span>
            <el-icon class="entry-arrow"><ArrowRight /></el-icon>
          </button>
        </el-card>
      </div>

      <div class="hint-panel">
        <strong>核验范围</strong>
        企业核验为只读页面，不提供企业编辑、审批或成员角色调整；推荐核验含历史待核验记录，不代替猎头交付或客户反馈。
      </div>
    </template>

    <!-- 客户招聘方工作台 -->
    <template v-else-if="userStore.user?.role === 'recruiter'">
      <el-alert
        v-if="!userStore.user?.company_id"
        type="info"
        :closable="false"
        show-icon
        title="你的账号尚未加入企业。请进入“企业成员”处理主管发来的邀请，入企后再开展招聘业务。"
      >
        <template #default>
          <el-button type="primary" size="small" class="mt-8" @click="go('Company')">前往企业成员</el-button>
        </template>
      </el-alert>

      <template v-else>
        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <h2 class="card-title">当前企业</h2>
              <el-tag :type="userStore.isManager ? 'warning' : 'info'" size="small">
                {{ userStore.isManager ? '企业主管' : '普通员工' }}
              </el-tag>
            </div>
          </template>
          <div class="company-summary">
            <strong>{{ userStore.user?.company_name }}</strong>
            <p>
              {{ userStore.isManager
                ? '主管可确认需求、定向邀请与撤权、确认完成，并管理本企业成员。'
                : '普通员工可查看本企业需求并提交推荐反馈；授权与成员管理由主管操作。' }}
            </p>
          </div>
        </el-card>

        <div class="entry-grid entry-grid-three">
          <el-card v-for="entry in recruiterEntries" :key="entry.name" shadow="never" class="entry-card">
            <button type="button" class="entry-card-btn" @click="go(entry.name)">
              <span class="entry-icon" aria-hidden="true"><el-icon><component :is="entry.icon" /></el-icon></span>
              <span class="entry-copy">
                <strong>{{ entry.title }}</strong>
                <small>{{ entry.desc }}</small>
              </span>
              <el-icon class="entry-arrow"><ArrowRight /></el-icon>
            </button>
          </el-card>
        </div>
      </template>
    </template>

    <!-- 求职者工作台 -->
    <template v-else>
      <div class="entry-grid entry-grid-three">
        <el-card shadow="never" class="entry-card"><button type="button" class="entry-card-btn" @click="go('Jobs')"><span class="entry-copy"><strong>岗位浏览</strong><small>查看开放岗位与职位详情</small></span><el-icon class="entry-arrow"><ArrowRight /></el-icon></button></el-card>
        <el-card shadow="never" class="entry-card"><button type="button" class="entry-card-btn" @click="go('JobseekerResume')"><span class="entry-copy"><strong>我的简历</strong><small>维护资料、上传和设置主简历</small></span><el-icon class="entry-arrow"><ArrowRight /></el-icon></button></el-card>
        <el-card shadow="never" class="entry-card"><button type="button" class="entry-card-btn" @click="go('Applications')"><span class="entry-copy"><strong>我的投递</strong><small>查看每个岗位的处理进度</small></span><el-icon class="entry-arrow"><ArrowRight /></el-icon></button></el-card>
      </div>
    </template>

    <el-card v-if="showAccountMeta" shadow="never" class="account-card">
      <div class="account-meta">
        <span>登录账号：{{ userStore.user?.username || '-' }}</span>
        <span>身份：{{ userStore.roleLabel }}</span>
        <span>企业：{{ userStore.user?.company_name || '未归属企业' }}</span>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  Briefcase,
  Document,
  OfficeBuilding,
  Promotion,
  Search,
  User,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { listAssignments } from '@/api/assignment'

const router = useRouter()
const userStore = useUserStore()

const tasks = ref([])
const tasksLoading = ref(false)
const tasksError = ref('')

const heading = computed(() => {
  if (userStore.isAdmin) return '平台核验工作台'
  if (userStore.isHeadhunter) return '招聘协作工作台'
  if (userStore.user?.role === 'recruiter') return '客户招聘工作台'
  return '工作台'
})

const subheading = computed(() => {
  if (userStore.isAdmin) return '核验客户企业、猎头机构、候选人与推荐记录，掌握平台业务归属。'
  if (userStore.isHeadhunter) return '从已获授权的招聘需求出发，整理候选人、核对匹配依据，再完成推荐交付。'
  if (userStore.user?.role === 'recruiter') {
    if (!userStore.user?.company_id) return '账号尚未加入企业，先处理主管发来的邀请。'
    return '查看本企业招聘需求与推荐反馈，按企业内角色开展协作。'
  }
  return '浏览开放岗位，完善个人简历并跟踪投递进度。'
})

const actions = computed(() => {
  if (userStore.isHeadhunter) {
    return [
      { name: 'Assignments', label: '我的任务' },
      { name: 'Candidates', label: '录入候选人', primary: true },
    ]
  }
  if (userStore.isAdmin) {
    return [
      { name: 'Companies', label: '企业核验', primary: true },
      { name: 'Recommendations', label: '推荐核验' },
    ]
  }
  if (userStore.user?.role === 'recruiter' && userStore.user?.company_id) {
    return [
      { name: 'Recommendations', label: '推荐反馈', primary: true },
      { name: 'Company', label: '企业成员' },
    ]
  }
  return []
})

const adminEntries = [
  { name: 'Companies', title: '企业核验', desc: '只读查看客户企业、招聘成员与启用主管', icon: OfficeBuilding },
  { name: 'Agencies', title: '机构管理', desc: '管理猎头机构与机构成员', icon: User },
  { name: 'Candidates', title: '候选人核验', desc: '查看平台候选人归属与异常记录', icon: Search },
  { name: 'Recommendations', title: '推荐核验', desc: '只读检查推荐快照与历史待核验记录', icon: Promotion },
  { name: 'Users', title: '用户管理', desc: '查看账号状态并启用或禁用账号', icon: Document },
]

const recruiterEntries = [
  { name: 'Jobs', title: '招聘需求', desc: '查看、发布与维护本企业需求', icon: Briefcase },
  { name: 'Assignments', title: '需求承接', desc: '查看猎头承接与授权状态', icon: Search },
  { name: 'Recommendations', title: '推荐反馈', desc: '查看固定交付材料并追加反馈', icon: Promotion },
]

const showAccountMeta = computed(
  () => userStore.user?.role === 'recruiter' || userStore.user?.role === 'jobseeker',
)

function go(name) {
  router.push({ name })
}

function goTask(task) {
  router.push({ name: 'AssignmentDetail', params: { id: task.id } })
}

function assignmentText(status) {
  return {
    invited: '待接受',
    active: '已承接',
    declined: '已拒绝',
    cancelled: '已撤销',
    completed: '已完成',
  }[status] || status
}

function assignmentTag(status) {
  return {
    invited: 'warning',
    active: 'success',
    declined: 'info',
    cancelled: 'danger',
    completed: 'success',
  }[status] || 'info'
}

async function loadTasks() {
  tasksLoading.value = true
  tasksError.value = ''
  try {
    const data = await listAssignments()
    tasks.value = Array.isArray(data) ? data : []
  } catch (error) {
    tasks.value = []
    tasksError.value = error.message || error || '任务加载失败'
  } finally {
    tasksLoading.value = false
  }
}

onMounted(() => {
  if (userStore.isHeadhunter) loadTasks()
})
</script>

<style scoped>
.home-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 292px;
  gap: 22px;
  align-items: start;
}

.home-side {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.task-list {
  min-height: 90px;
}

.task-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 15px 0;
  border-bottom: 1px solid #e9eef4;
}

.task-row:first-child {
  padding-top: 0;
}

.task-row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.task-main {
  min-width: 0;
}

.task-main strong {
  display: block;
  font-size: 15px;
  overflow-wrap: anywhere;
}

.task-main span {
  color: var(--app-muted);
  font-size: 12px;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.entry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.entry-grid-three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.entry-card :deep(.el-card__body) {
  padding: 0;
}

.entry-card-btn {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 20px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--app-text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.entry-card-btn:hover {
  background: #f5faf9;
}

.entry-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  flex: none;
  border-radius: 9px;
  background: var(--app-primary-soft);
  color: var(--app-primary);
  font-size: 20px;
}

.entry-copy {
  min-width: 0;
  flex: 1;
}

.entry-copy strong {
  display: block;
  font-size: 15px;
}

.entry-copy small {
  display: block;
  margin-top: 2px;
  color: var(--app-muted);
  font-size: 12px;
}

.entry-arrow {
  color: var(--app-muted);
  flex: none;
}

.company-summary strong {
  font-size: 18px;
}

.company-summary p {
  margin: 6px 0 0;
  color: var(--app-muted);
  font-size: 13px;
}

.account-card :deep(.el-card__body) {
  padding: 14px 22px;
}

.account-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  color: var(--app-muted);
  font-size: 12px;
}

.empty-note {
  max-width: 520px;
  margin: 0;
  color: var(--app-muted);
  font-size: 13px;
  line-height: 1.7;
}

.mt-8 {
  margin-top: 8px;
}

.mb {
  margin-bottom: 12px;
}

@media (max-width: 1150px) {
  .home-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .entry-grid-three {
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  }
}

@media (max-width: 800px) {
  .task-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .entry-grid,
  .entry-grid-three {
    grid-template-columns: minmax(0, 1fr);
  }

  .entry-card-btn {
    padding: 16px;
  }
}
</style>
