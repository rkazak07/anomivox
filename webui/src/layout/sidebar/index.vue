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
      <div class="columnCC"
           style="margin-bottom: 10px; cursor: pointer; background: RGBA(232, 231, 230, 1.00); padding: 2px; border-radius: 8px"
           @click="onThemeClick">
        <svg class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="14888" width="40"
             height="40">
          <path d="M298.35 84.69h427.3a213.65 213.65 0 0 1 213.66 213.66v427.3a213.65 213.65 0 0 1-213.66 213.66H298.34A213.65 213.65 0 0 1 84.69 725.66V298.35A213.66 213.66 0 0 1 298.35 84.69z" fill="#E8E7E6" p-id="14889"/><path d="M792 504.56l-1.34 0.05C777.09 368.79 662.9 262.74 524 262.74c-144.77 0-262.71 115.19-267.82 259.21h23.91l-24 0.81c-3.76 125 67.29 236.09 201.55 273s112.74-61.85 100.78-69.09-20.39-26.83-9.83-49.35 19.64-21.31 68.82-22.21C750.85 657.28 782.39 562 789.75 522h2.06c-0.12-3.29-0.31-6.57-0.54-9.83 0.58-4.83 0.73-7.61 0.73-7.61z m-434 29.65a48.1 48.1 0 1 1 47.84-48.1 48 48 0 0 1-47.84 48.1z m88.6-116.07a48 48 0 1 1 47.95-48 48 48 0 0 1-47.93 48z m150 2.53a48.1 48.1 0 1 1 47.85-48.1 48 48 0 0 1-47.85 48.1z m93.26 113.54a48.1 48.1 0 1 1 47.95-48.1 48 48 0 0 1-47.95 48.1z" fill="#DD4F47" p-id="14890"/></svg>
      </div>
      <div class="columnCC" style="padding-bottom: 20px;">
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

const themeList = ['lighting-theme', 'china-red']

setTimeout(() => {
  import('@/store/config').then((res) => {
    useConfigStore = res.useConfigStore
    currentLang.value = useConfigStore().language
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
  setTheme(themeList[(themeList.indexOf(theme) + 1) % themeList.length])
  console.log('change theme:', theme)
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

.lang-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.1);
  padding: 8px 16px;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #a3b1c6;
  font-weight: 600;
  font-size: 14px;
  
  &:hover {
    background: rgba(255, 255, 255, 0.2);
    color: #ffffff;
  }

  span {
    transition: color 0.3s ease;
    &.active {
      color: #38bdf8;
    }
  }

  .divider {
    margin: 0 8px;
    opacity: 0.5;
  }
}
</style>
