from fastapi import Body, Request
from fastapi.responses import StreamingResponse
from configs import (
    LLM_MODELS,
    VECTOR_SEARCH_TOP_K,
    SCORE_THRESHOLD,
    TEMPERATURE, DEFAULT_VS_TYPES)
from server.utils import wrap_done, get_ChatOpenAI
from server.utils import BaseResponse, get_prompt_template
from langchain.chains import LLMChain
from langchain.callbacks import AsyncIteratorCallbackHandler
from typing import AsyncIterable, List, Optional
import asyncio
from langchain.prompts.chat import ChatPromptTemplate
from server.chat.utils import History
from server.knowledge_base.kb_service.base import KBServiceFactory, SupportedVSType
from langchain.docstore.document import Document
import json
from urllib.parse import urlencode
from server.knowledge_base.kb_doc_api import search_docs


async def knowledge_base_chat(query: str = Body(..., description="User input", examples=["hello"]),
                              ignore_cache: bool = Body(True, description="Ignore cache"),
                              answer_cache: bool = Body(False, description="Cache search results"),
                              knowledge_base_name: str = Body(..., description="Knowledge base name", examples=["samples"]),
                              top_k: int = Body(VECTOR_SEARCH_TOP_K, description="Number of matching vectors"),
                              score_threshold: float = Body(
                                  SCORE_THRESHOLD,
                                  description="Knowledge base match threshold. Lower SCORE = higher relevance. Use higher values to include more results.",
                                  ge=0,
                                  le=4
),
    history: List[History] = Body(
                                  [],
                                  description="Conversation history",
                                  examples=[[
                                      {"role": "user", "content": "Hello"},
                                      {"role": "assistant",
                                       "content": "Tigerly brave"}]]
),
    stream: bool = Body(False, description="Stream output"),
    model_name: str = Body(LLM_MODELS[0], description="LLM model name"),
    temperature: float = Body(TEMPERATURE, description="LLM sampling temperature", ge=0.0, le=1.0),
    max_tokens: Optional[int] = Body(
                                  None,
                                  description="Limit LLM generated token count, None defaults to model maximum"
),
    prompt_name: str = Body(
                                  "default",
                                  description="Prompt template name used (configured in configs/prompt_config.py)"
),
    request: Request = None,
):

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name, DEFAULT_VS_TYPES[0])
    if kb is None:
        return BaseResponse(code=404, msg=f"Knowledge base {knowledge_base_name} not found")

    history = [History.from_data(h) for h in history]

    async def knowledge_base_chat_iterator(
            query: str,
            top_k: int,
            history: Optional[List[History]],
            ignore_cache: bool = True,
            answer_cache: bool = False,
            model_name: str = LLM_MODELS[0],
            prompt_name: str = prompt_name,
    ) -> AsyncIterable[str]:
        nonlocal max_tokens
        callback = AsyncIteratorCallbackHandler()
        if isinstance(max_tokens, int) and max_tokens <= 0:
            max_tokens = None

        if not ignore_cache:
            cache_kb = KBServiceFactory.get_service(
                "cache", SupportedVSType.CHROMADB)
            docs = cache_kb.search_docs(query, top_k)
            if len(docs) > 0:
                if stream:
                    cache_data = []
                    for doc, score in docs:
                        answer = doc.metadata.get("answer")
                        if answer:
                            yield json.dumps({"answer": f"<span style='word-break:break-all; color:#333333; font-size:16px; margin-bottom:10px;'>{doc.page_content}:<br><span style='color:#999999; font-size:14px;'>{answer}</span></span><br>", "cache": True}, ensure_ascii=False)
                    cache_data.append({
                        "answer": doc.metadata.get("answer"),
                        "page_content": doc.page_content
                    })
                    yield json.dumps({"cacheData": cache_data, "cache": True}, ensure_ascii=False)
                else:
                    cache_data = []
                    answers = ""
                    for doc, score in docs:
                        answers += f"<span style='word-break:break-all; color:#333333; font-size:16px; margin-bottom:10px;'>{doc.page_content}:<br><span style='color:#999999; font-size:14px;'>{doc.metadata.get('answer')}</span></span><br>"
                        cache_data.append({
                            "answer": doc.metadata.get("answer"),
                            "page_content": doc.page_content
                        })
                    yield json.dumps({"cacheData": cache_data, "cache": True, "answer": answers}, ensure_ascii=False)
            else:
                yield json.dumps({"answer": "No Cache"}, ensure_ascii=False)
            return
        model = get_ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=[callback],
        )
        docs = search_docs(query, knowledge_base_name, top_k, score_threshold)
        context = "\n".join([doc.page_content for doc in docs])

        if len(docs) == 0:
            empty_key = "empty_tr" if prompt_name == "tr" else "empty"
            prompt_template = get_prompt_template(
                "knowledge_base_chat", empty_key)
        else:
            prompt_template = get_prompt_template(
                "knowledge_base_chat", prompt_name)

        input_msg = History(
            role="user",
            content=prompt_template).to_msg_template(False)
        chat_prompt = ChatPromptTemplate.from_messages(
            [i.to_msg_template() for i in history] + [input_msg])

        chain = LLMChain(prompt=chat_prompt, llm=model)

        # Begin a task that runs in the background.
        task = asyncio.create_task(wrap_done(
            chain.acall({"context": context, "question": query}),
            callback.done),
        )

        source_documents = []
        source_documents_map = {}
        for inum, doc in enumerate(docs):
            filename = doc.metadata.get("source")
            parameters = urlencode(
                {"knowledge_base_name": knowledge_base_name, "file_name": filename})
            base_url = request.base_url
            url = f"{base_url}knowledge_base/download_doc?" + parameters
            text = f"""Source [{inum + 1}] [{filename}]({url}) \n\n{doc.page_content}\n\n"""
            source_documents.append(text)
            if filename in source_documents_map:
                source_documents_map[filename]["contents"].append(doc.page_content)
            else:
                source_documents_map[filename] = {"filename": filename, "url": url, "contents": [doc.page_content]}

        if len(source_documents) == 0:
            source_documents.append(
                f"<span style='color:red'>No relevant documents found, this answer is based on the model's own capabilities!</span>")
        answer = ""
        if stream:
            async for token in callback.aiter():
                # Use server-sent-events to stream the response
                answer += token
                yield json.dumps({"answer": token}, ensure_ascii=False)
            yield json.dumps({"docs": source_documents, "docsDetail": list(source_documents_map.values())}, ensure_ascii=False)
        else:
            answer = ""
            async for token in callback.aiter():
                answer += token
            yield json.dumps({"answer": answer,
                              "docs": source_documents,
                              "docsDetail": list(source_documents_map.values())},
                             ensure_ascii=False)
        if answer_cache:
            cache_kb = KBServiceFactory.get_service(
                "cache", SupportedVSType.CHROMADB)
            doc_infos = cache_kb.do_add_doc([Document(page_content=query, metadata={"source": "cache", "answer": answer})])
            print("cache doc_infos：", doc_infos)
        await task

    return StreamingResponse(
        knowledge_base_chat_iterator(
            query=query,
            top_k=top_k,
            history=history,
            ignore_cache=ignore_cache,
            answer_cache=answer_cache,
            model_name=model_name,
            prompt_name=prompt_name),
        media_type="text/event-stream")
