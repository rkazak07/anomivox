import axiosReq from "@/utils/axios-req";

export const getDashboardHealth = () => {
  return axiosReq({
    url: 'dashboard/health',
    method: 'get'
  })
}

export const getDashboardDiagnosisSummary = (hours = 24) => {
  return axiosReq({
    url: 'dashboard/diagnosis_summary',
    data: { hours },
    method: 'post'
  })
}

export const getDashboardPipelineStatus = () => {
  return axiosReq({
    url: 'dashboard/pipeline_status',
    method: 'get'
  })
}
