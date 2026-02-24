<template>
  <div class="relative columnSC chat-container">
    <div class="header">
      <div class="header-item">
        <span style="color: #333333;">{{ $t('llmModel') }}</span>
        <el-select
            v-model="llmModel"
            class="llm-select"
            placeholder="Select"
            size="default"
            style="width: 120px"
        >
          <template #empty>
            <div class="el-select__empty">{{ $t('noData') }}</div>
          </template>
          <el-option
              v-for="item in modelList"
              :key="item"
              :label="item"
              :value="item"
          />
        </el-select>
      </div>
      <div class="header-item">
        <span style="color: #333333;">{{ $t('historicalSessionRounds') }}</span>
        <el-input-number v-model="historyLength" size="default" :min="1" :max="5"/>
      </div>
    </div>

    <div ref="messagesScrollDiv" class="messages-container">
      <chat-item v-for="(item, index) in messageList" :key="index" class="infinite-list-item" :message="item"/>
    </div>

    <BottomInputContainer style="width: calc(100% - 20px)" :placeholder="$t('askAnything')" @send-click="onSendClick"/>
  </div>
</template>

<script setup lang="ts" name="Index">

import {chatReq, llmModelListModelsReq} from "@/api/knowledge";
import BottomInputContainer from "@/components/BottomInputContainer.vue";
import ChatItem from "@/components/ChatItem.vue";
import {ElMessage} from "element-plus";
import moment from "moment-mini";
import {ref, watch, nextTick, onMounted} from 'vue'
import {useRouter} from 'vue-router'
import {useI18n} from 'vue-i18n'

interface Message {
  role: string;
  content: string;
  time: string;
  loading: boolean;
}

const CHAT_HISTORY_KEY = 'anomivox-chat-history'

const router = useRouter()
const { t } = useI18n()

const llmModel: Ref<string> = ref('')

const historyLength: Ref<number> = ref(3)

const modelList = ref<string[]>([])

const messageList: Ref<Message[]> = ref([]);

const messagesScrollDiv = ref<HTMLElement | null>(null);


watch(() => messageList.value, () => {
  nextTick(() => {
    if (messagesScrollDiv.value) {
      messagesScrollDiv.value.scrollTop = messagesScrollDiv.value.scrollHeight;
    }
  })
})

onMounted(() => {
  nextTick(() => {
    getLlmModelListModels()
    messageList.value = getLocalHistoryMessages()
  })
});

const getLlmModelListModels = async () => {
  llmModelListModelsReq().then(res => {
    modelList.value = res.data;
    llmModel.value = modelList.value[0]
  })
}

const addUserMessage = (content: string) => {
  const userMessage: Message = {
    role: 'user',
    content,
    time: moment().format('YYYY-MM-DD HH:mm:ss'),
    loading: false
  }
  messageList.value.push(userMessage)
}

const addRobotMessage = (content: string) => {
  const robotMessage: Message = {
    role: 'assistant',
    content,
    time: moment().format('YYYY-MM-DD HH:mm:ss'),
    loading: true
  }
  messageList.value.push(robotMessage)
}

const updateLastRobotMessage = (content: string) => {
  const lastMessageIndex = messageList.value.length - 1;
  const lastMessage = messageList.value[lastMessageIndex];
  const updatedMessage = {
    ...lastMessage,
    content,
    loading: false
  };
  messageList.value[lastMessageIndex] = updatedMessage;
}

const updateLastRobotMessageLoading = (loading: boolean) => {
  const lastMessage = messageList.value[messageList.value.length - 1]
  lastMessage.loading = loading
}

const getHistoryMessages = () => {
  return messageList.value.slice(-historyLength.value).map(item => {
    return {
      role: item.role,
      content: item.content
    }
  })
}

const saveHistoryMessagesToLocal = () => {
  localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(messageList.value))
}

const getLocalHistoryMessages = () => {
  const historyMessages = JSON.parse(localStorage.getItem(CHAT_HISTORY_KEY) || '[]')
  return historyMessages.map((item: Message) => {
    return {
      role: item.role,
      content: item.content,
      time: item.time,
      loading: item.loading
    };
  });
}

const onSendClick = (value) => {
  if (value === '') {
    ElMessage.error(t('pleaseInputSomething'))
    return
  }
  const userInputValue = value
  const historyMessages = getHistoryMessages() || []
  addUserMessage(userInputValue)
  saveHistoryMessagesToLocal()
  addRobotMessage('')
  saveHistoryMessagesToLocal()
  const { isDone, fetchResult } = chatReq(userInputValue,"",llmModel.value,historyMessages,historyLength.value)
  watch([isDone, fetchResult], ([done, result]) => {
    if(done){
      updateLastRobotMessageLoading(false)
      saveHistoryMessagesToLocal()
    }
    let content = ''
    result.forEach((item) => {
      content += item.text
    })
    updateLastRobotMessage(content)
  }, {deep: true})
}

</script>

<style>
.llm-select .el-select__wrapper {
  background-color: transparent !important;
  box-shadow: None !important;
}
</style>


<style lang="scss" scoped>
.chat-container {
  height: calc(100vh - 48px);
  overflow: hidden;
  background: #FFFFFF;
  border-radius: 16px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
  border: 1px solid var(--border-color);

  .header {
    width: 100%;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    padding: 16px 24px;
    flex-wrap: wrap;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    grid-gap: 12px 24px;
    background: #F8FAFC;
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    
    .header-item {
      display: flex;
      align-items: center;
      gap: 8px;
      
      span {
        font-weight: 500;
        color: #475569 !important;
      }
    }
  }

  .messages-container {
    height: calc(100vh - 180px);
    width: 100%;
    flex-shrink: 1;
    background: transparent;
    overflow-y: auto;
    padding: 20px;
  }
}
</style>
