import router from '@/router'
import {progressClose, progressStart } from '@/hooks/use-permission'
import { useBasicStore } from '@/store/basic'
import { langTitle } from '@/hooks/use-common'
import settings from "@/settings";

const whiteList = ['/login', '/404', '/401'] // no redirect whitelist

// Token verification cache — avoids blocking every route navigation with a network call
let tokenVerifyCache = { token: null, valid: false, at: 0 }
const TOKEN_CACHE_TTL = 5 * 60 * 1000 // 5 minutes

const verifyToken = async (token) => {
  const now = Date.now()
  if (tokenVerifyCache.token === token && (now - tokenVerifyCache.at) < TOKEN_CACHE_TTL) {
    return tokenVerifyCache.valid
  }
  try {
    const baseUrl = import.meta.env.VITE_APP_BASE_URL || ''
    const res = await fetch(`${baseUrl}auth/me`, {
      headers: { Authorization: token }
    })
    if (!res.ok) {
      tokenVerifyCache = { token, valid: false, at: now }
      return false
    }
    const data = await res.json()
    const valid = data?.code === 200
    tokenVerifyCache = { token, valid, at: now }
    return valid
  } catch {
    return tokenVerifyCache.valid // network error → keep last known state
  }
}

router.beforeEach(async (to) => {
  progressStart()
  document.title = langTitle(to.meta?.title) // i18 page title
  const basicStore = useBasicStore()
  //not login
  if (!settings.isNeedLogin) {
    basicStore.setFilterAsyncRoutes([])
    return true
  }
  if (basicStore.token) {
    // Verify token is still valid on the server
    const valid = await verifyToken(basicStore.token)
    if (!valid) {
      basicStore.resetState()
      return `/login?redirect=${to.path}`
    }
    if (to.path === '/login') {
      return '/'
    } else {
      basicStore.setFilterAsyncRoutes([])
      return true
    }
  } else {
    if (!whiteList.includes(to.path)) {
      return `/login?redirect=${to.path}`
    } else {
      return true
    }
  }
})
router.afterEach(() => {
  progressClose()
})
