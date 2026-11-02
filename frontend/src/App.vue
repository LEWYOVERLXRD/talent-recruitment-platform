<template>
  <AppLayout v-if="$route.meta.requiresAuth">
    <el-result
      v-if="accessDenied"
      icon="warning"
      title="403"
      sub-title="当前账号无权访问此页面"
    >
      <template #extra>
        <el-button type="primary" @click="$router.push({ name: 'Home' })">返回工作台</el-button>
      </template>
    </el-result>
    <router-view v-else />
  </AppLayout>
  <router-view v-else />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import AppLayout from '@/layouts/AppLayout.vue'

const route = useRoute()
const userStore = useUserStore()
const accessDenied = computed(
  () => route.meta.roles && !route.meta.roles.includes(userStore.role),
)
</script>
