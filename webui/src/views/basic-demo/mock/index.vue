<template>
  <div class="scroll-y">
    <div class="font-bold mb-20px">Mock usage example</div>
    <el-button type="primary" @click="listReq">Click to send mock request</el-button>
  </div>
</template>

<script setup lang="ts">
import axios from 'axios'
const listReq = () => {
  axios.get('/getMapInfo').then(({ data }) => {
    elMessage(data)
  })
}
</script>

<style scoped lang="scss"></style>
