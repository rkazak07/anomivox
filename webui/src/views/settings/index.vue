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
  }
})

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
</style>
