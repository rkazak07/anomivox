<template>
  <div class="dashboard-wrap" style="height: calc(100vh - 30px); overflow-y: auto; padding: 20px 24px; box-sizing: border-box;">

    <!-- ── Başlık + Yenile ── -->
    <div class="rowBC" style="margin-bottom: 20px;">
      <div>
        <div style="font-size: 22px; font-weight: bold;">{{ $t('dashboardTitle') }}</div>
        <div style="font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px;">
          {{ $t('dashboardSubtitle') }} &nbsp;·&nbsp; {{ lastRefreshed }}
        </div>
      </div>
      <div class="rowSC" style="gap: 10px;">
        <el-select v-model="periodHours" style="width: 120px;" @change="loadAll">
          <el-option :value="6"  label="6 saat" />
          <el-option :value="24" label="24 saat" />
          <el-option :value="48" label="48 saat" />
          <el-option :value="168" label="7 gün" />
        </el-select>
        <el-button :loading="loading" type="primary" circle @click="loadAll">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- ── Bölüm 1: Servis Sağlık Kartları ── -->
    <div style="margin-bottom: 8px; font-size: 13px; font-weight: 600; color: var(--el-text-color-secondary); letter-spacing: 0.5px; text-transform: uppercase;">
      {{ $t('dashboardServices') }}
    </div>
    <div class="cards-grid" style="margin-bottom: 24px;">
      <div
        v-for="svc in services"
        :key="svc.name"
        class="svc-card"
        :class="svc.status"
      >
        <div class="svc-icon">
          <el-icon :size="22"><component :is="svcIcon(svc.name)" /></el-icon>
        </div>
        <div style="flex:1; min-width: 0;">
          <div class="svc-name">{{ svcLabel(svc.name) }}</div>
          <div class="svc-status-text" :class="svc.status">{{ $t('svc_' + svc.status) }}</div>
        </div>
        <div class="svc-badge" :class="svc.status">
          <span class="svc-dot" />
        </div>
      </div>
      <!-- Skeleton yükleme -->
      <template v-if="loadingHealth && services.length === 0">
        <div v-for="i in 6" :key="i" class="svc-card skeleton" />
      </template>
    </div>

    <!-- ── Bölüm 2: Özet Kartlar + Pipeline ── -->
    <div class="two-col" style="margin-bottom: 24px;">

      <!-- Sol: Teşhis Özet Kartları -->
      <div>
        <div style="margin-bottom: 8px; font-size: 13px; font-weight: 600; color: var(--el-text-color-secondary); letter-spacing: 0.5px; text-transform: uppercase;">
          {{ $t('dashboardDiagnosis') }} ({{ periodHours }}h)
        </div>
        <div class="stat-cards">
          <div class="stat-card">
            <div class="stat-value">{{ summary.total ?? '—' }}</div>
            <div class="stat-label">{{ $t('dashboardTotal') }}</div>
          </div>
          <div class="stat-card success">
            <div class="stat-value">{{ summary.success ?? '—' }}</div>
            <div class="stat-label">{{ $t('dashboardSuccess') }}</div>
          </div>
          <div class="stat-card danger">
            <div class="stat-value">{{ summary.failed ?? '—' }}</div>
            <div class="stat-label">{{ $t('dashboardFailed') }}</div>
          </div>
          <div class="stat-card info">
            <div class="stat-value">{{ summary.success_rate != null ? summary.success_rate + '%' : '—' }}</div>
            <div class="stat-label">{{ $t('dashboardSuccessRate') }}</div>
          </div>
        </div>

        <!-- Severity sayıları -->
        <div class="severity-row" style="margin-top: 12px;">
          <div class="severity-badge critical">
            <span>🔥 CRITICAL</span>
            <strong>{{ summary.severity_counts?.CRITICAL ?? 0 }}</strong>
          </div>
          <div class="severity-badge warning">
            <span>⚠️ WARNING</span>
            <strong>{{ summary.severity_counts?.WARNING ?? 0 }}</strong>
          </div>
          <div class="severity-badge info">
            <span>ℹ️ INFO</span>
            <strong>{{ summary.severity_counts?.INFO ?? 0 }}</strong>
          </div>
        </div>
      </div>

      <!-- Sağ: Pipeline Zinciri -->
      <div>
        <div style="margin-bottom: 8px; font-size: 13px; font-weight: 600; color: var(--el-text-color-secondary); letter-spacing: 0.5px; text-transform: uppercase;">
          {{ $t('dashboardPipeline') }}
        </div>
        <div class="pipeline-card">
          <div
            v-for="(step, idx) in pipelineSteps"
            :key="step.step"
            class="pipeline-step"
          >
            <div class="pipe-dot" :class="step.status" />
            <div style="flex:1; min-width: 0;">
              <div class="pipe-step-name">{{ step.step }}</div>
              <div class="pipe-detail">{{ step.detail }}</div>
            </div>
            <div class="pipe-status-label" :class="step.status">{{ $t('pipe_' + step.status) }}</div>
            <div v-if="idx < pipelineSteps.length - 1" class="pipe-arrow">↓</div>
          </div>
          <div v-if="pipelineSteps.length === 0 && loadingPipeline" class="columnCC" style="padding: 30px 0; color: var(--el-text-color-secondary);">
            <el-icon class="is-loading"><Loading /></el-icon>
          </div>
          <!-- Genel durum -->
          <div v-if="pipelineOverall" class="pipeline-overall" :class="pipelineOverall">
            <el-icon><component :is="overallIcon" /></el-icon>
            {{ $t('pipeline_' + pipelineOverall) }}
          </div>
        </div>
      </div>

    </div>

    <!-- ── Bölüm 3: Son Teşhisler Tablosu ── -->
    <div style="margin-bottom: 8px; font-size: 13px; font-weight: 600; color: var(--el-text-color-secondary); letter-spacing: 0.5px; text-transform: uppercase;">
      {{ $t('dashboardRecentDiagnoses') }}
    </div>
    <div class="recent-card">
      <el-empty v-if="!loadingDiag && recentList.length === 0" :description="$t('dashboardNoData')" style="padding: 20px 0;" />
      <table v-else class="recent-table">
        <thead>
          <tr>
            <th>{{ $t('dashboardTime') }}</th>
            <th>{{ $t('dashboardModel') }}</th>
            <th>{{ $t('dashboardAlerts') }}</th>
            <th>{{ $t('dashboardResult') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in recentList" :key="row.file">
            <td style="white-space: nowrap;">{{ row.time }}</td>
            <td><el-tag size="small" type="info">{{ row.model }}</el-tag></td>
            <td style="max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              {{ row.alert_names.join(', ') || '—' }}
            </td>
            <td>
              <el-tag size="small" :type="row.has_result ? 'success' : 'danger'">
                {{ row.has_result ? $t('dashboardDone') : $t('dashboardFailed') }}
              </el-tag>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Refresh, Loading, CircleCheck, WarningFilled, CircleClose, Connection, Monitor, DataBoard, Odometer, SetUp, ChatLineRound } from '@element-plus/icons-vue'
import { getDashboardHealth, getDashboardDiagnosisSummary, getDashboardPipelineStatus } from '@/api/dashboard'

// ── State ────────────────────────────────────────────────
const loading = ref(false)
const loadingHealth = ref(false)
const loadingDiag = ref(false)
const loadingPipeline = ref(false)
const lastRefreshed = ref('—')
const periodHours = ref(24)

const services = ref([])
const summary = ref({})
const pipelineSteps = ref([])
const pipelineOverall = ref('')

// ── Hesaplamalı ──────────────────────────────────────────
const recentList = computed(() => summary.value.last_diagnoses || [])
const overallIcon = computed(() => {
  if (pipelineOverall.value === 'healthy') return CircleCheck
  if (pipelineOverall.value === 'warning') return WarningFilled
  return CircleClose
})

// ── Servis ikon + etiket eşlemeleri ──────────────────────
const svcIcon = (name) => {
  const map = {
    api: SetUp,
    litellm: ChatLineRound,
    prometheus: DataBoard,
    alertmanager: WarningFilled,
    notify_worker: Connection,
    dba_agent: Odometer,
  }
  return map[name] || Monitor
}
const svcLabel = (name) => {
  const map = {
    api: 'API Server',
    litellm: 'AI Gateway',
    prometheus: 'Prometheus',
    alertmanager: 'Alertmanager',
    notify_worker: 'Notify Worker',
    dba_agent: 'DBA Agent',
  }
  return map[name] || name
}

// ── Veri yükleme ─────────────────────────────────────────
const loadHealth = async () => {
  loadingHealth.value = true
  try {
    const res = await getDashboardHealth()
    if (res.data?.services) services.value = res.data.services
  } catch (e) {
    console.error('health error', e)
  } finally {
    loadingHealth.value = false
  }
}

const loadDiagnosis = async () => {
  loadingDiag.value = true
  try {
    const res = await getDashboardDiagnosisSummary(periodHours.value)
    if (res.data) summary.value = res.data
  } catch (e) {
    console.error('diagnosis summary error', e)
  } finally {
    loadingDiag.value = false
  }
}

const loadPipeline = async () => {
  loadingPipeline.value = true
  try {
    const res = await getDashboardPipelineStatus()
    if (res.data?.steps) pipelineSteps.value = res.data.steps
    if (res.data?.overall) pipelineOverall.value = res.data.overall
  } catch (e) {
    console.error('pipeline error', e)
  } finally {
    loadingPipeline.value = false
  }
}

const loadAll = async () => {
  loading.value = true
  await Promise.all([loadHealth(), loadDiagnosis(), loadPipeline()])
  loading.value = false
  lastRefreshed.value = new Date().toLocaleTimeString()
}

// ── Otomatik yenileme (60 saniye) ────────────────────────
let refreshTimer = null
onMounted(() => {
  loadAll()
  refreshTimer = setInterval(loadAll, 60_000)
})
onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
/* ── Grid ── */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
@media (max-width: 900px) {
  .two-col { grid-template-columns: 1fr; }
}

/* ── Servis Kartı ── */
.svc-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  transition: box-shadow 0.2s;
}
.svc-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); }
.svc-card.online  { border-left: 4px solid #67c23a; }
.svc-card.offline { border-left: 4px solid #f56c6c; }
.svc-card.degraded{ border-left: 4px solid #e6a23c; }
.svc-card.timeout { border-left: 4px solid #909399; }
.svc-card.skeleton{ height: 66px; background: var(--el-fill-color); animation: pulse 1.4s ease-in-out infinite; }

.svc-icon { color: var(--el-text-color-secondary); flex-shrink: 0; }
.svc-name { font-weight: 600; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.svc-status-text { font-size: 12px; margin-top: 2px; }
.svc-status-text.online  { color: #67c23a; }
.svc-status-text.offline { color: #f56c6c; }
.svc-status-text.degraded{ color: #e6a23c; }
.svc-status-text.timeout { color: #909399; }

.svc-badge { display: flex; align-items: center; flex-shrink: 0; }
.svc-dot { width: 10px; height: 10px; border-radius: 50%; }
.svc-dot.online  { background: #67c23a; box-shadow: 0 0 6px #67c23a; }
.svc-dot.offline { background: #f56c6c; }
.svc-dot.degraded{ background: #e6a23c; }
.svc-dot.timeout { background: #909399; }

/* ── Stat Kartlar ── */
.stat-cards {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr;
  gap: 10px;
}
.stat-card {
  padding: 14px 10px;
  border-radius: 10px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  text-align: center;
}
.stat-card.success { border-top: 3px solid #67c23a; }
.stat-card.danger  { border-top: 3px solid #f56c6c; }
.stat-card.info    { border-top: 3px solid #409eff; }
.stat-value { font-size: 24px; font-weight: 700; line-height: 1.2; }
.stat-label { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 4px; }

/* ── Severity ── */
.severity-row { display: flex; gap: 8px; flex-wrap: wrap; }
.severity-badge {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 20px;
  font-size: 12px; font-weight: 500;
}
.severity-badge.critical { background: #fef0f0; color: #c0392b; }
.severity-badge.warning  { background: #fdf6ec; color: #e67e22; }
.severity-badge.info     { background: #ecf5ff; color: #2980b9; }

/* ── Pipeline ── */
.pipeline-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 16px;
  position: relative;
}
.pipeline-step {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 8px 0;
  position: relative;
}
.pipe-dot {
  width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0; margin-top: 3px;
}
.pipe-dot.ok      { background: #67c23a; box-shadow: 0 0 6px #67c23a; }
.pipe-dot.offline { background: #f56c6c; }
.pipe-dot.degraded{ background: #e6a23c; }
.pipe-dot.warning { background: #e6a23c; }

.pipe-step-name { font-weight: 600; font-size: 13px; }
.pipe-detail    { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 2px; }
.pipe-status-label { font-size: 11px; font-weight: 600; flex-shrink: 0; align-self: center; }
.pipe-status-label.ok      { color: #67c23a; }
.pipe-status-label.offline { color: #f56c6c; }
.pipe-status-label.degraded{ color: #e6a23c; }
.pipe-status-label.warning { color: #e6a23c; }

.pipe-arrow {
  position: absolute; left: 4px; bottom: -6px;
  font-size: 14px; color: var(--el-text-color-placeholder);
  z-index: 1;
}
.pipeline-overall {
  display: flex; align-items: center; gap: 6px;
  margin-top: 12px; padding: 8px 14px;
  border-radius: 8px; font-size: 13px; font-weight: 600;
}
.pipeline-overall.healthy { background: #f0f9eb; color: #67c23a; }
.pipeline-overall.warning { background: #fdf6ec; color: #e6a23c; }
.pipeline-overall.degraded{ background: #fef0f0; color: #f56c6c; }

/* ── Son Teşhisler ── */
.recent-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 0;
  overflow: hidden;
}
.recent-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}
.recent-table th, .recent-table td {
  padding: 10px 16px;
  text-align: left;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.recent-table th { font-weight: 600; background: var(--el-fill-color-light); }
.recent-table tr:last-child td { border-bottom: none; }
.recent-table tr:hover td { background: var(--el-fill-color); }

/* ── Genel ── */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
