<template>
  <div class="chat-root">
    <!-- Sol panel: Konuşma listesi -->
    <div class="chat-sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">💬 {{ $t('chatSessions') }}</span>
        <el-button type="primary" size="small" :icon="Plus" circle @click="onNewConversation" :loading="creatingConv" />
      </div>

      <!-- Admin: kullanıcı filtresi -->
      <div v-if="isAdmin" class="user-filter">
        <el-select
          v-model="filterUserId"
          :placeholder="$t('allUsers')"
          size="small"
          clearable
          style="width:100%"
          @change="loadConversations"
        >
          <el-option :label="$t('allUsers')" :value="null" />
          <el-option
            v-for="u in userList"
            :key="u.id"
            :label="u.username + (u.is_admin ? ' (admin)' : '')"
            :value="u.id"
          />
        </el-select>
      </div>

      <div class="conv-list" v-loading="loadingConvs">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: activeConvId === conv.id }"
          @click="onSelectConversation(conv)"
        >
          <div class="conv-item-main">
            <el-icon class="conv-icon"><ChatDotRound /></el-icon>
            <span v-if="renamingId !== conv.id" class="conv-name" :title="conv.name">{{ conv.name }}</span>
            <el-input
              v-else
              v-model="renamingValue"
              size="small"
              class="rename-input"
              @keyup.enter="confirmRename(conv)"
              @blur="confirmRename(conv)"
              @click.stop
              autofocus
            />
          </div>
          <div class="conv-item-meta" v-if="isAdmin && conv.user_id">
            <span class="user-badge">{{ getUserName(conv.user_id) }}</span>
          </div>
          <div class="conv-actions" @click.stop>
            <el-tooltip v-if="isAdmin || conv.user_id === currentUserId" :content="$t('rename')" placement="top">
              <el-icon class="action-icon" @click="startRename(conv)"><Edit /></el-icon>
            </el-tooltip>
            <el-tooltip v-if="isAdmin" :content="$t('delete')" placement="top">
              <el-icon class="action-icon danger" @click="onDeleteConversation(conv)"><Delete /></el-icon>
            </el-tooltip>
          </div>
        </div>
        <div v-if="!loadingConvs && conversations.length === 0" class="conv-empty">
          {{ $t('noConversations') }}
        </div>
      </div>
    </div>

    <!-- Sağ panel: Chat alanı -->
    <div class="chat-main">
      <div class="chat-toolbar">
        <div class="header-item">
          <span>{{ $t('llmModel') }}</span>
          <el-select v-model="llmModel" size="default" style="width: 140px" placeholder="Select">
            <template #empty><div class="el-select__empty">{{ $t('noData') }}</div></template>
            <el-option v-for="item in modelList" :key="item" :label="item" :value="item" />
          </el-select>
        </div>
        <div class="header-item">
          <span>{{ $t('historicalSessionRounds') }}</span>
          <el-input-number v-model="historyLength" size="default" :min="1" :max="10" />
        </div>
        <div v-if="activeConvId" class="header-item conv-title-display">
          <el-icon><ChatDotRound /></el-icon>
          <span>{{ activeConvName }}</span>
        </div>
      </div>

      <div ref="messagesScrollDiv" class="messages-container">
        <div v-if="!activeConvId && messageList.length === 0" class="empty-state">
          <el-icon :size="48" style="opacity:0.2"><ChatDotRound /></el-icon>
          <p>{{ $t('selectOrNewChat') }}</p>
        </div>
        <chat-item
          v-for="(item, index) in messageList"
          :key="index"
          class="infinite-list-item"
          :message="item"
        />
      </div>

      <BottomInputContainer
        style="width: calc(100% - 20px)"
        :placeholder="isAdminViewingOther ? $t('adminCannotChat') : $t('askAnything')"
        :inputDisabled="isAdminViewingOther"
        @send-click="onSendClick"
      />
    </div>
  </div>
</template>

<script setup lang="ts" name="Index">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, ChatDotRound } from '@element-plus/icons-vue'
import moment from 'moment-mini'

import { useBasicStore } from '@/store/basic'
import BottomInputContainer from '@/components/BottomInputContainer.vue'
import ChatItem from '@/components/ChatItem.vue'
import {
  chatReq,
  llmModelListModelsReq,
  createConversationReq,
  listConversationsReq,
  getConversationMessagesReq,
  renameConversationReq,
  deleteConversationReq,
} from '@/api/knowledge'
import { listUsersReq } from '@/api/user'

interface Message {
  role: string
  content: string
  time: string
  loading: boolean
}

interface Conversation {
  id: string
  name: string
  chat_type: string
  user_id: number | null
  create_time: string
}

const { t } = useI18n()
const basicStore = useBasicStore()
const isAdmin = computed(() => basicStore.roles?.includes('admin'))
const currentUserId = computed(() => basicStore.userInfo?.id ?? null)

