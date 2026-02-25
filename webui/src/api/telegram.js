import axiosReq from '@/utils/axios-req'

/**
 * Telegram alert ayarlarını getir
 */
export const getTelegramAlertConfigReq = () => {
  return axiosReq({
    url: 'telegram/config',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * Telegram alert ayarlarını kaydet
 */
export const saveTelegramAlertConfigReq = (data) => {
  return axiosReq({
    url: 'telegram/config',
    data,
    method: 'post',
  })
}

/**
 * Telegram bağlantı testi — test mesajı gönder
 */
export const testTelegramAlertReq = () => {
  return axiosReq({
    url: 'telegram/test',
    method: 'post',
    timeout: 20000,
  })
}

/**
 * Bot'a gelen mesajlardan chat ID bul
 */
export const telegramGetChatIdReq = () => {
  return axiosReq({
    url: 'telegram/chatid',
    method: 'get',
    reqLoading: false,
  })
}
