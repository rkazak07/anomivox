<template>
  <div class="layout-wrapper" :class="{ hideSidebar: !settings.showLeftMenu }">
    <!--left side-->
    <Sidebar v-if="settings.showLeftMenu" class="sidebar-container" />
    <!--right container-->
    <div class="main-container">
      <AppMain />
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import Sidebar from './sidebar/index.vue'
import AppMain from './app-main/index.vue'
import { useBasicStore } from '@/store/basic'
import { resizeHandler } from '@/hooks/use-layout'
const { sidebar, settings } = useBasicStore()
resizeHandler()
</script>

<style lang="scss" scoped>
.main-container {
  min-height: 100%;
  transition: margin-left var(--sideBar-switch-duration);
  margin-left: var(--side-bar-width);
  margin-top: var(--app-main-padding);
  margin-bottom: var(--app-main-padding);
  margin-right: var(--app-main-padding);
  position: relative;
  border-radius: 15px;
  overflow: auto;
  border: 1px solid var(--el-border-color-light);
}
.sidebar-container {
  transition: width var(--sideBar-switch-duration);
  width: var(--side-bar-width) !important;
  background-color: var(--body-background) !important;
  height: 100%;
  position: fixed;
  font-size: 0;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 1001;
  overflow: hidden;
}
.hideSidebar {
  .sidebar-container {
    width: 0 !important;
  }
  .main-container {
    margin-left: 0;
  }
}
</style>
