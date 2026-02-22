import { jsErrorCollection } from 'js-error-collection'
import pack from '../../package.json'
import settings from '@/settings'
import bus from '@/utils/bus'
import axiosReq from 'axios'
const reqUrl = '/integration-front/errorCollection/insert'
let repeatErrorLogJudge = ''

const errorLogReq = (errLog) => {
  axiosReq({
    url: import.meta.env.VITE_APP_BASE_URL + reqUrl,
    data: {
      pageUrl: window.location.href,
      errorLog: errLog,
      browserType: navigator.userAgent,
      version: pack.version
    },
    method: 'post'
  }).then(() => {
    bus.emit('reloadErrorPage', {})
  })
}

export const useErrorLog = () => {
  if (settings.errorLog?.includes(import.meta.env.VITE_APP_ENV)) {
    jsErrorCollection({ runtimeError: true, rejectError: true, consoleError: true }, (errLog) => {
      if (!repeatErrorLogJudge || !errLog.includes(repeatErrorLogJudge)) {
        errorLogReq(errLog)
        repeatErrorLogJudge = errLog.slice(0, 20)
      }
    })
  }
}
