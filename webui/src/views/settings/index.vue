<template>
  <div class="settings-container">
    <div class="settings-header">
      <h2>{{ $t('settingsTitle') }}</h2>
    </div>

    <!-- Non-admin: access denied -->
    <div v-if="!isAdmin" class="no-permission">
      <el-result icon="warning" :title="$t('noPermission')" :sub-title="$t('noPermissionDesc')" />
    </div>

    <template v-if="isAdmin">

    <!-- ══════════════════════════════════════════════════════════ -->
    <!-- SECTION 1 — User Management (collapsible)                -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div v-if="isAdmin" class="collapse-card" :class="{ open: sections.users }">
      <div class="collapse-card-header" @click="toggleSection('users')">
        <div class="collapse-card-title">
          <div class="collapse-card-icon user-icon">
            <el-icon :size="20"><User /></el-icon>
          </div>
          <div>
            <h3>{{ $t('userManagement') }}</h3>
            <span class="collapse-card-subtitle">{{ users.length }} {{ $t('users') || 'kullanıcı' }}</span>
          </div>
        </div>
        <div class="collapse-card-right">
          <el-button type="primary" size="small" @click.stop="showCreateDialog = true">
            <el-icon style="margin-right: 4px"><Plus /></el-icon>
            {{ $t('addUser') }}
          </el-button>
          <div class="collapse-chevron" :class="{ rotated: sections.users }">
            <el-icon :size="18"><ArrowDown /></el-icon>
          </div>
        </div>
      </div>
      <Transition name="collapse-body">
        <div v-show="sections.users" class="collapse-card-body">
          <el-table
            v-loading="loading"
            :data="users"
            stripe
            style="width: 100%"
            :empty-text="$t('noData')"
          >
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="username" :label="$t('username')" min-width="150">
              <template #default="{ row }">
                <div class="rowSC">
                  <el-icon style="margin-right: 8px;" size="16">
                    <UserFilled v-if="row.role === 'admin'" />
                    <User v-else />
                  </el-icon>
                  <span>{{ row.username }}</span>
                  <el-tag v-if="row.role === 'admin'" size="small" type="warning" style="margin-left: 8px">Admin</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column :label="$t('role')" width="100">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'warning' : 'info'" size="small">
                  {{ row.role === 'admin' ? 'Admin' : 'User' }}
                </el-tag>
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
            </el-table-column>
          </el-table>
        </div>
      </Transition>
    </div>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!-- SECTION 2 — AI Gateway Agent & DBA Agent Management (collapsible) -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <div v-if="isAdmin" class="collapse-card" :class="{ open: sections.litellm }">
      <div class="collapse-card-header" @click="toggleSection('litellm')">
        <div class="collapse-card-title">
          <div class="collapse-card-icon ai-icon">
            <span style="font-size: 20px;">🤖</span>
          </div>
          <div>
            <h3>{{ $t('litellmSettings') }}</h3>
            <span class="collapse-card-subtitle">{{ $t('litellmDesc') }}</span>
          </div>
        </div>
        <div class="collapse-card-right">
          <el-tag :type="litellmOnline ? 'success' : 'info'" size="default" effect="plain" round>
            <el-icon style="margin-right: 4px;"><CircleCheck v-if="litellmOnline" /><WarningFilled v-else /></el-icon>
            {{ litellmOnline ? $t('litellmProxyOnline') : $t('litellmProxyOffline') }}
          </el-tag>
          <el-tag :type="dbaAgentOnline ? 'success' : 'info'" size="default" effect="plain" round style="margin-left: 4px;">
            <el-icon style="margin-right: 4px;"><CircleCheck v-if="dbaAgentOnline" /><WarningFilled v-else /></el-icon>
            {{ dbaAgentOnline ? 'DBA Agent ✓' : 'DBA Agent ✗' }}
          </el-tag>
          <el-tag v-if="dbTargets.length > 0" type="success" size="default" effect="plain" round style="margin-left: 4px;">
            🗄️ {{ dbTargets.length }} DB
          </el-tag>
          <div class="collapse-chevron" :class="{ rotated: sections.litellm }">
            <el-icon :size="18"><ArrowDown /></el-icon>
          </div>
        </div>
      </div>
      <Transition name="collapse-body">
        <div v-show="sections.litellm" class="collapse-card-body">
          <el-form label-position="top" class="telegram-form" v-loading="litellmLoading">

            <!-- ═══ Model Listesi ═══ -->
            <div class="inner-card">
              <div class="inner-card-header" @click="toggleInner('models')">
                <span>🧠 {{ $t('litellmModels') }}</span>
                <div class="collapse-chevron small" :class="{ rotated: innerSections.models }">
                  <el-icon :size="14"><ArrowDown /></el-icon>
                </div>
              </div>
              <Transition name="collapse-body">
                <div v-show="innerSections.models" class="inner-card-body">

                  <!-- Mevcut modeller tablosu -->
                  <el-table :data="litellmModels" stripe size="small" style="margin-bottom: 16px;" empty-text="Henüz model eklenmemiş">
                    <el-table-column prop="model_name" :label="$t('litellmModelName')" min-width="140" />
                    <el-table-column prop="litellm_model" :label="$t('litellmModelId')" min-width="180" />
                    <el-table-column prop="api_base" :label="$t('litellmApiBase')" min-width="200">
                      <template #default="{ row }">
                        <span>{{ row.api_base || '—' }}</span>
                      </template>
                    </el-table-column>
                    <el-table-column :label="$t('litellmRole')" width="100">
                      <template #default="{ row }">
                        <el-tag v-if="row.model_info?.role" size="small" type="info">{{ row.model_info.role }}</el-tag>
                        <span v-else>—</span>
                      </template>
                    </el-table-column>
                    <el-table-column :label="$t('status')" width="90" align="center">
                      <template #default="{ row }">
                        <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain">
                          {{ row.is_active ? '●' : '○' }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column :label="$t('actions')" width="160" align="center">
                      <template #default="{ row }">
                        <el-button size="small" type="primary" link :loading="testingModel === row.model_name" @click="onTestModel(row.model_name)">
                          {{ $t('litellmTest') }}
                        </el-button>
                        <el-button size="small" type="danger" link @click="onRemoveModel(row.model_name)">
                          {{ $t('delete') }}
                        </el-button>
                      </template>
                    </el-table-column>
                  </el-table>

                  <!-- Test sonucu -->
                  <div v-if="testResult" style="background: var(--el-fill-color-light); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
                    <div style="font-weight: 500; margin-bottom: 6px;">🧪 {{ $t('litellmTestResult') }}:</div>
                    <div style="font-size: 13px; color: var(--el-text-color-secondary);">
                      <strong>{{ $t('litellmModelName') }}:</strong> {{ testResult.model }}<br>
                      <strong>{{ $t('litellmResponse') }}:</strong> {{ testResult.response?.substring(0, 200) }}<br>
                      <strong>Tokens:</strong> {{ testResult.tokens }} (prompt: {{ testResult.prompt_tokens }}, completion: {{ testResult.completion_tokens }})
                    </div>
                  </div>

                  <!-- Yeni model ekleme formu -->
                  <el-divider content-position="left">
                    <span style="font-size: 13px;">➕ {{ $t('litellmAddModel') }}</span>
                  </el-divider>

                  <el-row :gutter="16">
                    <el-col :span="6">
                      <el-form-item :label="$t('litellmModelName')">
                        <el-input v-model="newModel.model_name" placeholder="llama3.1:8b" clearable />
                      </el-form-item>
                    </el-col>
                    <el-col :span="6">
                      <el-form-item :label="$t('litellmModelId')">
                        <el-input v-model="newModel.litellm_model" placeholder="ollama/llama3.1:8b" clearable />
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item :label="$t('litellmApiBase')">
                        <el-input v-model="newModel.api_base" placeholder="http://192.168.1.202:11434" clearable />
                      </el-form-item>
                    </el-col>
                    <el-col :span="4">
                      <el-form-item :label="$t('litellmRole')">
                        <el-select v-model="newModel.role" style="width: 100%" clearable>
                          <el-option label="Reasoning" value="reasoning" />
                          <el-option label="SQL" value="sql" />
                          <el-option label="Triage" value="triage" />
                          <el-option label="Fallback" value="fallback" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <el-row :gutter="16">
                    <el-col :span="4">
                      <el-form-item label="Timeout (s)">
                        <el-input-number v-model="newModel.timeout" :min="30" :max="600" :step="30" style="width: 100%" controls-position="right" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="4">
                      <el-form-item label="Context (num_ctx)">
                        <el-input-number v-model="newModel.num_ctx" :min="256" :max="32768" :step="512" style="width: 100%" controls-position="right" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="4">
                      <el-form-item label="Max Output">
                        <el-input-number v-model="newModel.num_predict" :min="32" :max="4096" :step="64" style="width: 100%" controls-position="right" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12" style="display: flex; align-items: flex-end; padding-bottom: 18px;">
                      <el-button type="primary" :loading="addingModel" @click="onAddModel" :disabled="!newModel.model_name || !newModel.litellm_model">
                        <el-icon style="margin-right: 6px;"><Plus /></el-icon>
                        {{ $t('litellmAddModel') }}
                      </el-button>
                    </el-col>
                  </el-row>
                </div>
              </Transition>
            </div>

            <!-- ═══ Genel Ayarlar ═══ -->
            <div class="inner-card">
              <div class="inner-card-header" @click="toggleInner('litellmSettings')">
                <span>⚙️ {{ $t('litellmGeneralSettings') }}</span>
                <div class="collapse-chevron small" :class="{ rotated: innerSections.litellmSettings }">
                  <el-icon :size="14"><ArrowDown /></el-icon>
                </div>
              </div>
              <Transition name="collapse-body">
                <div v-show="innerSections.litellmSettings" class="inner-card-body">
                  <el-row :gutter="20">
                    <el-col :span="8">
                      <el-form-item :label="$t('litellmTimeout')">
                        <el-input-number v-model="litellmSettings.request_timeout" :min="30" :max="600" :step="30" style="width: 100%" controls-position="right" />
                        <div class="form-hint">{{ $t('litellmTimeoutHint') }}</div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item :label="$t('litellmRetries')">
                        <el-input-number v-model="litellmSettings.num_retries" :min="0" :max="5" style="width: 100%" controls-position="right" />
                        <div class="form-hint">{{ $t('litellmRetriesHint') }}</div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item :label="$t('litellmCache')">
                        <div class="toggle-item" style="padding: 0;">
                          <el-switch v-model="litellmSettings.cache" />
                          <div class="toggle-info">
                            <span class="toggle-hint">{{ $t('litellmCacheHint') }}</span>
                          </div>
                        </div>
                      </el-form-item>
                    </el-col>
                  </el-row>
                </div>
              </Transition>
            </div>

            <!-- ═══ DB Connections (moved from separate section) ═══ -->
            <div class="inner-card">
              <div class="inner-card-header" @click="toggleInner('dbTargetList')">
                <span>🗄️ {{ $t('dbTargetSettings') }}
                  <el-tag :type="dbTargets.length > 0 ? 'success' : 'info'" size="small" effect="plain" round style="margin-left: 8px;">
                    {{ dbTargets.length }} {{ $t('dbTargetCount') }}
                  </el-tag>
                </span>
                <div class="collapse-chevron small" :class="{ rotated: innerSections.dbTargetList }">
                  <el-icon :size="14"><ArrowDown /></el-icon>
                </div>
              </div>
              <Transition name="collapse-body">
                <div v-show="innerSections.dbTargetList" class="inner-card-body" v-loading="dbTargetsLoading">

                  <el-table :data="dbTargets" stripe size="small" style="margin-bottom: 16px;" :empty-text="$t('dbTargetNoTargets')">
                    <el-table-column :label="$t('dbTargetPrimary')" width="70" align="center">
                      <template #default="{ row }">
                        <el-tag v-if="row.is_primary" type="warning" size="small" effect="dark" round>★</el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="name" :label="$t('name')" min-width="120" />
                    <el-table-column prop="db_type" :label="$t('dbTargetType')" width="110">
                      <template #default="{ row }">
                        <el-tag :type="row.db_type === 'postgresql' ? 'primary' : 'success'" size="small" effect="plain">
                          {{ row.db_type === 'postgresql' ? '🐘 PostgreSQL' : '🐬 MySQL' }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column :label="$t('dbTargetHost')" min-width="200">
                      <template #default="{ row }">
                        <code style="font-size: 12px;">{{ row.host }}:{{ row.port }}/{{ row.dbname }}</code>
                      </template>
                    </el-table-column>
                    <el-table-column prop="user" :label="$t('username')" width="100" />
                    <el-table-column :label="'SSL'" width="70" align="center">
                      <template #default="{ row }">
                        <el-tag v-if="row.ssl_enabled" type="success" size="small" effect="plain">🔒</el-tag>
                        <span v-else style="color: var(--el-text-color-placeholder); font-size: 12px;">—</span>
                      </template>
                    </el-table-column>
                    <el-table-column :label="'SSH'" width="70" align="center">
                      <template #default="{ row }">
                        <template v-if="row.ssh_enabled">
                          <el-tag v-if="row.ssh_last_status === 'ok'" type="success" size="small" effect="plain">🖥 ✓</el-tag>
                          <el-tag v-else-if="row.ssh_last_status === 'error'" type="danger" size="small" effect="plain">🖥 ✗</el-tag>
                          <el-tag v-else type="info" size="small" effect="plain">🖥</el-tag>
                        </template>
                        <span v-else style="color: var(--el-text-color-placeholder); font-size: 12px;">—</span>
                      </template>
                    </el-table-column>
                    <el-table-column :label="$t('status')" width="90" align="center">
                      <template #default="{ row }">
                        <el-tag v-if="row.last_status === 'ok'" type="success" size="small" effect="plain">✓</el-tag>
                        <el-tag v-else-if="row.last_status === 'error'" type="danger" size="small" effect="plain">✗</el-tag>
                        <span v-else style="color: var(--el-text-color-placeholder); font-size: 12px;">—</span>
                      </template>
                    </el-table-column>
                    <el-table-column :label="$t('actions')" width="320" align="center">
                      <template #default="{ row }">
                        <el-button size="small" type="primary" link :loading="testingDbTarget === row.id" @click="onTestDbTarget(row.id)">
                          {{ $t('testConnection') }}
                        </el-button>
                        <el-button v-if="row.ssh_enabled" size="small" type="info" link :loading="testingSshTarget === row.id" @click="onTestSshTarget(row.id)">
                          SSH Test
                        </el-button>
                        <el-button size="small" type="default" link @click="onEditDbTarget(row)">
                          {{ $t('edit') }}
                        </el-button>
                        <el-button v-if="!row.is_primary" size="small" type="warning" link @click="onSetPrimaryDb(row.id)">
                          {{ $t('dbTargetSetPrimary') }}
                        </el-button>
                        <el-button size="small" type="danger" link @click="onDeleteDbTarget(row)">
                          {{ $t('delete') }}
                        </el-button>
                      </template>
                    </el-table-column>
                  </el-table>

                  <!-- Test Sonucu -->
                  <div v-if="dbTestResult" style="background: var(--el-fill-color-light); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
                    <div style="font-weight: 500; margin-bottom: 6px;">🧪 {{ $t('dbTargetTestResult') }}:</div>
                    <div style="font-size: 13px; color: var(--el-text-color-secondary);">
                      <strong>Version:</strong> {{ dbTestResult.version }}<br>
                      <strong>Database:</strong> {{ dbTestResult.database }}<br>
                      <strong>User:</strong> {{ dbTestResult.user }}
                      <template v-if="dbTestResult.size"><br><strong>Size:</strong> {{ dbTestResult.size }}</template>
                    </div>
                  </div>

                  <!-- SSH Test Sonucu -->
                  <div v-if="sshTestResult" style="background: var(--el-fill-color-light); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
                    <div style="font-weight: 500; margin-bottom: 6px;">🖥️ {{ $t('sshTestResult') }}:</div>
                    <pre style="font-size: 12px; color: var(--el-text-color-secondary); white-space: pre-wrap; margin: 0;">{{ sshTestResult.output || sshTestResult.error_output || '' }}</pre>
                  </div>

                  <!-- Yeni DB Bağlantısı Ekleme Formu -->
                  <el-divider content-position="left">
                    <span style="font-size: 13px;">➕ {{ $t('dbTargetAdd') }}</span>
                  </el-divider>

                  <el-row :gutter="16">
                    <el-col :span="5">
                      <el-form-item :label="$t('name')">
                        <el-input v-model="newDbTarget.name" :placeholder="$t('dbTargetNamePlaceholder')" clearable />
                      </el-form-item>
                    </el-col>
                    <el-col :span="4">
                      <el-form-item :label="$t('dbTargetType')">
                        <el-select v-model="newDbTarget.db_type" style="width: 100%">
                          <el-option label="🐘 PostgreSQL" value="postgresql" />
                          <el-option label="🐬 MySQL" value="mysql" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="5">
                      <el-form-item :label="$t('dbTargetHost')">
                        <el-input v-model="newDbTarget.host" :placeholder="$t('dbTargetHostPlaceholder')" clearable />
                      </el-form-item>
                    </el-col>
                    <el-col :span="3">
                      <el-form-item :label="$t('smtpPort')">
                        <el-input-number v-model="newDbTarget.port" :min="1" :max="65535" style="width: 100%" controls-position="right" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="4">
                      <el-form-item :label="$t('username')">
                        <el-input v-model="newDbTarget.user" :placeholder="$t('dbTargetUserPlaceholder')" clearable />
                      </el-form-item>
                    </el-col>
                    <el-col :span="3">
                      <el-form-item :label="$t('password')">
                        <el-input v-model="newDbTarget.password" type="password" show-password placeholder="••••" clearable />
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <el-row :gutter="16">
                    <el-col :span="6">
                      <el-form-item :label="$t('dbTargetDbName')">
                        <el-input v-model="newDbTarget.dbname" :placeholder="$t('dbTargetDbNamePlaceholder')" clearable />
                      </el-form-item>
                    </el-col>
                    <el-col :span="4">
                      <el-form-item :label="$t('dbTargetPrimary')">
                        <div class="toggle-item" style="padding: 0;">
                          <el-switch v-model="newDbTarget.is_primary" />
                        </div>
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <!-- SSL Bağlantı (Opsiyonel) -->
                  <el-divider content-position="left">
                    <span style="font-size: 13px;">🔒 {{ $t('sslSection') }}</span>
                  </el-divider>

                  <el-row :gutter="16">
                    <el-col :span="3">
                      <el-form-item :label="$t('sslEnabled')">
                        <div class="toggle-item" style="padding: 0;">
                          <el-switch v-model="newDbTarget.ssl_enabled" />
                        </div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="4">
                      <el-form-item :label="$t('sslMode')">
                        <el-select v-model="newDbTarget.ssl_mode" :disabled="!newDbTarget.ssl_enabled" style="width: 100%">
                          <el-option label="require" value="require" />
                          <el-option label="verify-ca" value="verify-ca" />
                          <el-option label="verify-full" value="verify-full" />
                          <el-option label="prefer" value="prefer" />
                          <el-option label="disable" value="disable" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="6">
                      <el-form-item :label="$t('sslCaPath')">
                        <el-input v-model="newDbTarget.ssl_ca_path" :placeholder="$t('sslCaPathPlaceholder')" :disabled="!newDbTarget.ssl_enabled" clearable />
                      </el-form-item>
                    </el-col>
                    <el-col :span="5">
                      <el-form-item :label="$t('sslCertPath')">
                        <el-input v-model="newDbTarget.ssl_cert_path" :placeholder="$t('sslCertPathPlaceholder')" :disabled="!newDbTarget.ssl_enabled" clearable />
                      </el-form-item>
                    </el-col>
                    <el-col :span="5">
                      <el-form-item :label="$t('sslKeyPath')">
                        <el-input v-model="newDbTarget.ssl_key_path" :placeholder="$t('sslKeyPathPlaceholder')" :disabled="!newDbTarget.ssl_enabled" clearable />
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <!-- SSH / OS Erişimi (Opsiyonel) -->
                  <el-divider content-position="left">
                    <span style="font-size: 13px;">🖥️ {{ $t('sshAccessOptional') }}</span>
                  </el-divider>
                  <div class="form-hint" style="margin-bottom: 12px;">{{ $t('sshAccessHint') }}</div>

                  <el-row :gutter="16">
                    <el-col :span="3">
                      <el-form-item :label="$t('sshEnabled')">
                        <div class="toggle-item" style="padding: 0;">
                          <el-switch v-model="newDbTarget.ssh_enabled" />
                        </div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="5">
                      <el-form-item :label="$t('sshHost')">
                        <el-input v-model="newDbTarget.ssh_host" :placeholder="$t('sshHostPlaceholder')" :disabled="!newDbTarget.ssh_enabled" clearable />
                      </el-form-item>
                    </el-col>
                    <el-col :span="3">
                      <el-form-item :label="$t('sshPort')">
                        <el-input-number v-model="newDbTarget.ssh_port" :min="1" :max="65535" :disabled="!newDbTarget.ssh_enabled" style="width: 100%" controls-position="right" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="5">
                      <el-form-item :label="$t('sshUser')">
                        <el-input v-model="newDbTarget.ssh_user" :placeholder="$t('sshUserPlaceholder')" :disabled="!newDbTarget.ssh_enabled" clearable />
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item :label="$t('sshAuthMethod')">
                        <el-radio-group v-model="newDbTarget.ssh_auth_type" :disabled="!newDbTarget.ssh_enabled">
                          <el-radio-button label="key">🔑 {{ $t('sshAuthKey') }}</el-radio-button>
                          <el-radio-button label="password">🔒 {{ $t('sshAuthPassword') }}</el-radio-button>
                        </el-radio-group>
                      </el-form-item>
                    </el-col>
                  </el-row>

                  <!-- SSH Key Auth -->
                  <div v-if="newDbTarget.ssh_enabled && newDbTarget.ssh_auth_type === 'key'">
                    <el-row :gutter="16">
                      <el-col :span="12">
                        <el-form-item :label="$t('sshKeyPath')">
                          <el-input v-model="newDbTarget.ssh_key_path" :placeholder="$t('sshKeyPathPlaceholder')" clearable />
                          <div class="form-hint">{{ $t('sshKeyPathHint') }}</div>
                        </el-form-item>
                      </el-col>
                      <el-col :span="12">
                        <el-form-item :label="$t('sshKeyPassphrase')">
                          <el-input v-model="newDbTarget.ssh_key_passphrase" type="password" show-password :placeholder="$t('sshKeyPassphrasePlaceholder')" clearable />
                          <div class="form-hint">{{ $t('sshKeyPassphraseHint') }}</div>
                        </el-form-item>
                      </el-col>
                    </el-row>
                    <el-row :gutter="16">
                      <el-col :span="24">
                        <el-form-item :label="$t('sshKeyContent')">
                          <el-input
                            v-model="newDbTarget.ssh_key_content"
                            type="textarea"
                            :rows="4"
                            :placeholder="$t('sshKeyContentPlaceholder')"
                            style="font-family: monospace; font-size: 12px;"
                          />
                          <div class="form-hint" style="margin-top: 4px;">{{ $t('sshKeyContentHint') }}</div>
                        </el-form-item>
                      </el-col>
                    </el-row>
                  </div>

                  <!-- SSH Password Auth -->
                  <div v-if="newDbTarget.ssh_enabled && newDbTarget.ssh_auth_type === 'password'">
                    <el-row :gutter="16">
                      <el-col :span="12">
                        <el-form-item :label="$t('sshPassword')">
                          <el-input v-model="newDbTarget.ssh_password" type="password" show-password placeholder="••••" clearable />
                        </el-form-item>
                      </el-col>
                    </el-row>
                  </div>

                  <!-- Ekle Butonu -->
                  <el-row :gutter="16" style="margin-top: 8px;">
                    <el-col :span="24" style="display: flex; justify-content: flex-end;">
                      <el-button
                        type="primary"
                        :loading="addingDbTarget"
                        @click="onAddDbTarget"
                      >
                        <el-icon style="margin-right: 6px;"><Plus /></el-icon>
                        {{ $t('dbTargetAdd') }}
                      </el-button>
                    </el-col>
                  </el-row>
                </div>
              </Transition>
            </div>

            <!-- ═══ Setup Guide ═══ -->
            <div class="inner-card">
              <div class="inner-card-header" @click="toggleInner('litellmGuide')">
                <span>📖 {{ $t('litellmSetupGuide') }}</span>
                <div class="collapse-chevron small" :class="{ rotated: innerSections.litellmGuide }">
                  <el-icon :size="14"><ArrowDown /></el-icon>
                </div>
              </div>
              <Transition name="collapse-body">
                <div v-show="innerSections.litellmGuide" class="inner-card-body">
                  <div class="guide-steps">
                    <p>{{ $t('litellmStep1') }}</p>
                    <p>{{ $t('litellmStep2') }}</p>
                    <p>{{ $t('litellmStep3') }}</p>
                    <p>{{ $t('litellmStep4') }}</p>
                    <p>{{ $t('litellmStep5') }}</p>
                  </div>
                </div>
              </Transition>
            </div>

            <!-- Action buttons -->
            <div class="telegram-actions">
              <el-button type="default" :loading="refreshingLitellm" @click="onRefreshLitellm">
                <el-icon style="margin-right: 6px;"><Refresh /></el-icon>
                {{ $t('litellmRefresh') }}
              </el-button>
              <el-button type="default" :loading="refreshingDbTargets" @click="onRefreshDbTargets" style="margin-left: 8px;">
                <el-icon style="margin-right: 6px;"><Refresh /></el-icon>
                {{ $t('dbTargetRefresh') }}
              </el-button>
              <el-button type="primary" :loading="savingLitellm" @click="onSaveLitellmSettings">
                <el-icon style="margin-right: 6px;"><Check /></el-icon>
                {{ $t('save') }}
              </el-button>
            </div>
          </el-form>
        </div>
      </Transition>
    </div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!-- SECTION 3 — Notification Channels (collapsible, tabbed)  -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div v-if="isAdmin" class="collapse-card" :class="{ open: sections.notifications }">
      <div class="collapse-card-header" @click="toggleSection('notifications')">
        <div class="collapse-card-title">
          <div class="collapse-card-icon notification-icon">
            <span style="font-size: 20px;">🔔</span>
          </div>
          <div>
            <h3>{{ $t('notificationChannels') }}</h3>
            <span class="collapse-card-subtitle">{{ $t('notificationChannelsDesc') }}</span>
          </div>
        </div>
        <div class="collapse-card-right">
          <el-tag v-if="mailConfig.password_set" type="success" size="small" effect="plain" round style="margin-right: 4px;">📧</el-tag>
          <el-tag v-if="telegramConfig.bot_token_set" type="success" size="small" effect="plain" round><svg class="telegram-logo" viewBox="0 0 24 24" width="14" height="14" style="vertical-align: middle;"><path fill="currentColor" d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg></el-tag>
          <el-tag v-if="!mailConfig.password_set && !telegramConfig.bot_token_set" type="info" size="default" effect="plain" round>
            {{ $t('notConnected') }}
          </el-tag>
          <div class="collapse-chevron" :class="{ rotated: sections.notifications }">
            <el-icon :size="18"><ArrowDown /></el-icon>
          </div>
        </div>
      </div>
      <Transition name="collapse-body">
        <div v-show="sections.notifications" class="collapse-card-body">
          <el-tabs v-model="activeNotificationTab" type="border-card" class="notification-tabs">

            <!-- ════════════════════════════════════════════════ -->
            <!-- TAB: Email (SMTP)                               -->
            <!-- ════════════════════════════════════════════════ -->
            <el-tab-pane :label="$t('notificationTabEmail')" name="email">
              <template #label>
                <span class="tab-label-custom">
                  <span>📧</span>
                  <span>{{ $t('notificationTabEmail') }}</span>
                  <el-tag v-if="mailConfig.password_set" type="success" size="small" effect="plain" round style="margin-left: 6px;">{{ $t('connected') }}</el-tag>
                </span>
              </template>
              <el-form label-position="top" class="telegram-form" v-loading="mailLoading">
                <!-- SMTP Presets -->
                <div class="inner-card">
                  <div class="inner-card-header" @click="toggleInner('smtpServer')">
                    <span>🖥️ {{ $t('smtpPresets') || 'SMTP Server' }}</span>
                    <div class="collapse-chevron small" :class="{ rotated: innerSections.smtpServer }">
                      <el-icon :size="14"><ArrowDown /></el-icon>
                    </div>
                  </div>
                  <Transition name="collapse-body">
                    <div v-show="innerSections.smtpServer" class="inner-card-body">
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
                    </div>
                  </Transition>
                </div>

                <!-- Notification Toggles -->
                <div class="inner-card">
                  <div class="inner-card-header" @click="toggleInner('mailNotify')">
                    <span>🔔 {{ $t('notifyOnAlert') }}</span>
                    <div class="collapse-chevron small" :class="{ rotated: innerSections.mailNotify }">
                      <el-icon :size="14"><ArrowDown /></el-icon>
                    </div>
                  </div>
                  <Transition name="collapse-body">
                    <div v-show="innerSections.mailNotify" class="inner-card-body">
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
                    </div>
                  </Transition>
                </div>

                <!-- Setup Guide -->
                <div class="inner-card">
                  <div class="inner-card-header" @click="toggleInner('mailGuide')">
                    <span>📖 {{ $t('mailSetupGuide') }}</span>
                    <div class="collapse-chevron small" :class="{ rotated: innerSections.mailGuide }">
                      <el-icon :size="14"><ArrowDown /></el-icon>
                    </div>
                  </div>
                  <Transition name="collapse-body">
                    <div v-show="innerSections.mailGuide" class="inner-card-body">
                      <div class="guide-steps">
                        <p>{{ $t('mailStep1') }}</p>
                        <p>{{ $t('mailStep2') }}</p>
                        <p>{{ $t('mailStep3') }}</p>
                        <p>{{ $t('mailStep4') }}</p>
                        <p>{{ $t('mailStep5') }}</p>
                      </div>
                    </div>
                  </Transition>
                </div>

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
            </el-tab-pane>

            <!-- ════════════════════════════════════════════════ -->
            <!-- TAB: Telegram                                   -->
            <!-- ════════════════════════════════════════════════ -->
            <el-tab-pane :label="$t('notificationTabTelegram')" name="telegram">
              <template #label>
                <span class="tab-label-custom">
                  <svg class="telegram-logo" viewBox="0 0 24 24" width="16" height="16" style="vertical-align: middle;"><path fill="#26A5E4" d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
                  <span>{{ $t('notificationTabTelegram') }}</span>
                  <el-tag v-if="telegramConfig.bot_token_set" type="success" size="small" effect="plain" round style="margin-left: 6px;">{{ $t('telegramBotConnected') }}</el-tag>
                </span>
              </template>
              <el-form label-position="top" class="telegram-form" v-loading="telegramLoading">

                <!-- ═══ Bot Settings ═══ -->
                <div class="inner-card">
                  <div class="inner-card-header" @click="toggleInner('telegramBot')">
                    <span>🤖 {{ $t('telegramBotToken') }}</span>
                    <div class="collapse-chevron small" :class="{ rotated: innerSections.telegramBot }">
                      <el-icon :size="14"><ArrowDown /></el-icon>
                    </div>
                  </div>
                  <Transition name="collapse-body">
                    <div v-show="innerSections.telegramBot" class="inner-card-body">
                      <div class="form-group">
                        <el-row :gutter="20">
                          <el-col :span="16">
                            <el-form-item :label="$t('telegramBotToken')">
                              <el-input
                                v-model="telegramConfig.bot_token"
                                :placeholder="$t('telegramBotTokenPlaceholder')"
                                clearable
                                type="password"
                                show-password
                              />
                              <div class="form-hint">
                                {{ $t('telegramBotTokenHint') }}
                                <span v-if="telegramConfig.bot_token_set" class="token-status token-set"> — {{ $t('tokenSetLeaveBlank') }}</span>
                              </div>
                            </el-form-item>
                          </el-col>
                          <el-col :span="8">
                            <el-form-item label="Status">
                              <div v-if="telegramConfig.bot_username" style="display:flex; align-items:center; gap:8px; padding-top: 4px;">
                                <el-tag type="success" effect="plain" round>
                                  <span>@{{ telegramConfig.bot_username }}</span>
                                </el-tag>
                              </div>
                              <div v-else style="padding-top: 8px; color: var(--el-text-color-placeholder); font-size: 13px;">
                                {{ $t('telegramBotNotConnected') }}
                              </div>
                            </el-form-item>
                          </el-col>
                        </el-row>
                      </div>

                      <div class="form-group">
                        <el-row :gutter="20">
                          <el-col :span="8">
                            <el-form-item :label="$t('telegramAdminChatId')">
                              <el-input
                                v-model="telegramConfig.admin_chat_id"
                                :placeholder="$t('telegramAdminChatIdPlaceholder')"
                                clearable
                              />
                              <div class="form-hint">{{ $t('telegramAdminChatIdHint') }}</div>
                            </el-form-item>
                          </el-col>
                          <el-col :span="8">
                            <el-form-item :label="$t('telegramExtraChatIds')">
                              <el-input
                                v-model="telegramConfig.extra_chat_ids"
                                :placeholder="$t('telegramExtraChatIdsPlaceholder')"
                                clearable
                              />
                              <div class="form-hint">{{ $t('telegramExtraChatIdsHint') }}</div>
                            </el-form-item>
                          </el-col>
                          <el-col :span="8" style="display: flex; align-items: flex-end; padding-bottom: 18px;">
                            <el-button
                              type="default"
                              :loading="findingChatId"
                              @click="onFindChatId"
                              :disabled="!telegramConfig.bot_token_set && !telegramConfig.bot_token"
                            >
                              <el-icon style="margin-right: 6px;"><Search /></el-icon>
                              {{ $t('telegramFindChatId') }}
                            </el-button>
                          </el-col>
                        </el-row>
                      </div>

                      <!-- Chat ID Sonuçları -->
                      <div v-if="foundChats.length > 0" style="margin-bottom: 16px;">
                        <div class="form-group-title">{{ $t('telegramFoundChats') }}</div>
                        <div v-for="chat in foundChats" :key="chat.chat_id" style="display: flex; align-items: center; gap: 8px; padding: 6px 0;">
                          <el-tag type="info" size="small">{{ chat.type }}</el-tag>
                          <code style="font-size: 13px; font-weight: 600;">{{ chat.chat_id }}</code>
                          <span style="font-size: 13px; color: var(--el-text-color-secondary);">
                            {{ chat.first_name || chat.title || chat.username || '' }}
                          </span>
                          <el-button size="small" type="primary" link @click="telegramConfig.admin_chat_id = String(chat.chat_id)">
                            {{ $t('use') }}
                          </el-button>
                        </div>
                      </div>
                    </div>
                  </Transition>
                </div>

                <!-- ═══ Notification Toggles ═══ -->
                <div class="inner-card">
                  <div class="inner-card-header" @click="toggleInner('telegramNotify')">
                    <span>🔔 {{ $t('telegramEnabled') }}</span>
                    <div class="collapse-chevron small" :class="{ rotated: innerSections.telegramNotify }">
                      <el-icon :size="14"><ArrowDown /></el-icon>
                    </div>
                  </div>
                  <Transition name="collapse-body">
                    <div v-show="innerSections.telegramNotify" class="inner-card-body">
                      <div class="form-group">
                        <el-row :gutter="20">
                          <el-col :span="8">
                            <div class="toggle-item">
                              <el-switch v-model="telegramConfig.notify_on_alert" />
                              <div class="toggle-info">
                                <span class="toggle-label">{{ $t('telegramNotifyAlert') }}</span>
                                <span class="toggle-hint">{{ $t('telegramNotifyAlertHint') }}</span>
                              </div>
                            </div>
                          </el-col>
                          <el-col :span="8">
                            <div class="toggle-item">
                              <el-switch v-model="telegramConfig.notify_on_resolved" />
                              <div class="toggle-info">
                                <span class="toggle-label">{{ $t('telegramNotifyResolved') }}</span>
                                <span class="toggle-hint">{{ $t('telegramNotifyResolvedHint') }}</span>
                              </div>
                            </div>
                          </el-col>
                          <el-col :span="8">
                            <div class="toggle-item">
                              <el-switch v-model="telegramConfig.notify_on_diagnosis" />
                              <div class="toggle-info">
                                <span class="toggle-label">{{ $t('telegramNotifyDiagnosis') }}</span>
                                <span class="toggle-hint">{{ $t('telegramNotifyDiagnosisHint') }}</span>
                              </div>
                            </div>
                          </el-col>
                        </el-row>
                      </div>
                    </div>
                  </Transition>
                </div>

                <!-- ═══ Setup Guide ═══ -->
                <div class="inner-card">
                  <div class="inner-card-header" @click="toggleInner('telegramGuide')">
                    <span>📖 {{ $t('telegramSetupGuide') }}</span>
                    <div class="collapse-chevron small" :class="{ rotated: innerSections.telegramGuide }">
                      <el-icon :size="14"><ArrowDown /></el-icon>
                    </div>
                  </div>
                  <Transition name="collapse-body">
                    <div v-show="innerSections.telegramGuide" class="inner-card-body">
                      <div class="guide-steps">
                        <p>{{ $t('telegramStep1') }}</p>
                        <p>{{ $t('telegramStep2') }}</p>
                        <p>{{ $t('telegramStep3') }}</p>
                        <p>{{ $t('telegramStep4') }}</p>
                        <p>{{ $t('telegramStep5') }}</p>
                      </div>
                    </div>
                  </Transition>
                </div>

                <!-- Action buttons -->
                <div class="telegram-actions">
                  <el-button
                    type="default"
                    :loading="testingTelegram"
                    @click="onTestTelegram"
                    :disabled="!telegramConfig.bot_token_set && !telegramConfig.bot_token"
                  >
                    <el-icon style="margin-right: 6px;"><Connection /></el-icon>
                    {{ $t('telegramTestSend') }}
                  </el-button>
                  <el-button type="primary" :loading="savingTelegram" @click="onSaveTelegram">
                    <el-icon style="margin-right: 6px;"><Check /></el-icon>
                    {{ $t('save') }}
                  </el-button>
                </div>
              </el-form>
            </el-tab-pane>

          </el-tabs>
        </div>
      </Transition>
    </div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!-- SECTION 4 — Knowledge Base Settings (combined)           -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div v-if="isAdmin" class="collapse-card" :class="{ open: sections.knowledgeBase }">
      <div class="collapse-card-header" @click="toggleSection('knowledgeBase')">
        <div class="collapse-card-title">
          <div class="collapse-card-icon kb-icon">
            <span style="font-size: 20px;">📚</span>
          </div>
          <div>
            <h3>{{ $t('kbCombinedTitle') }}</h3>
            <span class="collapse-card-subtitle">{{ $t('kbCombinedDesc') }}</span>
          </div>
        </div>
        <div class="collapse-card-right">
          <el-tag type="primary" size="small" effect="plain" round style="margin-left: 4px;">
            {{ kbSettingsConfig.default_vs_type }}
          </el-tag>
          <el-tag :type="autoIngestConfig.enabled ? 'success' : 'info'" size="small" effect="plain" round style="margin-left: 4px;">
            Auto-Ingest {{ autoIngestConfig.enabled ? 'ON' : 'OFF' }}
          </el-tag>
          <div class="collapse-chevron" :class="{ rotated: sections.knowledgeBase }">
            <el-icon :size="18"><ArrowDown /></el-icon>
          </div>
        </div>
      </div>
      <Transition name="collapse-body">
        <div v-show="sections.knowledgeBase" class="collapse-card-body">
          <el-form label-position="top" class="telegram-form" v-loading="kbSettingsLoading || autoIngestLoading">

            <!-- ═══════════════════════════════════════════════════ -->
            <!-- KB GENERAL SETTINGS                                -->
            <!-- ═══════════════════════════════════════════════════ -->

            <!-- ═══ Document Processing ═══ -->
            <div class="inner-card">
              <div class="inner-card-header" @click="toggleInner('kbSettingsDocProcessing')">
                <span>📄 {{ $t('kbSettingsDocProcessing') }}</span>
                <div class="collapse-chevron small" :class="{ rotated: innerSections.kbSettingsDocProcessing }">
                  <el-icon :size="14"><ArrowDown /></el-icon>
                </div>
              </div>
              <Transition name="collapse-body">
                <div v-show="innerSections.kbSettingsDocProcessing" class="inner-card-body">
                  <el-row :gutter="20">
                    <el-col :span="6">
                      <el-form-item :label="$t('kbSettingsChunkSize')">
                        <el-input-number v-model="kbSettingsConfig.chunk_size" :min="100" :max="8000" :step="100" style="width: 100%" controls-position="right" />
                        <div class="form-hint">{{ $t('kbSettingsChunkSizeHint') }}</div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="6">
                      <el-form-item :label="$t('kbSettingsOverlapSize')">
                        <el-input-number v-model="kbSettingsConfig.overlap_size" :min="0" :max="1000" :step="10" style="width: 100%" controls-position="right" />
                        <div class="form-hint">{{ $t('kbSettingsOverlapSizeHint') }}</div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="6">
                      <el-form-item :label="$t('kbSettingsTextSplitter')">
                        <el-select v-model="kbSettingsConfig.text_splitter_name" style="width: 100%">
                          <el-option label="RecursiveCharacterTextSplitter" value="RecursiveCharacterTextSplitter" />
                          <el-option label="SpacyTextSplitter" value="SpacyTextSplitter" />
                          <el-option label="MarkdownHeaderTextSplitter" value="MarkdownHeaderTextSplitter" />
                        </el-select>
                        <div class="form-hint">{{ $t('kbSettingsTextSplitterHint') }}</div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="6">
                      <div class="toggle-item" style="margin-top: 4px;">
                        <el-switch v-model="kbSettingsConfig.zh_title_enhance" />
                        <div class="toggle-info">
                          <span class="toggle-label">{{ $t('kbSettingsZhTitleEnhance') }}</span>
                          <span class="toggle-hint">{{ $t('kbSettingsZhTitleEnhanceHint') }}</span>
                        </div>
                      </div>
                    </el-col>
                  </el-row>
                </div>
              </Transition>
            </div>

            <!-- ═══ Search Parameters ═══ -->
            <div class="inner-card">
              <div class="inner-card-header" @click="toggleInner('kbSettingsSearchParams')">
                <span>🔍 {{ $t('kbSettingsSearchParams') }}</span>
                <div class="collapse-chevron small" :class="{ rotated: innerSections.kbSettingsSearchParams }">
                  <el-icon :size="14"><ArrowDown /></el-icon>
                </div>
              </div>
              <Transition name="collapse-body">
                <div v-show="innerSections.kbSettingsSearchParams" class="inner-card-body">
                  <el-row :gutter="20">
                    <el-col :span="8">
                      <el-form-item :label="$t('kbSettingsTopK')">
                        <el-input-number v-model="kbSettingsConfig.vector_search_top_k" :min="1" :max="20" :step="1" style="width: 100%" controls-position="right" />
                        <div class="form-hint">{{ $t('kbSettingsTopKHint') }}</div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item :label="$t('kbSettingsScoreThreshold')">
                        <el-input-number v-model="kbSettingsConfig.score_threshold" :min="0" :max="4" :step="0.1" :precision="2" style="width: 100%" controls-position="right" />
                        <div class="form-hint">{{ $t('kbSettingsScoreThresholdHint') }}</div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item :label="$t('kbSettingsVsType')">
                        <el-select v-model="kbSettingsConfig.default_vs_type" style="width: 100%">
                          <el-option label="🟢 ChromaDB" value="chromadb" />
                          <el-option label="🔵 Elasticsearch" value="es" />
                        </el-select>
                        <div class="form-hint">{{ $t('kbSettingsVsTypeHint') }}</div>
                      </el-form-item>
                    </el-col>
                  </el-row>
                </div>
              </Transition>
            </div>

            <!-- ═══════════════════════════════════════════════════ -->
            <!-- KB AUTO-INGEST                                     -->
            <!-- ═══════════════════════════════════════════════════ -->

            <!-- ═══ Auto-Ingest General ═══ -->
            <div class="inner-card">
              <div class="inner-card-header" @click="toggleInner('kbAutoIngestSettings')">
                <span>🔄 {{ $t('kbAutoIngestSettings') }}
                  <el-tag :type="autoIngestConfig.enabled ? 'success' : 'info'" size="small" effect="plain" round style="margin-left: 8px;">
                    {{ autoIngestConfig.enabled ? 'ON' : 'OFF' }}
                  </el-tag>
                </span>
                <div class="collapse-chevron small" :class="{ rotated: innerSections.kbAutoIngestSettings }">
                  <el-icon :size="14"><ArrowDown /></el-icon>
                </div>
              </div>
              <Transition name="collapse-body">
                <div v-show="innerSections.kbAutoIngestSettings" class="inner-card-body">
                  <div class="form-group">
                    <el-row :gutter="20">
                      <el-col :span="6">
                        <div class="toggle-item">
                          <el-switch v-model="autoIngestConfig.enabled" />
                          <div class="toggle-info">
                            <span class="toggle-label">{{ $t('kbAutoIngestEnabled') }}</span>
                            <span class="toggle-hint">{{ $t('kbAutoIngestEnabledHint') }}</span>
                          </div>
                        </div>
                      </el-col>
                      <el-col :span="6">
                        <el-form-item :label="$t('kbAutoIngestTargetKb')">
                          <el-input v-model="autoIngestConfig.target_kb_name" :placeholder="$t('kbAutoIngestTargetKbPlaceholder')" clearable />
                          <div class="form-hint">{{ $t('kbAutoIngestTargetKbHint') }}</div>
                        </el-form-item>
                      </el-col>
                      <el-col :span="6">
                        <el-form-item :label="$t('kbAutoIngestEmbedModel')">
                          <el-input v-model="autoIngestConfig.embed_model" :placeholder="$t('kbAutoIngestEmbedModelPlaceholder')" clearable />
                          <div class="form-hint">{{ $t('kbAutoIngestEmbedModelHint') }}</div>
                        </el-form-item>
                      </el-col>
                      <el-col :span="6">
                        <div class="toggle-item">
                          <el-switch v-model="autoIngestConfig.auto_create_kb" />
                          <div class="toggle-info">
                            <span class="toggle-label">{{ $t('kbAutoIngestAutoCreate') }}</span>
                            <span class="toggle-hint">{{ $t('kbAutoIngestAutoCreateHint') }}</span>
                          </div>
                        </div>
                      </el-col>
                    </el-row>
                  </div>
                </div>
              </Transition>
            </div>

            <!-- ═══ Content Options ═══ -->
            <div class="inner-card">
              <div class="inner-card-header" @click="toggleInner('kbAutoIngestContent')">
                <span>📝 {{ $t('kbAutoIngestContentOptions') }}</span>
                <div class="collapse-chevron small" :class="{ rotated: innerSections.kbAutoIngestContent }">
                  <el-icon :size="14"><ArrowDown /></el-icon>
                </div>
              </div>
              <Transition name="collapse-body">
                <div v-show="innerSections.kbAutoIngestContent" class="inner-card-body">
                  <div class="form-group">
                    <el-row :gutter="20">
                      <el-col :span="8">
                        <div class="toggle-item">
                          <el-switch v-model="autoIngestConfig.include_metrics" />
                          <div class="toggle-info">
                            <span class="toggle-label">{{ $t('kbAutoIngestIncludeMetrics') }}</span>
                            <span class="toggle-hint">{{ $t('kbAutoIngestIncludeMetricsHint') }}</span>
                          </div>
                        </div>
                      </el-col>
                      <el-col :span="8">
                        <div class="toggle-item">
                          <el-switch v-model="autoIngestConfig.include_root_cause" />
                          <div class="toggle-info">
                            <span class="toggle-label">{{ $t('kbAutoIngestIncludeRootCause') }}</span>
                            <span class="toggle-hint">{{ $t('kbAutoIngestIncludeRootCauseHint') }}</span>
                          </div>
                        </div>
                      </el-col>
                      <el-col :span="8">
                        <div class="toggle-item">
                          <el-switch v-model="autoIngestConfig.include_solution" />
                          <div class="toggle-info">
                            <span class="toggle-label">{{ $t('kbAutoIngestIncludeSolution') }}</span>
                            <span class="toggle-hint">{{ $t('kbAutoIngestIncludeSolutionHint') }}</span>
                          </div>
                        </div>
                      </el-col>
                    </el-row>
                  </div>
                </div>
              </Transition>
            </div>

            <!-- ═══ Advanced Settings ═══ -->
            <div class="inner-card">
              <div class="inner-card-header" @click="toggleInner('kbAutoIngestAdvanced')">
                <span>🔧 {{ $t('kbAutoIngestAdvanced') }}</span>
                <div class="collapse-chevron small" :class="{ rotated: innerSections.kbAutoIngestAdvanced }">
                  <el-icon :size="14"><ArrowDown /></el-icon>
                </div>
              </div>
              <Transition name="collapse-body">
                <div v-show="innerSections.kbAutoIngestAdvanced" class="inner-card-body">
                  <el-row :gutter="20">
                    <el-col :span="6">
                      <el-form-item :label="$t('kbAutoIngestMinSeverity')">
                        <el-input-number v-model="autoIngestConfig.min_severity" :min="1" :max="5" style="width: 100%" controls-position="right" />
                        <div class="form-hint">{{ $t('kbAutoIngestMinSeverityHint') }}</div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="6">
                      <el-form-item :label="$t('kbAutoIngestChunkSize')">
                        <el-input-number v-model="autoIngestConfig.chunk_size" :min="100" :max="4000" :step="100" style="width: 100%" controls-position="right" />
                        <div class="form-hint">{{ $t('kbAutoIngestChunkSizeHint') }}</div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="6">
                      <el-form-item :label="$t('kbAutoIngestChunkOverlap')">
                        <el-input-number v-model="autoIngestConfig.chunk_overlap" :min="0" :max="500" :step="10" style="width: 100%" controls-position="right" />
                        <div class="form-hint">{{ $t('kbAutoIngestChunkOverlapHint') }}</div>
                      </el-form-item>
                    </el-col>
                    <el-col :span="6">
                      <el-form-item :label="$t('kbAutoIngestMaxDocs')">
                        <el-input-number v-model="autoIngestConfig.max_history_docs" :min="0" :max="100000" :step="100" style="width: 100%" controls-position="right" />
                        <div class="form-hint">{{ $t('kbAutoIngestMaxDocsHint') }}</div>
                      </el-form-item>
                    </el-col>
                  </el-row>
                </div>
              </Transition>
            </div>

            <!-- ═══ Statistics ═══ -->
            <div class="inner-card">
              <div class="inner-card-header" @click="toggleInner('kbAutoIngestStats')">
                <span>📊 {{ $t('kbAutoIngestStats') }}</span>
                <div class="collapse-chevron small" :class="{ rotated: innerSections.kbAutoIngestStats }">
                  <el-icon :size="14"><ArrowDown /></el-icon>
                </div>
              </div>
              <Transition name="collapse-body">
                <div v-show="innerSections.kbAutoIngestStats" class="inner-card-body">
                  <el-row :gutter="20" style="margin-bottom: 16px;">
                    <el-col :span="8">
                      <div style="font-size: 13px; color: var(--el-text-color-secondary);">
                        <strong>{{ $t('kbAutoIngestStatsKbExists') }}:</strong>
                        <el-tag :type="autoIngestStats.kb_exists ? 'success' : 'info'" size="small" effect="plain" style="margin-left: 6px;">
                          {{ autoIngestStats.kb_exists ? $t('kbAutoIngestStatsKbExistsYes') : $t('kbAutoIngestStatsKbExistsNo') }}
                        </el-tag>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div style="font-size: 13px; color: var(--el-text-color-secondary);">
                        <strong>{{ $t('kbAutoIngestStatsDocCount') }}:</strong>
                        <span style="margin-left: 6px; font-weight: 600; color: var(--el-text-color-primary);">{{ autoIngestStats.doc_count ?? '—' }}</span>
                      </div>
                    </el-col>
                    <el-col :span="8" style="display: flex; align-items: center;">
                      <el-button size="small" type="default" @click="onRefreshAutoIngestStats">
                        <el-icon style="margin-right: 4px;"><Refresh /></el-icon>
                        {{ $t('litellmRefresh') }}
                      </el-button>
                    </el-col>
                  </el-row>
                  <el-divider />
                  <div style="margin-bottom: 8px;">
                    <span style="font-size: 13px; font-weight: 500; color: var(--el-text-color-primary);">{{ $t('kbAutoIngestManualIngest') }}</span>
                    <div class="form-hint">{{ $t('kbAutoIngestManualIngestHint') }}</div>
                  </div>
                  <el-button type="primary" size="small" :loading="manualIngesting" @click="onManualIngest">
                    <el-icon style="margin-right: 4px;"><Upload /></el-icon>
                    {{ $t('kbAutoIngestManualIngest') }}
                  </el-button>
                </div>
              </Transition>
            </div>

            <!-- ═══ Setup Guide ═══ -->
            <div class="inner-card">
              <div class="inner-card-header" @click="toggleInner('kbSettingsGuide')">
                <span>📖 {{ $t('kbSettingsGuide') }}</span>
                <div class="collapse-chevron small" :class="{ rotated: innerSections.kbSettingsGuide }">
                  <el-icon :size="14"><ArrowDown /></el-icon>
                </div>
              </div>
              <Transition name="collapse-body">
                <div v-show="innerSections.kbSettingsGuide" class="inner-card-body">
                  <div class="guide-steps">
                    <p>{{ $t('kbSettingsStep1') }}</p>
                    <p>{{ $t('kbSettingsStep2') }}</p>
                    <p>{{ $t('kbSettingsStep3') }}</p>
                    <p>{{ $t('kbSettingsStep4') }}</p>
                    <p>{{ $t('kbSettingsStep5') }}</p>
                  </div>
                </div>
              </Transition>
            </div>

            <!-- Action buttons -->
            <div class="telegram-actions">
              <el-button type="primary" :loading="savingKbSettings" @click="onSaveAllKbSettings">
                <el-icon style="margin-right: 6px;"><Check /></el-icon>
                {{ $t('save') }}
              </el-button>
            </div>
          </el-form>
        </div>
      </Transition>
    </div>

    <!-- Change My Password (visible to all users) -->
    <div class="collapse-card" :class="{ open: sections.myPassword }">
      <div class="collapse-card-header" @click="toggleSection('myPassword')">
        <div class="collapse-card-title">
          <div class="collapse-card-icon" style="background: linear-gradient(135deg,#667eea,#764ba2);">
            <el-icon :size="20"><Lock /></el-icon>
          </div>
          <div>
            <h3>{{ $t('changeMyPassword') }}</h3>
            <span class="collapse-card-subtitle">{{ $t('changeMyPasswordDesc') }}</span>
          </div>
        </div>
        <div class="collapse-chevron" :class="{ rotated: sections.myPassword }">
          <el-icon :size="18"><ArrowDown /></el-icon>
        </div>
      </div>
      <Transition name="collapse-body">
        <div v-show="sections.myPassword" class="collapse-card-body">
          <el-form ref="refMyPasswordForm" :model="myPasswordForm" :rules="myPasswordRules" label-position="top" style="max-width: 500px;">
            <el-form-item :label="$t('currentPassword')" prop="currentPassword">
              <el-input v-model="myPasswordForm.currentPassword" type="password" show-password :placeholder="$t('pleaseInputCurrentPassword')" />
            </el-form-item>
            <el-form-item :label="$t('newPassword')" prop="newPassword">
              <el-input v-model="myPasswordForm.newPassword" type="password" show-password :placeholder="$t('pleaseInputNewPassword')" />
            </el-form-item>
            <el-form-item :label="$t('confirmPassword')" prop="confirmPassword">
              <el-input v-model="myPasswordForm.confirmPassword" type="password" show-password :placeholder="$t('pleaseConfirmPassword')" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="myPasswordLoading" @click="onSubmitMyPassword">{{ $t('save') }}</el-button>
            </el-form-item>
          </el-form>
        </div>
      </Transition>
    </div>

    <!-- Edit DB Target Dialog -->
    <el-dialog v-model="showEditDbDialog" :title="$t('editDbTarget')" width="720px" :close-on-click-modal="false" destroy-on-close>
      <el-form label-width="130px" size="default">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="$t('name')">
              <el-input v-model="editDbTarget.name" :placeholder="$t('dbTargetNamePlaceholder')" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('dbTargetType')">
              <el-select v-model="editDbTarget.db_type" style="width: 100%">
                <el-option label="🐘 PostgreSQL" value="postgresql" />
                <el-option label="🐬 MySQL" value="mysql" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item :label="$t('dbTargetHost')">
              <el-input v-model="editDbTarget.host" :placeholder="$t('dbTargetHostPlaceholder')" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item :label="$t('smtpPort')">
              <el-input-number v-model="editDbTarget.port" :min="1" :max="65535" style="width: 100%" controls-position="right" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="$t('dbTargetDbName')">
              <el-input v-model="editDbTarget.dbname" :placeholder="$t('dbTargetDbNamePlaceholder')" clearable />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item :label="$t('username')">
              <el-input v-model="editDbTarget.user" :placeholder="$t('dbTargetUserPlaceholder')" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item :label="$t('password')">
              <el-input v-model="editDbTarget.password" type="password" show-password :placeholder="$t('editPasswordPlaceholder')" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item :label="$t('dbTargetPrimary')">
              <el-switch v-model="editDbTarget.is_primary" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- SSL Section -->
        <el-divider content-position="left">
          <span style="font-size: 13px;">🔒 {{ $t('sslSection') }}</span>
        </el-divider>
        <el-row :gutter="16">
          <el-col :span="4">
            <el-form-item :label="$t('sslEnabled')">
              <el-switch v-model="editDbTarget.ssl_enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item :label="$t('sslMode')">
              <el-select v-model="editDbTarget.ssl_mode" :disabled="!editDbTarget.ssl_enabled" style="width: 100%">
                <el-option label="require" value="require" />
                <el-option label="verify-ca" value="verify-ca" />
                <el-option label="verify-full" value="verify-full" />
                <el-option label="prefer" value="prefer" />
                <el-option label="disable" value="disable" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="14">
            <el-form-item :label="$t('sslCaPath')">
              <el-input v-model="editDbTarget.ssl_ca_path" :placeholder="$t('sslCaPathPlaceholder')" :disabled="!editDbTarget.ssl_enabled" clearable />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16" v-if="editDbTarget.ssl_enabled">
          <el-col :span="12">
            <el-form-item :label="$t('sslCertPath')">
              <el-input v-model="editDbTarget.ssl_cert_path" :placeholder="$t('sslCertPathPlaceholder')" :disabled="!editDbTarget.ssl_enabled" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('sslKeyPath')">
              <el-input v-model="editDbTarget.ssl_key_path" :placeholder="$t('sslKeyPathPlaceholder')" :disabled="!editDbTarget.ssl_enabled" clearable />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- SSH Section -->
        <el-divider content-position="left">
          <span style="font-size: 13px;">🖥️ {{ $t('sshAccessOptional') }}</span>
        </el-divider>
        <el-row :gutter="16">
          <el-col :span="4">
            <el-form-item :label="$t('sshEnabled')">
              <el-switch v-model="editDbTarget.ssh_enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item :label="$t('sshHost')">
              <el-input v-model="editDbTarget.ssh_host" :placeholder="$t('sshHostPlaceholder')" :disabled="!editDbTarget.ssh_enabled" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item :label="$t('sshPort')">
              <el-input-number v-model="editDbTarget.ssh_port" :min="1" :max="65535" :disabled="!editDbTarget.ssh_enabled" style="width: 100%" controls-position="right" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item :label="$t('sshUser')">
              <el-input v-model="editDbTarget.ssh_user" :placeholder="$t('sshUserPlaceholder')" :disabled="!editDbTarget.ssh_enabled" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item :label="$t('sshAuthMethod')">
              <el-radio-group v-model="editDbTarget.ssh_auth_type" :disabled="!editDbTarget.ssh_enabled" size="small">
                <el-radio-button label="key">🔑 {{ $t('sshAuthKey') }}</el-radio-button>
                <el-radio-button label="password">🔒 {{ $t('sshAuthPassword') }}</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- SSH Key Auth -->
        <div v-if="editDbTarget.ssh_enabled && editDbTarget.ssh_auth_type === 'key'">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item :label="$t('sshKeyPath')">
                <el-input v-model="editDbTarget.ssh_key_path" :placeholder="$t('sshKeyPathPlaceholder')" clearable />
                <div class="form-hint">{{ $t('sshKeyPathHint') }}</div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="$t('sshKeyPassphrase')">
                <el-input v-model="editDbTarget.ssh_key_passphrase" type="password" show-password :placeholder="$t('sshKeyPassphrasePlaceholder')" clearable />
                <div class="form-hint">{{ $t('sshKeyPassphraseHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="24">
              <el-form-item :label="$t('sshKeyContent')">
                <el-input
                  v-model="editDbTarget.ssh_key_content"
                  type="textarea"
                  :rows="4"
                  :placeholder="$t('sshKeyContentPlaceholder')"
                  style="font-family: monospace; font-size: 12px;"
                />
                <div class="form-hint" style="margin-top: 4px;">{{ $t('sshKeyContentHint') }}</div>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- SSH Password Auth -->
        <div v-if="editDbTarget.ssh_enabled && editDbTarget.ssh_auth_type === 'password'">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item :label="$t('sshPassword')">
                <el-input v-model="editDbTarget.ssh_password" type="password" show-password :placeholder="$t('editPasswordPlaceholder')" clearable />
              </el-form-item>
            </el-col>
          </el-row>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="showEditDbDialog = false">{{ $t('cancel') }}</el-button>
        <el-button type="primary" :loading="savingEditDb" @click="onSaveEditDbTarget">
          {{ $t('save') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Create User Dialog -->
    <el-dialog v-model="showCreateDialog" :title="$t('addUser')" width="420px" :close-on-click-modal="false">
      <el-form ref="refCreateForm" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item :label="$t('username')" prop="username">
          <el-input v-model="createForm.username" :placeholder="$t('pleaseInputUsername')" />
        </el-form-item>
        <el-form-item :label="$t('password')" prop="password">
          <el-input v-model="createForm.password" type="password" show-password :placeholder="$t('pleaseInputPassword')" />
        </el-form-item>
        <el-form-item :label="$t('confirmPassword')" prop="confirmPassword">
          <el-input v-model="createForm.confirmPassword" type="password" show-password :placeholder="$t('pleaseConfirmPassword')" />
        </el-form-item>
        <el-form-item :label="$t('role')" prop="role">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option label="User" value="user" />
            <el-option label="Admin" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="E-posta" prop="email">
          <el-input v-model="createForm.email" type="email" placeholder="kullanici@sirket.com" />
          <div style="color:#909399; font-size:12px; margin-top:4px;">Parola sıfırlama için gerekli</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">{{ $t('cancel') }}</el-button>
        <el-button type="primary" :loading="createLoading" @click="onCreateUser">{{ $t('create') }}</el-button>
      </template>
    </el-dialog>

    <!-- Change Password Dialog -->
    <el-dialog v-model="showPasswordDialog" :title="$t('changePassword')" width="420px" :close-on-click-modal="false">
      <el-form ref="refPasswordForm" :model="passwordForm" :rules="passwordRules" label-position="top">
        <el-form-item :label="$t('username')">
          <el-input :model-value="passwordForm.username" disabled />
        </el-form-item>
        <el-form-item :label="$t('newPassword')" prop="newPassword">
          <el-input v-model="passwordForm.newPassword" type="password" show-password :placeholder="$t('pleaseInputNewPassword')" />
        </el-form-item>
        <el-form-item :label="$t('confirmPassword')" prop="confirmPassword">
          <el-input v-model="passwordForm.confirmPassword" type="password" show-password :placeholder="$t('pleaseConfirmPassword')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">{{ $t('cancel') }}</el-button>
        <el-button type="primary" :loading="passwordLoading" @click="onSubmitPassword">{{ $t('save') }}</el-button>
      </template>
    </el-dialog>
    </template><!-- end v-if="isAdmin" -->
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useBasicStore } from '@/store/basic'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsersReq, createUserReq, toggleUserReq, deleteUserReq, changePasswordReq, changeMyPasswordReq } from '@/api/user'
import { litellmHealthReq, litellmModelsReq, litellmAddModelReq, litellmRemoveModelReq, litellmTestModelReq, dbaAgentHealthReq, litellmUpdateSettingsReq } from '@/api/litellm'
import { getMailConfigReq, saveMailConfigReq, testMailReq } from '@/api/mail'
import { getTelegramAlertConfigReq, saveTelegramAlertConfigReq, testTelegramAlertReq, telegramGetChatIdReq } from '@/api/telegram'
import { listDbTargetsReq, addDbTargetReq, updateDbTargetReq, deleteDbTargetReq, testDbTargetReq, testSshTargetReq, setPrimaryDbTargetReq } from '@/api/dbTargets'
import { getAutoIngestConfigReq, saveAutoIngestConfigReq, manualIngestReq, getAutoIngestStatsReq, getKbSettingsReq, saveKbSettingsReq } from '@/api/knowledge'
import { useI18n } from 'vue-i18n'

const { t: $t } = useI18n()
const basicStore = useBasicStore()
const isAdmin = computed(() => basicStore.roles.includes('admin'))

const validatePasswordStrength = (rule, value, callback) => {
  if (!value) { callback(); return }
  const re = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$/
  if (!re.test(value)) callback(new Error($t('passwordStrength')))
  else callback()
}

// Collapsible sections state
const sections = reactive({
  users: true,
  litellm: true,
  notifications: false,
  knowledgeBase: false,
  myPassword: false,
})
const innerSections = reactive({
  models: true,
  litellmSettings: false,
  litellmGuide: false,
  smtpServer: true,
  mailNotify: false,
  mailGuide: false,
  telegramBot: true,
  telegramNotify: false,
  telegramGuide: false,
  dbTargetList: true,
  dbTargetGuide: false,
  kbAutoIngestSettings: true,
  kbAutoIngestContent: false,
  kbAutoIngestAdvanced: false,
  kbAutoIngestStats: false,
  kbAutoIngestGuide: false,
  kbSettingsEmbedding: true,
  kbSettingsDocProcessing: true,
  kbSettingsSearchParams: false,
  kbSettingsGuide: false,
})
const toggleSection = (key) => { sections[key] = !sections[key] }
const toggleInner = (key) => { innerSections[key] = !innerSections[key] }
const activeNotificationTab = ref('email')

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
    fetchLitellmData()
    fetchMailConfig()
    fetchTelegramConfig()
    fetchDbTargets()
    fetchAutoIngestConfig()
    fetchAutoIngestStats()
    fetchKbSettings()
  }
})

// ========== LiteLLM & DBA Agent ==========
const litellmLoading = ref(false)
const savingLitellm = ref(false)
const refreshingLitellm = ref(false)
const litellmOnline = ref(false)
const dbaAgentOnline = ref(false)
const litellmModels = ref([])
const testingModel = ref('')
const testResult = ref(null)
const addingModel = ref(false)

// Yeni model formu
const newModel = reactive({
  model_name: '',
  litellm_model: '',
  api_base: '',
  role: '',
  timeout: 300,
  num_ctx: 2048,
  num_predict: 256,
})

// Genel ayarlar
const litellmSettings = reactive({
  request_timeout: 300,
  num_retries: 0,
  cache: true,
})

const fetchLitellmData = async () => {
  litellmLoading.value = true
  try {
    // Health check — paralel
    const [healthRes, dbaRes, modelsRes] = await Promise.allSettled([
      litellmHealthReq(),
      dbaAgentHealthReq(),
      litellmModelsReq(),
    ])

    // LiteLLM proxy durumu
    if (healthRes.status === 'fulfilled') {
      litellmOnline.value = healthRes.value?.code === 200 && healthRes.value?.data?.status === 'online'
    } else {
      litellmOnline.value = false
    }

    // DBA Agent durumu
    if (dbaRes.status === 'fulfilled') {
      const d = dbaRes.value?.data
      dbaAgentOnline.value = d?.status === 'healthy' || d?.status === 'online'
    } else {
      dbaAgentOnline.value = false
    }

    // Model listesi
    if (modelsRes.status === 'fulfilled' && modelsRes.value?.code === 200) {
      litellmModels.value = modelsRes.value.data?.models || []
    }
  } catch (e) {
    console.error('LiteLLM data fetch error:', e)
  } finally {
    litellmLoading.value = false
  }
}

const onAddModel = async () => {
  addingModel.value = true
  try {
    const res = await litellmAddModelReq({
      model_name: newModel.model_name,
      litellm_model: newModel.litellm_model,
      api_base: newModel.api_base,
      role: newModel.role,
      timeout: newModel.timeout,
      num_ctx: newModel.num_ctx,
      num_predict: newModel.num_predict,
      stream_timeout: newModel.timeout,
    })
    if (res.code === 200) {
      ElMessage.success(res.msg || $t('litellmModelAdded'))
      // Formu temizle
      newModel.model_name = ''
      newModel.litellm_model = ''
      newModel.api_base = ''
      newModel.role = ''
      newModel.timeout = 300
      newModel.num_ctx = 2048
      newModel.num_predict = 256
      fetchLitellmData()
    } else {
      ElMessage.error(res.msg || $t('litellmModelAddFail'))
    }
  } catch (e) {
    ElMessage.error($t('litellmModelAddFail'))
  } finally {
    addingModel.value = false
  }
}

const onRemoveModel = async (modelName) => {
  try {
    await ElMessageBox.confirm(
      `'${modelName}' modelini silmek istediğinize emin misiniz?`,
      $t('warning'),
      { confirmButtonText: $t('delete'), cancelButtonText: $t('cancel'), type: 'warning' }
    )
    const res = await litellmRemoveModelReq({ model_name: modelName })
    if (res.code === 200) {
      ElMessage.success(res.msg)
      fetchLitellmData()
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    // cancelled
  }
}

const onTestModel = async (modelName) => {
  testingModel.value = modelName
  testResult.value = null
  try {
    const res = await litellmTestModelReq({ model_name: modelName, prompt: 'Say hello in 5 words.' })
    if (res.code === 200 && res.data) {
      testResult.value = res.data
      ElMessage.success($t('litellmTestSuccess'))
    } else {
      ElMessage.error(res.msg || $t('litellmTestFail'))
    }
  } catch (e) {
    ElMessage.error($t('litellmTestFail'))
  } finally {
    testingModel.value = ''
  }
}

const onRefreshLitellm = async () => {
  refreshingLitellm.value = true
  await fetchLitellmData()
  refreshingLitellm.value = false
  ElMessage.success($t('litellmRefreshed'))
}

const onSaveLitellmSettings = async () => {
  savingLitellm.value = true
  try {
    const res = await litellmUpdateSettingsReq({
      request_timeout: litellmSettings.request_timeout,
      num_retries: litellmSettings.num_retries,
      cache: litellmSettings.cache,
    })
    if (res.code === 200) {
      ElMessage.success($t('saveSuccess'))
    } else {
      ElMessage.error(res.msg || 'Error')
    }
  } catch (e) {
    ElMessage.error('Error saving settings')
  } finally {
    savingLitellm.value = false
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

// ========== Telegram Config ==========
const telegramLoading = ref(false)
const savingTelegram = ref(false)
const testingTelegram = ref(false)
const findingChatId = ref(false)
const foundChats = ref([])
const telegramConfig = reactive({
  bot_token: '',
  bot_token_set: false,
  bot_username: '',
  admin_chat_id: '',
  extra_chat_ids: '',
  enabled: true,
  notify_on_alert: true,
  notify_on_resolved: true,
  notify_on_diagnosis: true,
})

const fetchTelegramConfig = async () => {
  telegramLoading.value = true
  try {
    const res = await getTelegramAlertConfigReq()
    if (res.code === 200 && res.data) {
      const d = res.data
      telegramConfig.bot_token = ''
      telegramConfig.bot_token_set = d.bot_token_set || false
      telegramConfig.bot_username = d.bot_username || ''
      telegramConfig.admin_chat_id = d.admin_chat_id || ''
      telegramConfig.extra_chat_ids = d.extra_chat_ids || ''
      telegramConfig.enabled = d.enabled ?? true
      telegramConfig.notify_on_alert = d.notify_on_alert ?? true
      telegramConfig.notify_on_resolved = d.notify_on_resolved ?? true
      telegramConfig.notify_on_diagnosis = d.notify_on_diagnosis ?? true
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
    const payload = {
      enabled: telegramConfig.enabled,
      admin_chat_id: telegramConfig.admin_chat_id,
      extra_chat_ids: telegramConfig.extra_chat_ids,
      notify_on_alert: telegramConfig.notify_on_alert,
      notify_on_resolved: telegramConfig.notify_on_resolved,
      notify_on_diagnosis: telegramConfig.notify_on_diagnosis,
    }
    if (telegramConfig.bot_token) {
      payload.bot_token = telegramConfig.bot_token
    }
    const res = await saveTelegramAlertConfigReq(payload)
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

const onTestTelegram = async () => {
  testingTelegram.value = true
  try {
    const res = await testTelegramAlertReq()
    if (res.code === 200) {
      ElMessage.success($t('telegramTestSuccess'))
    } else {
      ElMessage.error($t('telegramTestFail') + ': ' + (res.msg || ''))
    }
  } catch (e) {
    ElMessage.error($t('telegramTestFail'))
  } finally {
    testingTelegram.value = false
  }
}

const onFindChatId = async () => {
  findingChatId.value = true
  foundChats.value = []
  try {
    const res = await telegramGetChatIdReq()
    if (res.code === 200 && res.data) {
      foundChats.value = res.data.chats || []
      if (foundChats.value.length === 0) {
        ElMessage.warning($t('telegramNoChatFound'))
      }
    } else {
      ElMessage.error(res.msg || 'Error')
    }
  } catch (e) {
    ElMessage.error('Error finding chat ID')
  } finally {
    findingChatId.value = false
  }
}

// ========== DB Targets ==========
const dbTargetsLoading = ref(false)
const refreshingDbTargets = ref(false)
const addingDbTarget = ref(false)
const testingDbTarget = ref('')
const dbTargets = ref([])
const dbTestResult = ref(null)

const testingSshTarget = ref('')
const sshTestResult = ref(null)

const newDbTarget = reactive({
  name: '',
  db_type: 'postgresql',
  host: '',
  port: 5432,
  user: '',
  password: '',
  dbname: '',
  is_primary: false,
  ssl_enabled: false,
  ssl_mode: 'require',
  ssl_ca_path: '',
  ssl_cert_path: '',
  ssl_key_path: '',
  ssh_auth_type: 'key',
  ssh_enabled: false,
  ssh_host: '',
  ssh_port: 22,
  ssh_user: '',
  ssh_password: '',
  ssh_key_path: '',
  ssh_key_content: '',
  ssh_key_passphrase: '',
})

// Edit dialog state
const showEditDbDialog = ref(false)
const savingEditDb = ref(false)
const editingDbTargetId = ref('')
const editDbTarget = reactive({
  name: '',
  db_type: 'postgresql',
  host: '',
  port: 5432,
  user: '',
  password: '',
  dbname: '',
  is_primary: false,
  ssl_enabled: false,
  ssl_mode: 'require',
  ssl_ca_path: '',
  ssl_cert_path: '',
  ssl_key_path: '',
  ssh_auth_type: 'key',
  ssh_enabled: false,
  ssh_host: '',
  ssh_port: 22,
  ssh_user: '',
  ssh_password: '',
  ssh_key_path: '',
  ssh_key_content: '',
  ssh_key_passphrase: '',
})

const fetchDbTargets = async () => {
  dbTargetsLoading.value = true
  try {
    const res = await listDbTargetsReq()
    if (res.code === 200) {
      dbTargets.value = res.data || []
    }
  } catch (e) {
    console.error('Failed to load DB targets:', e)
  } finally {
    dbTargetsLoading.value = false
  }
}

const onAddDbTarget = async () => {
  // Zorunlu alan kontrolü
  const missing = []
  if (!newDbTarget.name?.trim()) missing.push('Name')
  if (!newDbTarget.host?.trim()) missing.push('Host')
  if (!newDbTarget.user?.trim()) missing.push('User')
  if (!newDbTarget.dbname?.trim()) missing.push('Database')
  if (missing.length) {
    ElMessage.warning(`Lütfen zorunlu alanları doldurun: ${missing.join(', ')}`)
    return
  }
  addingDbTarget.value = true
  try {
    const res = await addDbTargetReq({
      name: newDbTarget.name,
      db_type: newDbTarget.db_type,
      host: newDbTarget.host,
      port: newDbTarget.port,
      user: newDbTarget.user,
      password: newDbTarget.password,
      dbname: newDbTarget.dbname,
      is_primary: newDbTarget.is_primary,
      ssl_enabled: newDbTarget.ssl_enabled,
      ssl_mode: newDbTarget.ssl_mode,
      ssl_ca_path: newDbTarget.ssl_ca_path,
      ssl_cert_path: newDbTarget.ssl_cert_path,
      ssl_key_path: newDbTarget.ssl_key_path,
      ssh_enabled: newDbTarget.ssh_enabled,
      ssh_auth_type: newDbTarget.ssh_auth_type,
      ssh_host: newDbTarget.ssh_host,
      ssh_port: newDbTarget.ssh_port,
      ssh_user: newDbTarget.ssh_user,
      ssh_password: newDbTarget.ssh_auth_type === 'password' ? newDbTarget.ssh_password : '',
      ssh_key_path: newDbTarget.ssh_auth_type === 'key' ? newDbTarget.ssh_key_path : '',
      ssh_key_content: newDbTarget.ssh_auth_type === 'key' ? newDbTarget.ssh_key_content : '',
      ssh_key_passphrase: newDbTarget.ssh_auth_type === 'key' ? newDbTarget.ssh_key_passphrase : '',
    })
    if (res.code === 200) {
      ElMessage.success(res.msg)
      newDbTarget.name = ''
      newDbTarget.host = ''
      newDbTarget.port = newDbTarget.db_type === 'postgresql' ? 5432 : 3306
      newDbTarget.user = ''
      newDbTarget.password = ''
      newDbTarget.dbname = ''
      newDbTarget.is_primary = false
      newDbTarget.ssl_enabled = false
      newDbTarget.ssl_mode = 'require'
      newDbTarget.ssl_ca_path = ''
      newDbTarget.ssl_cert_path = ''
      newDbTarget.ssl_key_path = ''
      newDbTarget.ssh_enabled = false
      newDbTarget.ssh_auth_type = 'key'
      newDbTarget.ssh_host = ''
      newDbTarget.ssh_port = 22
      newDbTarget.ssh_user = ''
      newDbTarget.ssh_password = ''
      newDbTarget.ssh_key_path = ''
      newDbTarget.ssh_key_content = ''
      newDbTarget.ssh_key_passphrase = ''
      fetchDbTargets()
    } else {
      ElMessage.error(res.msg || 'Error')
    }
  } catch (e) {
    ElMessage.error(e?.msg || 'Error')
  } finally {
    addingDbTarget.value = false
  }
}

const onDeleteDbTarget = (row) => {
  ElMessageBox.confirm(
    `'${row.name}' bağlantısını silmek istediğinize emin misiniz?`,
    $t('warning'),
    { confirmButtonText: $t('delete'), cancelButtonText: $t('cancel'), type: 'warning' }
  ).then(async () => {
    try {
      const res = await deleteDbTargetReq({ id: row.id })
      if (res.code === 200) {
        ElMessage.success(res.msg)
        fetchDbTargets()
      } else {
        ElMessage.error(res.msg)
      }
    } catch (e) {
      ElMessage.error(e?.msg || 'Error')
    }
  }).catch(() => {})
}

const onTestDbTarget = async (id) => {
  testingDbTarget.value = id
  dbTestResult.value = null
  try {
    const res = await testDbTargetReq({ id })
    if (res.code === 200 && res.data) {
      dbTestResult.value = res.data
      ElMessage.success($t('dbTargetTestSuccess'))
      fetchDbTargets()
    } else {
      ElMessage.error(res.msg || $t('dbTargetTestFail'))
    }
  } catch (e) {
    ElMessage.error($t('dbTargetTestFail'))
  } finally {
    testingDbTarget.value = ''
  }
}

const onSetPrimaryDb = async (id) => {
  try {
    const res = await setPrimaryDbTargetReq({ id })
    if (res.code === 200) {
      ElMessage.success(res.msg)
      fetchDbTargets()
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error(e?.msg || 'Error')
  }
}

const onRefreshDbTargets = async () => {
  refreshingDbTargets.value = true
  await fetchDbTargets()
  refreshingDbTargets.value = false
  ElMessage.success($t('litellmRefreshed'))
}

const onTestSshTarget = async (id) => {
  testingSshTarget.value = id
  sshTestResult.value = null
  try {
    const res = await testSshTargetReq({ id })
    if (res.code === 200 && res.data) {
      sshTestResult.value = res.data
      ElMessage.success($t('sshTestSuccess'))
      fetchDbTargets()
    } else {
      ElMessage.error(res.msg || $t('sshTestFail'))
    }
  } catch (e) {
    ElMessage.error($t('sshTestFail'))
  } finally {
    testingSshTarget.value = ''
  }
}

const onEditDbTarget = (row) => {
  editingDbTargetId.value = row.id
  editDbTarget.name = row.name || ''
  editDbTarget.db_type = row.db_type || 'postgresql'
  editDbTarget.host = row.host || ''
  editDbTarget.port = row.port || 5432
  editDbTarget.user = row.user || ''
  editDbTarget.password = ''
  editDbTarget.dbname = row.dbname || ''
  editDbTarget.is_primary = row.is_primary || false
  editDbTarget.ssl_enabled = row.ssl_enabled || false
  editDbTarget.ssl_mode = row.ssl_mode || 'require'
  editDbTarget.ssl_ca_path = row.ssl_ca_path || ''
  editDbTarget.ssl_cert_path = row.ssl_cert_path || ''
  editDbTarget.ssl_key_path = row.ssl_key_path || ''
  editDbTarget.ssh_enabled = row.ssh_enabled || false
  editDbTarget.ssh_auth_type = row.ssh_auth_type || (row.ssh_key_path || row.ssh_key_content ? 'key' : 'password')
  editDbTarget.ssh_host = row.ssh_host || ''
  editDbTarget.ssh_port = row.ssh_port || 22
  editDbTarget.ssh_user = row.ssh_user || ''
  editDbTarget.ssh_password = ''
  editDbTarget.ssh_key_path = row.ssh_key_path || ''
  editDbTarget.ssh_key_content = ''
  editDbTarget.ssh_key_passphrase = ''
  showEditDbDialog.value = true
}

const onSaveEditDbTarget = async () => {
  savingEditDb.value = true
  try {
    const payload = {
      id: editingDbTargetId.value,
      name: editDbTarget.name,
      db_type: editDbTarget.db_type,
      host: editDbTarget.host,
      port: editDbTarget.port,
      user: editDbTarget.user,
      dbname: editDbTarget.dbname,
      is_primary: editDbTarget.is_primary,
      ssl_enabled: editDbTarget.ssl_enabled,
      ssl_mode: editDbTarget.ssl_mode,
      ssl_ca_path: editDbTarget.ssl_ca_path,
      ssl_cert_path: editDbTarget.ssl_cert_path,
      ssl_key_path: editDbTarget.ssl_key_path,
      ssh_enabled: editDbTarget.ssh_enabled,
      ssh_auth_type: editDbTarget.ssh_auth_type,
      ssh_host: editDbTarget.ssh_host,
      ssh_port: editDbTarget.ssh_port,
      ssh_user: editDbTarget.ssh_user,
      ssh_key_path: editDbTarget.ssh_key_path,
    }
    // Only send password fields if user actually typed something
    if (editDbTarget.password) payload.password = editDbTarget.password
    if (editDbTarget.ssh_password) payload.ssh_password = editDbTarget.ssh_password
    if (editDbTarget.ssh_key_content) payload.ssh_key_content = editDbTarget.ssh_key_content
    if (editDbTarget.ssh_key_passphrase) payload.ssh_key_passphrase = editDbTarget.ssh_key_passphrase

    const res = await updateDbTargetReq(payload)
    if (res.code === 200) {
      ElMessage.success(res.msg)
      showEditDbDialog.value = false
      fetchDbTargets()
    } else {
      ElMessage.error(res.msg || 'Error')
    }
  } catch (e) {
    ElMessage.error(e?.msg || 'Error')
  } finally {
    savingEditDb.value = false
  }
}

// ========== KB Auto-Ingest ==========
const autoIngestLoading = ref(false)
const savingAutoIngest = ref(false)
const manualIngesting = ref(false)
const autoIngestConfig = reactive({
  enabled: false,
  target_kb_name: 'dba_diagnosis_history',
  embed_model: 'm3e-base',
  auto_create_kb: true,
  include_metrics: true,
  include_root_cause: true,
  include_solution: true,
  min_severity: 1,
  chunk_size: 500,
  chunk_overlap: 50,
  max_history_docs: 1000,
})
const autoIngestStats = reactive({
  kb_exists: false,
  doc_count: 0,
})

const fetchAutoIngestConfig = async () => {
  autoIngestLoading.value = true
  try {
    const res = await getAutoIngestConfigReq()
    if (res.code === 200 && res.data) {
      const d = res.data
      autoIngestConfig.enabled = d.enabled ?? false
      autoIngestConfig.target_kb_name = d.target_kb_name || 'dba_diagnosis_history'
      autoIngestConfig.embed_model = d.embed_model || 'm3e-base'
      autoIngestConfig.auto_create_kb = d.auto_create_kb ?? true
      autoIngestConfig.include_metrics = d.include_metrics ?? true
      autoIngestConfig.include_root_cause = d.include_root_cause ?? true
      autoIngestConfig.include_solution = d.include_solution ?? true
      autoIngestConfig.min_severity = d.min_severity ?? 1
      autoIngestConfig.chunk_size = d.chunk_size ?? 500
      autoIngestConfig.chunk_overlap = d.chunk_overlap ?? 50
      autoIngestConfig.max_history_docs = d.max_history_docs ?? 1000
    }
  } catch (e) {
    console.error('Failed to load Auto-Ingest config:', e)
  } finally {
    autoIngestLoading.value = false
  }
}

const onSaveAutoIngest = async () => {
  savingAutoIngest.value = true
  try {
    const res = await saveAutoIngestConfigReq({
      enabled: autoIngestConfig.enabled,
      target_kb_name: autoIngestConfig.target_kb_name,
      embed_model: autoIngestConfig.embed_model,
      auto_create_kb: autoIngestConfig.auto_create_kb,
      include_metrics: autoIngestConfig.include_metrics,
      include_root_cause: autoIngestConfig.include_root_cause,
      include_solution: autoIngestConfig.include_solution,
      min_severity: autoIngestConfig.min_severity,
      chunk_size: autoIngestConfig.chunk_size,
      chunk_overlap: autoIngestConfig.chunk_overlap,
      max_history_docs: autoIngestConfig.max_history_docs,
    })
    if (res.code === 200) {
      ElMessage.success($t('saveSuccess'))
    } else {
      ElMessage.error(res.msg || 'Error')
    }
  } catch (e) {
    ElMessage.error(e?.msg || 'Error')
  } finally {
    savingAutoIngest.value = false
  }
}

const fetchAutoIngestStats = async () => {
  try {
    const res = await getAutoIngestStatsReq()
    if (res.code === 200 && res.data) {
      autoIngestStats.kb_exists = res.data.kb_exists ?? false
      autoIngestStats.doc_count = res.data.doc_count ?? 0
    }
  } catch (e) {
    console.error('Failed to load Auto-Ingest stats:', e)
  }
}

const onRefreshAutoIngestStats = async () => {
  await fetchAutoIngestStats()
  ElMessage.success($t('litellmRefreshed'))
}

const onManualIngest = async () => {
  manualIngesting.value = true
  try {
    const res = await manualIngestReq('diagnose_run_data.jsonl')
    if (res.code === 200) {
      ElMessage.success($t('kbAutoIngestManualIngestSuccess'))
      fetchAutoIngestStats()
    } else {
      ElMessage.error($t('kbAutoIngestManualIngestFail') + ': ' + (res.msg || ''))
    }
  } catch (e) {
    ElMessage.error($t('kbAutoIngestManualIngestFail'))
  } finally {
    manualIngesting.value = false
  }
}

// ========== KB General Settings ==========
const kbSettingsLoading = ref(false)
const savingKbSettings = ref(false)
const kbSettingsConfig = reactive({
  chunk_size: 500,
  overlap_size: 50,
  vector_search_top_k: 3,
  score_threshold: 2.0,
  text_splitter_name: 'RecursiveCharacterTextSplitter',
  default_vs_type: 'chromadb',
  zh_title_enhance: false,
  embedding_model: 'all-MiniLM-L6-v2',
  default_knowledge_base: 'samples',
  vs_type_prompt_total_byte_size: 3000,
})

const fetchKbSettings = async () => {
  kbSettingsLoading.value = true
  try {
    const res = await getKbSettingsReq()
    if (res.code === 200 && res.data) {
      const d = res.data
      kbSettingsConfig.chunk_size = d.chunk_size ?? 500
      kbSettingsConfig.overlap_size = d.overlap_size ?? 50
      kbSettingsConfig.vector_search_top_k = d.vector_search_top_k ?? 3
      kbSettingsConfig.score_threshold = d.score_threshold ?? 2.0
      kbSettingsConfig.text_splitter_name = d.text_splitter_name || 'RecursiveCharacterTextSplitter'
      kbSettingsConfig.default_vs_type = d.default_vs_type || 'chromadb'
      kbSettingsConfig.zh_title_enhance = d.zh_title_enhance ?? false
      kbSettingsConfig.embedding_model = d.embedding_model || 'all-MiniLM-L6-v2'
      kbSettingsConfig.default_knowledge_base = d.default_knowledge_base || 'samples'
      kbSettingsConfig.vs_type_prompt_total_byte_size = d.vs_type_prompt_total_byte_size ?? 3000
    }
  } catch (e) {
    console.error(e)
  } finally {
    kbSettingsLoading.value = false
  }
}

const onSaveKbSettings = async () => {
  savingKbSettings.value = true
  try {
    const res = await saveKbSettingsReq({
      chunk_size: kbSettingsConfig.chunk_size,
      overlap_size: kbSettingsConfig.overlap_size,
      vector_search_top_k: kbSettingsConfig.vector_search_top_k,
      score_threshold: kbSettingsConfig.score_threshold,
      text_splitter_name: kbSettingsConfig.text_splitter_name,
      default_vs_type: kbSettingsConfig.default_vs_type,
      zh_title_enhance: kbSettingsConfig.zh_title_enhance,
      embedding_model: kbSettingsConfig.embedding_model,
      default_knowledge_base: kbSettingsConfig.default_knowledge_base,
      vs_type_prompt_total_byte_size: kbSettingsConfig.vs_type_prompt_total_byte_size,
    })
    if (res.code === 200) {
      ElMessage.success($t('kbSettingsSaveSuccess'))
    } else {
      ElMessage.error(res.msg || 'Save failed')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('Save failed')
  } finally {
    savingKbSettings.value = false
  }
}

const onSaveAllKbSettings = async () => {
  savingKbSettings.value = true
  try {
    await Promise.all([
      saveKbSettingsReq({
        chunk_size: kbSettingsConfig.chunk_size,
        overlap_size: kbSettingsConfig.overlap_size,
        vector_search_top_k: kbSettingsConfig.vector_search_top_k,
        score_threshold: kbSettingsConfig.score_threshold,
        text_splitter_name: kbSettingsConfig.text_splitter_name,
        default_vs_type: kbSettingsConfig.default_vs_type,
        zh_title_enhance: kbSettingsConfig.zh_title_enhance,
        embedding_model: kbSettingsConfig.embedding_model,
        default_knowledge_base: kbSettingsConfig.default_knowledge_base,
        vs_type_prompt_total_byte_size: kbSettingsConfig.vs_type_prompt_total_byte_size,
      }),
      saveAutoIngestConfigReq({
        enabled: autoIngestConfig.enabled,
        target_kb_name: autoIngestConfig.target_kb_name,
        embed_model: autoIngestConfig.embed_model,
        auto_create_kb: autoIngestConfig.auto_create_kb,
        include_metrics: autoIngestConfig.include_metrics,
        include_root_cause: autoIngestConfig.include_root_cause,
        include_solution: autoIngestConfig.include_solution,
        min_severity: autoIngestConfig.min_severity,
        chunk_size: autoIngestConfig.chunk_size,
        chunk_overlap: autoIngestConfig.chunk_overlap,
        max_history_docs: autoIngestConfig.max_history_docs,
      }),
    ])
    ElMessage.success($t('saveSuccess'))
  } catch (e) {
    console.error(e)
    ElMessage.error('Save failed')
  } finally {
    savingKbSettings.value = false
  }
}

// Create user
const showCreateDialog = ref(false)
const createLoading = ref(false)
const refCreateForm = ref(null)
const createForm = reactive({ username: '', password: '', confirmPassword: '', role: 'user', email: '' })
const createRules = {
  username: [{ required: true, message: () => $t('pleaseInputUsername'), trigger: 'blur' }],
  password: [
    { required: true, message: () => $t('pleaseInputPassword'), trigger: 'blur' },
    { validator: validatePasswordStrength, trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: () => $t('pleaseConfirmPassword'), trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== createForm.password) callback(new Error($t('passwordMismatch')))
        else callback()
      },
      trigger: 'blur'
    }
  ]
}

const onCreateUser = () => {
  refCreateForm.value.validate(async (valid) => {
    if (!valid) return
    createLoading.value = true
    try {
      const res = await createUserReq(createForm.username, createForm.password, createForm.role, createForm.email || null)
      if (res.code === 200) {
        ElMessage.success(res.msg)
        showCreateDialog.value = false
        createForm.username = ''
        createForm.password = ''
        createForm.confirmPassword = ''
        createForm.role = 'user'
        createForm.email = ''
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
const passwordForm = reactive({ userId: null, username: '', newPassword: '', confirmPassword: '' })
const passwordRules = {
  newPassword: [
    { required: true, message: () => $t('pleaseInputNewPassword'), trigger: 'blur' },
    { validator: validatePasswordStrength, trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: () => $t('pleaseConfirmPassword'), trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.newPassword) callback(new Error($t('passwordMismatch')))
        else callback()
      },
      trigger: 'blur'
    }
  ]
}

const onChangePassword = (row) => {
  passwordForm.userId = row.id
  passwordForm.username = row.username
  passwordForm.newPassword = ''
  passwordForm.confirmPassword = ''
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

// ── Change My Own Password ────────────────────────────────────────────────────
const refMyPasswordForm = ref(null)
const myPasswordLoading = ref(false)
const myPasswordForm = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })
const myPasswordRules = {
  currentPassword: [{ required: true, message: () => $t('pleaseInputCurrentPassword'), trigger: 'blur' }],
  newPassword: [
    { required: true, message: () => $t('pleaseInputNewPassword'), trigger: 'blur' },
    { validator: validatePasswordStrength, trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: () => $t('pleaseConfirmPassword'), trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== myPasswordForm.newPassword) {
          callback(new Error($t('passwordMismatch')))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const onSubmitMyPassword = () => {
  refMyPasswordForm.value.validate(async (valid) => {
    if (!valid) return
    myPasswordLoading.value = true
    try {
      const res = await changeMyPasswordReq(myPasswordForm.currentPassword, myPasswordForm.newPassword)
      if (res.code === 200) {
        ElMessage.success(res.msg)
        myPasswordForm.currentPassword = ''
        myPasswordForm.newPassword = ''
        myPasswordForm.confirmPassword = ''
      } else {
        ElMessage.error(res.msg)
      }
    } catch (e) {
      ElMessage.error(e?.msg || 'Error')
    } finally {
      myPasswordLoading.value = false
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

.no-permission {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
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

/* ══════════════════════════════════════════════════════════ */
/*  Collapsible Card — outer sections                       */
/* ══════════════════════════════════════════════════════════ */
.collapse-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  margin-bottom: 16px;
  overflow: hidden;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;

  &:hover {
    border-color: var(--el-border-color);
  }

  &.open {
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
    border-color: var(--el-color-primary-light-7);
  }
}

.collapse-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s ease;

  &:hover {
    background: var(--el-fill-color-lighter);
  }
}

.collapse-card-title {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  flex: 1;

  h3 {
    font-size: 15px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0;
    line-height: 1.3;
  }
}

.collapse-card-subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
  display: block;
  margin-top: 2px;
  max-width: 420px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.collapse-card-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &.user-icon {
    background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
    color: #4f46e5;
  }

  &.ai-icon {
    background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
    color: #2563eb;
  }

  &.mail-icon {
    background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%);
    color: #db2777;
  }

  &.telegram-icon {
    background: linear-gradient(135deg, #dbeafe 0%, #93c5fd 100%);
    color: #2563eb;
  }

  &.notification-icon {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    color: #d97706;
  }

  &.db-icon {
    background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
    color: #059669;
  }

  &.kb-icon {
    background: linear-gradient(135deg, #ede9fe 0%, #c4b5fd 100%);
    color: #7c3aed;
  }

  &.kbs-icon {
    background: linear-gradient(135deg, #dbeafe 0%, #93c5fd 100%);
    color: #2563eb;
  }
}

.collapse-card-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.collapse-chevron {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), background 0.2s ease;
  color: var(--el-text-color-secondary);

  &:hover {
    background: var(--el-fill-color-light);
  }

  &.rotated {
    transform: rotate(180deg);
  }

  &.small {
    width: 22px;
    height: 22px;
  }
}

.collapse-card-body {
  padding: 0 24px 24px 24px;
}

/* Transition for collapsible body */
.collapse-body-enter-active,
.collapse-body-leave-active {
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  max-height: 3000px;
  opacity: 1;
  overflow: hidden;
}

.collapse-body-enter-from,
.collapse-body-leave-to {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}

/* ══════════════════════════════════════════════════════════ */
/*  Inner Card — sub-sections inside a main section         */
/* ══════════════════════════════════════════════════════════ */
.inner-card {
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-extra-light);
  border-radius: 10px;
  margin-bottom: 12px;
  overflow: hidden;
  transition: border-color 0.2s ease;

  &:last-of-type {
    margin-bottom: 16px;
  }
}

.inner-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s ease;

  &:hover {
    background: var(--el-fill-color-light);
  }

  span {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
}

.inner-card-body {
  padding: 4px 16px 16px 16px;
}

/* ══════════════════════════════════════════════════════════ */
/*  Form elements                                            */
/* ══════════════════════════════════════════════════════════ */
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

.guide-steps {
  padding: 4px 0;

  p {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    margin: 6px 0;
    line-height: 1.6;
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

/* ══════════════════════════════════════════════════════════ */
/*  Notification Tabs                                        */
/* ══════════════════════════════════════════════════════════ */
.notification-tabs {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;

  :deep(.el-tabs__header) {
    background: var(--el-fill-color-extra-light);
    border-radius: 8px;
    margin-bottom: 16px;
    border: 1px solid var(--el-border-color-extra-light);
  }

  :deep(.el-tabs__content) {
    padding: 0;
  }

  :deep(.el-tabs__item) {
    font-size: 13px;
    height: 40px;
    line-height: 40px;
  }

  :deep(.el-tabs__item.is-active) {
    font-weight: 600;
  }
}

.tab-label-custom {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* ══════════════════════════════════════════════════════════ */
/*  Channel cards                                            */
/* ══════════════════════════════════════════════════════════ */
.channel-card {
  border: 1px solid var(--el-border-color-extra-light);
  border-radius: 8px;
  margin-bottom: 10px;
  overflow: hidden;
  background: var(--el-bg-color);
  transition: border-color 0.2s ease;

  &:hover {
    border-color: var(--el-border-color-light);
  }

  .channel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: var(--el-fill-color-extra-light);

    .channel-name {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      font-weight: 500;
      color: var(--el-text-color-primary);

      svg {
        flex-shrink: 0;
      }
    }
  }

  .channel-body {
    padding: 14px;
  }
}

.form-group-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 16px;
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
