<template>
  <div>
    <div class="font-bold mb-20px">Thanks to AutoImport plugin, Pinia API can be imported directly</div>
    <el-button @click="sidebar.opened = !sidebar.opened">switch sidebar.opened</el-button>
  </div>
</template>

<script setup lang="ts">
const { sidebar } = storeToRefs(useBasicStore())
</script>

<style scoped lang="scss"></style>
