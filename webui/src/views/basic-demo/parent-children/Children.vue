<template>
  <div>
    <div class="font-bold mb-10px mt-20px">call father method</div>
    <el-button @click="emitFather">emitFather</el-button>
    <el-button @click="getFatherMethod">getFatherMethod</el-button>
    <SubChildren />
  </div>

  <div class="mt-20px font-bold mb-10px">slot using</div>
  <!-- Default slot -->
  <slot>
    <!-- Fallback content -->
    <h3>No content passed</h3>
  </slot>
  <!-- Named slot -->
  <slot name="header">
    <h3>No header slot passed</h3>
  </slot>
  <!-- Scoped slot -->
  <slot name="footer" test-props="value from child scope">
    <h3>No footer slot passed</h3>
  </slot>

  <div class="mt-20px mb-10px font-bold">v-model sync using</div>
  <div>{{ childrenTitle }}</div>
  <el-button @click="changeParentValue">changeParentValue</el-button>
</template>

<script setup lang="ts">
import SubChildren from './SubChildren.vue'
const props = defineProps({
  fatherName: {
    require: true,
    default: '',
    type: String
  },
  childrenTitle: {
    require: true,
    default: '',
    type: String
  }
})
const state = reactive({
  name: 'Children'
})
const childRef = ref('childRef')
const childMethod = () => {
  return 'childMethod'
}

const vm = getCurrentInstance()?.proxy
const getFatherMethod = () => {
  vm?.$parent?.fartherMethod()
}
//emit
const emit = defineEmits(['emitParent', 'update:childrenTitle'])
const emitFather = () => {
  emit('emitParent', { val: 'Message from child component' })
}
onMounted(() => {
  console.log('Got parent prop', props.fatherName)
})

//v-model sync
onMounted(() => {
  console.log(`this is v-model parent data:${props.childrenTitle}`)
})
const changeParentValue = () => {
  emit('update:childrenTitle', 'update it childrenTitle')
}
defineExpose({ childRef, childMethod })
//export to page for use
const { name } = toRefs(state)
</script>
