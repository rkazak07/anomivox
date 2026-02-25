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

    <!-- Telegram Bot Settings (admin only) -->
    <div v-if="isAdmin" class="settings-section telegram-section">
      <div class="section-header rowBC">
        <h3>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style="margin-right: 8px; vertical-align: middle;">
            <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
          </svg>
          {{ $t('telegramSettings') }}
        </h3>
        <el-tag :type="telegramConfig.bot_token_set ? 'success' : 'info'" size="default" effect="plain" round>
          <el-icon style="margin-right: 4px;"><CircleCheck v-if="telegramConfig.bot_token_set" /><WarningFilled v-else /></el-icon>
          {{ telegramConfig.bot_token_set ? $t('connected') : $t('notConnected') }}
        </el-tag>
      </div>

      <p class="section-desc">{{ $t('telegramDesc') }}</p>

      <el-form label-position="top" class="telegram-form" v-loading="telegramLoading">
        <!-- Connection Settings -->
        <div class="form-group">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('botToken')">
                <el-input
                  v-model="telegramConfig.bot_token"
                  type="password"
                  show-password
                  :placeholder="$t('botTokenPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('botTokenHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('chatId')">
                <el-input
                  v-model="telegramConfig.chat_id"
                  :placeholder="$t('chatIdPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('chatIdHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item :label="$t('allowedUsers')">
                <el-input
                  v-model="telegramConfig.allowed_users"
                  :placeholder="$t('allowedUsersPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('allowedUsersHint') }}</div>
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
                <el-switch v-model="telegramConfig.notify_on_alert" />
                <div class="toggle-info">
                  <span class="toggle-label">{{ $t('notifyOnAlert') }}</span>
                  <span class="toggle-hint">{{ $t('notifyOnAlertHint') }}</span>
                </div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="toggle-item">
                <el-switch v-model="telegramConfig.notify_on_diagnosis" />
                <div class="toggle-info">
                  <span class="toggle-label">{{ $t('notifyOnDiagnosis') }}</span>
                  <span class="toggle-hint">{{ $t('notifyOnDiagnosisHint') }}</span>
                </div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="toggle-item">
                <el-switch v-model="telegramConfig.auto_diagnose" />
                <div class="toggle-info">
                  <span class="toggle-label">{{ $t('autoDiagnose') }}</span>
                  <span class="toggle-hint">{{ $t('autoDiagnoseHint') }}</span>
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
                  v-model="telegramConfig.health_check_interval"
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
                  v-model="telegramConfig.slow_query_threshold"
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
          <el-collapse-item :title="$t('telegramBotSetupGuide')">
            <div class="guide-steps">
              <p>{{ $t('telegramStep1') }}</p>
              <p>{{ $t('telegramStep2') }}</p>
              <p>{{ $t('telegramStep3') }}</p>
              <p>{{ $t('telegramStep4') }}</p>
            </div>
          </el-collapse-item>
        </el-collapse>

        <!-- Action buttons -->
        <div class="telegram-actions">
          <el-button
            type="default"
            :loading="testingConnection"
            @click="onTestConnection"
            :disabled="!telegramConfig.bot_token && !telegramConfig.bot_token_set"
          >
            <el-icon style="margin-right: 6px;"><Connection /></el-icon>
            {{ $t('testConnection') }}
          </el-button>
          <el-button type="primary" :loading="savingTelegram" @click="onSaveTelegram">
            <el-icon style="margin-right: 6px;"><Check /></el-icon>
            {{ $t('save') }}
          </el-button>
        </div>
      </el-form>
    </div>

    <!-- WhatsApp Business Settings (admin only) -->
    <div v-if="isAdmin" class="settings-section whatsapp-section">
      <div class="section-header rowBC">
        <h3>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style="margin-right: 8px; vertical-align: middle;">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
          </svg>
          {{ $t('whatsappSettings') }}
        </h3>
        <el-tag :type="whatsappConfig.access_token_set ? 'success' : 'info'" size="default" effect="plain" round>
          <el-icon style="margin-right: 4px;"><CircleCheck v-if="whatsappConfig.access_token_set" /><WarningFilled v-else /></el-icon>
          {{ whatsappConfig.access_token_set ? $t('connected') : $t('notConnected') }}
        </el-tag>
      </div>

      <p class="section-desc">{{ $t('whatsappDesc') }}</p>

      <el-form label-position="top" class="telegram-form" v-loading="whatsappLoading">
        <!-- Connection Settings -->
        <div class="form-group">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('accessToken')">
                <el-input
                  v-model="whatsappConfig.access_token"
                  type="password"
                  show-password
                  :placeholder="$t('accessTokenPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('accessTokenHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('phoneNumberId')">
                <el-input
                  v-model="whatsappConfig.phone_number_id"
                  :placeholder="$t('phoneNumberIdPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('phoneNumberIdHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item :label="$t('businessAccountId')">
                <el-input
                  v-model="whatsappConfig.business_account_id"
                  :placeholder="$t('businessAccountIdPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('businessAccountIdHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('verifyToken')">
                <el-input
                  v-model="whatsappConfig.verify_token"
                  :placeholder="$t('verifyTokenPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('verifyTokenHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item :label="$t('allowedNumbers')">
                <el-input
                  v-model="whatsappConfig.allowed_numbers"
                  :placeholder="$t('allowedNumbersPlaceholder')"
                  clearable
                />
                <div class="form-hint">{{ $t('allowedNumbersHint') }}</div>
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
                <el-switch v-model="whatsappConfig.notify_on_alert" />
                <div class="toggle-info">
                  <span class="toggle-label">{{ $t('notifyOnAlert') }}</span>
                  <span class="toggle-hint">{{ $t('notifyOnAlertHint') }}</span>
                </div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="toggle-item">
                <el-switch v-model="whatsappConfig.notify_on_diagnosis" />
                <div class="toggle-info">
                  <span class="toggle-label">{{ $t('notifyOnDiagnosis') }}</span>
                  <span class="toggle-hint">{{ $t('notifyOnDiagnosisHint') }}</span>
                </div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="toggle-item">
                <el-switch v-model="whatsappConfig.auto_diagnose" />
                <div class="toggle-info">
                  <span class="toggle-label">{{ $t('autoDiagnose') }}</span>
                  <span class="toggle-hint">{{ $t('autoDiagnoseHint') }}</span>
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
                  v-model="whatsappConfig.health_check_interval"
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
                  v-model="whatsappConfig.slow_query_threshold"
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
          <el-collapse-item :title="$t('whatsappSetupGuide')">
            <div class="guide-steps">
              <p>{{ $t('whatsappStep1') }}</p>
              <p>{{ $t('whatsappStep2') }}</p>
              <p>{{ $t('whatsappStep3') }}</p>
              <p>{{ $t('whatsappStep4') }}</p>
              <p>{{ $t('whatsappStep5') }}</p>
            </div>
          </el-collapse-item>
        </el-collapse>

        <!-- Action buttons -->
        <div class="telegram-actions">
          <el-button
            type="default"
            :loading="testingWhatsapp"
            @click="onTestWhatsapp"
            :disabled="!whatsappConfig.access_token && !whatsappConfig.access_token_set"
          >
            <el-icon style="margin-right: 6px;"><Connection /></el-icon>
            {{ $t('testConnection') }}
          </el-button>
          <el-button type="primary" :loading="savingWhatsapp" @click="onSaveWhatsapp">
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

    <!-- ClawBot Settings (admin only) -->
    <div v-if="isAdmin" class="settings-section clawbot-section">
      <div class="section-header rowBC">
        <h3>
          <span style="margin-right: 8px; vertical-align: middle; font-size: 18px;">🤖</span>
          {{ $t('clawbotSettings') }}
        </h3>
        <el-tag :type="clawbotDatabases.length > 0 ? 'success' : 'info'" size="default" effect="plain" round>
          <el-icon style="margin-right: 4px;"><Monitor /></el-icon>
          {{ clawbotDatabases.length }} DB
        </el-tag>
      </div>

      <p class="section-desc">{{ $t('clawbotDesc') }}</p>

      <el-form label-position="top" class="telegram-form">

        <!-- ═══ Multi-DB Bağlantıları ═══ -->
        <div class="form-group">
          <div class="form-group-title" style="display: flex; justify-content: space-between; align-items: center;">
            <span>🐘 {{ $t('clawbotDatabases') }}</span>
            <el-button type="primary" size="small" @click="onAddDatabase">
              <el-icon style="margin-right: 4px;"><Plus /></el-icon>
              {{ $t('clawbotAddDb') }}
            </el-button>
          </div>

          <!-- DB List -->
          <el-table :data="clawbotDatabases" style="width: 100%; margin-top: 12px;" size="small" stripe>
            <el-table-column prop="name" :label="$t('clawbotDbName')" min-width="120">
              <template #default="{ row }">
                <span>{{ row.name }}</span>
                <el-tag v-if="row.is_default" type="success" size="small" style="margin-left: 6px;">Default</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="$t('clawbotPgHost')" min-width="140">
              <template #default="{ row }">{{ row.host }}:{{ row.port }}</template>
            </el-table-column>
            <el-table-column prop="dbname" :label="$t('clawbotPgDb')" min-width="100" />
            <el-table-column prop="user" :label="$t('clawbotPgUser')" min-width="80" />
            <el-table-column :label="$t('status')" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? 'ON' : 'OFF' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="$t('actions')" width="180" align="center">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="onEditDatabase(row)">
                  <el-icon><Edit /></el-icon>
                </el-button>
                <el-button size="small" type="success" text :loading="testingDb === row.id" @click="onTestDatabase(row)">
                  <el-icon><Connection /></el-icon>
                </el-button>
                <el-button size="small" type="danger" text @click="onDeleteDatabase(row)" :disabled="row.is_default && clawbotDatabases.length === 1">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- ═══ Agent / LLM Ayarları ═══ -->
        <div class="form-group">
          <div class="form-group-title">🧠 {{ $t('clawbotAgentSettings') }}</div>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item :label="$t('clawbotAgentMode')">
                <el-radio-group v-model="clawbotConfig.agent_mode">
                  <el-radio-button value="cloud">☁️ Cloud</el-radio-button>
                  <el-radio-button value="local">🖥️ Local</el-radio-button>
                </el-radio-group>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="$t('clawbotLlmProvider')">
                <el-select v-model="clawbotConfig.llm_provider" style="width: 100%" :disabled="clawbotConfig.agent_mode === 'local'">
                  <el-option label="Groq" value="groq" />
                  <el-option label="OpenAI" value="openai" />
                  <el-option label="Google Gemini" value="gemini" />
                  <el-option label="DeepSeek" value="deepseek" />
                  <el-option label="Anthropic" value="anthropic" />
                  <el-option label="Custom" value="custom" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="$t('clawbotLlmModel')">
                <el-input v-model="clawbotConfig.llm_model" :placeholder="clawbotConfig.agent_mode === 'local' ? 'llama3' : 'llama-3.3-70b-versatile'" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item :label="$t('clawbotLlmApiKey')">
                <el-input v-model="clawbotConfig.llm_api_key" type="password" show-password :placeholder="clawbotConfig.llm_api_key_set ? '••••••••' : 'API Key'" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('clawbotLlmApiUrl')">
                <el-input v-model="clawbotConfig.llm_api_url" :placeholder="clawbotConfig.agent_mode === 'local' ? 'http://localhost:11434/v1' : 'Auto (provider)'" />
                <div class="form-hint">{{ $t('clawbotLlmApiUrlHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16" v-show="clawbotConfig.agent_mode === 'local'">
            <el-col :span="12">
              <el-form-item :label="$t('clawbotLocalModel')">
                <el-input v-model="clawbotConfig.local_model" placeholder="llama3" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('clawbotLocalApiUrl')">
                <el-input v-model="clawbotConfig.local_api_url" placeholder="http://localhost:11434/v1" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item :label="$t('clawbotTemperature')">
                <el-slider v-model="clawbotConfig.llm_temperature" :min="0" :max="1" :step="0.1" show-input :show-input-controls="false" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="$t('clawbotMaxTokens')">
                <el-input-number v-model="clawbotConfig.llm_max_tokens" :min="256" :max="8192" :step="256" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- ═══ Davranış Ayarları ═══ -->
        <div class="form-group">
          <div class="form-group-title">⚙️ {{ $t('clawbotBehavior') }}</div>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item :label="$t('clawbotUseLlm')">
                <el-switch v-model="clawbotConfig.use_llm" />
                <div class="form-hint">{{ $t('clawbotUseLlmHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="$t('clawbotConfirmActions')">
                <el-switch v-model="clawbotConfig.require_action_confirm" />
                <div class="form-hint">{{ $t('clawbotConfirmActionsHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="$t('clawbotSlowThreshold')">
                <el-input-number v-model="clawbotConfig.slow_query_threshold" :min="100" :max="60000" :step="100" style="width: 100%" />
                <div class="form-hint">{{ $t('clawbotSlowThresholdHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item :label="$t('clawbotProactiveInterval')">
                <el-input-number v-model="clawbotConfig.proactive_interval" :min="0" :max="3600" :step="30" style="width: 100%" />
                <div class="form-hint">{{ $t('clawbotProactiveIntervalHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="16">
              <el-form-item :label="$t('clawbotProactiveChannels')">
                <el-input v-model="clawbotConfig.proactive_channels" placeholder="telegram,whatsapp,mail" />
                <div class="form-hint">{{ $t('clawbotProactiveChannelsHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- Action buttons -->
        <div class="telegram-actions">
          <el-button type="primary" :loading="savingClawbot" @click="onSaveClawbot">
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

    <!-- DB Add/Edit Dialog -->
    <el-dialog v-model="showDbDialog" :title="dbForm.id ? $t('clawbotEditDb') : $t('clawbotAddDb')" width="520px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item :label="$t('clawbotDbName')">
          <el-input v-model="dbForm.name" placeholder="Production DB" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="14">
            <el-form-item :label="$t('clawbotPgHost')">
              <el-input v-model="dbForm.host" placeholder="192.168.1.100" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item :label="$t('clawbotPgPort')">
              <el-input-number v-model="dbForm.port" :min="1" :max="65535" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="$t('clawbotPgUser')">
              <el-input v-model="dbForm.user" placeholder="postgres" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('clawbotPgPassword')">
              <el-input v-model="dbForm.password" type="password" show-password placeholder="••••••••" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item :label="$t('clawbotPgDb')">
          <el-input v-model="dbForm.dbname" placeholder="mydb" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item>
              <el-checkbox v-model="dbForm.is_default">{{ $t('clawbotSetDefault') }}</el-checkbox>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item>
              <el-checkbox v-model="dbForm.enabled">{{ $t('clawbotEnabled') }}</el-checkbox>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showDbDialog = false">{{ $t('cancel') }}</el-button>
        <el-button type="success" :loading="testingDb === '__dialog__'" @click="onTestDbFromDialog">
          <el-icon style="margin-right: 4px;"><Connection /></el-icon>
          {{ $t('testConnection') }}
        </el-button>
        <el-button type="primary" :loading="savingDb" @click="onSaveDatabase">{{ $t('save') }}</el-button>
      </template>
    </el-dialog>

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
import { getTelegramConfigReq, saveTelegramConfigReq, testTelegramReq } from '@/api/telegram'
import { getWhatsappConfigReq, saveWhatsappConfigReq, testWhatsappReq } from '@/api/whatsapp'
import { getMailConfigReq, saveMailConfigReq, testMailReq } from '@/api/mail'
import { getClawbotConfigReq, saveClawbotConfigReq, listClawbotDatabasesReq, saveClawbotDatabaseReq, deleteClawbotDatabaseReq, testClawbotDatabaseReq } from '@/api/clawbot'
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
    fetchTelegramConfig()
    fetchWhatsappConfig()
    fetchMailConfig()
    fetchClawbotConfig()
    fetchClawbotDatabases()
  }
})

// ========== Telegram Config ==========
const telegramLoading = ref(false)
const savingTelegram = ref(false)
const testingConnection = ref(false)
const telegramConfig = reactive({
  bot_token: '',
  bot_token_set: false,
  chat_id: '',
  allowed_users: '',
  notify_on_alert: true,
  notify_on_diagnosis: true,
  auto_diagnose: false,
  health_check_interval: 300,
  slow_query_threshold: 5.0
})

const fetchTelegramConfig = async () => {
  telegramLoading.value = true
  try {
    const res = await getTelegramConfigReq()
    if (res.code === 200 && res.data) {
      const d = res.data
      telegramConfig.bot_token = d.bot_token || ''
      telegramConfig.bot_token_set = d.bot_token_set || false
      telegramConfig.chat_id = d.chat_id || ''
      telegramConfig.allowed_users = d.allowed_users || ''
      telegramConfig.notify_on_alert = d.notify_on_alert ?? true
      telegramConfig.notify_on_diagnosis = d.notify_on_diagnosis ?? true
      telegramConfig.auto_diagnose = d.auto_diagnose ?? false
      telegramConfig.health_check_interval = d.health_check_interval || 300
      telegramConfig.slow_query_threshold = d.slow_query_threshold || 5.0
    }
  } catch (e) {
    console.error('Failed to load Telegram config:', e)
  } finally {
    telegramLoading.value = false
  }
}

const onSaveTelegram = async () => {
  savingTelegram.value = true
  try {
    const res = await saveTelegramConfigReq({
      bot_token: telegramConfig.bot_token,
      chat_id: telegramConfig.chat_id,
      allowed_users: telegramConfig.allowed_users,
      notify_on_alert: telegramConfig.notify_on_alert,
      notify_on_diagnosis: telegramConfig.notify_on_diagnosis,
      auto_diagnose: telegramConfig.auto_diagnose,
      health_check_interval: telegramConfig.health_check_interval,
      slow_query_threshold: telegramConfig.slow_query_threshold
    })
    if (res.code === 200) {
      ElMessage.success($t('saveSuccess'))
      fetchTelegramConfig()
    } else {
      ElMessage.error(res.msg || 'Error')
    }
  } catch (e) {
    ElMessage.error(e?.msg || 'Error')
  } finally {
    savingTelegram.value = false
  }
}

const onTestConnection = async () => {
  testingConnection.value = true
  try {
    const res = await testTelegramReq()
    if (res.code === 200) {
      ElMessage.success($t('testConnectionSuccess'))
    } else {
      ElMessage.error($t('testConnectionFail') + ': ' + (res.msg || ''))
    }
  } catch (e) {
    ElMessage.error($t('testConnectionFail'))
  } finally {
    testingConnection.value = false
  }
}

// ========== WhatsApp Config ==========
const whatsappLoading = ref(false)
const savingWhatsapp = ref(false)
const testingWhatsapp = ref(false)
const whatsappConfig = reactive({
  access_token: '',
  access_token_set: false,
  phone_number_id: '',
  business_account_id: '',
  verify_token: 'anomivox_whatsapp_verify_2024',
  allowed_numbers: '',
  notify_on_alert: true,
  notify_on_diagnosis: true,
  auto_diagnose: false,
  health_check_interval: 300,
  slow_query_threshold: 5.0
})

const fetchWhatsappConfig = async () => {
  whatsappLoading.value = true
  try {
    const res = await getWhatsappConfigReq()
    if (res.code === 200 && res.data) {
      const d = res.data
      whatsappConfig.access_token = d.access_token || ''
      whatsappConfig.access_token_set = d.access_token_set || false
      whatsappConfig.phone_number_id = d.phone_number_id || ''
      whatsappConfig.business_account_id = d.business_account_id || ''
      whatsappConfig.verify_token = d.verify_token || 'anomivox_whatsapp_verify_2024'
      whatsappConfig.allowed_numbers = d.allowed_numbers || ''
      whatsappConfig.notify_on_alert = d.notify_on_alert ?? true
      whatsappConfig.notify_on_diagnosis = d.notify_on_diagnosis ?? true
      whatsappConfig.auto_diagnose = d.auto_diagnose ?? false
      whatsappConfig.health_check_interval = d.health_check_interval || 300
      whatsappConfig.slow_query_threshold = d.slow_query_threshold || 5.0
    }
  } catch (e) {
    console.error('Failed to load WhatsApp config:', e)
  } finally {
    whatsappLoading.value = false
  }
}

const onSaveWhatsapp = async () => {
  savingWhatsapp.value = true
  try {
    const res = await saveWhatsappConfigReq({
      access_token: whatsappConfig.access_token,
      phone_number_id: whatsappConfig.phone_number_id,
      business_account_id: whatsappConfig.business_account_id,
      verify_token: whatsappConfig.verify_token,
      allowed_numbers: whatsappConfig.allowed_numbers,
      notify_on_alert: whatsappConfig.notify_on_alert,
      notify_on_diagnosis: whatsappConfig.notify_on_diagnosis,
      auto_diagnose: whatsappConfig.auto_diagnose,
      health_check_interval: whatsappConfig.health_check_interval,
      slow_query_threshold: whatsappConfig.slow_query_threshold
    })
    if (res.code === 200) {
      ElMessage.success($t('saveSuccess'))
      fetchWhatsappConfig()
    } else {
      ElMessage.error(res.msg || 'Error')
    }
  } catch (e) {
    ElMessage.error(e?.msg || 'Error')
  } finally {
    savingWhatsapp.value = false
  }
}

const onTestWhatsapp = async () => {
  testingWhatsapp.value = true
  try {
    const res = await testWhatsappReq()
    if (res.code === 200) {
      ElMessage.success($t('whatsappTestSuccess'))
    } else {
      ElMessage.error($t('whatsappTestFail') + ': ' + (res.msg || ''))
    }
  } catch (e) {
    ElMessage.error($t('whatsappTestFail'))
  } finally {
    testingWhatsapp.value = false
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

// ========== ClawBot Config ==========
const savingClawbot = ref(false)
const clawbotDatabases = ref([])
const testingDb = ref(null)
const showDbDialog = ref(false)
const savingDb = ref(false)
const dbForm = reactive({
  id: null,
  name: '',
  host: '',
  port: 5432,
  user: '',
  password: '',
  dbname: '',
  is_default: false,
  enabled: true,
})

const clawbotConfig = reactive({
  agent_mode: 'cloud',
  llm_provider: 'groq',
  llm_model: 'llama-3.3-70b-versatile',
  llm_api_key: '',
  llm_api_key_set: false,
  llm_api_url: '',
  llm_temperature: 0.3,
  llm_max_tokens: 2048,
  local_model: 'llama3',
  local_api_url: 'http://localhost:11434/v1',
  use_llm: true,
  require_action_confirm: true,
  slow_query_threshold: 1000,
  proactive_interval: 300,
  proactive_channels: 'telegram,whatsapp,mail',
})

const fetchClawbotConfig = async () => {
  try {
    const res = await getClawbotConfigReq()
    if (res.code === 200 && res.data) {
      const d = res.data
      clawbotConfig.agent_mode = d.agent_mode || 'cloud'
      clawbotConfig.llm_provider = d.llm_provider || 'groq'
      clawbotConfig.llm_model = d.llm_model || 'llama-3.3-70b-versatile'
      clawbotConfig.llm_api_key = d.llm_api_key || ''
      clawbotConfig.llm_api_key_set = d.llm_api_key_set || false
      clawbotConfig.llm_api_url = d.llm_api_url || ''
      clawbotConfig.llm_temperature = d.llm_temperature ?? 0.3
      clawbotConfig.llm_max_tokens = d.llm_max_tokens || 2048
      clawbotConfig.local_model = d.local_model || 'llama3'
      clawbotConfig.local_api_url = d.local_api_url || 'http://localhost:11434/v1'
      clawbotConfig.use_llm = d.use_llm ?? true
      clawbotConfig.require_action_confirm = d.require_action_confirm ?? true
      clawbotConfig.slow_query_threshold = d.slow_query_threshold || 1000
      clawbotConfig.proactive_interval = d.proactive_interval ?? 300
      clawbotConfig.proactive_channels = d.proactive_channels || 'telegram,whatsapp,mail'
    }
  } catch (e) {
    console.error('Failed to load ClawBot config:', e)
  }
}

const fetchClawbotDatabases = async () => {
  try {
    const res = await listClawbotDatabasesReq()
    if (res.code === 200 && res.data) {
      clawbotDatabases.value = res.data
    }
  } catch (e) {
    console.error('Failed to load ClawBot databases:', e)
  }
}

const onSaveClawbot = async () => {
  savingClawbot.value = true
  try {
    const res = await saveClawbotConfigReq({
      agent_mode: clawbotConfig.agent_mode,
      llm_provider: clawbotConfig.llm_provider,
      llm_model: clawbotConfig.llm_model,
      llm_api_key: clawbotConfig.llm_api_key,
      llm_api_url: clawbotConfig.llm_api_url,
      llm_temperature: clawbotConfig.llm_temperature,
      llm_max_tokens: clawbotConfig.llm_max_tokens,
      local_model: clawbotConfig.local_model,
      local_api_url: clawbotConfig.local_api_url,
      use_llm: clawbotConfig.use_llm,
      require_action_confirm: clawbotConfig.require_action_confirm,
      slow_query_threshold: clawbotConfig.slow_query_threshold,
      proactive_interval: clawbotConfig.proactive_interval,
      proactive_channels: clawbotConfig.proactive_channels,
    })
    if (res.code === 200) {
      ElMessage.success(res.msg || 'ClawBot ayarları kaydedildi')
    } else {
      ElMessage.error(res.msg || 'Kaydetme hatası')
    }
  } catch (e) {
    ElMessage.error('ClawBot kaydetme hatası')
    console.error(e)
  } finally {
    savingClawbot.value = false
  }
}

// DB CRUD
const onAddDatabase = () => {
  dbForm.id = null
  dbForm.name = ''
  dbForm.host = ''
  dbForm.port = 5432
  dbForm.user = ''
  dbForm.password = ''
  dbForm.dbname = ''
  dbForm.is_default = clawbotDatabases.value.length === 0
  dbForm.enabled = true
  showDbDialog.value = true
}

const onEditDatabase = (row) => {
  dbForm.id = row.id
  dbForm.name = row.name
  dbForm.host = row.host
  dbForm.port = row.port
  dbForm.user = row.user
  dbForm.password = row.password_set ? '••••••••' : ''
  dbForm.dbname = row.dbname
  dbForm.is_default = row.is_default
  dbForm.enabled = row.enabled
  showDbDialog.value = true
}

const onSaveDatabase = async () => {
  if (!dbForm.name || !dbForm.host || !dbForm.dbname || !dbForm.user) {
    ElMessage.warning('Ad, Host, Kullanıcı ve DB alanları zorunludur')
    return
  }
  savingDb.value = true
  try {
    const res = await saveClawbotDatabaseReq({
      id: dbForm.id,
      name: dbForm.name,
      host: dbForm.host,
      port: dbForm.port,
      user: dbForm.user,
      password: dbForm.password,
      dbname: dbForm.dbname,
      is_default: dbForm.is_default,
      enabled: dbForm.enabled,
    })
    if (res.code === 200) {
      ElMessage.success(res.msg || 'Kaydedildi')
      showDbDialog.value = false
      fetchClawbotDatabases()
    } else {
      ElMessage.error(res.msg || 'Hata')
    }
  } catch (e) {
    ElMessage.error('Kaydetme hatası')
  } finally {
    savingDb.value = false
  }
}

const onDeleteDatabase = async (row) => {
  try {
    await ElMessageBox.confirm(`"${row.name}" bağlantısını silmek istediğinize emin misiniz?`, 'Dikkat', { type: 'warning' })
    const res = await deleteClawbotDatabaseReq(row.id)
    if (res.code === 200) {
      ElMessage.success(res.msg || 'Silindi')
      fetchClawbotDatabases()
    } else {
      ElMessage.error(res.msg || 'Silme hatası')
    }
  } catch (e) { /* cancelled */ }
}

const onTestDatabase = async (row) => {
  testingDb.value = row.id
  try {
    const res = await testClawbotDatabaseReq({
      host: row.host,
      port: row.port,
      user: row.user,
      password: '', // masked password — API will resolve from stored
      dbname: row.dbname,
      id: row.id,
    })
    if (res.code === 200) {
      const d = res.data || {}
      ElMessage.success(`✅ ${d.version || 'Bağlantı başarılı'} — ${d.size || ''}`)
    } else {
      ElMessage.error(res.msg || 'Bağlantı başarısız')
    }
  } catch (e) {
    ElMessage.error('Bağlantı test hatası')
  } finally {
    testingDb.value = null
  }
}

const onTestDbFromDialog = async () => {
  if (!dbForm.host || !dbForm.dbname || !dbForm.user) {
    ElMessage.warning('Host, Kullanıcı ve DB alanları zorunludur')
    return
  }
  testingDb.value = '__dialog__'
  try {
    const res = await testClawbotDatabaseReq({
      host: dbForm.host,
      port: dbForm.port,
      user: dbForm.user,
      password: dbForm.password,
      dbname: dbForm.dbname,
      id: dbForm.id,
    })
    if (res.code === 200) {
      const d = res.data || {}
      ElMessage.success(`✅ ${d.version || 'Bağlantı başarılı'} — ${d.size || ''}`)
    } else {
      ElMessage.error(res.msg || 'Bağlantı başarısız')
    }
  } catch (e) {
    ElMessage.error('Bağlantı test hatası')
  } finally {
    testingDb.value = null
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

.whatsapp-section {
  margin-top: 20px;
}

.mail-section {
  margin-top: 20px;
}
</style>
