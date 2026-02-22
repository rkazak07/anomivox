<template>
  <div>
    <div>the recommend using way of worker</div>
    <div>Calculation result: {{ showPageRef }}</div>
    <el-icon v-if="!showPageRef" class="is-loading">
      <Loading />
    </el-icon>
  </div>
</template>
<script setup lang="ts">
const workerCode = () => {
  onmessage = (e) => {
    console.time('load time')
    console.log(`Received message from main thread: ${e.data}`)
    let countNum = 0
    for (let i = 0; i < e.data; i++) {
      countNum = i + countNum
    }
    console.log('Worker finished processing, returning to main thread')
    console.timeEnd('load time')
    postMessage(countNum)
  }
}

//change func to url for worker using
const changeFuncToUrl = (func) => {
  const workBlob = new Blob([`(${func.toString()})()`]) // Convert function to self-executing function
  const url = URL.createObjectURL(workBlob)
  return new Worker(url)
}

const worker = changeFuncToUrl(workerCode)
worker.postMessage(30000000)
const showPageRef = ref()
worker.onmessage = (e) => {
    console.log(`Main thread received message from worker: ${e.data}`)
  showPageRef.value = e.data
  worker.terminate()
}
</script>
