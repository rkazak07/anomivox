<template>
  <div class="sidebar-logo-container" :class="{ 'collapse': collapse }">
    <transition name="sidebar-logo-fade">
      <div class="logo-wrapper">
        <svg class="anomivox-logo" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:#4facfe;stop-opacity:1" />
              <stop offset="100%" style="stop-color:#00f2fe;stop-opacity:1" />
            </linearGradient>
          </defs>
          <circle cx="50" cy="50" r="45" fill="url(#grad1)" />
          <path d="M30 50 L45 65 L70 35" stroke="white" stroke-width="8" fill="none" stroke-linecap="round" stroke-linejoin="round" />
          <circle cx="70" cy="35" r="6" fill="white" />
          <path d="M30 70 L70 70" stroke="rgba(255,255,255,0.5)" stroke-width="4" stroke-linecap="round" />
        </svg>
        <h1 v-if="!collapse" class="sidebar-title">{{ title }}</h1>
      </div>
    </transition>
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
  position: relative;
  width: 100%;
  height: 60px;
  line-height: 60px;
  background: transparent;
  text-align: center;
  overflow: hidden;
  padding: 0 10px;
  transition: all 0.3s;
  
  &.collapse {
    padding: 0;
    .logo-wrapper {
      justify-content: center;
    }
  }

  .logo-wrapper {
    display: flex;
    align-items: center;
    height: 100%;
    width: 100%;
    gap: 12px;
  }

  .anomivox-logo {
    width: 36px;
    height: 36px;
    flex-shrink: 0;
    filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
    transition: transform 0.3s ease;
    
    &:hover {
      transform: scale(1.05);
    }
  }

  .sidebar-title {
    display: inline-block;
    margin: 0;
    color: #2c3e50;
    font-weight: 700;
    line-height: 60px;
    font-size: 20px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
    white-space: nowrap;
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
}

.sidebar-logo-fade-enter-active {
  transition: opacity 1.5s;
}

.sidebar-logo-fade-enter,
.sidebar-logo-fade-leave-to {
  opacity: 0;
}
</style>
