<template>
  <div class="bottom-input-container">
    <slot name="left">
      <div />
    </slot>
    <div class="input-container">
      <el-input
          v-model="userInput"
          :disabled=inputDisabled
          :placeholder="placeholder"
          clearable
          size="default"
          style="width: calc(100% - 40px);"
          @keydown.enter.prevent="onSendClick"
      />
      <el-button icon="Position" type="success" :disabled="sendBtnDisabled" circle size="default" style="font-size: 22px;" @click="onSendClick" />
    </div>
    <slot name="right">
      <div />
    </slot>
  </div>
</template>

<script setup lang="ts" name="BottomInputContainer">

import {ref, computed, Ref} from "vue";

const props = defineProps({
  placeholder: {
    require: true,
    default: 'Please enter your request',
    type: String
  },
  inputDisabled: {
    require: false,
    default: false,
    type: Boolean
  }
})

const emit = defineEmits(['send-click'])

const userInput: Ref<string> = ref('')

const sendBtnDisabled = computed(() => userInput.value === '')

const onSendClick = (e?: Event) => {
  if (e && (e as any).isComposing) return
  if (sendBtnDisabled.value) return
  emit('send-click', userInput.value)
  userInput.value = ''
}

</script>

<style>
.input-container .el-input__wrapper {
  border: None !important;
  box-shadow: None !important;
}
</style>

<style lang="scss" scoped>
.bottom-input-container {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.input-container {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  width: 100%;
  flex-shrink: 1;
  border-radius: 30px;
  background: var(--el-bg-color);
  overflow: hidden;
  padding: 10px 20px;
  border: 1px solid var(--el-border-color-light);
  box-shadow: var(--el-box-shadow-light);
  transition: all 0.3s ease;

  &:focus-within {
    box-shadow: 0 4px 16px rgba(var(--el-color-primary-rgb), 0.15);
    border-color: var(--el-color-primary);
  }
}

</style>
