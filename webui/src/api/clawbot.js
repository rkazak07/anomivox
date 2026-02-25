import axiosReq from '@/utils/axios-req'

/**
 * ClawBot'a mesaj gönder
 * @param {string} message - Kullanıcı mesajı
 * @param {boolean} useLlm - LLM ile zenginleştir
 * @param {string|null} dbId - Hedef veritabanı ID
 */
export const clawbotAskReq = (message, useLlm = true, dbId = null) => {
  return axiosReq({
    url: 'clawbot/ask',
    data: { message, use_llm: useLlm, db_id: dbId },
    method: 'post',
    timeout: 60000,
  })
}

/**
 * ClawBot sağlık durumu
 */
export const clawbotHealthReq = () => {
  return axiosReq({
    url: 'clawbot/health',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * ClawBot skill listesi
 */
export const clawbotSkillsReq = () => {
  return axiosReq({
    url: 'clawbot/skills',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * ClawBot ayarlarını getir (Agent/LLM + davranış)
 */
export const getClawbotConfigReq = () => {
  return axiosReq({
    url: 'clawbot/config',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * ClawBot ayarlarını kaydet (Agent/LLM + davranış)
 */
export const saveClawbotConfigReq = (data) => {
  return axiosReq({
    url: 'clawbot/config',
    data,
    method: 'post',
  })
}

// ── Multi-DB CRUD ──────────────────────────────────────

/**
 * DB bağlantılarını listele
 */
export const listClawbotDatabasesReq = () => {
  return axiosReq({
    url: 'clawbot/databases',
    method: 'get',
    reqLoading: false,
  })
}

/**
 * DB bağlantısı ekle/güncelle
 */
export const saveClawbotDatabaseReq = (data) => {
  return axiosReq({
    url: 'clawbot/databases',
    data,
    method: 'post',
  })
}

/**
 * DB bağlantısı sil
 */
export const deleteClawbotDatabaseReq = (id) => {
  return axiosReq({
    url: 'clawbot/databases',
    data: { id },
    method: 'delete',
  })
}

/**
 * DB bağlantısı test et
 */
export const testClawbotDatabaseReq = (data) => {
  return axiosReq({
    url: 'clawbot/databases/test',
    data,
    method: 'post',
    timeout: 15000,
  })
}
