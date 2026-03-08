<template>
  <div class="dashboard-wrap">

    <!-- ── Header ── -->
    <div class="dash-header">
      <div class="dash-header-left">
        <div class="dash-logo-area">
          <div class="dash-logo-icon">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/>
              <path d="M2 17l10 5 10-5"/>
              <path d="M2 12l10 5 10-5"/>
            </svg>
          </div>
          <div>
            <div class="dash-title">{{ $t('dashboardTitle') }}</div>
            <div class="dash-subtitle">{{ $t('dashboardSubtitle') }}</div>
          </div>
        </div>
      </div>
      <div class="dash-header-right">
        <el-select v-model="periodHours" size="small" style="width: 110px;" @change="loadAll">
          <el-option :value="6"  label="6h" />
          <el-option :value="24" label="24h" />
          <el-option :value="48" label="48h" />
          <el-option :value="168" label="7d" />
        </el-select>
        <el-button :loading="loading" size="small" type="primary" @click="loadAll" :icon="Refresh" circle />
        <span class="dash-time">{{ lastRefreshed }}</span>
      </div>
    </div>

    <!-- ── Platform Score + KPI Row ── -->
    <div class="score-kpi-row">

      <!-- Platform Health Score -->
      <div class="score-card" :class="overviewData.platform_status || 'healthy'">
        <div class="score-ring-wrap">
          <svg class="score-ring" viewBox="0 0 120 120">
            <circle class="ring-bg" cx="60" cy="60" r="52" />
            <circle class="ring-fill" cx="60" cy="60" r="52"
              :style="{ strokeDashoffset: ringOffset }" />
          </svg>
          <div class="score-value">{{ Math.round(overviewData.platform_score || 0) }}</div>
        </div>
        <div class="score-label">{{ $t('dashboardPlatformScore') }}</div>
        <div class="score-status" :class="overviewData.platform_status || 'healthy'">
          {{ $t('dashboard' + capitalize(overviewData.platform_status || 'healthy')) }}
        </div>
      </div>

      <!-- KPI Cards -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-icon services"><el-icon :size="20"><Monitor /></el-icon></div>
          <div class="kpi-body">
            <div class="kpi-value">{{ kpi.services_online ?? '—' }}<span class="kpi-sub">/{{ kpi.services_total ?? 0 }}</span></div>
            <div class="kpi-label">{{ $t('dashboardServicesOnline') }}</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon targets"><el-icon :size="20"><Coin /></el-icon></div>
          <div class="kpi-body">
            <div class="kpi-value">{{ kpi.targets_total ?? '—' }}<span class="kpi-sub" v-if="kpi.targets_ok != null"> ({{ kpi.targets_ok }} ok)</span></div>
            <div class="kpi-label">{{ $t('dashboardTargets') }}</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon diagnoses"><el-icon :size="20"><DataAnalysis /></el-icon></div>
          <div class="kpi-body">
            <div class="kpi-value">{{ kpi.diagnoses_total ?? '—' }}</div>
            <div class="kpi-label">{{ $t('dashboardDiagnoses') }} ({{ periodHours }}h)</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon rate"><el-icon :size="20"><TrendCharts /></el-icon></div>
          <div class="kpi-body">
            <div class="kpi-value">{{ kpi.diagnoses_success_rate != null ? kpi.diagnoses_success_rate + '%' : '—' }}</div>
            <div class="kpi-label">{{ $t('dashboardSuccessRate') }}</div>
          </div>
        </div>
        <div class="kpi-card" :class="{ 'alert-pulse': (kpi.critical_alerts || 0) > 0 }">
          <div class="kpi-icon critical"><el-icon :size="20"><WarningFilled /></el-icon></div>
          <div class="kpi-body">
            <div class="kpi-value">{{ kpi.critical_alerts ?? 0 }}</div>
            <div class="kpi-label">{{ $t('dashboardCriticalAlerts') }}</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon warning"><el-icon :size="20"><Bell /></el-icon></div>
          <div class="kpi-body">
            <div class="kpi-value">{{ kpi.warning_alerts ?? 0 }}</div>
            <div class="kpi-label">{{ $t('dashboardWarningAlerts') }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Main Grid: Services + Pipeline ── -->
    <div class="main-grid">

      <!-- Platform Services -->
      <div class="panel">
        <div class="panel-header">
          <el-icon :size="16"><Monitor /></el-icon>
          <span>{{ $t('dashboardServices') }}</span>
        </div>
        <div class="services-list">
          <div v-for="svc in services" :key="svc.name" class="svc-row" :class="svc.status">
            <div class="svc-dot" :class="svc.status" />
            <div class="svc-info">
              <span class="svc-name">{{ svcLabel(svc.name) }}</span>
            </div>
            <el-tag size="small" :type="statusTagType(svc.status)" effect="light">
              {{ $t('svc_' + svc.status) }}
            </el-tag>
          </div>
          <template v-if="loading && services.length === 0">
            <div v-for="i in 6" :key="i" class="svc-row skeleton" />
          </template>
        </div>
      </div>

      <!-- Pipeline Status -->
      <div class="panel">
        <div class="panel-header">
          <el-icon :size="16"><Connection /></el-icon>
          <span>{{ $t('dashboardPipeline') }}</span>
          <el-tag v-if="pipelineOverall" size="small" :type="pipelineOverall === 'healthy' ? 'success' : (pipelineOverall === 'warning' ? 'warning' : 'danger')" effect="dark" style="margin-left: auto;">
            {{ $t('pipeline_' + pipelineOverall) }}
          </el-tag>
        </div>
        <div class="pipeline-flow">
          <div v-for="(step, idx) in pipelineSteps" :key="step.step" class="pipe-item">
            <div class="pipe-node" :class="step.status">
              <span class="pipe-node-dot" />
            </div>
            <div class="pipe-info">
              <div class="pipe-name">{{ step.step }}</div>
              <div class="pipe-detail">{{ step.detail }}</div>
            </div>
            <div v-if="idx < pipelineSteps.length - 1" class="pipe-connector" :class="pipelineSteps[idx+1]?.status" />
          </div>
        </div>
      </div>

      <!-- Infrastructure Targets -->
      <div class="panel">
        <div class="panel-header">
          <el-icon :size="16"><Coin /></el-icon>
          <span>{{ $t('dashboardInfrastructure') }}</span>
          <div class="db-type-badges" style="margin-left: auto;">
            <el-tag v-for="(count, dbType) in infra.db_types" :key="dbType" size="small" type="info" effect="plain">
              {{ dbType.toUpperCase() }} ({{ count }})
            </el-tag>
          </div>
        </div>
        <div class="targets-list">
          <div v-for="target in infra.targets" :key="target.name" class="target-row">
            <div class="target-icon" :class="target.db_type">
              <span>{{ dbIcon(target.db_type) }}</span>
            </div>
            <div class="target-info">
              <div class="target-name">{{ target.name }}</div>
              <div class="target-host">{{ target.host }}</div>
            </div>
            <el-tag size="small" effect="light" :type="target.status === 'ok' ? 'success' : 'info'">
              {{ target.status === 'ok' ? $t('target_ok') : $t('target_unknown') }}
            </el-tag>
            <el-tag v-if="target.ssh" size="small" type="warning" effect="plain">SSH</el-tag>
          </div>
          <el-empty v-if="!loading && (!infra.targets || infra.targets.length === 0)" :description="$t('dashboardNoData')" :image-size="60" />
        </div>
      </div>

      <!-- Diagnosis Analytics -->
      <div class="panel">
        <div class="panel-header">
          <el-icon :size="16"><DataAnalysis /></el-icon>
          <span>{{ $t('dashboardDiagnosisStats') }}</span>
        </div>
        <div class="diag-stats">
          <div class="diag-bar-row">
            <span class="diag-bar-label">{{ $t('dashboardDone') }}</span>
            <div class="diag-bar-track">
              <div class="diag-bar-fill success" :style="{ width: successBarWidth }" />
            </div>
            <span class="diag-bar-val">{{ diagStats.success || 0 }}</span>
          </div>
          <div class="diag-bar-row">
            <span class="diag-bar-label">{{ $t('dashboardFailed') }}</span>
            <div class="diag-bar-track">
              <div class="diag-bar-fill danger" :style="{ width: failedBarWidth }" />
            </div>
            <span class="diag-bar-val">{{ diagStats.failed || 0 }}</span>
          </div>
          <div class="severity-chips">
            <div class="sev-chip critical">
              <span class="sev-dot" />
              <span>CRITICAL</span>
              <strong>{{ diagStats.severity_counts?.CRITICAL ?? 0 }}</strong>
            </div>
            <div class="sev-chip warning">
              <span class="sev-dot" />
              <span>WARNING</span>
              <strong>{{ diagStats.severity_counts?.WARNING ?? 0 }}</strong>
            </div>
            <div class="sev-chip info">
              <span class="sev-dot" />
              <span>INFO</span>
              <strong>{{ diagStats.severity_counts?.INFO ?? 0 }}</strong>
            </div>
          </div>
          <!-- Models Used -->
          <div v-if="diagStats.models_used && Object.keys(diagStats.models_used).length > 0" class="models-used">
            <div class="models-title">AI Models</div>
            <div class="models-list">
              <el-tag v-for="(count, model) in diagStats.models_used" :key="model" size="small" type="" effect="plain">
                {{ model }} ({{ count }})
              </el-tag>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- ── Recent Activity Timeline ── -->
    <div class="panel" style="margin-top: 16px;">
      <div class="panel-header">
        <el-icon :size="16"><Clock /></el-icon>
        <span>{{ $t('dashboardActivity') }}</span>
      </div>
      <div class="activity-timeline">
        <el-empty v-if="!loading && recentActivity.length === 0" :description="$t('dashboardNoData')" :image-size="60" />
        <div v-for="item in recentActivity" :key="item.file" class="activity-item">
          <div class="activity-time">
            <div class="activity-date">{{ formatDate(item.time) }}</div>
            <div class="activity-hour">{{ formatHour(item.time) }}</div>
          </div>
          <div class="activity-line">
            <div class="activity-dot" :class="item.has_result ? 'success' : 'failed'" />
            <div class="activity-connector" v-if="recentActivity.indexOf(item) < recentActivity.length - 1" />
          </div>
          <div class="activity-content">
            <div class="activity-title">
              <el-tag size="small" :type="item.has_result ? 'success' : 'danger'" effect="light">
                {{ item.has_result ? $t('dashboardDone') : $t('dashboardFailed') }}
              </el-tag>
              <el-tag size="small" type="info" effect="plain">{{ item.model }}</el-tag>
              <span v-if="item.alert_count" class="activity-alert-count">{{ item.alert_count }} {{ $t('dashboardAlerts').toLowerCase() }}</span>
            </div>
            <div v-if="item.alert_names && item.alert_names.length > 0" class="activity-alerts">
              {{ item.alert_names.join(', ') }}
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  Refresh, Monitor, Connection, Coin, DataAnalysis,
  TrendCharts, WarningFilled, Bell, Clock, CircleCheck
} from '@element-plus/icons-vue'
import { getDashboardOverview, getDashboardPipelineStatus } from '@/api/dashboard'

