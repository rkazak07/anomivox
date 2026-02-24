<template>
  <div class="chat-item-container">
    <div :class="'rowSC ' + roleClass">
      <img v-if="isUser" src="@/assets/chat-user.png" class="face"/>
      <img v-else src="@/assets/chat-robot.png" class="face" />
<!--      <span style="margin: 0 10px; color: red">abc</span>-->
<!--      <span style="color: #2c59cb">sdada</span>-->
    </div>
    <div :class="'rowSC ' + roleClass">
      <div v-if="!message.loading">
        <div class="content" v-html="htmlContent" />
      </div>
      <div v-else>
        <div class="content rowBC" style="padding: 10px 20px">
          <el-icon class="is-loading" size="20" color="#333333">
            <Loading />
          </el-icon>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">

import marked from '@/utils/markdownConfig.js'

const props = defineProps({
  message: {required:true, type: Object, default: null }
})

const isUser = computed(() => props.message.role === 'user')

const roleClass = computed(() => props.message.role === 'user' ? 'right' : 'left')

const htmlContent = computed(() => {
  return marked.parse(props.message.content)
})

</script>

<style>
.hljs {
  border-radius: 8px!important;
  padding: 10px!important;
}
</style>

<style scoped lang="scss">

.chat-item-container {
  margin: 5px 0;
  display: flex;
  flex-direction: column;
}

.face {
  width: 36px;
  height: 36px;
  border-radius: 36px;
}

.content {
  color: var(--el-text-color-primary);
  font-size: 14px;
  min-height: 20px;
  border-radius: 16px;
  padding: 12px 20px;
  line-height: 1.6;
  word-break: break-all;
  word-wrap: break-word;
  position: relative;
  margin-top: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.3s ease;
}

.left {
  margin: 0 10px;
  .face {}
  .content {
    color: var(--el-text-color-primary);
    background: var(--el-fill-color-light);
    border: 1px solid var(--el-border-color-light);
    border-radius: 4px 16px 16px 16px;
  }
}

.right {
  margin: 0 10px;
  flex-direction: row-reverse;
  .face {}
  .content {
    color: #FFFFFF;
    background: linear-gradient(135deg, #38BDF8 0%, #0284C7 100%);
    border: none;
    border-radius: 16px 4px 16px 16px;
    box-shadow: 0 4px 12px rgba(2, 132, 199, 0.2);
  }
}

</style>
