import axiosReq from '@/utils/axios-req'

/**
 * LiteLLM Proxy sağlık durumu
 */
export const litellmHealthReq = () => {
  return axiosReq({
    url: 'litellm/health',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * LiteLLM model listesi
 */
export const litellmModelsReq = () => {
  return axiosReq({
    url: 'litellm/models',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * Model ekle/güncelle
 */
export const litellmAddModelReq = (data) => {
  return axiosReq({
    url: 'litellm/models/add',
    data,
    method: 'post',
  })
}

/**
 * Model sil
 */
export const litellmRemoveModelReq = (data) => {
  return axiosReq({
    url: 'litellm/models/remove',
    data,
    method: 'post',
  })
}

/**
 * Model test et
 */
export const litellmTestModelReq = (data) => {
  return axiosReq({
    url: 'litellm/models/test',
    data,
    method: 'post',
    timeout: 120000,
  })
}

/**
 * DBA Agent sağlık durumu
 */
export const dbaAgentHealthReq = () => {
  return axiosReq({
    url: 'litellm/dba-agent/health',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * LiteLLM genel config
 */
export const litellmConfigReq = () => {
  return axiosReq({
    url: 'litellm/config',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * LiteLLM genel ayarları güncelle
 */
export const litellmUpdateSettingsReq = (data) => {
  return axiosReq({
    url: 'litellm/settings',
    data,
    method: 'post',
  })
}
