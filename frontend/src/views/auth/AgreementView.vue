<template>
  <div class="agreement-container">
    <el-card class="agreement-card" shadow="never">
      <template #header>
        <div class="header-row">
          <h2 class="doc-title">{{ doc.title }}</h2>
          <el-button text type="primary" @click="handleBack">返回</el-button>
        </div>
      </template>

      <p class="meta">更新日期：2026-09-22　生效日期：2026-09-22</p>

      <section v-for="(section, index) in doc.sections" :key="index" class="section">
        <h3 class="section-title">{{ section.heading }}</h3>
        <p v-for="(para, pIndex) in section.paragraphs" :key="pIndex" class="para">
          {{ para }}
        </p>
      </section>
    </el-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const DOCS = {
  service: {
    title: '智能招聘平台服务协议',
    sections: [
      {
        heading: '一、协议说明',
        paragraphs: [
          '欢迎使用智能招聘平台（以下简称“本平台”）。本平台为高校毕业设计项目，面向企业招聘方、猎头与求职者提供岗位发布、简历投递与智能匹配等信息的在线服务。',
          '在使用本平台前，请您完整阅读本协议。注册账号或登录使用本平台，即表示您已阅读、理解并同意本协议全部内容。',
        ],
      },
      {
        heading: '二、账号与身份',
        paragraphs: [
          '用户注册时需选择身份（企业招聘方 / 猎头 / 求职者），并如实填写注册信息。企业招聘方需填写所属企业名称：该企业尚无成员时，注册者成为企业主管；企业已存在时，注册者以普通员工身份加入该企业。',
          '账号仅供本人使用，请妥善保管用户名、密码及密保问题答案。因用户保管不当导致账号被他人使用所产生的后果，由用户自行承担。',
          '平台管理员账号不开放注册，由平台在系统初始化时创建，用于企业管理与账号状态维护。',
        ],
      },
      {
        heading: '三、使用规范',
        paragraphs: [
          '用户应保证发布的信息（岗位信息、企业信息、简历信息等）真实、准确、合法，不得发布虚假招聘信息、不得含有歧视性内容，不得侵犯他人合法权益。',
          '用户不得利用本平台从事任何违反法律法规的活动，不得干扰平台正常运行，不得尝试越权访问他人数据。',
          '企业主管可在本企业范围内管理员工账号的启用与禁用；平台管理员可管理全部账号。账号被禁用后，已登录的会话将立即失效。',
        ],
      },
      {
        heading: '四、服务变更与终止',
        paragraphs: [
          '本平台为教学研究用途，服务内容可能随开发进度调整。对于违反本协议的用户，平台有权限制或终止其账号使用。',
        ],
      },
    ],
  },
  privacy: {
    title: '智能招聘平台隐私政策',
    sections: [
      {
        heading: '一、我们收集的信息',
        paragraphs: [
          '注册信息：用户名、密码（以加密哈希形式存储，平台不保存明文密码）、真实姓名、邮箱、手机号，以及您选择填写的所属企业名称与身份。',
          '密保信息：您设置的 3 道密保问题及对应答案。答案同样以哈希形式存储，仅用于您忘记密码时验证身份。',
          '使用信息：登录与业务操作产生的必要记录，用于权限校验与问题排查。',
        ],
      },
      {
        heading: '二、信息的使用',
        paragraphs: [
          '我们将上述信息用于：账号创建与登录认证、按身份展示对应的功能与数据范围、企业内部的成员管理，以及您主动发起的密码重置。',
          '平台不会将您的个人信息用于与招聘服务无关的用途。',
        ],
      },
      {
        heading: '三、信息的共享',
        paragraphs: [
          '企业主管在管理本企业员工时，可查看本企业成员的账号、姓名、邮箱、手机号与企业内角色；跨企业数据相互隔离，不可互相查看。',
          '除法律法规要求外，平台不会向第三方提供您的个人信息。',
        ],
      },
      {
        heading: '四、信息的存储与保护',
        paragraphs: [
          '账号密码与密保答案均采用不可逆哈希算法存储。为防范密保答案被暴力猜测，连续答错达到上限后账号将被临时锁定。',
          '本平台为毕业设计项目，数据仅用于教学演示，请勿在平台上填写真实敏感信息。',
        ],
      },
      {
        heading: '五、您的权利',
        paragraphs: [
          '您可以随时通过“忘记密码”流程使用密保问题重置密码，也可以联系平台管理员申请停用账号。',
        ],
      },
    ],
  },
}

// 路由参数决定展示哪份文档，未知参数回落到服务协议
const doc = computed(() => DOCS[route.params.type] || DOCS.service)

function handleBack() {
  // 从新标签页打开时无来源历史，回落到登录页
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push({ name: 'Login' })
  }
}
</script>

<style scoped>
.agreement-container {
  min-height: 100vh;
  background: var(--app-canvas);
  padding: 32px 20px;
}

.agreement-card {
  max-width: 820px;
  margin: 0 auto;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.doc-title {
  margin: 0;
  font-size: 20px;
  color: var(--app-text);
}

.meta {
  margin: 0 0 20px;
  font-size: 13px;
  color: var(--app-muted);
}

.section {
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 8px;
  font-size: 15px;
  color: var(--app-text);
}

.para {
  margin: 0 0 8px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--app-muted);
}
</style>