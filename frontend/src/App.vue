<template>
  <div>
    <Header />
  </div>

  <router-view />

  
</template>

<script setup>
// 仅作为路由出口，不做其他逻辑
import Header from '@/views/common/Header.vue'
</script>

<style>
/* 全局样式重置（轻量，不依赖 reset.css） */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body,
#app {
  height: 100%;
  width: 100%;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    'Helvetica Neue', Arial, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', sans-serif;
  color: #303133;
  background: #fff;
}
</style>
