<template>
  <div class="scroll-y">
    <div class="font-bold mb-10px">call child method</div>
    <el-button @click="childMethod">call childMethod</el-button>
    <!--v-model sync -->
    <Children ref="refChildren" v-model:childrenTitle="parentTitle" father-name="Vue3Template" @emitParent="emitParent">
      <!-- Default slot v-slot -->
      <template #default>
        <div>Default Slot</div>
      </template>
      <!-- Named slot // v-slot:header -->
      <template #header>
        <div>Named Slot</div>
      </template>
      <!-- Scoped slot  //v-slot:footer -->
      <template #footer="{ testProps }">
        {{ testProps }}
      </template>
    </Children>
  </div>
</template>

<script setup lang="ts">
import Children from './Children.vue'
const refChildren = ref()
onMounted(() => {
  console.log(refChildren.value)
})
const childMethod = () => {
  console.log(refChildren.value.childMethod())
  console.log(refChildren.value.childRef)
}
const emitParent = (data) => {
  console.log('Got message from child component 111', data)
}
const fartherMethod = () => {
  console.log('fartherMethod')
}
//provide
provide('title', 'provide value')

//v-model sync
const parentTitle = ref('parentTitle')

watch(
  () => parentTitle.value,
  (oldValue, newValue) => {
    console.log('Parent update triggered', oldValue, newValue)
  },
  { immediate: true }
)
defineExpose({ fartherMethod })
</script>
