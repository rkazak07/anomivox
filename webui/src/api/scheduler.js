import axiosReq from '@/utils/axios-req'

export function listScheduledTasksReq() {
  return axiosReq({ url: 'scheduler/tasks', method: 'get' })
}

export function createScheduledTaskReq(data) {
  return axiosReq({ url: 'scheduler/tasks', method: 'post', data })
}

export function updateScheduledTaskReq(data) {
  return axiosReq({ url: 'scheduler/tasks', method: 'put', data })
}

export function deleteScheduledTaskReq(data) {
  return axiosReq({ url: 'scheduler/tasks/delete', method: 'post', data })
}

export function runScheduledTaskNowReq(data) {
  return axiosReq({ url: 'scheduler/tasks/run', method: 'post', data })
}