// Admin baska kullanicinin sohbetini mi goruntuluyor?
const isAdminViewingOther = computed(() => {
  if (!isAdmin.value || !activeConvId.value) return false
  const conv = conversations.value.find(c => c.id === activeConvId.value)
  if (!conv) return false
  return conv.user_id !== null && conv.user_id !== currentUserId.value
})

const llmModel = ref('')
const historyLength = ref(3)
const modelList = ref<string[]>([])

const conversations = ref<Conversation[]>([])
const loadingConvs = ref(false)
const activeConvId = ref<string | null>(null)
const activeConvName = ref('')
const creatingConv = ref(false)

const filterUserId = ref<number | null>(null)
const userList = ref<{ id: number; username: string; is_admin: boolean }[]>([])

const messageList = ref<Message[]>([])
const messagesScrollDiv = ref<HTMLElement | null>(null)

const renamingId = ref<string | null>(null)
const renamingValue = ref('')

watch(() => messageList.value, () => {
  nextTick(() => {
    if (messagesScrollDiv.value) {
      messagesScrollDiv.value.scrollTop = messagesScrollDiv.value.scrollHeight
    }
  })
}, { deep: true })

onMounted(async () => {
  await nextTick()
  await getLlmModelListModels()
  await loadConversations()
  if (isAdmin.value) {
    await loadUserList()
  }
})

const getLlmModelListModels = async () => {
  try {
    const res = await llmModelListModelsReq()
    modelList.value = res.data || []
    if (modelList.value.length) llmModel.value = modelList.value[0]
  } catch (e) {}
}

const loadConversations = async () => {
  loadingConvs.value = true
  try {
    const res = await listConversationsReq(filterUserId.value)
    if (res.code === 200) conversations.value = res.data || []
  } catch (e) {
    ElMessage.error(t('loadFailed'))
  } finally {
    loadingConvs.value = false
  }
}

const loadUserList = async () => {
  try {
    const res = await listUsersReq()
    if (res.code === 200) userList.value = res.data || []
  } catch (e) {}
}

const getUserName = (userId: number) => {
  const u = userList.value.find(u => u.id === userId)
  return u ? u.username : `#${userId}`
}

const onNewConversation = async () => {
  creatingConv.value = true
  try {
    const res = await createConversationReq(t('newChat'))
    if (res.code === 200) {
      await loadConversations()
      const newConv = conversations.value.find(c => c.id === res.data.conversation_id)
      if (newConv) onSelectConversation(newConv)
    }
  } catch (e) {
    ElMessage.error(t('createFailed'))
  } finally {
    creatingConv.value = false
  }
}

const onSelectConversation = async (conv: Conversation) => {
  activeConvId.value = conv.id
  activeConvName.value = conv.name
  messageList.value = []
  try {
    const res = await getConversationMessagesReq(conv.id)
    if (res.code === 200 && res.data) {
      messageList.value = (res.data as any[]).map(m => ({
        role: m.role,
        content: m.content,
        time: m.time || '',
        loading: false,
      }))
    }
  } catch (e) {}
}

const startRename = (conv: Conversation) => {
  renamingId.value = conv.id
  renamingValue.value = conv.name
}

