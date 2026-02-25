import axiosReq from '@/utils/axios-req'

export function getMailConfigReq() {
  return axiosReq({
    url: 'mail/config',
    method: 'get'
  })
}

export function saveMailConfigReq(data) {
  return axiosReq({
    url: 'mail/config',
    method: 'post',
    data
  })
}

export function testMailReq() {
  return axiosReq({
    url: 'mail/test',
    method: 'post'
  })
}
