import axiosReq from "@/utils/axios-req";

export const getDashboardOverview = (hours = 24) => {
  return axiosReq({
    url: 'dashboard/overview',
    data: { hours },
    method: 'post'
  })
}

export const getDashboardHealth = () => {
  return axiosReq({
    url: 'dashboard/health',
    method: 'get'
  })
}

export const getDashboardPipelineStatus = () => {
  return axiosReq({
    url: 'dashboard/pipeline_status',
    method: 'get'
  })
}
