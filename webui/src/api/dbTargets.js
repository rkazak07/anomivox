import axiosReq from '@/utils/axios-req'

/**
 * Tüm DB bağlantılarını listele
 */
export const listDbTargetsReq = () => {
  return axiosReq({
    url: 'db-targets/list',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * Yeni DB bağlantısı ekle
 */
export const addDbTargetReq = (data) => {
  return axiosReq({
    url: 'db-targets/add',
    data,
    method: 'post',
  })
}

/**
 * DB bağlantısı güncelle
 */
export const updateDbTargetReq = (data) => {
  return axiosReq({
    url: 'db-targets/update',
    data,
    method: 'post',
  })
}

/**
 * DB bağlantısı sil
 */
export const deleteDbTargetReq = (data) => {
  return axiosReq({
    url: 'db-targets/delete',
    data,
    method: 'post',
  })
}

/**
 * DB bağlantısını test et
 */
export const testDbTargetReq = (data) => {
  return axiosReq({
    url: 'db-targets/test',
    data,
    method: 'post',
    timeout: 20000,
  })
}

/**
 * SSH bağlantısını test et
 */
export const testSshTargetReq = (data) => {
  return axiosReq({
    url: 'db-targets/test-ssh',
    data,
    method: 'post',
    timeout: 20000,
  })
}

/**
 * Primary DB bağlantısını ayarla
 */
export const setPrimaryDbTargetReq = (data) => {
  return axiosReq({
    url: 'db-targets/set-primary',
    data,
    method: 'post',
  })
}