const confirmRename = async (conv: Conversation) => {
  if (!renamingValue.value.trim() || renamingValue.value === conv.name) {
    renamingId.value = null
    return
  }
  try {
    const res = await renameConversationReq(conv.id, renamingValue.value.trim())
    if (res.code === 200) {
      conv.name = renamingValue.value.trim()
      if (activeConvId.value === conv.id) activeConvName.value = conv.name
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error(t('saveFailed'))
  } finally {
    renamingId.value = null
  }
}

const onDeleteConversation = async (conv: Conversation) => {
  try {
    await ElMessageBox.confirm(t('deleteConvConfirm'), t('confirm'), {
      type: 'warning',
      confirmButtonText: t('delete'),
      cancelButtonText: t('cancel'),
    })
  } catch (_) { return }

  try {
    const res = await deleteConversationReq(conv.id)
    if (res.code === 200) {
      if (activeConvId.value === conv.id) {
        activeConvId.value = null
        activeConvName.value = ''
        messageList.value = []
      }
      await loadConversations()
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error(t('deleteFailed'))
  }
}

const addUserMessage = (content: string) => {
  messageList.value.push({ role: 'user', content, time: moment().format('YYYY-MM-DD HH:mm:ss'), loading: false })
}

const addRobotMessage = () => {
  messageList.value.push({ role: 'assistant', content: '', time: moment().format('YYYY-MM-DD HH:mm:ss'), loading: true })
}

const updateLastRobotMessage = (content: string) => {
  const idx = messageList.value.length - 1
  if (idx >= 0) messageList.value[idx] = { ...messageList.value[idx], content, loading: false }
}

const getHistoryMessages = () =>
  messageList.value.slice(-historyLength.value).map(item => ({ role: item.role, content: item.content }))

const onSendClick = async (value: string) => {
  if (isAdminViewingOther.value) {
    ElMessage.warning(t('adminCannotChat'))
    return
  }
  if (!value.trim()) {
    ElMessage.error(t('pleaseInputSomething'))
    return
  }

  if (!activeConvId.value) {
    creatingConv.value = true
    try {
      const res = await createConversationReq(value.slice(0, 30))
      if (res.code === 200) {
        activeConvId.value = res.data.conversation_id
        activeConvName.value = value.slice(0, 30)
        await loadConversations()
      }
    } catch (e) {
      ElMessage.error(t('createFailed'))
      creatingConv.value = false
      return
    } finally {
      creatingConv.value = false
    }
  }

  const historyMessages = getHistoryMessages()
  addUserMessage(value)
  addRobotMessage()

  const { isDone, fetchResult } = chatReq(
    value, activeConvId.value!, llmModel.value, historyMessages, historyLength.value
  )

  watch([isDone, fetchResult], ([done, result]) => {
    if (done) {
      const idx = messageList.value.length - 1
      if (idx >= 0) messageList.value[idx] = { ...messageList.value[idx], loading: false }
    }
    let content = ''
    ;(result as any[]).forEach(item => { content += item.text })
    updateLastRobotMessage(content)
  }, { deep: true })

  const conv = conversations.value.find(c => c.id === activeConvId.value)
  if (conv && ['Yeni Sohbet', 'New Chat', t('newChat')].includes(conv.name)) {
    const newName = value.slice(0, 30)
    try {
      await renameConversationReq(activeConvId.value!, newName)
      conv.name = newName
      activeConvName.value = newName
    } catch (_) {}
  }
}
</script>

<style lang="scss" scoped>
.chat-root {
  display: flex;
  height: calc(100vh - 48px);
  gap: 12px;
  overflow: hidden;
}

.chat-sidebar {
  width: 240px;
  flex-shrink: 0;
  background: var(--el-bg-color);
  border-radius: 16px;
  border: 1px solid var(--el-border-color-light);
  box-shadow: var(--el-box-shadow-light);
  display: flex;
  flex-direction: column;
  overflow: hidden;

  .sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 12px 10px;
    border-bottom: 1px solid var(--el-border-color-lighter);
    .sidebar-title {
      font-weight: 600;
      font-size: 13px;
      color: var(--el-text-color-primary);
    }
  }

  .user-filter {
    padding: 8px 10px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }

  .conv-list {
    flex: 1;
    overflow-y: auto;
    padding: 6px 0;
  }

  .conv-item {
    padding: 8px 10px;
    cursor: pointer;
    border-radius: 8px;
    margin: 2px 6px;
    transition: background 0.15s;
    position: relative;

    &:hover {
      background: var(--el-fill-color-light);
      .conv-actions { opacity: 1; }
    }

    &.active {
      background: var(--el-color-primary-light-9);
      .conv-name { color: var(--el-color-primary); font-weight: 600; }
    }

    .conv-item-main {
      display: flex;
      align-items: center;
      gap: 6px;
      .conv-icon { color: var(--el-text-color-placeholder); flex-shrink: 0; }
      .conv-name {
        font-size: 13px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex: 1;
        min-width: 0;
      }
      .rename-input { flex: 1; }
    }

    .conv-item-meta {
      margin-top: 3px;
      padding-left: 20px;
      .user-badge {
        font-size: 11px;
        color: var(--el-text-color-placeholder);
        background: var(--el-fill-color);
        border-radius: 4px;
        padding: 1px 5px;
      }
    }

    .conv-actions {
      position: absolute;
      right: 6px;
      top: 50%;
      transform: translateY(-50%);
      display: flex;
      gap: 4px;
      opacity: 0;
      transition: opacity 0.15s;
      .action-icon {
        font-size: 13px;
        color: var(--el-text-color-placeholder);
        cursor: pointer;
        padding: 3px;
        border-radius: 4px;
        &:hover { color: var(--el-color-primary); background: var(--el-fill-color); }
        &.danger:hover { color: var(--el-color-danger); }
      }
    }
  }

  .conv-empty {
    text-align: center;
    color: var(--el-text-color-placeholder);
    font-size: 12px;
    padding: 24px 12px;
  }
}

.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border-radius: 16px;
  border: 1px solid var(--el-border-color-light);
  box-shadow: var(--el-box-shadow-light);
  overflow: hidden;

  .chat-toolbar {
    display: flex;
    align-items: center;
    gap: 20px;
    padding: 14px 20px;
    border-bottom: 1px solid var(--el-border-color-light);
    background: var(--el-fill-color-light);
    flex-wrap: wrap;

    .header-item {
      display: flex;
      align-items: center;
      gap: 8px;
      span { font-weight: 500; color: var(--el-text-color-regular); font-size: 13px; }
    }

    .conv-title-display {
      margin-left: auto;
      color: var(--el-text-color-secondary);
      font-size: 13px;
      gap: 6px;
    }
  }

  .messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 20px;

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: var(--el-text-color-placeholder);
      gap: 12px;
      p { font-size: 14px; margin: 0; }
    }
  }
}
</style>
