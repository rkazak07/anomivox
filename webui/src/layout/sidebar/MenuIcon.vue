<template>
  <!-- Show elSvgIcon if available, otherwise show icon -->
  <div>{{ meta.icon }}</div>
</template>

<script setup lang="ts">
// import * as ElSvg from '@element-plus/icons-vue'
defineProps({
  meta: { type: Object, default: null }
})
</script>

<style scoped lang="scss">
.menu-svg-class {
  width: 30px;
  background: red;
  height: 30px;
}
</style>
