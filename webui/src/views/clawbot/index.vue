<template>
  <div class="clawbot-container">
    <!-- Header -->
    <div class="clawbot-header">
      <div class="header-left">
        <div class="bot-avatar">
          <span class="bot-icon">🤖</span>
        </div>
        <div class="header-info">
          <h3>ClawBot</h3>
          <span class="subtitle">{{ $t('clawbotSubtitle') }}</span>
        </div>
      </div>
      <div class="header-right">
        <el-select
          v-model="selectedDbId"
          :placeholder="$t('clawbotSelectDb')"
          size="small"
          style="width: 180px; margin-right: 12px;"
          :loading="loadingDbs"
        >
          <el-option v-for="db in databases" :key="db.id" :value="db.id" :label="db.name">
            <span>{{ db.name }}</span>
            <el-tag v-if="db.is_default" type="success" size="small" style="margin-left: 6px;">Default</el-tag>
          </el-option>
        </el-select>
        <el-tag :type="dbConnected ? 'success' : 'danger'" size="small" effect="plain">
          <el-icon style="margin-right: 4px;" size="12">
            <Connection v-if="dbConnected" />
            <CircleCloseFilled v-else />
          </el-icon>
          {{ dbConnected ? 'DB ' + $t('connected') : 'DB ' + $t('notConnected') }}
        </el-tag>
        <el-tag v-if="llmAvailable" type="success" size="small" effect="plain" style="margin-left: 8px;">
          <el-icon style="margin-right: 4px;" size="12"><MagicStick /></el-icon>
          {{ llmModel || 'LLM' }}
        </el-tag>
        <el-switch
          v-model="useLlm"
          :active-text="$t('clawbotLlmEnrich')"
          size="small"
          style="margin-left: 16px;"
        />
      </div>
    </div>

    <!-- Skill Chips -->
    <div class="skill-chips">
      <el-tag
        v-for="chip in quickChips"
        :key="chip.cmd"
        class="chip"
        effect="plain"
        round
        size="default"
        @click="onChipClick(chip.cmd)"
      >
        {{ chip.icon }} {{ chip.label }}
      </el-tag>
    </div>

    <!-- Messages -->
    <div ref="messagesDiv" class="messages-area">
      <!-- Welcome message -->
      <div v-if="messages.length === 0" class="welcome-card">
        <div class="welcome-icon">🤖</div>
        <h2>ClawBot</h2>
        <p>{{ $t('clawbotWelcome') }}</p>
        <div class="welcome-examples">
          <div class="example-item" @click="onChipClick('Veritabanı neden yavaş?')">
            💬 "{{ $t('clawbotExample1') }}"
          </div>
          <div class="example-item" @click="onChipClick('Kaç veritabanı var?')">
            💬 "{{ $t('clawbotExample2') }}"
          </div>
          <div class="example-item" @click="onChipClick('/health')">
            💬 "{{ $t('clawbotExample3') }}"
          </div>
          <div class="example-item" @click="onChipClick('/index')">
            💬 "{{ $t('clawbotExample4') }}"
          </div>
        </div>
      </div>

      <!-- Chat messages -->
      <div v-for="(msg, idx) in messages" :key="idx" class="message-row" :class="msg.role">
        <div class="msg-avatar">
          <el-avatar v-if="msg.role === 'user'" style="background: var(--el-color-primary);" :size="36">
            <el-icon size="18"><UserFilled /></el-icon>
          </el-avatar>
          <div v-else class="bot-msg-avatar">🤖</div>
        </div>
        <div class="msg-bubble" :class="msg.role">
          <div v-if="msg.loading" class="loading-dots">
            <el-icon class="is-loading" size="20" color="var(--el-text-color-secondary)"><Loading /></el-icon>
            <span style="margin-left: 8px; color: var(--el-text-color-secondary); font-size: 13px;">{{ $t('clawbotThinking') }}</span>
          </div>
          <div v-else class="msg-content" v-html="renderMarkdown(msg.content)" />
          <div v-if="!msg.loading && msg.intent" class="msg-meta">
            <el-tag size="small" type="info" effect="plain">{{ msg.intent }}</el-tag>
            <span v-if="msg.elapsed" class="elapsed">{{ msg.elapsed }}s</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="input-area">
      <div class="input-box">
        <el-input
          v-model="userInput"
          :placeholder="$t('clawbotPlaceholder')"
          clearable
          size="large"
          @keydown.enter.prevent="onSend"
        >
          <template #prefix>
            <span style="font-size: 18px;">🤖</span>
          </template>
        </el-input>
        <el-button
          type="primary"
          icon="Position"
          circle
          size="large"
          :disabled="!userInput.trim() || sending"
          :loading="sending"
          @click="onSend"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { clawbotAskReq, clawbotHealthReq, listClawbotDatabasesReq } from '@/api/clawbot'
