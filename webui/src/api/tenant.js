import axiosReq from '@/utils/axios-req'

export function listTenantsReq() {
  return axiosReq({ url: 'auth/tenants', method: 'get' })
}

export function createTenantReq(data) {
  return axiosReq({ url: 'auth/tenants', method: 'post', data })
}

export function deleteTenantReq(data) {
  return axiosReq({ url: 'auth/tenants/delete', method: 'post', data })
}

export function assignUserToTenantReq(data) {
  return axiosReq({ url: 'auth/tenants/assign', method: 'post', data })
}

export function listTenantUsersReq(tenantId) {
  return axiosReq({ url: `auth/tenants/${tenantId}/users`, method: 'get' })
}
