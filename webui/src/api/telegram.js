import axiosReq from '@/utils/axios-req'

export function getTelegramConfigReq() {
  return axiosReq({
    url: 'telegram/config',
    method: 'get'
  })
}

export function saveTelegramConfigReq(data) {
  return axiosReq({
    url: 'telegram/config',
    method: 'post',
    data
  })
}

export function testTelegramReq() {
  return axiosReq({
    url: 'telegram/test',
    method: 'post'
  })
}
