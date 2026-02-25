import axiosReq from '@/utils/axios-req'

/**
 * OpenClaw Gateway sağlık durumu
 */
export const openclawHealthReq = () => {
  return axiosReq({
    url: 'openclaw/health',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * OpenClaw ayarlarını getir
 */
export const getOpenclawConfigReq = () => {
  return axiosReq({
    url: 'openclaw/config',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * OpenClaw ayarlarını kaydet
 */
export const saveOpenclawConfigReq = (data) => {
  return axiosReq({
    url: 'openclaw/config',
    data,
    method: 'post',
  })
}

/**
 * OpenClaw üzerinden mesaj gönder
 */
export const openclawSendReq = (data) => {
  return axiosReq({
    url: 'openclaw/send',
    data,
    method: 'post',
    timeout: 30000,
  })
}

/**
 * OpenClaw aktif kanalları listele
 */
export const openclawChannelsReq = () => {
  return axiosReq({
    url: 'openclaw/channels',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * OpenClaw Gateway restart
 */
export const openclawRestartReq = () => {
  return axiosReq({
    url: 'openclaw/restart',
    method: 'post',
  })
}
