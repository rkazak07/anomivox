<template>
  <div class="c-flex-column c-relative" style="width: 100%; height: 100%;">
    <div :id="componentId + '-scroll-container'" class="scroll-container c-relative">
      <div
        class="message-header c-relative c-flex-row c-align-items-center"
        :style="'background-color: ' + headerStyles[(sender || 'A').charCodeAt(0) % headerStyles.length]"
      >
        <span class="face">
          {{ sender.slice(0, 1) }}
        </span>
        <span style="font-size: 16px; color: #FFFFFF; margin-left: 10px">{{ sender }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>

import marked from '@/utils/markdownConfig.js'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  sender: { required: true, type: String },
  skipTyped: { type: Boolean, default: false },
  typeSpeed: { type: Number, default: 100 }
})

const emit = defineEmits(['playback-complete'])

const headerStyles = ["#01B77E", "#0F2F5F", "#FB9996", "#7649af", "#ecb42b", "#67C23A", "#FFC2E3", "#D51374"]

const typedObjs = ref([])
const componentId = `report-one-chat-${Math.random().toString(36).slice(2, 11)}`
let scrollObserver = undefined
// watch props changes
watch(() => props.messages, (newVal, oldVal) => {
  setTimeout(() => {
    if (props.messages.length > 0) {
      dealMessage(0)
    }
  })
}, { deep: true, immediate: true })

onBeforeUnmount(() => {
  if (scrollObserver) {
    scrollObserver.disconnect()
    scrollObserver = undefined
  }
  typedObjs.value.forEach(item => {
    item.destroy()
  })
})

onMounted(() => {
  const target = document.querySelector(`#${componentId}-scroll-container`)
  if (target) {
    scrollObserver = new MutationObserver((mutationsList, observer) => {
      target.scrollTop = target.scrollHeight - target.clientHeight
    })
    const config = { attributes: true, childList: true, subtree: true }

    if(scrollObserver){ // check if scrollObserver exists
      scrollObserver.observe(target, config)
    } else {
      console.error('scrollObserver is undefined')
    }
  } else {
    console.error('Element is not mounted yet')
  }
})

const dealMessage = async (index) => {
  if (index >= props.messages.length) {
    emit('playback-complete');
    if (scrollObserver) {
      scrollObserver.disconnect();
      scrollObserver = undefined;
    }
    return;
  }

  const message = props.messages[index];

  if (!(message.data && message.data.trim())) {
    dealMessage(index + 1);
    return;
  }

  const divId = `message-${  Math.random().toString(36).slice(2, 11)}`;

  const messagesContainer = document.querySelector(`#${componentId}-scroll-container`);
  messagesContainer.innerHTML = `${messagesContainer.innerHTML
  }<div class="text-item c-flex-column">
          <span style="font-size: 1rem; color: var(--el-text-color-primary); margin-bottom: 5px">
            <span style="margin-left: 5px; color: var(--el-text-color-secondary)">${message.time}</span>
          </span>
          <div id="${divId}" class="content c-flex-column"></div>
      </div>`;

  await nextTick();

  try {
    if (props.skipTyped) {
      const contentContainer = document.querySelector(`#${divId}`);
      contentContainer.innerHTML = marked.parse(message.data);
      dealMessage(index + 1);
    } else {
      const typedObj = new Typed(`#${  divId}`, {
        strings: [marked.parse(message.data)],
        typeSpeed: 100 - props.typeSpeed,
        showCursor: false,
        contentType: 'html',
        onComplete: () => {
          dealMessage(index + 1);
        }
      });
      typedObjs.value.push(typedObj);
    }
  } catch (e) {
    console.log('Typed Error', e);
  }
}
</script>

<style>
.text-item {
  margin: 20px;
  align-items: flex-start;
  justify-content: flex-start;
  word-break: break-all;
  word-wrap: break-word;
  overflow-x: scroll;
}

.content {
  color: var(--el-text-color-primary);
  font-size: 14px;
  min-height: 20px;
  border-radius: 12px;
  padding: 16px 20px;
  line-height: 1.6;
  background-color: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-light);
  word-break: break-all;
  word-wrap: break-word;
  position: relative;
  width: 100%;
}

.json-viewer {
  width: 100%;
}

</style>

<style lang="scss" scoped>

.json-viewer {
  width: 100%;
}

.message-header {
  position: sticky;
  top: 0;
  width: 100%;
  z-index: 10;
  padding: 12px 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.scroll-container {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
  padding-bottom: 20px;
  width: 100%;
  height: 100%;

  .item-space {
    height: 15px;
  }

  .time {
    color: var(--el-text-color-secondary);
    font-size: 12px;
    text-align: center;
    margin-bottom: 10px;
  }

  .time-item {
    align-items: center;
    justify-content: center;
    margin-bottom: 10px;
    font-size: 15px;
    color: var(--el-text-color-secondary);
  }

  .face {
    width: 40px;
    height: 40px;
    line-height: 40px;
    border-radius: 40px;
    margin-right: 12px;
    background-color: var(--el-bg-color);
    text-align: center;
    color: var(--el-text-color-primary);
    font-size: 20px;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
}
</style>

