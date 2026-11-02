<template>
  <div class="auth-container">
    <el-card class="auth-card" shadow="hover">
      <template #header>
        <h2 class="auth-title">智能招聘平台 · 找回密码</h2>
      </template>

      <el-steps :active="step" align-center finish-status="success" class="steps">
        <el-step title="验证账号" />
        <el-step title="回答密保问题" />
      </el-steps>

      <!-- 第一步：输入账号，取回密保问题 -->
      <el-form
        v-if="step === 0"
        ref="accountFormRef"
        :model="accountForm"
        :rules="accountRules"
        label-position="top"
        @submit.prevent="handleFetchQuestions"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="accountForm.username"
            placeholder="请输入注册时使用的用户名"
            :prefix-icon="User"
            clearable
            @keyup.enter="handleFetchQuestions"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            class="submit-btn"
            :loading="loading"
            @click="handleFetchQuestions"
          >
            下一步
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 第二步：回答密保问题 + 设置新密码 -->
      <el-form
        v-else
        ref="resetFormRef"
        :model="resetForm"
        :rules="resetRules"
        label-position="top"
        @submit.prevent="handleReset"
      >
        <el-form-item
          v-for="(item, index) in resetForm.answers"
          :key="item.question_code"
          :label="`${index + 1}. ${item.question_text}`"
          :prop="`answers.${index}.answer`"
          :rules="[{ required: true, message: '请填写答案', trigger: 'blur' }]"
        >
          <el-input v-model="item.answer" placeholder="请输入答案" clearable />
        </el-form-item>

        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="resetForm.new_password"
            type="password"
            placeholder="6-50 位字符"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="resetForm.confirmPassword"
            type="password"
            placeholder="请再次输入新密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-alert
          v-if="locked"
          class="lock-tip"
          type="error"
          :closable="false"
          show-icon
          title="密保校验失败次数过多，账号已被临时锁定，请稍后再试。"
        />

        <el-form-item>
          <div class="btn-row">
            <el-button :disabled="loading" @click="backToAccount">返回上一步</el-button>
            <el-button
              type="primary"
              :loading="loading"
              :disabled="locked"
              @click="handleReset"
            >
              重置密码
            </el-button>
          </div>
        </el-form-item>
      </el-form>

      <div class="auth-footer">
        想起密码了？
        <router-link to="/login">返回登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { getSecurityQuestions, resetPassword } from '@/api/auth'

const router = useRouter()

const step = ref(0)
const loading = ref(false)
const locked = ref(false)

const accountFormRef = ref(null)
const resetFormRef = ref(null)

const accountForm = reactive({ username: '' })

// 第二步表单：answers 由后端返回的题目填充
const resetForm = reactive({
  answers: [],
  new_password: '',
  confirmPassword: '',
})

const accountRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '长度在 3 到 50 个字符', trigger: 'blur' },
  ],
}

const validateConfirm = (rule, value, callback) => {
  if (value !== resetForm.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const resetRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 50, message: '长度在 6 到 50 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

// 第一步：按账号取密保问题（404 账号不存在 / 400 未设密保由后端返回文案）
async function handleFetchQuestions() {
  if (!accountFormRef.value) return
  try {
    await accountFormRef.value.validate()
  } catch (e) {
    return
  }

  loading.value = true
  try {
    const data = await getSecurityQuestions(accountForm.username)
    resetForm.answers = (data.questions || []).map((q) => ({
      question_code: q.question_code,
      question_text: q.question_text,
      answer: '',
    }))
    resetForm.new_password = ''
    resetForm.confirmPassword = ''
    locked.value = false
    step.value = 1
  } catch (err) {
    ElMessage.error(err || '获取密保问题失败')
  } finally {
    loading.value = false
  }
}

// 第二步：答对全部密保问题才能改密码
async function handleReset() {
  if (!resetFormRef.value) return
  try {
    await resetFormRef.value.validate()
  } catch (e) {
    return
  }

  loading.value = true
  try {
    await resetPassword({
      username: accountForm.username,
      answers: resetForm.answers.map((item) => ({
        question_code: item.question_code,
        answer: item.answer,
      })),
      new_password: resetForm.new_password,
    })
    ElMessage.success('密码重置成功，请使用新密码登录')
    router.push({ name: 'Login' })
  } catch (err) {
    const message = err || '密码重置失败'
    ElMessage.error(message)
    // 后端锁定账号时返回 423，文案含“锁定/分钟后再试”，此时禁止继续提交
    if (/锁定|分钟后再试/.test(message)) {
      locked.value = true
    }
  } finally {
    loading.value = false
  }
}

function backToAccount() {
  step.value = 0
  locked.value = false
}
</script>

<style scoped>
.auth-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--app-canvas);
  padding: 24px 20px;
}

.auth-card {
  width: 100%;
  max-width: 460px;
}

.auth-title {
  text-align: center;
  margin: 0;
  font-size: 20px;
  color: var(--app-text);
}

.steps {
  margin-bottom: 24px;
}

.lock-tip {
  margin-bottom: 18px;
}

.btn-row {
  display: flex;
  gap: 12px;
  width: 100%;
}

.btn-row .el-button {
  flex: 1;
}

.submit-btn {
  width: 100%;
}

.auth-footer {
  text-align: center;
  font-size: 14px;
  color: var(--app-muted);
  margin-top: 8px;
}

.auth-footer a {
  color: var(--app-primary);
  text-decoration: none;
}

.auth-footer a:hover {
  text-decoration: underline;
}
</style>