import marked from '@/utils/markdownConfig.js'

const { t } = useI18n()

const HISTORY_KEY = 'anomivox-clawbot-history'

const messagesDiv = ref(null)
const messages = ref([])
const userInput = ref('')
const sending = ref(false)
const useLlm = ref(true)
const dbConnected = ref(false)
const llmAvailable = ref(false)
const llmModel = ref('')
const selectedDbId = ref(null)
const databases = ref([])
const loadingDbs = ref(false)

const quickChips = [
  { icon: '📊', label: 'Status', cmd: '/status' },
  { icon: '🏥', label: 'Health', cmd: '/health' },
  { icon: '🐌', label: 'Slow Queries', cmd: '/slow' },
  { icon: '⚡', label: 'Active', cmd: '/active' },
  { icon: '🔒', label: 'Locks', cmd: '/locks' },
  { icon: '📋', label: 'Tables', cmd: '/tables' },
  { icon: '📑', label: 'Index', cmd: '/index' },
  { icon: '🔍', label: 'Analyze', cmd: '/performance' },
]

const renderMarkdown = (text) => {
  if (!text) return ''
  // Convert **bold** and *italic* markdown
  return marked.parse(text)
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesDiv.value) {
      messagesDiv.value.scrollTop = messagesDiv.value.scrollHeight
    }
  })
}

const saveHistory = () => {
  const toSave = messages.value.filter(m => !m.loading).slice(-50)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(toSave))
}

const loadHistory = () => {
  try {
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
    messages.value = saved
  } catch {
    messages.value = []
  }
}

const checkHealth = async () => {
  try {
    const res = await clawbotHealthReq()
    if (res.code === 200 && res.data) {
      const d = res.data
      // Multi-DB health: check if any DB is connected
      if (d.databases && d.databases.length > 0) {
        dbConnected.value = d.databases.some(db => db.connected)
      } else {
        dbConnected.value = d.db_connected || false
      }
      llmAvailable.value = d.llm_model ? true : false
      llmModel.value = d.llm_model || ''
    }
  } catch {
    dbConnected.value = false
  }
}

const fetchDatabases = async () => {
  loadingDbs.value = true
  try {
    const res = await listClawbotDatabasesReq()
    if (res.code === 200 && res.data) {
      databases.value = res.data.filter(db => db.enabled)
      // Select default DB
      if (!selectedDbId.value && databases.value.length > 0) {
        const def = databases.value.find(db => db.is_default)
        selectedDbId.value = def ? def.id : databases.value[0].id
      }
    }
  } catch {
    databases.value = []
  } finally {
    loadingDbs.value = false
  }
}

const onChipClick = (cmd) => {
  userInput.value = cmd
  onSend()
}

const onSend = async () => {
  const msg = userInput.value.trim()
  if (!msg || sending.value) return

  // Add user message
  messages.value.push({
    role: 'user',
    content: msg,
    time: new Date().toISOString(),
  })
  userInput.value = ''
  scrollToBottom()

  // Add bot loading message
  messages.value.push({
    role: 'assistant',
    content: '',
    loading: true,
    time: new Date().toISOString(),
  })
  scrollToBottom()

  sending.value = true

  try {
    const res = await clawbotAskReq(msg, useLlm.value, selectedDbId.value)

    // Update bot message
    const lastIdx = messages.value.length - 1
    if (res.code === 200 && res.data) {
      messages.value[lastIdx] = {
        role: 'assistant',
        content: res.data.response || 'Yanıt alınamadı.',
        loading: false,
        intent: res.data.intent,
        elapsed: res.data.elapsed_sec ? res.data.elapsed_sec.toFixed(1) : null,
        time: res.data.timestamp,
      }
    } else {
      messages.value[lastIdx] = {
        role: 'assistant',
        content: `❌ ${res.msg || 'Hata oluştu'}`,
        loading: false,
        time: new Date().toISOString(),
      }
    }
  } catch (err) {
    const lastIdx = messages.value.length - 1
    messages.value[lastIdx] = {
      role: 'assistant',
      content: `❌ Bağlantı hatası: ${err.message || 'Sunucuya ulaşılamıyor'}`,
      loading: false,
      time: new Date().toISOString(),
    }
  } finally {
    sending.value = false
    scrollToBottom()
    saveHistory()
  }
}

watch(messages, scrollToBottom, { deep: true })

onMounted(() => {
  loadHistory()
  checkHealth()
  fetchDatabases()
  scrollToBottom()
})
</script>

<style lang="scss" scoped>
.clawbot-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 48px);
  background: var(--el-bg-color);
  border-radius: 16px;
  box-shadow: var(--el-box-shadow-light);
  border: 1px solid var(--el-border-color-light);
  overflow: hidden;
}

