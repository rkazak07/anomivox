<template>
  <div class="sidebar-logo-container" :class="{ 'collapse': collapse }">
    <transition name="sidebar-logo-fade">
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
          
          <!-- Background Squircle -->
          <rect x="10" y="10" width="100" height="100" rx="28" fill="url(#bgGrad)" />
          
          <!-- Soundwave / Pulse / Anomaly Spike -->
          <path d="M 25 60 L 40 60 L 50 35 L 65 85 L 75 60 L 95 60" 
                fill="none" 
                stroke="url(#pulseGrad)" 
                stroke-width="8" 
                stroke-linecap="round" 
                stroke-linejoin="round" 
                filter="url(#glow)" />
                
          <!-- AI Sparkles / Dots -->
          <circle cx="50" cy="35" r="4" fill="#38BDF8" filter="url(#glow)" />
          <circle cx="65" cy="85" r="4" fill="#E879F9" filter="url(#glow)" />
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
    color: var(--sidebar-logo-title-color, #0F172A);
    font-weight: 800;
    line-height: 60px;
    font-size: 22px;
    letter-spacing: -0.5px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
    white-space: nowrap;
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
