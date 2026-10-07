<template>
  <div class="auth-container">
    <el-card class="auth-card" shadow="hover">
      <template #header>
        <h2 class="auth-title">智能招聘平台 · 注册</h2>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleRegister"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="3-50 位字符，登录时使用"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="6-50 位字符"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item label="真实姓名" prop="real_name">
          <el-input v-model="form.real_name" placeholder="请输入真实姓名" clearable />
        </el-form-item>

        <el-form-item label="身份" prop="role">
          <el-radio-group v-model="form.role" @change="handleRoleChange">
            <el-radio-button value="recruiter">企业招聘方</el-radio-button>
            <el-radio-button value="headhunter">猎头</el-radio-button>
            <el-radio-button value="jobseeker">求职者</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 招聘方需要归属企业：首位注册者建企业并成为主管 -->
        <template v-if="form.role === 'recruiter'">
          <el-form-item label="所属企业名称" prop="company_name">
            <el-input
              v-model="form.company_name"
              placeholder="如：××科技有限公司"
              clearable
            />
          </el-form-item>
          <el-alert
            class="role-tip"
            type="info"
            :closable="false"
            show-icon
            title="该企业尚未有成员时，你将成为企业主管（可管理本企业员工）；若企业已存在，你将以普通员工身份加入。"
          />
        </template>

        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="选填" clearable />
        </el-form-item>

        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="选填" clearable />
        </el-form-item>

        <el-divider content-position="left">密保问题（用于找回密码）</el-divider>

        <el-form-item
          v-for="(item, index) in form.security_answers"
          :key="index"
          :label="`问题 ${index + 1}`"
          :prop="`security_answers.${index}.answer`"
          :rules="[
            { required: true, message: '请填写密保答案', trigger: 'blur' },
            { max: 50, message: '长度不超过 50 个字符', trigger: 'blur' },
          ]"
        >
          <div class="security-row">
            <el-select v-model="item.question_code" placeholder="请选择问题" style="width: 100%">
              <el-option
                v-for="q in securityQuestions"
                :key="q.code"
                :label="q.text"
                :value="q.code"
                :disabled="isQuestionUsed(q.code, index)"
              />
            </el-select>
            <el-input v-model="item.answer" placeholder="请输入答案" clearable />
          </div>
        </el-form-item>

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
            @click="handleRegister"
          >
            注册
          </el-button>
        </el-form-item>

        <div class="auth-footer">
          已有账号？
          <router-link to="/login">去登录</router-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

// 与后端 SECURITY_QUESTIONS 保持一致的题目文案
const securityQuestions = [
  { code: 'primary_school', text: '你就读的第一所小学叫什么名字？' },
  { code: 'mother_name', text: '你母亲的姓名是什么？' },
  { code: 'birth_city', text: '你出生的城市是哪个？' },
]

const formRef = ref(null)
const loading = ref(false)
const agreed = ref(false)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  real_name: '',
  email: '',
  phone: '',

  role: 'recruiter',
  company_name: '',
  // 固定 3 题，默认按顺序取三题
  security_answers: securityQuestions.map((q) => ({
    question_code: q.code,
    answer: '',
  })),
})

// 该题目是否已被其他行占用（保证 3 道题不重复）
function isQuestionUsed(code, currentIndex) {
  return form.security_answers.some(
    (item, index) => index !== currentIndex && item.question_code === code,
  )
}

// 切换身份时清掉无关字段，避免残留脏数据
function handleRoleChange(value) {
  if (value !== 'recruiter') {
    form.company_name = ''
  }
}

// 确认密码校验
const validateConfirm = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '长度在 3 到 50 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 50, message: '长度在 6 到 50 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
  real_name: [{ max: 50, message: '长度不超过 50 个字符', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
  role: [{ required: true, message: '请选择身份', trigger: 'change' }],
  company_name: [
    { required: true, message: '请输入所属企业名称', trigger: 'blur' },
    { max: 100, message: '长度不超过 100 个字符', trigger: 'blur' },
  ],
}

// 协议页在路由里按 meta.type 区分内容，用新标签页打开便于对照表单
function openAgreement(type) {
  const url = router.resolve({ name: 'Agreement', params: { type } }).href
  window.open(url, '_blank')
}

async function handleRegister() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }

  if (!agreed.value) {
    ElMessage.warning('请先阅读并同意《服务协议》和《隐私政策》')
    return
  }

  loading.value = true
  try {
    // 只提交后端接受的字段
    const payload = {
      username: form.username,
      password: form.password,
      real_name: form.real_name || null,
      email: form.email || null,
      phone: form.phone || null,
      role: form.role,
      company_name: form.role === 'recruiter' ? form.company_name : null,
      security_answers: form.security_answers.map((item) => ({
        question_code: item.question_code,
        answer: item.answer,
      })),
    }
    await userStore.register(payload)
    ElMessage.success('注册成功，已自动登录')
    router.push('/')
  } catch (err) {
    ElMessage.error(err || '注册失败')
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
  padding: 24px 20px;
}

.auth-card {
  width: 100%;
  max-width: 560px;
}

.auth-title {
  text-align: center;
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.role-tip {
  margin-bottom: 18px;
}

.security-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  width: 100%;
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