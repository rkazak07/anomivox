<template>
  <div class="scheduler-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>{{ $t('schedulerTitle') }}</span>
          <el-button type="primary" @click="openCreate">
            + {{ $t('schedulerAddTask') }}
          </el-button>
        </div>
      </template>

      <el-table :data="tasks" v-loading="loading" border stripe>
        <el-table-column prop="name" :label="$t('schedulerTaskName')" min-width="140" />
        <el-table-column prop="task_type" :label="$t('schedulerTaskType')" width="140" />
        <el-table-column prop="db_target_name" :label="$t('schedulerDbTarget')" width="140" />
        <el-table-column prop="cron_expression" :label="$t('schedulerCron')" width="130" />
        <el-table-column prop="risk_level" :label="$t('schedulerRiskLevel')" width="100">
          <template #default="{ row }">
            <el-tag :type="riskTagType(row.risk_level)" size="small">{{ row.risk_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('schedulerActive')" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="toggleActive(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="last_run_at" :label="$t('schedulerLastRun')" width="155" />
        <el-table-column prop="last_run_status" :label="$t('schedulerLastStatus')" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.last_run_status"
              :type="row.last_run_status === 'success' ? 'success' : row.last_run_status === 'skipped' ? 'warning' : 'danger'"
              size="small">{{ row.last_run_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('operations')" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">{{ $t('edit') }}</el-button>
            <el-button size="small" type="success" @click="runNow(row)">{{ $t('schedulerRunNow') }}</el-button>
            <el-button size="small" type="danger" @click="deleteTask(row)">{{ $t('delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create / Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editMode ? $t('schedulerEditTask') : $t('schedulerAddTask')"
      width="560px" destroy-on-close>
      <el-form :model="form" label-width="160px" ref="formRef">
        <el-form-item :label="$t('schedulerTaskName')" prop="name"
          :rules="[{ required: true, message: $t('schedulerTaskName') }]">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item :label="$t('schedulerTaskType')" prop="task_type"
          :rules="[{ required: true }]">
          <el-select v-model="form.task_type" style="width:100%">
            <el-option v-for="t in taskTypes" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('schedulerDbTarget')" prop="db_target_name"
          :rules="[{ required: true }]">
          <el-input v-model="form.db_target_name" placeholder="db_targets.json key" />
        </el-form-item>
        <el-form-item :label="$t('schedulerCron')" prop="cron_expression"
          :rules="[{ required: true }]">
          <el-input v-model="form.cron_expression" placeholder="0 2 * * 0" />
          <div class="form-hint">{{ $t('schedulerCronHelp') }}: <code>0 2 * * 0</code> = her Pazar 02:00</div>
        </el-form-item>
        <el-form-item :label="$t('schedulerRiskLevel')">
          <el-select v-model="form.risk_level" style="width:100%">
            <el-option label="LOW" value="LOW" />
            <el-option label="MEDIUM" value="MEDIUM" />
            <el-option label="HIGH" value="HIGH" />
          </el-select>
        </el-form-item>
        <template v-if="form.risk_level === 'HIGH'">
          <el-form-item :label="$t('schedulerWindowStart')">
            <el-input v-model="form.maintenance_window_start" placeholder="02:00" style="width:120px" />
          </el-form-item>
          <el-form-item :label="$t('schedulerWindowEnd')">
            <el-input v-model="form.maintenance_window_end" placeholder="04:00" style="width:120px" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ $t('cancel') }}</el-button>
        <el-button type="primary" @click="submitForm" :loading="saving">{{ $t('save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listScheduledTasksReq, createScheduledTaskReq,
  updateScheduledTaskReq, deleteScheduledTaskReq, runScheduledTaskNowReq,
} from '@/api/scheduler'

const { t: $t } = useI18n()

const tasks = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editMode = ref(false)
const formRef = ref(null)

const taskTypes = ['VACUUM', 'REINDEX', 'ANALYZE', 'LOG_ROTATE', 'STATS_COLLECT']

const emptyForm = () => ({
  id: null,
  name: '',
  task_type: 'VACUUM',
  db_target_name: '',
  cron_expression: '0 2 * * 0',
  risk_level: 'LOW',
  maintenance_window_start: '',
  maintenance_window_end: '',
})

const form = ref(emptyForm())

function riskTagType(level) {
  return level === 'HIGH' ? 'danger' : level === 'MEDIUM' ? 'warning' : 'success'
}

async function fetchTasks() {
  loading.value = true
  try {
    const res = await listScheduledTasksReq()
    tasks.value = res.data?.data || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = emptyForm()
  editMode.value = false
  dialogVisible.value = true
}

function openEdit(row) {
  form.value = { ...row }
  editMode.value = true
  dialogVisible.value = true
}

async function submitForm() {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editMode.value) {
      await updateScheduledTaskReq(form.value)
      ElMessage.success($t('schedulerUpdateSuccess'))
    } else {
      await createScheduledTaskReq(form.value)
      ElMessage.success($t('schedulerCreateSuccess'))
    }
    dialogVisible.value = false
    fetchTasks()
  } catch (e) {
    ElMessage.error(e?.msg || $t('error'))
  } finally {
    saving.value = false
  }
}

async function toggleActive(row) {
  try {
    await updateScheduledTaskReq({ id: row.id, is_active: row.is_active })
  } catch (e) {
    row.is_active = !row.is_active
    ElMessage.error(e?.msg || $t('error'))
  }
}

async function runNow(row) {
  try {
    await runScheduledTaskNowReq({ id: row.id })
    ElMessage.success($t('schedulerRunSuccess'))
  } catch (e) {
    ElMessage.error(e?.msg || $t('error'))
  }
}

async function deleteTask(row) {
  await ElMessageBox.confirm($t('schedulerDeleteConfirm'), $t('schedulerDeleteTask'), { type: 'warning' })
  try {
    await deleteScheduledTaskReq({ id: row.id })
    ElMessage.success($t('schedulerDeleteSuccess'))
    fetchTasks()
  } catch (e) {
    ElMessage.error(e?.msg || $t('error'))
  }
}

onMounted(fetchTasks)
</script>

<style scoped>
.scheduler-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.form-hint { font-size: 12px; color: #909399; margin-top: 4px; }
</style>
