<template>
  <div class="relative columnSC chat-container">
        <div class="header">
      <div class="header-item">
        <span>{{ $t('llmModel') }}</span>
        <el-select
            v-model="llmModel"
            class="llm-select"
            placeholder="Select"
            size="default"
            style="width: 200px"
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
        <span>{{ $t('knowledgeBase') }}</span>
        <el-select
            v-model="knowledgeBase"
            class="llm-select"
            placeholder="Select"
            size="default"
            style="width: 200px"
        >
          <template #empty>
            <div class="el-select__empty">{{ $t('noData') }}</div>
          </template>
          <el-option
              v-for="item in knowledgeBaseList"
              :key="item"
              :label="item"
              :value="item"
          />
        </el-select>
      </div>

      <div class="header-item">
        <span>{{ $t('historicalSessionRounds') }}</span>
        <el-input-number v-model="historyLength" size="default" :min="1" :max="5"/>
      </div>

      <div class="header-item">
        <span>{{ $t('useCache') }}</span>
        <el-switch v-model="userCache" size="default"/>
      </div>

      <div class="header-item" style="margin-left: auto;">
        <el-button type="danger" plain size="small" @click="clearChatHistory">
          🗑️ {{ $t('clearChat') }}
        </el-button>
      </div>
    </div>

    <div ref="messagesScrollDiv" class="messages-container">
      <knowledge-chat-item
          v-for="(item, index) in messageList" :key="index" class="infinite-list-item" :message="item"
          :is-last="index === messageList.length - 1" @ignore-message-cache="ignoreMessageCache"/>
    </div>

    <BottomInputContainer style="width: calc(100% - 20px)" :placeholder="$t('askAnything')" @send-click="onSendClick" />
  </div>
</template>

<script setup lang="ts" name="Index">

import {knowledgeChatReq, knowledgeListReq, llmModelListModelsReq} from "@/api/knowledge";
import KnowledgeChatItem from "@/components/KnowledgeChatItem.vue";
import BottomInputContainer from "@/components/BottomInputContainer.vue";
import {ElMessage} from "element-plus";
import moment from "moment-mini";
import {ref, watch, nextTick, onMounted} from 'vue'
import {useRouter} from 'vue-router'
import {useI18n} from 'vue-i18n'

interface KnowledgeMessage {
  role: string;
  ask: string;
  content: string;
  time: string;
  loading: boolean;
  docs: string[],
  docsDetail: object[],
  cache: boolean;
  cacheData: object[]
}

const KNOWLEDGE_CHAT_HISTORY_PREFIX = 'anomivox-kb-chat-'
const KNOWLEDGE_CHAT_USR_CACHE_KEY = 'anomivox-knowledge-chat-use-cache'

/** Return a per-KB localStorage key for chat history */
const chatHistoryKey = () => `${KNOWLEDGE_CHAT_HISTORY_PREFIX}${knowledgeBase.value}`

const router = useRouter()
const { t } = useI18n()

const llmModel: Ref<string> = ref('')

const historyLength: Ref<number> = ref(3)

const userCache = ref(localStorage.getItem(KNOWLEDGE_CHAT_USR_CACHE_KEY) === 'true');

const modelList = ref<string[]>([])

const knowledgeBaseList = ref<string[]>([])

const knowledgeBase: Ref<string> = ref('')

const messageList: Ref<KnowledgeMessage[]> = ref([]);

const messagesScrollDiv = ref<HTMLElement | null>(null);

watch(() => messageList.value, () => {
  nextTick(() => {
    if (messagesScrollDiv.value) {
      messagesScrollDiv.value.scrollTop = messagesScrollDiv.value.scrollHeight;
    }
  })
})

watch(userCache, (newValue) => {
  localStorage.setItem(KNOWLEDGE_CHAT_USR_CACHE_KEY, String(newValue));
});

// When the selected KB changes, load its own chat history
watch(knowledgeBase, (newKb, oldKb) => {
  if (newKb) {
    messageList.value = getLocalHistoryMessages()
  } else {
    messageList.value = []
  }
})

onMounted(() => {
  nextTick(() => {
    getLlmModelListModels()
    getKnowledgeList()
    // messageList will be loaded by the knowledgeBase watcher after getKnowledgeList sets it
  })
});

const getKnowledgeList = async () => {
  knowledgeListReq().then(res => {
    knowledgeBaseList.value = [...new Set<string>(res.data.map(item => item.kb_name))];
    knowledgeBase.value = knowledgeBaseList.value[0] || ''
  })
}

const getLlmModelListModels = async () => {
  llmModelListModelsReq().then(res => {
    modelList.value = res.data || [];
    llmModel.value = modelList.value[0]
  })
}

