import axiosReq from '@/utils/axios-req'
import {fetchData} from "@/utils/fetchData";

export const knowledgeListReq = () => {
  return axiosReq({
    url: 'knowledge_base/list_knowledge_bases',
    params: {},
    method: 'get'
  })
}


export const knowledgeFileDetailsReq = (knowledgeBaseName) => {
  return axiosReq({
    url: 'knowledge_base/kb_file_details',
    params: {knowledge_base_name: knowledgeBaseName},
    method: 'get'
  })
}

export const knowledgeDeleteDocsReq = (knowledgeBaseName, fileName) => {
  return axiosReq({
    url: 'knowledge_base/delete_docs',
    data: {knowledge_base_name: knowledgeBaseName, file_names: [fileName], delete_content: true, not_refresh_vs_cache: false},
    method: 'post',
    reqLoading: false
  })
}

export const knowledgeFileSplitContentReq = (knowledgeBaseName, fileName) => {
  return axiosReq({
    url: 'knowledge_base/docs_text_split_content',
    data: {knowledge_base_name: knowledgeBaseName, file_names: [fileName]},
    method: 'post',
    reqLoading: false
  })
}


export const knowledgeSearchDocsReq = (knowledgeBaseName, query) => {
  return axiosReq({
    url: 'knowledge_base/search_docs',
    data: {knowledge_base_name: knowledgeBaseName, query},
    method: 'post',
    reqLoading: false
  })
}

export const llmModelEmbedModelsReq = () => {
  return axiosReq({
    url: 'llm_model/embed_models',
    method: 'get',
    reqLoading: false
  })
}

export const llmModelListModelsReq = () => {
  return axiosReq({
    url: 'llm_model/list_models',
    method: 'get',
    reqLoading: false
  })
}

export const knowledgeBaseDetailReq = (knowledgeBaseName) => {
  return axiosReq({
    url: 'knowledge_base/detail',
    params: {knowledge_base_name: knowledgeBaseName},
    method: 'get'
  })
}

export const knowledgeBaseUpdateInfoReq = (knowledgeBaseName, info) => {
  return axiosReq({
    url: 'knowledge_base/update_info',
    data: {knowledge_base_name: knowledgeBaseName, kb_info: info},
    method: 'post'
  })
}

export const knowledgeBaseDeleteReq = (knowledgeBaseName) => {
  return axiosReq({
    url: 'knowledge_base/delete_knowledge_base',
    data: knowledgeBaseName,
    method: 'post'
  })
}

export const createKnowledgeBaseReq = (knowledgeBaseName, info, embedModel) => {
  return axiosReq({
    url: 'knowledge_base/create_knowledge_base',
    data: {knowledge_base_name: knowledgeBaseName, info, embed_model: embedModel},
    method: 'post',
    reqLoading: false
  })
}

export const chatReq = (query, conversationId, modelName, history, historyLen) => {
  return fetchData('chat/chat', {
    query, conversation_id: conversationId, model_name: modelName, history,
    prompt_name: 'default', temperature: 0.7, max_tokens: 0, history_len: historyLen, stream: true
  })
}

export const knowledgeChatReq = (query, ignoreCache, answerCache, knowledgeBaseName, modelName, history, historyLen) => {
  return fetchData('chat/knowledge_base_chat', {
    query, ignore_cache: ignoreCache, answer_cache: answerCache, knowledge_base_name: knowledgeBaseName,
    model_name: modelName, history, prompt_name: 'default',
    temperature: 0.7, max_tokens: 0, top_k: 3, score_threshold: 0.5, history_len: historyLen, stream: true
  })
}

export const knowledgeUploadDocsReq = (knowledgeBaseName, files, chunkSize = 250, chunkOverlap = 50, zhTitleEnhance = false) => {
  const formData = new FormData()
  formData.append('knowledge_base_name', knowledgeBaseName)
  formData.append('files', files)
  formData.append('override', true)
  formData.append('to_vector_store', true)
  formData.append('chunk_size', chunkSize)
  formData.append('chunk_overlap', chunkOverlap)
  formData.append('zh_title_enhance', zhTitleEnhance)
  return axiosReq({
    url: 'knowledge_base/upload_docs',
    data: formData,
    method: 'post',
    cache: false,
    contentType: false,
    processData: false,
    timeout: 0,
  })
}
