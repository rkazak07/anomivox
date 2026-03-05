import axiosReq from '@/utils/axios-req'

// Password is already SHA-256 hashed on the client side before being sent
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

const hashPassword = async (password) => {
  const encoder = new TextEncoder()
  const data = encoder.encode(password)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
}

export const createUserReq = async (username, password, role = 'user') => {
  const hashed = await hashPassword(password)
  return axiosReq({
    url: 'auth/create_user',
    data: { username, password: hashed, role },
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

export const changePasswordReq = async (user_id, new_password) => {
  const hashed = await hashPassword(new_password)
  return axiosReq({
    url: 'auth/change_password',
    data: { user_id, new_password: hashed },
    method: 'post'
  })
}

export const changeMyPasswordReq = async (current_password, new_password) => {
  const [currentHashed, newHashed] = await Promise.all([
    hashPassword(current_password),
    hashPassword(new_password)
  ])
  return axiosReq({
    url: 'auth/change_my_password',
    data: { current_password: currentHashed, new_password: newHashed },
    method: 'post'
  })
}