const addUserMessage = (content: string) => {
  const userMessage: KnowledgeMessage = {
    role: 'user',
    ask: '',
    content,
    time: moment().format('YYYY-MM-DD HH:mm:ss'),
    loading: false,
    docs: [],
    docsDetail: [],
    cache: false,
    cacheData: []
  }
  messageList.value.push(userMessage)
}

const addRobotMessage = (content: string, ask: string) => {
  const robotMessage: KnowledgeMessage = {
    role: 'assistant',
    ask,
    content,
    time: moment().format('YYYY-MM-DD HH:mm:ss'),
    loading: true,
    docs: [],
    docsDetail: [],
    cache: false,
    cacheData: []
  }
  messageList.value.push(robotMessage)
}

const updateLastRobotMessage = (content: string, docs: string[], docsDetail: object[], cache: boolean, cacheData: object[]) => {
  const lastMessageIndex = messageList.value.length - 1;
  const lastMessage = messageList.value[lastMessageIndex];
  const updatedMessage = {
    ...lastMessage,
    content,
    docs,
    docsDetail,
    cache,
    cacheData,
    loading:false
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
  if (!knowledgeBase.value) return
  localStorage.setItem(chatHistoryKey(), JSON.stringify(messageList.value))
}

const clearChatHistory = () => {
  if (!knowledgeBase.value) return
  messageList.value = []
  localStorage.removeItem(chatHistoryKey())
  ElMessage.success(t('chatCleared'))
}

const ignoreMessageCache = (message: KnowledgeMessage) => {
  const userInputValue = message.ask
  updateLastRobotMessage("", [], [], false, [])
  updateLastRobotMessageLoading(true)
  saveHistoryMessagesToLocal()
  knowledgeChat(userInputValue, true, true)
}

const getLocalHistoryMessages = () => {
  if (!knowledgeBase.value) return []
  const historyMessages = JSON.parse(localStorage.getItem(chatHistoryKey()) || '[]')
  return historyMessages.map((item: KnowledgeMessage) => {
    return {
      role: item.role,
      ask: item.ask,
      content: item.content,
      time: item.time,
      loading: item.loading,
      docs: item.docs || [],
      docsDetail: item.docsDetail || [],
      cache: item.cache || false,
      cacheData: item.cacheData || []
    };
  });
}

const onSendClick = (value) => {
  if (value === '') {
    ElMessage.error(t('pleaseInputSomething'))
    return
  }
  if (!knowledgeBase.value) {
    ElMessage.warning(t('pleaseCreateAndSelectKnowledgeBase'))
    return
  }
  const userInputValue = value
  addUserMessage(userInputValue)
  saveHistoryMessagesToLocal()
  addRobotMessage('', userInputValue)
  saveHistoryMessagesToLocal()
  knowledgeChat(userInputValue, !userCache.value, userCache.value)
}

const knowledgeChat = (userInputValue, ignoreCache, answerCache,) => {
  const historyMessages = getHistoryMessages() || []
  const { isDone, fetchResult } = knowledgeChatReq(userInputValue, ignoreCache, answerCache, knowledgeBase.value, llmModel.value, historyMessages, historyLength.value)
  watch([isDone, fetchResult], ([done, result]) => {
    let answer = ''
    let docs = []
    let docsDetail = []
    let cache = false
    let cacheData = []
    result.forEach((item) => {
      answer += (item.answer || '')
      docs = docs.concat(item.docs || [])
      docsDetail = docsDetail.concat(item.docsDetail || [])
      cache = item.cache || false
      cacheData = cacheData.concat(item.cacheData || [])
    })
    if(done){
      updateLastRobotMessageLoading(false)
      saveHistoryMessagesToLocal()
    }
    if (!answer.includes('No Cache')) {
      updateLastRobotMessage(answer, docs || [], docsDetail || [], cache || false, cacheData || [])
    }else {
      knowledgeChat(userInputValue, true, true)
    }
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
  background: var(--el-bg-color);
  border-radius: 16px;
  box-shadow: var(--el-box-shadow-light);
  border: 1px solid var(--el-border-color-light);

  .header {
    width: 100%;
    border-bottom: 1px solid var(--el-border-color-light);
    display: flex;
    align-items: center;
    padding: 16px 24px;
    flex-wrap: wrap;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    grid-gap: 12px 24px;
    background: var(--el-fill-color-light);
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    
    .header-item {
      display: flex;
      align-items: center;
      gap: 8px;
      
      span {
        font-weight: 500;
        color: var(--el-text-color-primary) !important;
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
