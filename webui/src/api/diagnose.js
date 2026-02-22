import axiosReq from '@/utils/axios-req'

export const diagnoseStatusReq = () => {
  return axiosReq({
    url: 'diagnose/diagnose_status',
    method: 'get',
    reqLoading: false
  })
}


export const runDiagnoseReq = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return axiosReq({
    url: 'diagnose/run_diagnose',
    data: formData,
    method: 'post',
    cache: false,
    contentType: false,
    processData: false,
    timeout: 0,
  })
}


export const diagnoseTerminalOutputReq = () => {
  return axiosReq({
    url: 'diagnose/terminal_output',
    method: 'get',
    reqLoading: false
  })
}

export const diagnoseSerializationOutputReq = () => {
  return axiosReq({
    url: 'diagnose/serialization_output',
    method: 'get',
    reqLoading: false
  })
}

export const diagnoseStopDiagnoseReq = () => {
  return axiosReq({
    url: 'diagnose/stop_diagnose',
    data: {},
    method: 'post',
    reqLoading: true
  })
}

export const diagnoseUserFeedbackReq = (input) => {
  return axiosReq({
    url: 'diagnose/user_feedback',
    data: {user_input: input},
    method: 'post',
    reqLoading: false
  })
}
