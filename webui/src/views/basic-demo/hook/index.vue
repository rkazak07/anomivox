<template>
  <div>
    <div class="font-bold mb-20px">Import copyValueToClipboard from use-common.ts</div>
    <el-button @click="hookExample">Execute hook method</el-button>
  </div>
</template>

<script setup lang="ts">
const hookExample = () => {
  copyValueToClipboard('Execute hook method')
}
</script>
