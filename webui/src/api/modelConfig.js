import axiosReq from '@/utils/axios-req'

export function getLlmConfigReq() {
  return axiosReq({
    url: 'config/llm',
    method: 'get'
  })
}

export function saveLlmConfigReq(data) {
  return axiosReq({
    url: 'config/llm',
    method: 'post',
    data
  })
}
