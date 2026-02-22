import axios from 'axios'
import { ElLoading, ElMessage, ElMessageBox } from 'element-plus'
import { useBasicStore } from '@/store/basic'

const service = axios.create()
let loadingInstance = null // loading instance
let tempReqUrlSave = ''
let authorTipDoor = true

const noAuthDill = () => {
  authorTipDoor = false
  ElMessageBox.confirm('Please re-login', {
    confirmButtonText: 'Re-login',
    closeOnClickModal: false,
    showCancelButton: false,
    showClose: false,
    type: 'warning'
  }).then(() => {
    useBasicStore().resetStateAndToLogin()
    authorTipDoor = true
  })
}

service.interceptors.request.use(
  (req) => {
    const { token, axiosPromiseArr } = useBasicStore()
    req.cancelToken = new axios.CancelToken((cancel) => {
      tempReqUrlSave = req.url
      axiosPromiseArr.push({
        url: req.url,
        cancel
      })
    })

    if (token) req.headers['Authorization'] = token
    if ('get'.includes(req.method?.toLowerCase()) && !req.params) req.params = req.data

    //req loading
    // @ts-ignore
    if (req.reqLoading ?? true) {
      loadingInstance = ElLoading.service({
        lock: true,
        fullscreen: true,
        // spinner: 'CircleCheck',
        text: 'Please wait...',
        background: 'rgba(0, 0, 0, 0.1)'
      })
    }
    return req
  },
  (err) => {
    Promise.reject(err)
  }
)
service.interceptors.response.use(
  (res) => {

    useBasicStore().remotePromiseArrByReqUrl(tempReqUrlSave)
    if (loadingInstance) {
      loadingInstance && loadingInstance.close()
    }
    //download file
    if (res.data?.type?.includes("sheet")) {
      return res
    }

    if (res.config.type === 'chat') {
      return res
    }

    const { code, msg } = res.data
    const successCode = [0,200,20000]
    const noAuthCode = [401,403]
    if (successCode.includes(code)) {
      return res.data
    } else {
      if (authorTipDoor) {
        if (noAuthCode.includes(code)) {
          noAuthDill()
        } else {
          // @ts-ignore
          if (!res.config?.isNotTipErrorMsg) {
            ElMessage.error({
              message: msg,
              duration: 2 * 1000
            })
          } else {
            return res
          }
          return Promise.reject(msg)
        }
      }
    }
  },
  (err) => {
    useBasicStore().remotePromiseArrByReqUrl(tempReqUrlSave)
    if (loadingInstance) {
      loadingInstance && loadingInstance.close()
    }
    ElMessage.error({
      message: err,
      duration: 2 * 1000
    })
    return Promise.reject(err)
  }
)
export default function axiosReq(config) {
  return service({
    baseURL: import.meta.env.VITE_APP_BASE_URL,
    timeout: 8000,
    ...config
  })
}
