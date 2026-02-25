import axiosReq from '@/utils/axios-req'

export const loginReq = (subForm) => {
  return axiosReq({
    url: 'auth/login',
    data: subForm,
    method: 'post',
    reqLoading: false
  })
}

export const loginOutReq = () => {
  return axiosReq({
    url: 'auth/logout',
    method: 'post',
    reqLoading: false
  })
}

export const listUsersReq = () => {
  return axiosReq({
    url: 'auth/list_users',
    method: 'get'
  })
}

export const createUserReq = (username, password) => {
  return axiosReq({
    url: 'auth/create_user',
    data: { username, password },
    method: 'post'
  })
}

export const toggleUserReq = (user_id) => {
  return axiosReq({
    url: 'auth/toggle_user',
    data: { user_id },
    method: 'post'
  })
}

export const deleteUserReq = (user_id) => {
  return axiosReq({
    url: 'auth/delete_user',
    data: { user_id },
    method: 'post'
  })
}

export const changePasswordReq = (user_id, new_password) => {
  return axiosReq({
    url: 'auth/change_password',
    data: { user_id, new_password },
    method: 'post'
  })
}