// ── State ────────────────────────────────────────────────
const loading = ref(false)
const lastRefreshed = ref('—')
const periodHours = ref(24)

const overviewData = ref({})
const pipelineSteps = ref([])
const pipelineOverall = ref('')

// ── Computed ─────────────────────────────────────────────
const kpi = computed(() => overviewData.value.kpi || {})
const services = computed(() => overviewData.value.services || [])
const infra = computed(() => overviewData.value.infrastructure || {})
const diagStats = computed(() => overviewData.value.diagnosis || {})
const recentActivity = computed(() => overviewData.value.recent_activity || [])

const ringOffset = computed(() => {
  const score = overviewData.value.platform_score || 0
  const circumference = 2 * Math.PI * 52 // r=52
  return circumference - (score / 100) * circumference
})

const successBarWidth = computed(() => {
  const total = (diagStats.value.success || 0) + (diagStats.value.failed || 0)
  if (total === 0) return '0%'
  return Math.round((diagStats.value.success / total) * 100) + '%'
})

const failedBarWidth = computed(() => {
  const total = (diagStats.value.success || 0) + (diagStats.value.failed || 0)
  if (total === 0) return '0%'
  return Math.round((diagStats.value.failed / total) * 100) + '%'
})

// ── Helpers ──────────────────────────────────────────────
const capitalize = (s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : ''

const svcLabel = (name) => {
  const map = {
    api: 'API Server',
    litellm: 'AI Gateway (LiteLLM)',
    prometheus: 'Prometheus',
    alertmanager: 'Alertmanager',
    notify_worker: 'Notify Worker',
    dba_agent: 'DBA Agent',
    redis: 'Redis Cache',
  }
  return map[name] || name
}

const statusTagType = (status) => {
  if (status === 'online') return 'success'
  if (status === 'offline') return 'danger'
  if (status === 'degraded') return 'warning'
  return 'info'
}

const dbIcon = (type) => {
  const map = { postgresql: 'PG', mysql: 'MY', mariadb: 'MA', mssql: 'MS', oracle: 'OR' }
  return map[type] || type?.substring(0, 2).toUpperCase() || '??'
}

const formatDate = (timeStr) => {
  if (!timeStr) return ''
  return timeStr.split(' ')[0]?.substring(5) || '' // MM-DD
}

const formatHour = (timeStr) => {
  if (!timeStr) return ''
  return timeStr.split(' ')[1]?.substring(0, 5) || '' // HH:MM
}

// ── Data Loading ─────────────────────────────────────────
const loadOverview = async () => {
  try {
    const res = await getDashboardOverview(periodHours.value)
    if (res.data) overviewData.value = res.data
  } catch (e) {
    console.error('overview error', e)
  }
}

const loadPipeline = async () => {
  try {
    const res = await getDashboardPipelineStatus()
    if (res.data?.steps) pipelineSteps.value = res.data.steps
    if (res.data?.overall) pipelineOverall.value = res.data.overall
  } catch (e) {
    console.error('pipeline error', e)
  }
}

const loadAll = async () => {
  loading.value = true
  await Promise.all([loadOverview(), loadPipeline()])
  loading.value = false
  lastRefreshed.value = new Date().toLocaleTimeString()
}

// ── Auto-refresh (60s) ──────────────────────────────────
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
/* ── Layout ── */
.dashboard-wrap {
  height: calc(100vh - 30px);
  overflow-y: auto;
  padding: 20px 24px;
  box-sizing: border-box;
  background: var(--el-bg-color-page);
}

/* ── Header ── */
.dash-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.dash-header-left { display: flex; align-items: center; gap: 12px; }
.dash-header-right { display: flex; align-items: center; gap: 10px; }
.dash-logo-area { display: flex; align-items: center; gap: 12px; }
.dash-logo-icon {
  width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}
.dash-title { font-size: 20px; font-weight: 700; color: var(--el-text-color-primary); }
.dash-subtitle { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 1px; }
.dash-time { font-size: 11px; color: var(--el-text-color-placeholder); }

/* ── Score + KPI Row ── */
.score-kpi-row {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
  align-items: stretch;
}

/* Score Card */
.score-card {
  flex-shrink: 0;
  width: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px 16px;
  border-radius: 16px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  gap: 8px;
}
.score-card.healthy { border-color: #67c23a30; background: linear-gradient(135deg, var(--el-bg-color) 0%, #67c23a08 100%); }
.score-card.warning { border-color: #e6a23c30; background: linear-gradient(135deg, var(--el-bg-color) 0%, #e6a23c08 100%); }
.score-card.critical { border-color: #f56c6c30; background: linear-gradient(135deg, var(--el-bg-color) 0%, #f56c6c08 100%); }

.score-ring-wrap { position: relative; width: 100px; height: 100px; }
.score-ring { width: 100%; height: 100%; transform: rotate(-90deg); }
.ring-bg { fill: none; stroke: var(--el-border-color-lighter); stroke-width: 8; }
.ring-fill {
  fill: none; stroke-width: 8; stroke-linecap: round;
  stroke-dasharray: 326.73; /* 2*PI*52 */
  transition: stroke-dashoffset 1s ease;
}
.score-card.healthy .ring-fill { stroke: #67c23a; }
.score-card.warning .ring-fill { stroke: #e6a23c; }
.score-card.critical .ring-fill { stroke: #f56c6c; }

.score-value {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  font-size: 28px; font-weight: 800;
  color: var(--el-text-color-primary);
}
.score-label { font-size: 12px; color: var(--el-text-color-secondary); font-weight: 500; }
.score-status { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
.score-status.healthy { color: #67c23a; }
.score-status.warning { color: #e6a23c; }
.score-status.critical { color: #f56c6c; }

/* KPI Grid */
.kpi-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.kpi-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  transition: transform 0.15s, box-shadow 0.15s;
}
.kpi-card:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,.06); }
.kpi-card.alert-pulse { animation: alertPulse 2s ease-in-out infinite; }

.kpi-icon {
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 10px; flex-shrink: 0;
}
.kpi-icon.services  { background: #ecf5ff; color: #409eff; }
.kpi-icon.targets   { background: #f0f9eb; color: #67c23a; }
.kpi-icon.diagnoses { background: #fdf6ec; color: #e6a23c; }
.kpi-icon.rate      { background: #ecf5ff; color: #409eff; }
.kpi-icon.critical  { background: #fef0f0; color: #f56c6c; }
.kpi-icon.warning   { background: #fdf6ec; color: #e6a23c; }

.kpi-body { min-width: 0; }
.kpi-value { font-size: 22px; font-weight: 700; color: var(--el-text-color-primary); line-height: 1.2; }
.kpi-sub { font-size: 13px; font-weight: 400; color: var(--el-text-color-secondary); }
.kpi-label { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 2px; white-space: nowrap; }

/* ── Main Grid (2x2) ── */
.main-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

/* Panel */
.panel {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  overflow: hidden;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

/* ── Services List ── */
.services-list { padding: 8px 12px; }
.svc-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 6px;
  border-radius: 8px;
  transition: background 0.15s;
}
.svc-row:hover { background: var(--el-fill-color); }
.svc-row.skeleton { height: 38px; background: var(--el-fill-color); animation: pulse 1.4s ease-in-out infinite; border-radius: 8px; margin-bottom: 4px; }

.svc-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.svc-dot.online  { background: #67c23a; box-shadow: 0 0 6px #67c23a88; }
.svc-dot.offline { background: #f56c6c; }
.svc-dot.degraded{ background: #e6a23c; }
.svc-dot.timeout { background: #909399; }

.svc-info { flex: 1; min-width: 0; }
.svc-name { font-size: 13px; font-weight: 500; }

/* ── Pipeline Flow ── */
.pipeline-flow { padding: 16px 18px; }
.pipe-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  position: relative;
  padding-bottom: 4px;
}
.pipe-node {
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%; flex-shrink: 0;
  border: 2px solid var(--el-border-color);
  background: var(--el-bg-color);
  z-index: 1;
}
.pipe-node.ok { border-color: #67c23a; }
.pipe-node.offline { border-color: #f56c6c; }
.pipe-node.degraded { border-color: #e6a23c; }
.pipe-node.warning { border-color: #e6a23c; }

.pipe-node-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--el-border-color);
}
.pipe-node.ok .pipe-node-dot { background: #67c23a; }
.pipe-node.offline .pipe-node-dot { background: #f56c6c; }
.pipe-node.degraded .pipe-node-dot { background: #e6a23c; }
.pipe-node.warning .pipe-node-dot { background: #e6a23c; }

.pipe-info { flex: 1; padding: 3px 0 12px; }
.pipe-name { font-size: 13px; font-weight: 600; }
.pipe-detail { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 1px; }

.pipe-connector {
  position: absolute;
  left: 13px; top: 28px; bottom: -4px;
  width: 2px;
  background: var(--el-border-color-lighter);
}
.pipe-connector.ok { background: #67c23a44; }
.pipe-connector.offline { background: #f56c6c44; }

/* ── Infrastructure Targets ── */
.targets-list { padding: 8px 12px; }
.target-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 6px;
  border-radius: 8px;
  transition: background 0.15s;
}
.target-row:hover { background: var(--el-fill-color); }
.target-icon {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 8px; font-size: 11px; font-weight: 700;
  background: var(--el-fill-color); color: var(--el-text-color-secondary);
}
.target-icon.postgresql { background: #336791; color: white; }
.target-icon.mysql { background: #4479A1; color: white; }
.target-icon.mariadb { background: #003545; color: white; }
.target-icon.mssql { background: #CC2927; color: white; }
.target-icon.oracle { background: #F80000; color: white; }

.target-info { flex: 1; min-width: 0; }
.target-name { font-size: 13px; font-weight: 500; }
.target-host { font-size: 11px; color: var(--el-text-color-secondary); }

.db-type-badges { display: flex; gap: 4px; }

/* ── Diagnosis Stats ── */
.diag-stats { padding: 16px 18px; }
.diag-bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.diag-bar-label { font-size: 12px; width: 70px; color: var(--el-text-color-secondary); }
.diag-bar-track {
  flex: 1; height: 8px;
  border-radius: 4px;
  background: var(--el-fill-color);
  overflow: hidden;
}
.diag-bar-fill {
  height: 100%; border-radius: 4px;
  transition: width 0.6s ease;
}
.diag-bar-fill.success { background: #67c23a; }
.diag-bar-fill.danger { background: #f56c6c; }
.diag-bar-val { font-size: 13px; font-weight: 600; width: 30px; text-align: right; }

.severity-chips {
  display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap;
}
.sev-chip {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 20px;
  font-size: 11px; font-weight: 500;
}
.sev-chip .sev-dot { width: 6px; height: 6px; border-radius: 50%; }
.sev-chip.critical { background: #fef0f0; color: #c0392b; }
.sev-chip.critical .sev-dot { background: #f56c6c; }
.sev-chip.warning { background: #fdf6ec; color: #e67e22; }
.sev-chip.warning .sev-dot { background: #e6a23c; }
.sev-chip.info { background: #ecf5ff; color: #2980b9; }
.sev-chip.info .sev-dot { background: #409eff; }

.models-used { margin-top: 14px; }
.models-title { font-size: 11px; color: var(--el-text-color-secondary); margin-bottom: 6px; font-weight: 600; }
.models-list { display: flex; gap: 6px; flex-wrap: wrap; }

/* ── Activity Timeline ── */
.activity-timeline { padding: 16px 18px; }
.activity-item {
  display: flex;
  gap: 12px;
  min-height: 52px;
}
.activity-time {
  width: 60px; flex-shrink: 0; text-align: right;
  padding-top: 2px;
}
.activity-date { font-size: 11px; color: var(--el-text-color-secondary); }
.activity-hour { font-size: 12px; font-weight: 600; color: var(--el-text-color-primary); }

.activity-line {
  width: 20px; flex-shrink: 0;
  display: flex; flex-direction: column; align-items: center;
  position: relative;
}
.activity-dot {
  width: 10px; height: 10px; border-radius: 50%;
  margin-top: 5px; flex-shrink: 0; z-index: 1;
}
.activity-dot.success { background: #67c23a; box-shadow: 0 0 6px #67c23a88; }
.activity-dot.failed { background: #f56c6c; }
.activity-connector {
  flex: 1; width: 2px;
  background: var(--el-border-color-lighter);
  margin-top: 4px;
}

.activity-content {
  flex: 1; padding-bottom: 16px; min-width: 0;
}
.activity-title {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.activity-alert-count {
  font-size: 11px; color: var(--el-text-color-secondary);
}
.activity-alerts {
  font-size: 11px; color: var(--el-text-color-secondary);
  margin-top: 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ── Animations ── */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
@keyframes alertPulse {
  0%, 100% { border-color: var(--el-border-color-light); }
  50% { border-color: #f56c6c88; }
}

/* ── Responsive ── */
@media (max-width: 1100px) {
  .score-kpi-row { flex-direction: column; }
  .score-card { width: 100%; flex-direction: row; gap: 20px; padding: 16px 24px; }
  .score-ring-wrap { width: 70px; height: 70px; }
  .score-value { font-size: 20px; }
  .kpi-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 900px) {
  .main-grid { grid-template-columns: 1fr; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .kpi-grid { grid-template-columns: 1fr; }
  .dash-header { flex-direction: column; align-items: flex-start; gap: 10px; }
}
</style>
