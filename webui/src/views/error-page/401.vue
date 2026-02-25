<template>
  <div class="errPage-container">
    <el-button icon="Back" class="pan-back-btn" @click="back">Go Back</el-button>
    <el-row>
      <el-col :span="12">
        <h1 class="text-jumbo text-ginormous">Oops!</h1>
        <h2>You do not have permission to access this page</h2>
        <h6>Contact your administrator if you need access</h6>
        <ul class="list-unstyled">
          <li>Or you can go to:</li>
          <li class="link-type">
            <router-link to="/dashboard">Home Page</router-link>
          </li>
        </ul>
      </el-col>
      <el-col :span="12" style="display: flex; justify-content: center; align-items: center;">
        <el-icon size="300" color="var(--el-color-warning)"><Warning /></el-icon>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const back = () => {
  if (route.query.noGoBack) {
    router.push({ path: '/dashboard' })
  } else {
    router.go(-1)
  }
}
const { ewizardClap, dialogVisible } = toRefs(state)
</script>

<style lang="scss" scoped>
.errPage-container {
  width: 800px;
  max-width: 100%;
  margin: 100px auto;
  .pan-back-btn {
    background: #008489;
    color: #fff;
    border: none !important;
  }
  .pan-gif {
    margin: 0 auto;
    display: block;
  }
  .pan-img {
    display: block;
    margin: 0 auto;
    width: 100%;
  }
  .text-jumbo {
    font-size: 60px;
    font-weight: 700;
    color: #484848;
  }
  .list-unstyled {
    font-size: 14px;
    li {
      padding-bottom: 5px;
    }
    a {
      color: #008489;
      text-decoration: none;
      &:hover {
        text-decoration: underline;
      }
    }
  }
}
</style>
