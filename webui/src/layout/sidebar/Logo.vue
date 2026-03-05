<template>
  <div class="sidebar-logo-container">
    <div class="logo-wrapper">
      <img src="/logo-kucuk.png" class="anomivox-logo" alt="Anomivox" />
      <span class="sidebar-title">{{ title }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, toRefs } from 'vue'
import { useBasicStore } from '@/store/basic'
const { settings } = useBasicStore()
defineProps({
  collapse: {
    type: Boolean,
    required: true
  }
})
const state = reactive({
  title: settings.title || 'Anomivox',
})
const { title } = toRefs(state)
</script>

<style lang="scss" scoped>
.sidebar-logo-container {
  width: 100%;
  overflow: hidden;

  .logo-wrapper {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 2px;
  }

  .anomivox-logo {
    width: 32px;
    height: 32px;
    flex-shrink: 0;
  }

  .sidebar-title {
    font-weight: 700;
    font-size: 16px;
    letter-spacing: -0.3px;
    color: var(--sidebar-logo-title-color, #0F172A);
    white-space: nowrap;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }
}
</style>
