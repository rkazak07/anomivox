<template>
  <div>
    <div class="font-bold mb-20px">Cross-domain usage example</div>
    <el-button @click="testReqExample">Test Cross-domain</el-button>
  </div>
</template>

<script setup lang="ts">
const testReqExample = () => {
  const isDev = import.meta.env.VITE_APP_ENV === 'dev'
  const reqConfig = {
    baseURL: isDev ? import.meta.env.VITE_PROXY_BASE_URL : import.meta.env.VITE_PROXY_URL,
    //baseURL: import.meta.env.VITE_PROXY_URL,
    url: '/basis-func/user/getUserInfo',
    timeout: 8000,
    params: { plateFormId: 2 },
    method: 'post'
  }
  axiosReq(reqConfig).then(({ data }) => {
    console.log(data)
  })
}
</script>
