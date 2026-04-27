<template>
  <a-layout class="app-shell">
    <a-layout-header class="app-header">
      <div class="brand">
        <span class="brand-mark">TA</span>
        <span>基于 LangGraph 多智能体协作的 AI 旅行规划系统</span>
      </div>
    </a-layout-header>
    <a-layout-content>
      <router-view />
    </a-layout-content>
  </a-layout>
</template>

<script setup lang="ts">
</script>

<style>
body {
  margin: 0;
  background: #f5f7fb;
}

#app {
  min-height: 100vh;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
  color: #0f172a;
}

.app-shell {
  min-height: 100vh;
}

.app-header {
  height: 56px;
  padding: 0 28px;
  display: flex;
  align-items: center;
  background: #0f172a;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #ffffff;
  font-weight: 800;
}

.brand-mark {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #0f766e;
  color: #ffffff;
  font-size: 12px;
}

.ant-btn {
  border-radius: 8px;
}

.ant-input,
.ant-picker,
.ant-select-selector,
.ant-input-number,
.ant-segmented {
  border-radius: 8px !important;
}
</style>
