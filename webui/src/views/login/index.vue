<template>
  <div class="login-container columnCC">
    <el-form ref="refLoginForm" class="login-form" :model="subForm" :rules="formRules" autocomplete="off">
      <div class="title-container">
        <img src="/logo-buyuk.png" class="login-logo" alt="Anomivox" />
      </div>
      <el-form-item prop="keyword" :rules="formRules.isNotNull($t('usernameRequired'))">
        <div class="rowSC">
          <span class="svg-container">
            <svg-icon icon-class="user" />
          </span>
          <el-input v-model="subForm.keyword" :placeholder="$t('usernamePlaceholder')" autocomplete="off" />
          <!-- placeholder -->
          <div class="show-pwd" />
        </div>
      </el-form-item>
      <!--<el-form-item prop="password" :rules="formRules.passwordValid">-->
      <el-form-item prop="password" :rules="formRules.isNotNull($t('passwordRequired'))">
        <div class="rowSC flex-1">
          <span class="svg-container">
            <svg-icon icon-class="password" />
          </span>
          <el-input
              :key="passwordType"
              ref="refPassword"
              v-model="subForm.password"
              :type="passwordType"
              name="password"
              autocomplete="new-password"
              :placeholder="$t('passwordPlaceholder')"
              @keyup.enter="handleLogin"
          />
          <span class="show-pwd" @click="showPwd">
            <svg-icon :icon-class="passwordType === 'password' ? 'eye' : 'eye-open'" />
          </span>
        </div>
      </el-form-item>
      <div class="tip-message">{{ tipMessage }}</div>
      <el-button :loading="subLoading" type="primary" class="login-btn" size="default" @click.prevent="handleLogin">
        {{ $t('loginButton') }}
      </el-button>
    </el-form>
  </div>
</template>

<script setup>
import { reactive, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBasicStore } from '@/store/basic'
import { elMessage, useElement } from '@/hooks/use-element'
import { loginReq } from '@/api/user'
import { useI18n } from 'vue-i18n'

const { t: $t } = useI18n()

/* listen router change and set the query  */
const { settings } = useBasicStore()
//element valid
const formRules = useElement().formRules
//form
const subForm = reactive({
  keyword: '',
  password: ''
})
const state = reactive({
  otherQuery: {},
  redirect: undefined
})
const route = useRoute()
const getOtherQuery = (query) => {
  return Object.keys(query).reduce((acc, cur) => {
    if (cur !== 'redirect') {
      acc[cur] = query[cur]
    }
    return acc
  }, {})
}
watch(
    () => route.query,
    (query) => {
      if (query) {
        state.redirect = query.redirect
        state.otherQuery = getOtherQuery(query)
      }
    },
    { immediate: true }
)

/*
 *  login relative
 * */
const subLoading = ref(false)
//tip message
const tipMessage = ref('')
//sub form
const refLoginForm = ref(null)
const handleLogin = () => {
  refLoginForm.value.validate((valid) => {
    subLoading.value = true
    if (valid) loginFunc()
  })
}
const router = useRouter()
const basicStore = useBasicStore()

const hashPassword = async (password) => {
  const encoder = new TextEncoder()
  const data = encoder.encode(password)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
}

const loginFunc = async () => {
  const hashedPwd = await hashPassword(subForm.password)
  loginReq({ username: subForm.keyword, password: hashedPwd })
      .then((res) => {
        if (res.code === 200) {
          elMessage($t('loginSuccess'))
          basicStore.setToken(res.data.token)
          basicStore.setUserInfo({
            userInfo: { username: res.data.username, avatar: '', id: res.data.user_id },
            roles: res.data.is_admin ? ['admin'] : ['user'],
            codes: []
          })
          router.push('/')
        } else {
          tipMessage.value = res.msg
        }
      })
      .catch((err) => {
        tipMessage.value = err?.msg || $t('loginFailed')
      })
      .finally(() => {
        subLoading.value = false
      })
}
/*
 *  password show or hidden
 * */
const passwordType = ref('password')
const refPassword = ref(null)
const showPwd = () => {
  if (passwordType.value === 'password') {
    passwordType.value = ''
  } else {
    passwordType.value = 'password'
  }
  nextTick(() => {
    refPassword.value.focus()
  })
}
</script>

<style lang="scss" scoped>
$bg: #2d3a4b;
$dark_gray: #889aa4;
$light_gray: #eee;
.login-container {
  height: 100vh;
  width: 100%;
  background-color: #2d3a4b;
  .login-form {
    margin-bottom: 20vh;
    width: 360px;
  }
  .title-container {
    text-align: center;
    margin-bottom: 25px;
    .login-logo {
      max-width: 240px;
      width: 100%;
    }
  }
}

.svg-container {
  padding-left: 6px;
  color: $dark_gray;
  text-align: center;
  width: 30px;
}


.tip-message {
  color: #e4393c;
  height: 30px;
  margin-top: -12px;
  font-size: 12px;
}


.login-btn {
  width: 100%;
  margin-bottom: 30px;
}
.show-pwd {
  width: 50px;
  font-size: 16px;
  color: $dark_gray;
  cursor: pointer;
  text-align: center;
}
</style>

<style lang="scss">
.login-container {
  .el-input__wrapper {
    background-color: transparent;
    box-shadow: none;
  }
  .el-form-item {
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(0, 0, 0, 0.1);
    border-radius: 5px;
    color: #454545;
  }
  .el-input input {
    background: transparent;
    border: 0px;
    -webkit-appearance: none;
    border-radius: 0px;
    padding: 10px 5px 10px 15px;
    color: #fff;
    height: 42px; // adjust item height here
    caret-color: #fff;
  }
  //hiden the input border
  .el-input__inner {
    box-shadow: none !important;
  }
}
</style>
