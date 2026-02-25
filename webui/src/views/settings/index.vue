<template>
  <div class="settings-container">
    <div class="settings-header">
      <h2>{{ $t('settingsTitle') }}</h2>
    </div>

    <!-- Only admin can see user management -->
    <div v-if="isAdmin" class="settings-section">
      <div class="section-header rowBC">
        <h3>
          <el-icon style="margin-right: 8px; vertical-align: middle;"><User /></el-icon>
          {{ $t('userManagement') }}
        </h3>
        <el-button type="primary" size="default" @click="showCreateDialog = true">
          <el-icon style="margin-right: 6px"><Plus /></el-icon>
          {{ $t('addUser') }}
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="users"
        stripe
        style="width: 100%; margin-top: 16px"
        :empty-text="$t('noData')"
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" :label="$t('username')" min-width="150">
          <template #default="{ row }">
            <div class="rowSC">
              <el-icon style="margin-right: 8px;" size="16">
                <UserFilled v-if="row.is_admin" />
                <User v-else />
              </el-icon>
              <span>{{ row.username }}</span>
              <el-tag v-if="row.is_admin" size="small" type="warning" style="margin-left: 8px">Admin</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="$t('status')" width="150">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="default">
              {{ row.is_active ? $t('active') : $t('inactive') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" :label="$t('createdAt')" width="200" />
        <el-table-column :label="$t('actions')" width="280" fixed="right">
          <template #default="{ row }">
            <template v-if="!row.is_admin">
              <el-button
                :type="row.is_active ? 'warning' : 'success'"
                size="small"
                plain
                @click="onToggleUser(row)"
              >
                {{ row.is_active ? $t('deactivate') : $t('activate') }}
              </el-button>
              <el-button
                type="primary"
                size="small"
                plain
                @click="onChangePassword(row)"
              >
                {{ $t('changePassword') }}
              </el-button>
              <el-button
                type="danger"
                size="small"
                plain
                @click="onDeleteUser(row)"
              >
                {{ $t('deleteUser') }}
              </el-button>
            </template>
            <span v-else style="color: var(--el-text-color-secondary); font-size: 12px;">
              {{ $t('adminProtected') }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- OpenClaw AI Gateway Settings (admin only) -->
    <div v-if="isAdmin" class="settings-section openclaw-section">
      <div class="section-header rowBC">
        <h3>
          <span style="margin-right: 8px; vertical-align: middle; font-size: 18px;">🤖</span>
          {{ $t('openclawSettings') }}
        </h3>
        <el-tag :type="openclawOnline ? 'success' : 'info'" size="default" effect="plain" round>
          <el-icon style="margin-right: 4px;"><CircleCheck v-if="openclawOnline" /><WarningFilled v-else /></el-icon>
          {{ openclawOnline ? $t('openclawGatewayOnline') : $t('openclawGatewayOffline') }}
        </el-tag>
      </div>

      <p class="section-desc">{{ $t('openclawDesc') }}</p>

      <el-form label-position="top" class="telegram-form" v-loading="openclawLoading">

        <!-- ═══ AI Model ═══ -->
        <div class="form-group">
          <div class="form-group-title">🧠 {{ $t('openclawModel') }}</div>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item :label="$t('openclawModelProvider')">
                <el-select v-model="openclawConfig.model_provider" style="width: 100%">
                  <el-option label="Anthropic (Claude)" value="anthropic" />
                  <el-option label="OpenAI (GPT)" value="openai" />
                  <el-option label="Google (Gemini)" value="google" />
                  <el-option label="Groq" value="groq" />
                  <el-option label="DeepSeek" value="deepseek" />
                  <el-option label="Ollama (Local)" value="ollama" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="$t('openclawModelName')">
                <el-input v-model="openclawConfig.model_name" :placeholder="$t('openclawModelNamePlaceholder')" />
                <div class="form-hint">{{ $t('openclawModelNameHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="$t('openclawApiKey')">
                <el-input
                  v-model="openclawConfig.api_key"
                  type="password"
                  show-password
                  :placeholder="openclawConfig.api_key_set ? $t('tokenSetLeaveBlank') : $t('openclawApiKeyPlaceholder')"
                  clearable
                />
                <div class="form-hint">
                  <span v-if="openclawConfig.api_key_set" class="token-status token-set">✓ {{ $t('tokenSet') }}</span>
                  <span v-else class="token-status token-not-set">○ {{ $t('tokenNotSet') }}</span>
                  — {{ $t('openclawApiKeyHint') }}
                </div>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- ═══ Channels ═══ -->
        <el-divider />
        <div class="form-group">
          <div class="form-group-title">📡 {{ $t('openclawChannels') }}</div>

          <!-- Telegram -->
          <div class="channel-card">
            <div class="channel-header">
              <div class="channel-name">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                </svg>
                {{ $t('openclawTelegram') }}
              </div>
              <el-switch v-model="openclawConfig.telegram_enabled" size="small" />
            </div>
            <div v-if="openclawConfig.telegram_enabled" class="channel-body">
              <el-form-item :label="$t('openclawTelegramToken')">
                <el-input
                  v-model="openclawConfig.telegram_token"
                  type="password"
                  show-password
                  :placeholder="openclawConfig.telegram_token_set ? $t('tokenSetLeaveBlank') : $t('openclawTelegramTokenPlaceholder')"
                  clearable
                />
                <div class="form-hint">
                  <span v-if="openclawConfig.telegram_token_set" class="token-status token-set">✓ {{ $t('tokenSet') }}</span>
                  <span v-else class="token-status token-not-set">○ {{ $t('tokenNotSet') }}</span>
                  — {{ $t('openclawTelegramTokenHint') }}
                </div>
              </el-form-item>
              <el-form-item :label="$t('openclawAllowFrom')">
                <el-input
                  v-model="openclawConfig.telegram_allow_from"
                  :placeholder="$t('openclawAllowFromPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('openclawAllowFromHint') }}</div>
              </el-form-item>
            </div>
          </div>

          <!-- WhatsApp -->
          <div class="channel-card">
            <div class="channel-header">
              <div class="channel-name">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                </svg>
                {{ $t('openclawWhatsapp') }}
              </div>
              <el-switch v-model="openclawConfig.whatsapp_enabled" size="small" />
            </div>
            <div v-if="openclawConfig.whatsapp_enabled" class="channel-body">
              <div class="form-hint" style="margin-bottom: 8px;">{{ $t('openclawWhatsappHint') }}</div>
              <el-form-item :label="$t('openclawAllowFrom')">
                <el-input
                  v-model="openclawConfig.whatsapp_allow_from"
                  :placeholder="$t('openclawAllowFromPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('openclawAllowFromHint') }}</div>
              </el-form-item>
            </div>
          </div>

          <!-- Discord -->
          <div class="channel-card">
            <div class="channel-header">
              <div class="channel-name">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286z"/>
                </svg>
                {{ $t('openclawDiscord') }}
              </div>
              <el-switch v-model="openclawConfig.discord_enabled" size="small" />
            </div>
            <div v-if="openclawConfig.discord_enabled" class="channel-body">
              <el-form-item :label="$t('openclawDiscordToken')">
                <el-input
                  v-model="openclawConfig.discord_token"
                  type="password"
                  show-password
                  :placeholder="openclawConfig.discord_token_set ? $t('tokenSetLeaveBlank') : $t('openclawDiscordTokenPlaceholder')"
                  clearable
                />
                <div class="form-hint">
                  <span v-if="openclawConfig.discord_token_set" class="token-status token-set">✓ {{ $t('tokenSet') }}</span>
                  <span v-else class="token-status token-not-set">○ {{ $t('tokenNotSet') }}</span>
                  — {{ $t('openclawDiscordTokenHint') }}
                </div>
              </el-form-item>
              <el-form-item :label="$t('openclawAllowFrom')">
                <el-input
                  v-model="openclawConfig.discord_allow_from"
                  :placeholder="$t('openclawAllowFromPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('openclawAllowFromHint') }}</div>
              </el-form-item>
            </div>
          </div>

          <!-- Slack -->
          <div class="channel-card">
            <div class="channel-header">
              <div class="channel-name">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/>
                </svg>
                {{ $t('openclawSlack') }}
              </div>
              <el-switch v-model="openclawConfig.slack_enabled" size="small" />
            </div>
            <div v-if="openclawConfig.slack_enabled" class="channel-body">
              <el-row :gutter="16">
                <el-col :span="12">
                  <el-form-item :label="$t('openclawSlackBotToken')">
                    <el-input
                      v-model="openclawConfig.slack_bot_token"
                      type="password"
                      show-password
                      :placeholder="openclawConfig.slack_token_set ? $t('tokenSetLeaveBlank') : $t('openclawSlackBotTokenPlaceholder')"
                      clearable
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item :label="$t('openclawSlackAppToken')">
                    <el-input
                      v-model="openclawConfig.slack_app_token"
                      type="password"
                      show-password
                      :placeholder="$t('openclawSlackAppTokenPlaceholder')"
                      clearable
                    />
                  </el-form-item>
                </el-col>
              </el-row>
              <div class="form-hint">
                <span v-if="openclawConfig.slack_token_set" class="token-status token-set">✓ {{ $t('tokenSet') }}</span>
                <span v-else class="token-status token-not-set">○ {{ $t('tokenNotSet') }}</span>
                — {{ $t('openclawSlackHint') }}
              </div>
            </div>
          </div>
        </div>

        <!-- ═══ Browser ═══ -->
        <el-divider />
        <div class="form-group">
          <div class="form-group-title">🌐 {{ $t('openclawBrowser') }}</div>
          <div class="toggle-item">
            <el-switch v-model="openclawConfig.browser_enabled" />
            <div class="toggle-info">
              <span class="toggle-label">{{ $t('openclawBrowserEnabled') }}</span>
              <span class="toggle-hint">{{ $t('openclawBrowserHint') }}</span>
            </div>
          </div>
        </div>

        <!-- Setup Guide -->
        <el-collapse class="setup-guide">
          <el-collapse-item :title="$t('openclawSetupGuide')">
            <div class="guide-steps">
              <p>{{ $t('openclawStep1') }}</p>
              <p>{{ $t('openclawStep2') }}</p>
              <p>{{ $t('openclawStep3') }}</p>
              <p>{{ $t('openclawStep4') }}</p>
              <p>{{ $t('openclawStep5') }}</p>
            </div>
          </el-collapse-item>
        </el-collapse>

        <!-- Action buttons -->
        <div class="telegram-actions">
          <el-button
            type="default"
            :loading="testingOpenclaw"
            @click="onTestOpenclaw"
          >
            <el-icon style="margin-right: 6px;"><Connection /></el-icon>
            {{ $t('testConnection') }}
          </el-button>
          <el-button
            type="warning"
            :loading="restartingOpenclaw"
            @click="onRestartOpenclaw"
          >
            <el-icon style="margin-right: 6px;"><RefreshRight /></el-icon>
            {{ $t('openclawRestart') }}
          </el-button>
          <el-button type="primary" :loading="savingOpenclaw" @click="onSaveOpenclaw">
            <el-icon style="margin-right: 6px;"><Check /></el-icon>
            {{ $t('save') }}
          </el-button>
        </div>
      </el-form>
    </div>

    <!-- Mail (SMTP) Settings (admin only) -->
    <div v-if="isAdmin" class="settings-section mail-section">
      <div class="section-header rowBC">
        <h3>
          <el-icon style="margin-right: 8px; vertical-align: middle;" :size="18"><Message /></el-icon>
          {{ $t('mailSettings') }}
        </h3>
        <el-tag :type="mailConfig.password_set ? 'success' : 'info'" size="default" effect="plain" round>
          <el-icon style="margin-right: 4px;"><CircleCheck v-if="mailConfig.password_set" /><WarningFilled v-else /></el-icon>
          {{ mailConfig.password_set ? $t('connected') : $t('notConnected') }}
        </el-tag>
      </div>

      <p class="section-desc">{{ $t('mailDesc') }}</p>

      <el-form label-position="top" class="telegram-form" v-loading="mailLoading">
        <!-- SMTP Presets -->
        <div class="form-group">
          <el-form-item :label="$t('smtpPresets')">
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              <el-button size="small" plain @click="applySmtpPreset('gmail')">Gmail</el-button>
              <el-button size="small" plain @click="applySmtpPreset('outlook')">Outlook / Office365</el-button>
              <el-button size="small" plain @click="applySmtpPreset('yandex')">Yandex</el-button>
              <el-button size="small" plain @click="applySmtpPreset('sendgrid')">SendGrid</el-button>
            </div>
          </el-form-item>
        </div>

        <!-- SMTP Server Settings -->
        <div class="form-group">
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item :label="$t('smtpHost')">
                <el-input
                  v-model="mailConfig.smtp_host"
                  :placeholder="$t('smtpHostPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('smtpHostHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item :label="$t('smtpPort')">
                <el-input-number
                  v-model="mailConfig.smtp_port"
                  :min="1"
                  :max="65535"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :span="5">
              <el-form-item :label="$t('useTls')">
                <div class="toggle-item" style="padding: 0;">
                  <el-switch v-model="mailConfig.use_tls" @change="onTlsChange" />
                  <div class="toggle-info">
                    <span class="toggle-hint">{{ $t('useTlsHint') }}</span>
                  </div>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="5">
              <el-form-item :label="$t('useSsl')">
                <div class="toggle-item" style="padding: 0;">
                  <el-switch v-model="mailConfig.use_ssl" @change="onSslChange" />
                  <div class="toggle-info">
                    <span class="toggle-hint">{{ $t('useSslHint') }}</span>
                  </div>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- Credentials -->
        <div class="form-group">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('smtpUsername')">
                <el-input
                  v-model="mailConfig.username"
                  :placeholder="$t('smtpUsernamePlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('smtpUsernameHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('smtpPassword')">
                <el-input
                  v-model="mailConfig.password"
                  type="password"
                  show-password
                  :placeholder="$t('smtpPasswordPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('smtpPasswordHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- From / Recipients -->
        <div class="form-group">
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item :label="$t('fromName')">
                <el-input
                  v-model="mailConfig.from_name"
                  :placeholder="$t('fromNamePlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('fromNameHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="$t('fromAddress')">
                <el-input
                  v-model="mailConfig.from_address"
                  :placeholder="$t('fromAddressPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('fromAddressHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="$t('mailRecipients')">
                <el-input
                  v-model="mailConfig.recipients"
                  :placeholder="$t('mailRecipientsPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('mailRecipientsHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- Notification Toggles -->
        <el-divider />
        <div class="form-group">
          <el-row :gutter="20">
            <el-col :span="8">
              <div class="toggle-item">
                <el-switch v-model="mailConfig.notify_on_alert" />
                <div class="toggle-info">
                  <span class="toggle-label">{{ $t('notifyOnAlert') }}</span>
                  <span class="toggle-hint">{{ $t('notifyOnAlertHint') }}</span>
                </div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="toggle-item">
                <el-switch v-model="mailConfig.notify_on_diagnosis" />
                <div class="toggle-info">
                  <span class="toggle-label">{{ $t('notifyOnDiagnosis') }}</span>
                  <span class="toggle-hint">{{ $t('notifyOnDiagnosisHint') }}</span>
                </div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="toggle-item">
                <el-switch v-model="mailConfig.notify_on_health" />
                <div class="toggle-info">
                  <span class="toggle-label">{{ $t('notifyOnHealth') }}</span>
                  <span class="toggle-hint">{{ $t('notifyOnHealthHint') }}</span>
                </div>
              </div>
            </el-col>
          </el-row>
        </div>

        <!-- Thresholds -->
        <el-divider />
        <div class="form-group">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('healthCheckInterval')">
                <el-input-number
                  v-model="mailConfig.health_check_interval"
                  :min="30"
                  :max="3600"
                  :step="30"
                  style="width: 100%"
                />
                <div class="form-hint">{{ $t('healthCheckIntervalHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('slowQueryThreshold')">
                <el-input-number
                  v-model="mailConfig.slow_query_threshold"
                  :min="0.5"
                  :max="60"
                  :step="0.5"
                  :precision="1"
                  style="width: 100%"
                />
                <div class="form-hint">{{ $t('slowQueryThresholdHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- Setup Guide -->
        <el-collapse class="setup-guide">
          <el-collapse-item :title="$t('mailSetupGuide')">
            <div class="guide-steps">
              <p>{{ $t('mailStep1') }}</p>
              <p>{{ $t('mailStep2') }}</p>
              <p>{{ $t('mailStep3') }}</p>
              <p>{{ $t('mailStep4') }}</p>
              <p>{{ $t('mailStep5') }}</p>
            </div>
          </el-collapse-item>
        </el-collapse>

        <!-- Action buttons -->
        <div class="telegram-actions">
          <el-button
            type="default"
            :loading="testingMail"
            @click="onTestMail"
            :disabled="!mailConfig.smtp_host || !mailConfig.username"
          >
            <el-icon style="margin-right: 6px;"><Connection /></el-icon>
            {{ $t('testConnection') }}
          </el-button>
          <el-button type="primary" :loading="savingMail" @click="onSaveMail">
            <el-icon style="margin-right: 6px;"><Check /></el-icon>
            {{ $t('save') }}
          </el-button>
        </div>
      </el-form>
    </div>

    <!-- Non-admin users see info message -->
    <div v-else class="settings-section">
      <el-result icon="info" :title="$t('noPermission')" :sub-title="$t('noPermissionDesc')">
        <template #icon>
          <el-icon size="64" color="var(--el-color-info)"><Lock /></el-icon>
        </template>
      </el-result>
    </div>

    <!-- Create User Dialog -->
    <el-dialog v-model="showCreateDialog" :title="$t('addUser')" width="420px" :close-on-click-modal="false">
      <el-form ref="refCreateForm" :model="createForm" :rules="createRules" label-width="120px">
        <el-form-item :label="$t('username')" prop="username">
          <el-input v-model="createForm.username" :placeholder="$t('pleaseInputUsername')" />
        </el-form-item>
        <el-form-item :label="$t('password')" prop="password">
          <el-input v-model="createForm.password" type="password" show-password :placeholder="$t('pleaseInputPassword')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">{{ $t('cancel') }}</el-button>
        <el-button type="primary" :loading="createLoading" @click="onCreateUser">{{ $t('create') }}</el-button>
      </template>
    </el-dialog>

    <!-- Change Password Dialog -->
    <el-dialog v-model="showPasswordDialog" :title="$t('changePassword')" width="420px" :close-on-click-modal="false">
      <el-form ref="refPasswordForm" :model="passwordForm" :rules="passwordRules" label-width="120px">
        <el-form-item :label="$t('username')">
          <el-input :model-value="passwordForm.username" disabled />
        </el-form-item>
        <el-form-item :label="$t('newPassword')" prop="newPassword">
          <el-input v-model="passwordForm.newPassword" type="password" show-password :placeholder="$t('pleaseInputNewPassword')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">{{ $t('cancel') }}</el-button>
        <el-button type="primary" :loading="passwordLoading" @click="onSubmitPassword">{{ $t('save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useBasicStore } from '@/store/basic'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsersReq, createUserReq, toggleUserReq, deleteUserReq, changePasswordReq } from '@/api/user'
import { openclawHealthReq, getOpenclawConfigReq, saveOpenclawConfigReq, openclawRestartReq } from '@/api/openclaw'
import { getMailConfigReq, saveMailConfigReq, testMailReq } from '@/api/mail'
import { useI18n } from 'vue-i18n'

const { t: $t } = useI18n()
const basicStore = useBasicStore()
const isAdmin = computed(() => basicStore.roles.includes('admin'))

const loading = ref(false)
const users = ref([])

const fetchUsers = async () => {
  loading.value = true
  try {
    const res = await listUsersReq()
    if (res.code === 200) {
      users.value = res.data || []
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (isAdmin.value) {
    fetchUsers()
    fetchOpenclawConfig()
    fetchMailConfig()
  }
})

// ========== OpenClaw Config ==========
const openclawLoading = ref(false)
const savingOpenclaw = ref(false)
const testingOpenclaw = ref(false)
const restartingOpenclaw = ref(false)
const openclawOnline = ref(false)

const openclawConfig = reactive({
  model_provider: 'anthropic',
  model_name: 'claude-sonnet-4-20250514',
  api_key: '',
  api_key_set: false,
  telegram_enabled: false,
  telegram_token: '',
  telegram_token_set: false,
  telegram_allow_from: '',
  whatsapp_enabled: false,
  whatsapp_allow_from: '',
  discord_enabled: false,
  discord_token: '',
  discord_token_set: false,
  discord_allow_from: '',
  slack_enabled: false,
  slack_bot_token: '',
  slack_app_token: '',
  slack_token_set: false,
  browser_enabled: false,
})

const fetchOpenclawConfig = async () => {
  openclawLoading.value = true
  try {
    // Check health
    try {
      const healthRes = await openclawHealthReq()
      openclawOnline.value = healthRes.code === 200 && healthRes.data?.status === 'online'
    } catch (e) {
      openclawOnline.value = false
    }

    // Get config — backend returns FLAT structure
    const res = await getOpenclawConfigReq()
    if (res.code === 200 && res.data) {
      const d = res.data

      // Model — flat "model" field like "anthropic/claude-opus-4-6"
      if (d.model) {
        const model = d.model
        if (model.includes('/')) {
          const idx = model.indexOf('/')
          openclawConfig.model_provider = model.substring(0, idx)
          openclawConfig.model_name = model.substring(idx + 1)
        } else {
          openclawConfig.model_name = model
        }
      }

      // API Key status
      openclawConfig.api_key_set = d.api_key_set || false
      openclawConfig.api_key = '' // never returned from backend

      // Telegram
      openclawConfig.telegram_enabled = d.telegram_enabled || false
      openclawConfig.telegram_token = '' // never returned
      openclawConfig.telegram_token_set = d.telegram_bot_token_set || false
      openclawConfig.telegram_allow_from = Array.isArray(d.telegram_allow_from)
        ? d.telegram_allow_from.join(', ')
        : (d.telegram_allow_from || '')

      // WhatsApp
      openclawConfig.whatsapp_enabled = d.whatsapp_enabled || false
      openclawConfig.whatsapp_allow_from = Array.isArray(d.whatsapp_allow_from)
        ? d.whatsapp_allow_from.join(', ')
        : (d.whatsapp_allow_from || '')

      // Discord
      openclawConfig.discord_enabled = d.discord_enabled || false
      openclawConfig.discord_token = '' // never returned
      openclawConfig.discord_token_set = d.discord_bot_token_set || false
      openclawConfig.discord_allow_from = Array.isArray(d.discord_allow_from)
        ? d.discord_allow_from.join(', ')
        : (d.discord_allow_from || '')

      // Slack
      openclawConfig.slack_enabled = d.slack_enabled || false
      openclawConfig.slack_bot_token = '' // never returned
      openclawConfig.slack_app_token = '' // never returned
      openclawConfig.slack_token_set = d.slack_bot_token_set || false

      // Browser
      openclawConfig.browser_enabled = d.browser_enabled || false
    }
  } catch (e) {
    console.error('Failed to load OpenClaw config:', e)
  } finally {
    openclawLoading.value = false
  }
}

const onSaveOpenclaw = async () => {
  savingOpenclaw.value = true
  try {
    // Build FLAT payload matching backend expectations
    const payload = {
      model: openclawConfig.model_provider + '/' + openclawConfig.model_name,
      browser_enabled: openclawConfig.browser_enabled,
      // Channel enable flags
      telegram_enabled: openclawConfig.telegram_enabled,
      whatsapp_enabled: openclawConfig.whatsapp_enabled,
      discord_enabled: openclawConfig.discord_enabled,
      slack_enabled: openclawConfig.slack_enabled,
    }

    // API Key
    if (openclawConfig.api_key) {
      payload.api_key = openclawConfig.api_key
    }

    // Telegram
    if (openclawConfig.telegram_enabled) {
      if (openclawConfig.telegram_token) {
        payload.telegram_bot_token = openclawConfig.telegram_token
      }
      payload.telegram_allow_from = openclawConfig.telegram_allow_from
        ? openclawConfig.telegram_allow_from.split(',').map(s => s.trim()).filter(Boolean)
        : []
    }

    // WhatsApp
    if (openclawConfig.whatsapp_enabled) {
      payload.whatsapp_allow_from = openclawConfig.whatsapp_allow_from
        ? openclawConfig.whatsapp_allow_from.split(',').map(s => s.trim()).filter(Boolean)
        : []
    }

    // Discord
    if (openclawConfig.discord_enabled) {
      if (openclawConfig.discord_token) {
        payload.discord_bot_token = openclawConfig.discord_token
      }
      payload.discord_allow_from = openclawConfig.discord_allow_from
        ? openclawConfig.discord_allow_from.split(',').map(s => s.trim()).filter(Boolean)
        : []
    }

    // Slack
    if (openclawConfig.slack_enabled) {
      if (openclawConfig.slack_bot_token) {
        payload.slack_bot_token = openclawConfig.slack_bot_token
      }
      if (openclawConfig.slack_app_token) {
        payload.slack_app_token = openclawConfig.slack_app_token
      }
    }

    const res = await saveOpenclawConfigReq(payload)
    if (res.code === 200) {
      ElMessage.success($t('openclawSaveSuccess'))
      openclawConfig.api_key = ''
      fetchOpenclawConfig()
    } else {
      ElMessage.error(res.msg || $t('openclawSaveFail'))
    }
  } catch (e) {
    ElMessage.error($t('openclawSaveFail'))
  } finally {
    savingOpenclaw.value = false
  }
}

const onTestOpenclaw = async () => {
  testingOpenclaw.value = true
  try {
    const res = await openclawHealthReq()
    if (res.code === 200 && res.data?.status === 'online') {
      openclawOnline.value = true
      ElMessage.success($t('openclawTestSuccess'))
    } else {
      openclawOnline.value = false
      ElMessage.error($t('openclawTestFail'))
    }
  } catch (e) {
    openclawOnline.value = false
    ElMessage.error($t('openclawTestFail'))
  } finally {
    testingOpenclaw.value = false
  }
}

const onRestartOpenclaw = async () => {
  restartingOpenclaw.value = true
  try {
    const res = await openclawRestartReq()
    if (res.code === 200) {
      ElMessage.success($t('openclawRestartSuccess'))
      setTimeout(() => fetchOpenclawConfig(), 3000)
    } else {
      ElMessage.error($t('openclawRestartFail'))
    }
  } catch (e) {
    ElMessage.error($t('openclawRestartFail'))
  } finally {
    restartingOpenclaw.value = false
  }
}

// ========== Mail Config ==========
const mailLoading = ref(false)
const savingMail = ref(false)
const testingMail = ref(false)
const mailConfig = reactive({
  smtp_host: '',
  smtp_port: 587,
  use_tls: true,
  use_ssl: false,
  username: '',
  password: '',
  password_set: false,
  from_name: 'Anomivox',
  from_address: '',
  recipients: '',
  notify_on_alert: true,
  notify_on_diagnosis: true,
  notify_on_health: false,
  health_check_interval: 300,
  slow_query_threshold: 5.0
})

const fetchMailConfig = async () => {
  mailLoading.value = true
  try {
    const res = await getMailConfigReq()
    if (res.code === 200 && res.data) {
      const d = res.data
      mailConfig.smtp_host = d.smtp_host || ''
      mailConfig.smtp_port = d.smtp_port || 587
      mailConfig.use_tls = d.use_tls ?? true
      mailConfig.use_ssl = d.use_ssl ?? false
      mailConfig.username = d.username || ''
      mailConfig.password = ''
      mailConfig.password_set = d.password_set || false
      mailConfig.from_name = d.from_name || 'Anomivox'
      mailConfig.from_address = d.from_address || ''
      mailConfig.recipients = d.recipients || ''
      mailConfig.notify_on_alert = d.notify_on_alert ?? true
      mailConfig.notify_on_diagnosis = d.notify_on_diagnosis ?? true
      mailConfig.notify_on_health = d.notify_on_health ?? false
      mailConfig.health_check_interval = d.health_check_interval || 300
      mailConfig.slow_query_threshold = d.slow_query_threshold || 5.0
    }
  } catch (e) {
    console.error('Failed to load Mail config:', e)
  } finally {
    mailLoading.value = false
  }
}

const onSaveMail = async () => {
  savingMail.value = true
  try {
    const res = await saveMailConfigReq({
      smtp_host: mailConfig.smtp_host,
      smtp_port: mailConfig.smtp_port,
      use_tls: mailConfig.use_tls,
      use_ssl: mailConfig.use_ssl,
      username: mailConfig.username,
      password: mailConfig.password,
      from_name: mailConfig.from_name,
      from_address: mailConfig.from_address,
      recipients: mailConfig.recipients,
      notify_on_alert: mailConfig.notify_on_alert,
      notify_on_diagnosis: mailConfig.notify_on_diagnosis,
      notify_on_health: mailConfig.notify_on_health,
      health_check_interval: mailConfig.health_check_interval,
      slow_query_threshold: mailConfig.slow_query_threshold
    })
    if (res.code === 200) {
      ElMessage.success($t('saveSuccess'))
      fetchMailConfig()
    } else {
      ElMessage.error(res.msg || 'Error')
    }
  } catch (e) {
    ElMessage.error(e?.msg || 'Error')
  } finally {
    savingMail.value = false
  }
}

const onTestMail = async () => {
  testingMail.value = true
  try {
    const res = await testMailReq()
    if (res.code === 200) {
      ElMessage.success($t('mailTestSuccess'))
    } else {
      ElMessage.error($t('mailTestFail') + ': ' + (res.msg || ''))
    }
  } catch (e) {
    ElMessage.error($t('mailTestFail'))
  } finally {
    testingMail.value = false
  }
}

// TLS/SSL mutually exclusive
const onTlsChange = (val) => {
  if (val) {
    mailConfig.use_ssl = false
    mailConfig.smtp_port = 587
  }
}
const onSslChange = (val) => {
  if (val) {
    mailConfig.use_tls = false
    mailConfig.smtp_port = 465
  }
}

// SMTP presets
const applySmtpPreset = (preset) => {
  const presets = {
    gmail: { host: 'smtp.gmail.com', port: 587, tls: true, ssl: false },
    outlook: { host: 'smtp.office365.com', port: 587, tls: true, ssl: false },
    yandex: { host: 'smtp.yandex.com', port: 465, tls: false, ssl: true },
    sendgrid: { host: 'smtp.sendgrid.net', port: 587, tls: true, ssl: false },
  }
  const p = presets[preset]
  if (p) {
    mailConfig.smtp_host = p.host
    mailConfig.smtp_port = p.port
    mailConfig.use_tls = p.tls
    mailConfig.use_ssl = p.ssl
  }
}

// Create user
const showCreateDialog = ref(false)
const createLoading = ref(false)
const refCreateForm = ref(null)
const createForm = reactive({ username: '', password: '' })
const createRules = {
  username: [{ required: true, message: () => $t('pleaseInputUsername'), trigger: 'blur' }],
  password: [
    { required: true, message: () => $t('pleaseInputPassword'), trigger: 'blur' },
    { min: 6, message: () => $t('passwordMinLength'), trigger: 'blur' }
  ]
}

const onCreateUser = () => {
  refCreateForm.value.validate(async (valid) => {
    if (!valid) return
    createLoading.value = true
    try {
      const res = await createUserReq(createForm.username, createForm.password)
      if (res.code === 200) {
        ElMessage.success(res.msg)
        showCreateDialog.value = false
        createForm.username = ''
        createForm.password = ''
        fetchUsers()
      } else {
        ElMessage.error(res.msg)
      }
    } catch (e) {
      ElMessage.error(e?.msg || 'Error')
    } finally {
      createLoading.value = false
    }
  })
}

// Toggle user
const onToggleUser = async (row) => {
  try {
    const res = await toggleUserReq(row.id)
    if (res.code === 200) {
      ElMessage.success(res.msg)
      fetchUsers()
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error(e?.msg || 'Error')
  }
}

// Delete user
const onDeleteUser = (row) => {
  ElMessageBox.confirm(
    $t('deleteUserConfirm', { username: row.username }),
    $t('warning'),
    { confirmButtonText: $t('deleteUser'), cancelButtonText: $t('cancel'), type: 'warning' }
  ).then(async () => {
    try {
      const res = await deleteUserReq(row.id)
      if (res.code === 200) {
        ElMessage.success(res.msg)
        fetchUsers()
      } else {
        ElMessage.error(res.msg)
      }
    } catch (e) {
      ElMessage.error(e?.msg || 'Error')
    }
  }).catch(() => {})
}

// Change password
const showPasswordDialog = ref(false)
const passwordLoading = ref(false)
const refPasswordForm = ref(null)
const passwordForm = reactive({ userId: null, username: '', newPassword: '' })
const passwordRules = {
  newPassword: [
    { required: true, message: () => $t('pleaseInputNewPassword'), trigger: 'blur' },
    { min: 6, message: () => $t('passwordMinLength'), trigger: 'blur' }
  ]
}

const onChangePassword = (row) => {
  passwordForm.userId = row.id
  passwordForm.username = row.username
  passwordForm.newPassword = ''
  showPasswordDialog.value = true
}

const onSubmitPassword = () => {
  refPasswordForm.value.validate(async (valid) => {
    if (!valid) return
    passwordLoading.value = true
    try {
      const res = await changePasswordReq(passwordForm.userId, passwordForm.newPassword)
      if (res.code === 200) {
        ElMessage.success(res.msg)
        showPasswordDialog.value = false
      } else {
        ElMessage.error(res.msg)
      }
    } catch (e) {
      ElMessage.error(e?.msg || 'Error')
    } finally {
      passwordLoading.value = false
    }
  })
}
</script>

<style lang="scss" scoped>
.settings-container {
  padding: 24px;
  max-width: 960px;
  margin: 0 auto;
}

.settings-header {
  margin-bottom: 24px;

  h2 {
    font-size: 22px;
    font-weight: 700;
    color: var(--el-text-color-primary);
    margin: 0;
  }
}

.settings-section {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
}

.section-header {
  h3 {
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0;
  }
}

.section-desc {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin: 8px 0 20px 0;
  line-height: 1.5;
}

.telegram-form {
  .form-group {
    margin-bottom: 4px;
  }

  .form-hint {
    font-size: 12px;
    color: var(--el-text-color-placeholder);
    margin-top: 4px;
    line-height: 1.4;
  }

  .el-divider {
    margin: 16px 0;
  }
}

.toggle-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 0;

  .el-switch {
    flex-shrink: 0;
    margin-top: 2px;
  }

  .toggle-info {
    display: flex;
    flex-direction: column;
    gap: 2px;

    .toggle-label {
      font-size: 14px;
      font-weight: 500;
      color: var(--el-text-color-primary);
    }

    .toggle-hint {
      font-size: 12px;
      color: var(--el-text-color-placeholder);
      line-height: 1.4;
    }
  }
}

.setup-guide {
  margin: 16px 0;
  border: none;

  :deep(.el-collapse-item__header) {
    font-size: 13px;
    font-weight: 500;
    color: var(--el-color-primary);
    background: transparent;
    border-bottom: none;
    height: 36px;
    line-height: 36px;
  }

  :deep(.el-collapse-item__wrap) {
    background: transparent;
    border-bottom: none;
  }

  .guide-steps {
    padding: 8px 0;

    p {
      font-size: 13px;
      color: var(--el-text-color-secondary);
      margin: 6px 0;
      line-height: 1.6;
    }
  }
}

.telegram-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.telegram-section {
  margin-top: 20px;
}

.openclaw-section {
  margin-top: 20px;
}

.channel-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;

  .channel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: var(--el-fill-color-lighter);

    .channel-name {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      font-weight: 500;
      color: var(--el-text-color-primary);

      svg {
        flex-shrink: 0;
      }
    }
  }

  .channel-body {
    padding: 16px;
  }
}

.form-group-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 16px;
}

.whatsapp-section {
  margin-top: 20px;
}

.mail-section {
  margin-top: 20px;
}

.token-status {
  font-weight: 500;
  font-size: 12px;

  &.token-set {
    color: var(--el-color-success);
  }

  &.token-not-set {
    color: var(--el-text-color-placeholder);
  }
}
</style>
