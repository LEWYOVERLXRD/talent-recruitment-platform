<template>
  <div class="auth-container">
    <el-card class="auth-card" shadow="hover">
      <template #header>
        <h2 class="auth-title">智能招聘平台 · 登录</h2>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <div class="forgot-row">
          <router-link class="forgot-link" to="/forgot-password">忘记密码？</router-link>
        </div>

        <el-form-item>
          <el-checkbox v-model="agreed">
            我已阅读并同意
            <a class="agreement-link" @click.prevent="openAgreement('service')">《服务协议》</a>
            和
            <a class="agreement-link" @click.prevent="openAgreement('privacy')">《隐私政策》</a>
          </el-checkbox>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            class="submit-btn"
            :loading="loading"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>

        <div class="auth-footer">
          还没有账号？
          <router-link to="/register">立即注册</router-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)
const agreed = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '长度在 3 到 50 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 50, message: '长度在 6 到 50 个字符', trigger: 'blur' },
  ],
}

function openAgreement(type) {
  const url = router.resolve({ name: 'Agreement', params: { type } }).href
  window.open(url, '_blank')
}

async function handleLogin() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch (e) {
    return // 校验不通过
  }

  if (!agreed.value) {
    ElMessage.warning('请先阅读并同意《服务协议》和《隐私政策》')
    return
  }

  loading.value = true
  try {
    await userStore.login({ ...form })
    ElMessage.success('登录成功')
    // 登录成功跳首页（或 redirect 参数指向的页面）
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (err) {
    ElMessage.error(err || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #f5f7fa;
  padding: 20px;
}

.auth-card {
  width: 100%;
  max-width: 400px;
}

.auth-title {
  text-align: center;
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.forgot-row {
  display: flex;
  justify-content: flex-end;
  margin: -8px 0 12px;
}

.forgot-link {
  font-size: 13px;
  color: #409eff;
  text-decoration: none;
}

.forgot-link:hover {
  text-decoration: underline;
}

.agreement-link {
  color: #409eff;
  cursor: pointer;
}

.agreement-link:hover {
  text-decoration: underline;
}

.submit-btn {
  width: 100%;
}

.auth-footer {
  text-align: center;
  font-size: 14px;
  color: #606266;
}

.auth-footer a {
  color: #409eff;
  text-decoration: none;
}

.auth-footer a:hover {
  text-decoration: underline;
}
</style>