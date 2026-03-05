<template>
  <div id="Sidebar" class="sidebar-root">

    <!-- Logo -->
    <div class="sidebar-logo-area">
      <Logo :collapse="true" />
    </div>

    <!-- Navigation -->
    <nav class="sidebar-nav">
      <sidebar-item
        v-for="route in allRoutes"
        :key="route.path"
        :item="route"
        :base-path="route.path"
        :active-path="activeMenu"
      />
    </nav>

    <!-- Footer -->
    <div class="sidebar-footer">
      <!-- Quick actions row -->
      <div class="sidebar-actions">
        <button class="action-btn" :title="isDark ? 'Light Mode' : 'Dark Mode'" @click="onThemeClick">
          <svg v-if="isDark" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" /><line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" /><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
          </svg>
          <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        </button>
        <button class="action-btn lang-btn" :title="currentLang === 'tr' ? 'Switch to English' : 'Türkçe\'ye geç'" @click="onLanguageClick">
          {{ currentLang === 'tr' ? 'TR' : 'EN' }}
        </button>
      </div>

      <!-- User section -->
      <el-popover
        placement="right-end"
        :width="220"
        trigger="click"
        :show-arrow="false"
        :offset="12"
        popper-class="sidebar-user-popover"
      >
        <template #reference>
          <div class="sidebar-user">
            <div class="sidebar-user-avatar">
              <span>{{ avatarLetter }}</span>
            </div>
            <div class="sidebar-user-info">
              <span class="sidebar-user-name">{{ displayName }}</span>
              <span class="sidebar-user-role">{{ isAdmin ? 'Admin' : 'User' }}</span>
            </div>
            <svg class="sidebar-user-more" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="5" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="12" cy="19" r="1" />
            </svg>
          </div>
        </template>
        <div class="popover-menu">
          <div class="popover-menu-item" @click="goToSettings">
            <el-icon :size="16"><Setting /></el-icon>
            <span>{{ $t('settingsTitle') }}</span>
          </div>
          <div class="popover-menu-item" @click="showPwdDialog = true">
            <el-icon :size="16"><Lock /></el-icon>
            <span>{{ $t('changeMyPassword') }}</span>
          </div>
          <div class="popover-menu-divider"></div>
          <div class="popover-menu-item popover-menu-item--danger" @click="handleLogout">
            <el-icon :size="16"><SwitchButton /></el-icon>
            <span>{{ $t('logoutButton') }}</span>
          </div>
        </div>
      </el-popover>

      <!-- Teleport: dialog body'e render edilir, sidebar layout'u etkilemez -->
      <Teleport to="body">
        <el-dialog v-model="showPwdDialog" :title="$t('changeMyPassword')" width="420px" :close-on-click-modal="false" @close="resetPwdForm">
          <el-form ref="refPwdForm" :model="pwdForm" :rules="pwdRules" label-position="top">
            <el-form-item :label="$t('currentPassword')" prop="currentPassword">
              <el-input v-model="pwdForm.currentPassword" type="password" show-password :placeholder="$t('pleaseInputCurrentPassword')" />
            </el-form-item>
            <el-form-item :label="$t('newPassword')" prop="newPassword">
              <el-input v-model="pwdForm.newPassword" type="password" show-password :placeholder="$t('pleaseInputNewPassword')" />
            </el-form-item>
            <el-form-item :label="$t('confirmPassword')" prop="confirmPassword">
              <el-input v-model="pwdForm.confirmPassword" type="password" show-password :placeholder="$t('pleaseConfirmPassword')" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showPwdDialog = false">{{ $t('cancel') }}</el-button>
            <el-button type="primary" :loading="pwdLoading" @click="onSubmitPwd">{{ $t('save') }}</el-button>
          </template>
        </el-dialog>
      </Teleport>
    </div>
  </div>

</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia/dist/pinia'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Setting, SwitchButton, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import Logo from './Logo.vue'
import SidebarItem from './SidebarItem.vue'
import { useBasicStore } from '@/store/basic'
import { resetState } from '@/hooks/use-permission'
import { elMessage } from '@/hooks/use-element'
import { loginOutReq, changeMyPasswordReq } from '@/api/user'

const { t: $t } = useI18n()
const router = useRouter()
const basicStore = useBasicStore()
const { allRoutes } = storeToRefs(basicStore)
const routeInstance = useRoute()
let useConfigStore = reactive({})
const currentLang = ref('tr')
const currentTheme = ref('lighting-theme')

const themeList = ['lighting-theme', 'dark']
const isDark = computed(() => currentTheme.value === 'dark')

const displayName = computed(() => basicStore.userInfo?.username || 'User')
const avatarLetter = computed(() => (displayName.value[0] || 'U').toUpperCase())
const isAdmin = computed(() => basicStore.roles?.includes('admin'))

setTimeout(() => {
  import('@/store/config').then((res) => {
    useConfigStore = res.useConfigStore
    currentLang.value = useConfigStore().language
    currentTheme.value = useConfigStore().theme
  })
}, 300)

