<template>
  <div class="navbar rowBC reset-el-dropdown">
    <div class="rowSC">
      <hamburger
        v-if="settings.showHamburger"
        :is-active="sidebar.opened"
        class="hamburger-container"
        @toggleClick="toggleSideBar"
      />
      <breadcrumb class="breadcrumb-container" />
    </div>
    <div v-if="settings.showNavbarTitle" class="heardCenterTitle">{{ settings.title }}</div>
    <div v-if="settings.ShowDropDown" class="right-menu rowSC">
      <!-- Dil değiştirici -->
      <el-dropdown trigger="click" size="small" style="margin-right: 16px">
        <el-button size="small" plain>🌐 {{ currentLangLabel }}</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="switchLang('tr')">🇹🇷 Türkçe</el-dropdown-item>
            <el-dropdown-item @click="switchLang('en')">🇬🇧 English</el-dropdown-item>
          </el-dropdown-menu>
        </template>

      </el-dropdown>
      <!-- Kullanıcı menüsü -->
      <el-dropdown trigger="click" size="medium">
        <div class="avatar-wrapper">
          <img src="https://github.jzfai.top/file/images/nav-right-logo.gif" class="user-avatar" />
          <CaretBottom style="width: 1em; height: 1em; margin-left: 4px" />
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <router-link to="/">
              <el-dropdown-item>{{ langTitle('Home') }}</el-dropdown-item>
            </router-link>
            <a target="_blank" href="https://github.com/jzfai/vue3-admin-template">
              <el-dropdown-item>{{ langTitle('Github') }}</el-dropdown-item>
            </a>
            <el-dropdown-item divided @click="loginOut">{{ langTitle('login out') }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { nextTick, computed } from 'vue'
import { CaretBottom } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import Breadcrumb from './Breadcrumb.vue'
import Hamburger from './Hamburger.vue'
import { resetState } from '@/hooks/use-permission'
import { elMessage } from '@/hooks/use-element'
import { useBasicStore } from '@/store/basic'
import { langTitle } from '@/hooks/use-common'
import { loginOutReq } from '@/api/user'
import { i18n } from '@/lang'

const basicStore = useBasicStore()
const { settings, sidebar, setToggleSideBar } = basicStore
const toggleSideBar = () => {
  setToggleSideBar()
}

const switchLang = (lang) => {
  i18n.global.locale.value = lang
}

const langLabels = { tr: '🇹🇷 Türkçe', en: '🇬🇧 English' }
const currentLangLabel = computed(() => langLabels[i18n.global.locale.value] || 'Dil')

const router = useRouter()
const loginOut = () => {
  loginOutReq().then(() => {
    elMessage('Çıkış başarılı')
    router.push(`/login?redirect=/`)
    nextTick(() => {
      resetState()
    })
  })
}
</script>

<style lang="scss" scoped>
.navbar {
  height: var(--nav-bar-height);
  overflow: hidden;
  position: relative;
  background: var(--nav-bar-background);
  box-shadow: var(--nav-bar-box-shadow);
  z-index: 1;
}

.avatar-wrapper {
  margin-top: 5px;
  position: relative;
  cursor: pointer;

  .user-avatar {
    cursor: pointer;
    width: 40px;
    height: 40px;
    border-radius: 10px;
  }

  .el-icon-caret-bottom {
    cursor: pointer;
    position: absolute;
    right: -20px;
    top: 25px;
    font-size: 12px;
  }
}

.heardCenterTitle {
  text-align: center;
  position: absolute;
  top: 50%;
  left: 46%;
  font-weight: 600;
  font-size: 20px;
  transform: translate(-50%, -50%);
}

.right-menu {
  cursor: pointer;
  margin-right: 40px;
  background-color: var(--nav-bar-right-menu-background);
}
</style>
