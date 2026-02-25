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
          <el-avatar :size="32" style="background-color: var(--el-color-primary)">
            <el-icon :size="18"><UserFilled /></el-icon>
          </el-avatar>
          <span class="username-text">{{ basicStore.userInfo.username || 'User' }}</span>
          <CaretBottom style="width: 1em; height: 1em; margin-left: 4px" />
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <router-link to="/">
              <el-dropdown-item>
                <el-icon style="margin-right: 6px"><HomeFilled /></el-icon>
                {{ $t('home') }}
              </el-dropdown-item>
            </router-link>
            <router-link to="/settings">
              <el-dropdown-item>
                <el-icon style="margin-right: 6px"><Setting /></el-icon>
                {{ $t('settingsTitle') }}
              </el-dropdown-item>
            </router-link>
            <el-dropdown-item divided @click="loginOut">
              <el-icon style="margin-right: 6px"><SwitchButton /></el-icon>
              {{ $t('logoutButton') }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { nextTick, computed } from 'vue'
import { CaretBottom, UserFilled, HomeFilled, Setting, SwitchButton } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Breadcrumb from './Breadcrumb.vue'
import Hamburger from './Hamburger.vue'
import { resetState } from '@/hooks/use-permission'
import { elMessage } from '@/hooks/use-element'
import { useBasicStore } from '@/store/basic'
import { langTitle } from '@/hooks/use-common'
import { loginOutReq } from '@/api/user'
import { i18n } from '@/lang'

const { t: $t } = useI18n()

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
    elMessage($t('logoutSuccess'))
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
  display: flex;
  align-items: center;
  cursor: pointer;

  .username-text {
    margin-left: 8px;
    font-size: 14px;
    font-weight: 500;
    color: var(--el-text-color-primary);
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
