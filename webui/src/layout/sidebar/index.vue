<template>
  <div id="Sidebar" class="reset-menu-style columnBC relative">

    <div class="columnSC">
      <!--logo-->
      <Logo :collapse="true" style="margin: 20px 0; flex-shrink: 0" />
      <!--router menu-->
      <div class="columnSC" style="width: 100%; height: 100%; overflow-y: scroll; position: relative">
        <sidebar-item v-for="route in allRoutes" :key="route.path" :item="route" :base-path="route.path" :active-path="activeMenu" />
      </div>
    </div>

    <div class="columnCC">
      <div class="theme-toggle" @click="onThemeClick">
        <svg v-if="currentTheme === 'lighting-theme'" class="icon" viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
        <svg v-else class="icon" viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
          <line x1="1" y1="12" x2="3" y2="12"></line>
          <line x1="21" y1="12" x2="23" y2="12"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
      </div>
      <div class="columnCC" style="padding-bottom: 24px;">
        <div class="lang-toggle" @click="onLanguageClick">
          <span :class="{ active: currentLang === 'en' }">EN</span>
          <span class="divider">/</span>
          <span :class="{ active: currentLang === 'tr' }">TR</span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia/dist/pinia'
import { useRoute } from 'vue-router'
import Logo from './Logo.vue'
import SidebarItem from './SidebarItem.vue'
import { useBasicStore } from '@/store/basic'
const { allRoutes } = storeToRefs(useBasicStore())
const routeInstance = useRoute()
let useConfigStore = reactive({})
const currentLang = ref('tr')
const currentTheme = ref('lighting-theme')

const themeList = ['lighting-theme', 'dark']

setTimeout(() => {
  import('@/store/config').then((res) => {
    useConfigStore = res.useConfigStore
    currentLang.value = useConfigStore().language
    currentTheme.value = useConfigStore().theme
  })
}, 300)

const activeMenu = computed(() => {
  const { meta, path } = routeInstance
  // if set path, the sidebar will highlight the path you set
  if (meta.activeMenu) {
    return meta.activeMenu
  }
  return path
})

const onLanguageClick = () => {
  const { language, setLanguage } = useConfigStore()
  const newLang = language === 'tr' ? 'en' : 'tr'
  setLanguage(newLang)
  currentLang.value = newLang
}
const onThemeClick = () => {
  const { theme, setTheme } = useConfigStore()
  const newTheme = themeList[(themeList.indexOf(theme) + 1) % themeList.length]
  setTheme(newTheme)
  currentTheme.value = newTheme
  console.log('change theme:', newTheme)
}

</script>
<style lang="scss">
//fix open the item style issue
.el-menu-vertical {
  width: var(--side-bar-width);
}
.reset-menu-style {
  border-right: 1px solid var(--side-bar-border-right-color);
  background-color: var(--el-menu-bg-color);
}

.theme-toggle {
  margin-bottom: 16px;
  cursor: pointer;
  background: var(--el-fill-color-light, #F1F5F9);
  padding: 8px;
  border-radius: 12px;
  transition: all 0.3s ease;
  color: var(--el-text-color-regular, #64748B);
  display: flex;
  align-items: center;
  justify-content: center;
  
  &:hover {
    background: var(--el-fill-color, #E2E8F0);
    color: var(--el-color-primary, #0284C7);
  }
}

.lang-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-light, #F1F5F9);
  padding: 8px 16px;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  color: var(--el-text-color-regular, #64748B);
  font-weight: 600;
  font-size: 14px;
  border: 1px solid var(--el-border-color-light, #E2E8F0);
  
  &:hover {
    background: var(--el-fill-color, #E2E8F0);
    color: var(--el-text-color-primary, #0F172A);
  }

  span {
    transition: color 0.3s ease;
    &.active {
      color: var(--el-color-primary, #0284C7);
    }
  }

  .divider {
    margin: 0 8px;
    opacity: 0.5;
  }
}
</style>
