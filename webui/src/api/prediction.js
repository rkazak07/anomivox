import axiosReq from '@/utils/axios-req'

export function getSupportedMetricsReq() {
  return axiosReq({ url: 'prediction/metrics', method: 'get' })
}

export function getForecastReq(data) {
  return axiosReq({ url: 'prediction/forecast', method: 'post', data })
}

export function runAlertCheckReq() {
  return axiosReq({ url: 'prediction/alerts/check', method: 'post', data: {} })
}
