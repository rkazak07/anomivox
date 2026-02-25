<template>
  <div class="sidebar-logo-container">
    <div class="logo-wrapper">
      <svg class="anomivox-logo" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#0F172A" />
            <stop offset="100%" stop-color="#1E293B" />
          </linearGradient>
          <linearGradient id="pulseGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#38BDF8" />
            <stop offset="50%" stop-color="#818CF8" />
            <stop offset="100%" stop-color="#E879F9" />
          </linearGradient>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
        <rect x="10" y="10" width="100" height="100" rx="28" fill="url(#bgGrad)" />
        <path d="M 25 60 L 40 60 L 50 35 L 65 85 L 75 60 L 95 60"
              fill="none" stroke="url(#pulseGrad)" stroke-width="8"
              stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)" />
        <circle cx="50" cy="35" r="4" fill="#38BDF8" filter="url(#glow)" />
        <circle cx="65" cy="85" r="4" fill="#E879F9" filter="url(#glow)" />
      </svg>
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
