<template>
  <div class="scroll-y">
    <div class="font-bold mb-10px">Second Page KeepAlive Demo</div>

    <el-form ref="refsearchForm" :inline="true" class="mt-2">
      <el-form-item label-width="0px" label="" prop="errorLog" label-position="left">
        <el-input v-model="searchForm.name" class="w-150px" placeholder="input to test keepAlive" />
      </el-form-item>
      <el-form-item label-width="0px" label="" prop="pageUrl" label-position="left">
        <el-input v-model="searchForm.age" class="w-150px" placeholder="input to test keepAlive" />
      </el-form-item>
    </el-form>
    <el-button type="primary" @click="routerDemoF">to SecondChild.vue</el-button>
  </div>
</template>
<script setup lang="ts" name="SecondKeepAlive">
const searchForm = reactive({
  name: '',
  age: ''
})
const testRef = ref(1)
testRef.value = 2
console.log(testRef.value)
onActivated(() => {
  console.log('onActivated')
})
onDeactivated(() => {
  console.log('onDeactivated')
})

const routerDemoF = () => {
  routerPush('SecondChild', { name: 'SecondKeepAlive' })
}
</script>
