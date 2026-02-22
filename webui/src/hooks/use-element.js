import { reactive, ref, toRefs } from 'vue'
import { ElLoading, ElMessage, ElMessageBox, ElNotification } from 'element-plus'
export const useElement = () => {
  const upZeroInt = (rule, value, callback, msg) => {
    if (!value) {
      callback(new Error(`${msg} cannot be empty`))
    }
    if (/^\+?[1-9]\d*$/.test(value)) {
      callback()
    } else {
      callback(new Error(`${msg} is invalid`))
    }
  }

  const zeroInt = (rule, value, callback, msg) => {
    if (!value) {
      callback(new Error(`${msg} cannot be empty`))
    }
    if (/^\+?[0-9]\d*$/.test(value)) {
      callback()
    } else {
      callback(new Error(`${msg} is invalid`))
    }
  }

  const money = (rule, value, callback, msg) => {
    if (!value) {
      callback(new Error(`${msg} cannot be empty`))
    }
    if (/((^[1-9]\d*)|^0)(\.\d{0,2}){0,1}$/.test(value)) {
      callback()
    } else {
      callback(new Error(`${msg} is invalid`))
    }
  }

  const phone = (rule, value, callback, msg) => {
    if (!value) {
      callback(new Error(`${msg} cannot be empty`))
    }
    if (/^0?1[0-9]{10}$/.test(value)) {
      callback()
    } else {
      callback(new Error(`${msg} is invalid`))
    }
  }

  const email = (rule, value, callback, msg) => {
    if (!value) {
      callback(new Error(`${msg} cannot be empty`))
    }
    if (/(^([a-zA-Z]|[0-9])(\w|-)+@[a-zA-Z0-9]+\.([a-zA-Z]{2,4}))$/.test(value)) {
      callback()
    } else {
      callback(new Error(`${msg}`))
    }
  }
  const state = reactive({
    /* table*/
    tableData: [],
    rowDeleteIdArr: [],
    loadingId: null,
    formModel: {},
    subForm: {},
    searchForm: {},
    formRules: {
      isNull: (msg) => [{ required: false, message: `${msg}`, trigger: 'blur' }],
      isNotNull: (msg) => [{ required: true, message: `${msg}`, trigger: 'blur' }],
      upZeroInt: (msg) => [
        { required: true, validator: (rule, value, callback) => upZeroInt(rule, value, callback, msg), trigger: 'blur' }
      ],
      zeroInt: (msg) => [
        { required: true, validator: (rule, value, callback) => zeroInt(rule, value, callback, msg), trigger: 'blur' }
      ],
      money: (msg) => [
        { required: true, validator: (rule, value, callback) => money(rule, value, callback, msg), trigger: 'blur' }
      ],
      phone: (msg) => [
        { required: true, validator: (rule, value, callback) => phone(rule, value, callback, msg), trigger: 'blur' }
      ],
      email: (msg) => [
        { required: true, validator: (rule, value, callback) => email(rule, value, callback, msg), trigger: 'blur' }
      ]
    },
    datePickerOptions: {
      disabledDate: (time) => {
        return time.getTime() < Date.now() - 86400000
      }
    },
    startEndArr: [],
    dialogTitle: 'Add',
    detailDialog: false,
    isDialogEdit: false,
    dialogVisible: false,
    tableLoading: false,
    treeData: [],
    defaultProps: {
      children: 'children',
      label: 'label'
    }
  })
  return {
    ...toRefs(state)
  }
}

/*
 * */
export const elMessage = (message, type) => {
  ElMessage({
    showClose: true,
    message: message || 'Success',
    type: type || 'success',
    center: false
  })
}
/*
 * */
let loadingId = null
export const elLoading = (msg) => {
  loadingId = ElLoading.service({
    lock: true,
    text: msg || 'Please wait',
    // spinner: 'el-icon-loading',
    background: 'rgba(0, 0, 0, 0.1)'
  })
}
export const closeElLoading = () => {
  loadingId.close()
}
/*
 * */
export const elNotify = (message, type, title, duration) => {
  ElNotification({
    title: title || 'Notice',
    type: type || 'success',
    message: message || 'Please provide a message',
    position: 'top-right',
    duration: duration || 2500,
    offset: 40
  })
}
/*
  Confirm dialog (no cancel button)
* return Promise
* */
export const elConfirmNoCancelBtn = (title, message) => {
  return ElMessageBox({
    message: message || 'Are you sure you want to delete?',
    title: title || 'Confirm',
    confirmButtonText: 'OK',
    cancelButtonText: 'Cancel',
    showCancelButton: false,
    type: 'warning'
  })
}
/*
 * return Promise
 * */
export const elConfirm = (title, message) => {
  return ElMessageBox({
    message: message || 'Are you sure you want to delete?',
    title: title || 'Confirm',
    confirmButtonText: 'OK',
    cancelButtonText: 'Cancel',
    type: 'warning'
  })
}

const cascaderKey = ref()
export const casHandleChange = () => {
  cascaderKey.value += cascaderKey.value
}
