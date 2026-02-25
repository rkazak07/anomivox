import axiosReq from '@/utils/axios-req'

export function getWhatsappConfigReq() {
  return axiosReq({
    url: 'whatsapp/config',
    method: 'get'
  })
}

export function saveWhatsappConfigReq(data) {
  return axiosReq({
    url: 'whatsapp/config',
    method: 'post',
    data
  })
}

export function testWhatsappReq() {
  return axiosReq({
    url: 'whatsapp/test',
    method: 'post'
  })
}