const activeMenu = computed(() => {
  const { meta, path } = routeInstance
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
}

const goToSettings = () => {
  router.push('/settings')
}

const handleLogout = () => {
  loginOutReq().then(() => {
    elMessage($t('logoutSuccess'))
    router.push('/login?redirect=/')
    nextTick(() => {
      resetState()
    })
  })
}

const showPwdDialog = ref(false)
const pwdLoading = ref(false)
const refPwdForm = ref(null)
const pwdForm = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })
const validatePwdStrength = (rule, value, callback) => {
  if (!value) { callback(); return }
  const re = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$/
  if (!re.test(value)) callback(new Error($t('passwordStrength')))
  else callback()
}
const pwdRules = {
  currentPassword: [{ required: true, message: () => $t('pleaseInputCurrentPassword'), trigger: 'blur' }],
  newPassword: [
    { required: true, message: () => $t('pleaseInputNewPassword'), trigger: 'blur' },
    { validator: validatePwdStrength, trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: () => $t('pleaseConfirmPassword'), trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== pwdForm.newPassword) callback(new Error($t('passwordMismatch')))
        else callback()
      },
      trigger: 'blur'
    }
  ]
}
const resetPwdForm = () => {
  pwdForm.currentPassword = ''
  pwdForm.newPassword = ''
  pwdForm.confirmPassword = ''
  refPwdForm.value?.clearValidate()
}
const onSubmitPwd = () => {
  refPwdForm.value.validate(async (valid) => {
    if (!valid) return
    pwdLoading.value = true
    try {
      const res = await changeMyPasswordReq(pwdForm.currentPassword, pwdForm.newPassword)
      if (res.code === 200) {
        ElMessage.success(res.msg || $t('success'))
        showPwdDialog.value = false
      } else {
        ElMessage.error(res.msg)
      }
    } catch (e) {
      ElMessage.error(e?.msg || 'Error')
    } finally {
      pwdLoading.value = false
    }
  })
}
</script>

<style lang="scss">
/* ── Sidebar Root ── */
.sidebar-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--el-menu-bg-color);
  border-right: 1px solid var(--side-bar-border-right-color);
  overflow: hidden;
}

.el-menu-vertical {
  width: var(--side-bar-width);
}

/* ── Logo ── */
.sidebar-logo-area {
  flex-shrink: 0;
  padding: 20px 14px 16px;
  display: flex;
  align-items: center;
}

/* ── Navigation ── */
.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 0;
  display: flex;
  flex-direction: column;

  /* Thin custom scrollbar */
  &::-webkit-scrollbar {
    width: 3px;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--el-border-color-lighter);
    border-radius: 3px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
}

/* ── Footer ── */
.sidebar-footer {
  flex-shrink: 0;
  padding: 10px 14px 14px;
  border-top: 1px solid var(--el-border-color-lighter, rgba(255,255,255,0.06));
}

/* ── Action Buttons (theme + lang) ── */
.sidebar-actions {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: var(--el-fill-color-lighter, rgba(255,255,255,0.04));
  color: var(--el-text-color-secondary, #94A3B8);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;

  &:hover {
    background: var(--el-fill-color, rgba(255,255,255,0.08));
    color: var(--el-text-color-primary, #F8FAFC);
  }
}

.lang-btn {
  font-family: 'Inter', -apple-system, system-ui, sans-serif;
}

/* ── User Section ── */
.sidebar-user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: var(--el-fill-color-lighter, rgba(255,255,255,0.04));

    .sidebar-user-more {
      opacity: 1;
    }
  }
}

.sidebar-user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--el-color-primary, #38BDF8), var(--el-color-primary-light-3, #7DD3FC));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  span {
    font-weight: 700;
    font-size: 13px;
    color: #fff;
    line-height: 1;
  }
}

.sidebar-user-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.sidebar-user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary, #F8FAFC);
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-user-role {
  font-size: 11px;
  color: var(--el-text-color-secondary, #94A3B8);
  line-height: 1.2;
}

.sidebar-user-more {
  flex-shrink: 0;
  opacity: 0;
  color: var(--el-text-color-secondary, #94A3B8);
  transition: opacity 0.2s ease;
}

/* ── Popover Menu ── */
.sidebar-user-popover {
  border-radius: 12px !important;
  padding: 6px !important;
  border: 1px solid var(--el-border-color-lighter) !important;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.08) !important;
}

.popover-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  color: var(--el-text-color-regular);
  font-size: 13px;
  font-weight: 500;

  &:hover {
    background: var(--el-fill-color-light);
    color: var(--el-text-color-primary);
  }

  &--danger:hover {
    background: var(--el-color-danger-light-9, rgba(239,68,68,0.1));
    color: var(--el-color-danger, #EF4444);
  }
}

.popover-menu-divider {
  height: 1px;
  background: var(--el-border-color-lighter);
  margin: 4px 8px;
}
</style>
