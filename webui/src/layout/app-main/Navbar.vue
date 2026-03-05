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
            <el-dropdown-item @click="showChangePasswordDialog = true">
              <el-icon style="margin-right: 6px"><Lock /></el-icon>
              {{ $t('changeMyPassword') }}
            </el-dropdown-item>
            <el-dropdown-item divided @click="loginOut">
              <el-icon style="margin-right: 6px"><SwitchButton /></el-icon>
              {{ $t('logoutButton') }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>

  <!-- Change My Password Dialog -->
  <el-dialog v-model="showChangePasswordDialog" :title="$t('changeMyPassword')" width="420px" :close-on-click-modal="false" @close="resetMyPasswordForm">
    <el-form ref="refMyPwdForm" :model="myPwdForm" :rules="myPwdRules" label-width="140px">
      <el-form-item :label="$t('currentPassword')" prop="currentPassword">
        <el-input v-model="myPwdForm.currentPassword" type="password" show-password :placeholder="$t('pleaseInputCurrentPassword')" />
      </el-form-item>
      <el-form-item :label="$t('newPassword')" prop="newPassword">
        <el-input v-model="myPwdForm.newPassword" type="password" show-password :placeholder="$t('pleaseInputNewPassword')" />
      </el-form-item>
      <el-form-item :label="$t('confirmPassword')" prop="confirmPassword">
        <el-input v-model="myPwdForm.confirmPassword" type="password" show-password :placeholder="$t('pleaseConfirmPassword')" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showChangePasswordDialog = false">{{ $t('cancel') }}</el-button>
      <el-button type="primary" :loading="myPwdLoading" @click="onSubmitMyPassword">{{ $t('save') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { nextTick, computed, ref, reactive } from 'vue'
import { CaretBottom, UserFilled, HomeFilled, Setting, SwitchButton, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Breadcrumb from './Breadcrumb.vue'
import Hamburger from './Hamburger.vue'
import { resetState } from '@/hooks/use-permission'
import { elMessage } from '@/hooks/use-element'
import { useBasicStore } from '@/store/basic'
import { langTitle } from '@/hooks/use-common'
import { loginOutReq, changeMyPasswordReq } from '@/api/user'
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

// Change My Password
const showChangePasswordDialog = ref(false)
const myPwdLoading = ref(false)
const refMyPwdForm = ref(null)
const myPwdForm = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })
const myPwdRules = {
  currentPassword: [{ required: true, message: () => $t('pleaseInputCurrentPassword'), trigger: 'blur' }],
  newPassword: [
    { required: true, message: () => $t('pleaseInputNewPassword'), trigger: 'blur' },
    { min: 6, message: () => $t('passwordMinLength'), trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: () => $t('pleaseConfirmPassword'), trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== myPwdForm.newPassword) callback(new Error($t('passwordMismatch')))
        else callback()
      },
      trigger: 'blur'
    }
  ]
}

const resetMyPasswordForm = () => {
  myPwdForm.currentPassword = ''
  myPwdForm.newPassword = ''
  myPwdForm.confirmPassword = ''
  refMyPwdForm.value?.clearValidate()
}

const onSubmitMyPassword = () => {
  refMyPwdForm.value.validate(async (valid) => {
    if (!valid) return
    myPwdLoading.value = true
    try {
      const res = await changeMyPasswordReq(myPwdForm.currentPassword, myPwdForm.newPassword)
      if (res.code === 200) {
        ElMessage.success(res.msg || $t('success'))
        showChangePasswordDialog.value = false
      } else {
        ElMessage.error(res.msg)
      }
    } catch (e) {
      ElMessage.error(e?.msg || 'Error')
    } finally {
      myPwdLoading.value = false
    }
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
