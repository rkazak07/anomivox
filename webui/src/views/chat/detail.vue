<template>
  <div>Vue3 recommended template can be integrated into your VSCode or WebStorm for rapid development</div>
</template>

<script setup>

const props = defineProps({
  name: {
    require: true,
    default: 'fai',
    type: String
  }
})
const state = reactive({
  levelList: null
})

const routes = computed(() => 'value')
watch(
    () => props.name,
    (oldValue, newValue) => {
    },
    {immediate: true}
)

const router = useRouter()
onMounted(() => {
  console.log('Page mounted')
})
const helloFunc = () => {
  console.log('helloFunc')
}
defineExpose({helloFunc})
const {levelList} = toRefs(state)
</script>

<style scoped lang="scss"></style>