.clawbot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-light);
  flex-shrink: 0;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;

    .bot-avatar {
      width: 44px;
      height: 44px;
      border-radius: 12px;
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);

      .bot-icon {
        font-size: 24px;
      }
    }

    .header-info {
      h3 {
        margin: 0;
        font-size: 18px;
        font-weight: 700;
        color: var(--el-text-color-primary);
        letter-spacing: -0.3px;
      }
      .subtitle {
        font-size: 12px;
        color: var(--el-text-color-secondary);
      }
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
  }
}

.skill-chips {
  display: flex;
  gap: 8px;
  padding: 12px 24px;
  overflow-x: auto;
  flex-shrink: 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);

  &::-webkit-scrollbar {
    height: 4px;
  }

  .chip {
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s;
    border-color: var(--el-border-color-light);
    color: var(--el-text-color-regular);

    &:hover {
      background: var(--el-color-primary-light-9);
      border-color: var(--el-color-primary);
      color: var(--el-color-primary);
      transform: translateY(-1px);
    }
  }
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  scroll-behavior: smooth;

  .welcome-card {
    text-align: center;
    padding: 60px 20px;
    color: var(--el-text-color-regular);

    .welcome-icon {
      font-size: 64px;
      margin-bottom: 16px;
      animation: float 3s ease-in-out infinite;
    }

    @keyframes float {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-10px); }
    }

    h2 {
      font-size: 28px;
      font-weight: 700;
      margin: 0 0 8px 0;
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    p {
      font-size: 15px;
      color: var(--el-text-color-secondary);
      margin-bottom: 32px;
    }

    .welcome-examples {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      max-width: 600px;
      margin: 0 auto;

      .example-item {
        padding: 14px 18px;
        border-radius: 12px;
        background: var(--el-fill-color-light);
        border: 1px solid var(--el-border-color-lighter);
        cursor: pointer;
        transition: all 0.2s;
        font-size: 14px;
        text-align: left;
        color: var(--el-text-color-regular);

        &:hover {
          background: var(--el-color-primary-light-9);
          border-color: var(--el-color-primary);
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        }
      }
    }
  }

  .message-row {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    align-items: flex-start;

    &.user {
      flex-direction: row-reverse;
    }

    .msg-avatar {
      flex-shrink: 0;

      .bot-msg-avatar {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        box-shadow: 0 2px 8px rgba(99, 102, 241, 0.2);
      }
    }

    .msg-bubble {
      max-width: 75%;
      min-width: 60px;

      &.user {
        .msg-content {
          background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
          color: #fff;
          border-radius: 16px 4px 16px 16px;
          padding: 12px 18px;

          :deep(code) {
            background: rgba(255, 255, 255, 0.15);
            color: #fff;
          }
        }
      }

      &.assistant {
        .msg-content {
          background: var(--el-fill-color-light);
          border: 1px solid var(--el-border-color-light);
          color: var(--el-text-color-primary);
          border-radius: 4px 16px 16px 16px;
          padding: 14px 18px;
        }
      }

      .loading-dots {
        display: flex;
        align-items: center;
        padding: 14px 18px;
        background: var(--el-fill-color-light);
        border: 1px solid var(--el-border-color-light);
        border-radius: 4px 16px 16px 16px;
      }

      .msg-content {
        font-size: 14px;
        line-height: 1.7;
        word-break: break-word;

        :deep(p) {
          margin: 4px 0;
        }
        :deep(code) {
          background: var(--el-fill-color);
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 13px;
        }
        :deep(pre) {
          background: var(--el-fill-color-darker);
          padding: 12px;
          border-radius: 8px;
          overflow-x: auto;
          margin: 8px 0;

          code {
            background: transparent;
            padding: 0;
          }
        }
        :deep(strong) {
          font-weight: 600;
        }
        :deep(ul), :deep(ol) {
          padding-left: 20px;
          margin: 4px 0;
        }
      }

      .msg-meta {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 6px;
        padding: 0 4px;

        .elapsed {
          font-size: 11px;
          color: var(--el-text-color-placeholder);
        }
      }
    }
  }
}

.input-area {
  padding: 16px 24px;
  border-top: 1px solid var(--el-border-color-light);
  background: var(--el-fill-color-light);
  flex-shrink: 0;

  .input-box {
    display: flex;
    align-items: center;
    gap: 12px;
    max-width: 100%;

    :deep(.el-input__wrapper) {
      border-radius: 24px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06) !important;
      border: 1px solid var(--el-border-color-light);
      padding: 4px 16px;
      transition: all 0.3s;

      &:focus-within {
        box-shadow: 0 4px 16px rgba(99, 102, 241, 0.15) !important;
        border-color: #6366f1;
      }
    }
  }
}
</style>
