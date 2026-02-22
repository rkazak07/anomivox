

from typing import *
from pathlib import Path
from configs import (
    EMBEDDING_MODEL,
    LLM_MODELS,
    TEMPERATURE,
    SCORE_THRESHOLD,
    CHUNK_SIZE,
    OVERLAP_SIZE,
    ZH_TITLE_ENHANCE,
    VECTOR_SEARCH_TOP_K,
    SEARCH_ENGINE_TOP_K,
    HTTPX_DEFAULT_TIMEOUT,
    logger, log_verbose,
)
import httpx
import contextlib
import json
import os
from io import BytesIO
from server.utils import set_httpx_config, api_address, get_httpx_client

from pprint import pprint


set_httpx_config()


class ApiRequest:
    '''
    api.py çağrılarının senkron mod sarmalayıcısı
    '''
    def __init__(
        self,
        base_url: str = api_address(),
        timeout: float = HTTPX_DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self._use_async = False
        self._client = None

    @property
    def client(self):
        if self._client is None or self._client.is_closed:
            self._client = get_httpx_client(base_url=self.base_url,
                                            use_async=self._use_async,
                                            timeout=self.timeout)
        return self._client

    def get(
        self,
        url: str,
        params: Union[Dict, List[Tuple], bytes] = None,
        retry: int = 3,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[httpx.Response, Iterator[httpx.Response], None]:
        while retry > 0:
            try:
                if stream:
                    return self.client.stream("GET", url, params=params, **kwargs)
                else:
                    return self.client.get(url, params=params, **kwargs)
            except Exception as e:
                msg = f"error when get {url}: {e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                             exc_info=e if log_verbose else None)
                retry -= 1

    def post(
        self,
        url: str,
        data: Dict = None,
        json: Dict = None,
        retry: int = 3,
        stream: bool = False,
        **kwargs: Any
    ) -> Union[httpx.Response, Iterator[httpx.Response], None]:
        while retry > 0:
            try:
                # print(kwargs)
                if stream:
                    return self.client.stream("POST", url, data=data, json=json, **kwargs)
                else:
                    return self.client.post(url, data=data, json=json, **kwargs)
            except Exception as e:
                msg = f"error when post {url}: {e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                             exc_info=e if log_verbose else None)
                retry -= 1

    def delete(
        self,
        url: str,
        data: Dict = None,
        json: Dict = None,
        retry: int = 3,
        stream: bool = False,
        **kwargs: Any
    ) -> Union[httpx.Response, Iterator[httpx.Response], None]:
        while retry > 0:
            try:
                if stream:
                    return self.client.stream("DELETE", url, data=data, json=json, **kwargs)
                else:
                    return self.client.delete(url, data=data, json=json, **kwargs)
            except Exception as e:
                msg = f"error when delete {url}: {e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                             exc_info=e if log_verbose else None)
                retry -= 1

    def _httpx_stream2generator(
        self,
        response: contextlib._GeneratorContextManager,
        as_json: bool = False,
    ):
        '''
        httpx.stream GeneratorContextManager'ı normal generator'a dönüştür
        '''
        async def ret_async(response, as_json):
            try:
                async with response as r:
                    async for chunk in r.aiter_text(None):
                        if not chunk: # fastchat api yield empty bytes on start and end
                            continue
                        if as_json:
                            try:
                                data = json.loads(chunk)
                                # pprint(data, depth=1)
                                yield data
                            except Exception as e:
                                msg = f"API JSON hatası： ‘{chunk}’。Hata: {e}。"
                                logger.error(f'{e.__class__.__name__}: {msg}',
                                            exc_info=e if log_verbose else None)
                        else:
                            # print(chunk, end="", flush=True)
                            yield chunk
            except httpx.ConnectError as e:
                msg = f"API sunucusuna bağlanılamıyor，Lütfen kontrol edin ‘api.py’ çalışıyor olmalı。({e})"
                logger.error(msg)
                yield {"code": 500, "msg": msg}
            except httpx.ReadTimeout as e:
                msg = f"API iletişim zaman aşımı. FastChat ve API servisinin başlatıldığından emin olunWeb UI'）。（{e}）"
                logger.error(msg)
                yield {"code": 500, "msg": msg}
            except Exception as e:
                msg = f"API iletişim hatası: {e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                            exc_info=e if log_verbose else None)
                yield {"code": 500, "msg": msg}

        def ret_sync(response, as_json):
            try:
                with response as r:
                    for chunk in r.iter_text(None):
                        if not chunk: # fastchat api yield empty bytes on start and end
                            continue
                        if as_json:
                            try:
                                data = json.loads(chunk)
                                # pprint(data, depth=1)
                                yield data
                            except Exception as e:
                                msg = f"API JSON hatası： ‘{chunk}’。Hata: {e}。"
                                logger.error(f'{e.__class__.__name__}: {msg}',
                                            exc_info=e if log_verbose else None)
                        else:
                            # print(chunk, end="", flush=True)
                            yield chunk
            except httpx.ConnectError as e:
                msg = f"API sunucusuna bağlanılamıyor，Lütfen kontrol edin ‘api.py’ çalışıyor olmalı。({e})"
                logger.error(msg)
                yield {"code": 500, "msg": msg}
            except httpx.ReadTimeout as e:
                msg = f"API iletişim zaman aşımı. FastChat ve API servisinin başlatıldığından emin olunWeb UI'）。（{e}）"
                logger.error(msg)
                yield {"code": 500, "msg": msg}
            except Exception as e:
                msg = f"API iletişim hatası: {e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                            exc_info=e if log_verbose else None)
                yield {"code": 500, "msg": msg}

        if self._use_async:
            return ret_async(response, as_json)
        else:
            return ret_sync(response, as_json)

    def _get_response_value(
        self,
        response: httpx.Response,

        as_json: bool = False,
        value_func: Callable = None,
    ):
        '''
        Senkron veya asenkron istek yanıtını dönüştür
        `as_json`: JSON döndür
        `value_func`: Yanıt değerini özelleştirmek için fonksiyon
        '''
        def to_json(r):
            try:
                return r.json()
            except Exception as e:
                msg = "API geçerli JSON döndürmedi. " + str(e)
                if log_verbose:
                    logger.error(f'{e.__class__.__name__}: {msg}',
                                exc_info=e if log_verbose else None)
                return {"code": 500, "msg": msg, "data": None}

        if value_func is None:
            value_func = (lambda r: r)

        async def ret_async(response):
            if as_json:
                return value_func(to_json(await response))
            else:
                return value_func(await response)

        if self._use_async:
            return ret_async(response)
        else:
            if as_json:
                return value_func(to_json(response))
            else:
                return value_func(response)

    def get_server_configs(self, **kwargs) -> Dict:
        response = self.post("/server/configs", **kwargs)
        return self._get_response_value(response, as_json=True)

    def list_search_engines(self, **kwargs) -> List:
        response = self.post("/server/list_search_engines", **kwargs)
        return self._get_response_value(response, as_json=True, value_func=lambda r: r["data"])

    def get_prompt_template(
        self,
        type: str = "llm_chat",
        name: str = "default",
        **kwargs,
    ) -> str:
        data = {
            "type": type,
            "name": name,
        }
        response = self.post("/server/get_prompt_template", json=data, **kwargs)
        return self._get_response_value(response, value_func=lambda r: r.text)


    def chat_fastchat(
        self,
        messages: List[Dict],
        stream: bool = True,
        model: str = LLM_MODELS[0],
        temperature: float = TEMPERATURE,
        max_tokens: int = None,
        **kwargs: Any,
    ):
        '''
        api.py/chat/fastchat endpoint'i
        '''
        data = {
            "messages": messages,
            "stream": stream,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # print(f"received input message:")
        # pprint(data)

        response = self.post(
            "/chat/fastchat",
            json=data,
            stream=True,
            **kwargs,
        )
        return self._httpx_stream2generator(response)

    def chat_chat(
            self,
            query: str,
            conversation_id: str = None,
            history_len: int = -1,
            history: List[Dict] = [],
            stream: bool = True,
            model: str = LLM_MODELS[0],
            temperature: float = TEMPERATURE,
            max_tokens: int = None,
            prompt_name: str = "default",
            **kwargs,
    ):
        '''
        api.py/chat/chat endpoint'i
        '''
        data = {
            "query": query,
            "conversation_id": conversation_id,
            "history_len": history_len,
            "history": history,
            "stream": stream,
            "model_name": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_name": prompt_name,
        }

        response = self.post("/chat/chat", json=data, stream=True, **kwargs)
        return self._httpx_stream2generator(response, as_json=True)

    def agent_chat(
        self,
        query: str,
        history: List[Dict] = [],
        stream: bool = True,
        model: str = LLM_MODELS[0],
        temperature: float = TEMPERATURE,
        max_tokens: int = None,
        prompt_name: str = "default",
    ):
        '''
        api.py/chat/agent_chat endpoint'i
        '''
        data = {
            "query": query,
            "history": history,
            "stream": stream,
            "model_name": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_name": prompt_name,
        }

        # print(f"received input message:")
        # pprint(data)

        response = self.post("/chat/agent_chat", json=data, stream=True)
        return self._httpx_stream2generator(response)



    def diagnose_file(self, file_name: str, file_content: Union[bytes]):
        '''
        Anomali dosyasını tanıla
        '''
        response = self.post(
            "/diagnose/run_diagnose",
            files={"file": (file_name, file_content)},
            stream=False,
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", {}))


    def diagnose_output(self):
        '''
        Tanı çıktısını getir
        '''
        response = self.get(
            "/diagnose/terminal_output",
            stream=False,
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", {}))

    def diagnose_status(self):
        '''
        Tanı durumunu getir
        '''
        response = self.get(
            "/diagnose/diagnose_status",
            stream=False,
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", {}))

    def stop_diagnose(self):
        '''
        Tanıyı sonlandır
        '''
        response = self.post(
            "/diagnose/stop_diagnose",
            stream=False,
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", {}))

    def diagnose_diagnose_llm_model_list(self):
        '''
        Tanı geçmişini listele
        '''
        data = {}
        response = self.post(
            "/report/diagnose_llm_model_list",
            json=data,
            stream=False,
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", []))

    def diagnose_histories(self, start: str = None, end: str = None, model: str = "GPT4-0613"):
        '''
        Tanı geçmişini listele
        '''
        data = {
            "start": start,
            "end": end,
            "model": model
        }
        response = self.post(
            "/report/histories",
            json=data,
            stream=False,
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", []))

    def diagnose_history_detail(self, file_name: str, model: str = "GPT4-0613"):
        '''
        Tanı geçmiş detayını getir
        '''
        data = {
            "file_name": file_name,
            "model": model
        }
        response = self.post(
            "/report/history_detail",
            json=data,
            stream=False,
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", {}))


    def knowledge_base_chat(
        self,
        query: str,
        knowledge_base_name: str,
        top_k: int = VECTOR_SEARCH_TOP_K,
        score_threshold: float = SCORE_THRESHOLD,
        history: List[Dict] = [],
        stream: bool = True,
        ignore_cache: bool = True,
        model: str = LLM_MODELS[0],
        temperature: float = TEMPERATURE,
        max_tokens: int = None,
        prompt_name: str = "default",
    ):
        '''
        api.py/chat/knowledge_base_chat endpoint'i
        '''
        data = {
            "query": query,
            "knowledge_base_name": knowledge_base_name,
            "top_k": top_k,
            "score_threshold": score_threshold,
            "history": history,
            "stream": stream,
            "ignore_cache": ignore_cache,
            "model_name": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_name": prompt_name,
        }

        # print(f"received input message:")
        # pprint(data)

        response = self.post(
            "/chat/knowledge_base_chat",
            json=data,
            stream=True,
        )
        return self._httpx_stream2generator(response, as_json=True)


    def docs_text_split_content(self, knowledge_base_name, file_names):
        '''
        api.py/knowledge_base/doc_text_split_content endpoint'i
        '''
        data = {
            "knowledge_base_name": knowledge_base_name,
            "file_names": file_names,
        }
        response = self.post(
            "/knowledge_base/docs_text_split_content",
            json=data,
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", []))

    def upload_temp_docs(
        self,
        files: List[Union[str, Path, bytes]],
        knowledge_id: str = None,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=OVERLAP_SIZE,
        zh_title_enhance=ZH_TITLE_ENHANCE,
    ):
        '''
        api.py/knowledge_base/upload_temp_docs endpoint'i
        '''
        def convert_file(file, filename=None):
            if isinstance(file, bytes): # raw bytes
                file = BytesIO(file)
            elif hasattr(file, "read"): # a file io like object
                filename = filename or file.name
            else: # a local path
                file = Path(file).absolute().open("rb")
                filename = filename or os.path.split(file.name)[-1]
            return filename, file

        files = [convert_file(file) for file in files]
        data={
            "knowledge_id": knowledge_id,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "zh_title_enhance": zh_title_enhance,
        }

        response = self.post(
            "/knowledge_base/upload_temp_docs",
            data=data,
            files=[("files", (filename, file)) for filename, file in files],
        )
        return self._get_response_value(response, as_json=True)

    def file_chat(
        self,
        query: str,
        knowledge_id: str,
        top_k: int = VECTOR_SEARCH_TOP_K,
        score_threshold: float = SCORE_THRESHOLD,
        history: List[Dict] = [],
        stream: bool = True,
        model: str = LLM_MODELS[0],
        temperature: float = TEMPERATURE,
        max_tokens: int = None,
        prompt_name: str = "default",
    ):
        '''
        api.py/chat/file_chat endpoint'i
        '''
        data = {
            "query": query,
            "knowledge_id": knowledge_id,
            "top_k": top_k,
            "score_threshold": score_threshold,
            "history": history,
            "stream": stream,
            "model_name": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_name": prompt_name,
        }

        # print(f"received input message:")
        # pprint(data)

        response = self.post(
            "/chat/file_chat",
            json=data,
            stream=True,
        )
        return self._httpx_stream2generator(response, as_json=True)

    def search_engine_chat(
        self,
        query: str,
        search_engine_name: str,
        top_k: int = SEARCH_ENGINE_TOP_K,
        history: List[Dict] = [],
        stream: bool = True,
        model: str = LLM_MODELS[0],
        temperature: float = TEMPERATURE,
        max_tokens: int = None,
        prompt_name: str = "default",
        split_result: bool = False,
    ):
        '''
        api.py/chat/search_engine_chat endpoint'i
        '''
        data = {
            "query": query,
            "search_engine_name": search_engine_name,
            "top_k": top_k,
            "history": history,
            "stream": stream,
            "model_name": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_name": prompt_name,
            "split_result": split_result,
        }

        # print(f"received input message:")
        # pprint(data)

        response = self.post(
            "/chat/search_engine_chat",
            json=data,
            stream=True,
        )
        return self._httpx_stream2generator(response, as_json=True)


    def list_knowledge_bases(
        self,
    ):
        '''
        api.py/knowledge_base/list_knowledge_bases endpoint'i
        '''
        response = self.get("/knowledge_base/list_knowledge_bases")
        return self._get_response_value(response,
                                        as_json=True,
                                        value_func=lambda r: r.get("data", []))

    def create_knowledge_base(
        self,
        knowledge_base_name: str,
        embed_model: str = EMBEDDING_MODEL,
    ):
        '''
        api.py/knowledge_base/create_knowledge_base endpoint'i
        '''
        data = {
            "knowledge_base_name": knowledge_base_name,
            "embed_model": embed_model,
        }

        response = self.post(
            "/knowledge_base/create_knowledge_base",
            json=data,
        )
        return self._get_response_value(response, as_json=True)

    def delete_knowledge_base(
        self,
        knowledge_base_name: str,
    ):
        '''
        api.py/knowledge_base/delete_knowledge_base endpoint'i
        '''
        response = self.post(
            "/knowledge_base/delete_knowledge_base",
            json=f"{knowledge_base_name}",
        )
        return self._get_response_value(response, as_json=True)

    def list_kb_docs(
        self,
        knowledge_base_name: str,
    ):
        '''
        api.py/knowledge_base/list_files endpoint'i
        '''
        response = self.get(
            "/knowledge_base/list_files",
            params={"knowledge_base_name": knowledge_base_name}
        )
        return self._get_response_value(response,
                                        as_json=True,
                                        value_func=lambda r: r.get("data", []))

    def search_kb_docs(
        self,
        query: str,
        knowledge_base_name: str,
        top_k: int = VECTOR_SEARCH_TOP_K,
        score_threshold: int = SCORE_THRESHOLD,
    ) -> List:
        '''
        api.py/knowledge_base/search_docs endpoint'i
        '''
        data = {
            "query": query,
            "knowledge_base_name": knowledge_base_name,
            "top_k": top_k,
            "score_threshold": score_threshold,
        }

        response = self.post(
            "/knowledge_base/search_docs",
            json=data,
        )
        return self._get_response_value(response, as_json=True)

    def upload_kb_docs(
        self,
        files: List[Union[str, Path, bytes]],
        knowledge_base_name: str,
        override: bool = False,
        to_vector_store: bool = True,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=OVERLAP_SIZE,
        zh_title_enhance=ZH_TITLE_ENHANCE,
        docs: Dict = {},
        not_refresh_vs_cache: bool = False,
    ):
        '''
        api.py/knowledge_base/upload_docs endpoint'i
        '''
        def convert_file(file, filename=None):
            if isinstance(file, bytes): # raw bytes
                file = BytesIO(file)
            elif hasattr(file, "read"): # a file io like object
                filename = filename or file.name
            else: # a local path
                file = Path(file).absolute().open("rb")
                filename = filename or os.path.split(file.name)[-1]
            return filename, file

        files = [convert_file(file) for file in files]
        data={
            "knowledge_base_name": knowledge_base_name,
            "override": override,
            "to_vector_store": to_vector_store,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "zh_title_enhance": zh_title_enhance,
            "docs": docs,
            "not_refresh_vs_cache": not_refresh_vs_cache,
        }

        if isinstance(data["docs"], dict):
            data["docs"] = json.dumps(data["docs"], ensure_ascii=False)
        response = self.post(
            "/knowledge_base/upload_docs",
            data=data,
            files=[("files", (filename, file)) for filename, file in files],
        )
        return self._get_response_value(response, as_json=True)

    def delete_kb_docs(
        self,
        knowledge_base_name: str,
        file_names: List[str],
        delete_content: bool = False,
        not_refresh_vs_cache: bool = False,
    ):
        '''
        api.py/knowledge_base/delete_docs endpoint'i
        '''
        data = {
            "knowledge_base_name": knowledge_base_name,
            "file_names": file_names,
            "delete_content": delete_content,
            "not_refresh_vs_cache": not_refresh_vs_cache,
        }

        response = self.post(
            "/knowledge_base/delete_docs",
            json=data,
        )
        return self._get_response_value(response, as_json=True)


    def update_kb_info(self,knowledge_base_name,kb_info):
        '''
        api.py/knowledge_base/update_info endpoint'i
        '''
        data = {
            "knowledge_base_name": knowledge_base_name,
            "kb_info": kb_info,
        }

        response = self.post(
            "/knowledge_base/update_info",
            json=data,
        )
        return self._get_response_value(response, as_json=True)

    def update_kb_docs(
        self,
        knowledge_base_name: str,
        file_names: List[str],
        override_custom_docs: bool = False,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=OVERLAP_SIZE,
        zh_title_enhance=ZH_TITLE_ENHANCE,
        docs: Dict = {},
        not_refresh_vs_cache: bool = False,
    ):
        '''
        api.py/knowledge_base/update_docs endpoint'i
        '''
        data = {
            "knowledge_base_name": knowledge_base_name,
            "file_names": file_names,
            "override_custom_docs": override_custom_docs,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "zh_title_enhance": zh_title_enhance,
            "docs": docs,
            "not_refresh_vs_cache": not_refresh_vs_cache,
        }

        if isinstance(data["docs"], dict):
            data["docs"] = json.dumps(data["docs"], ensure_ascii=False)

        response = self.post(
            "/knowledge_base/update_docs",
            json=data,
        )
        return self._get_response_value(response, as_json=True)

    def recreate_vector_store(
        self,
        knowledge_base_name: str,
        allow_empty_kb: bool = True,
        embed_model: str = EMBEDDING_MODEL,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=OVERLAP_SIZE,
        zh_title_enhance=ZH_TITLE_ENHANCE,
    ):
        '''
        api.py/knowledge_base/recreate_vector_store endpoint'i
        '''
        data = {
            "knowledge_base_name": knowledge_base_name,
            "allow_empty_kb": allow_empty_kb,
            "embed_model": embed_model,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "zh_title_enhance": zh_title_enhance,
        }

        response = self.post(
            "/knowledge_base/recreate_vector_store",
            json=data,
            stream=True,
            timeout=None,
        )
        return self._httpx_stream2generator(response, as_json=True)

    def list_running_models(
        self,
        controller_address: str = None,
    ):
        '''
        FastChat'te çalışan modelleri listele
        '''
        data = {
            "controller_address": controller_address,
        }

        if log_verbose:
            logger.info(f'{self.__class__.__name__}:data: {data}')

        response = self.post(
            "/llm_model/list_running_models",
            json=data,
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", []))


    def get_default_llm_model(self, local_first: bool = True) -> Tuple[str, bool]:
        '''
        Sunucuda çalışan LLM modelini getir.
        local_first=True ise yerel modeller öncelikli, aksi halde LLM_MODELS sırası esas alınır.
        Dönüş tipi: (model_name, is_local_model)
        '''
        def ret_sync():
            running_models = self.list_running_models()
            if not running_models:
                return "", False

            model = ""
            for m in LLM_MODELS:
                if m not in running_models:
                    continue
                is_local = not running_models[m].get("online_api")
                if local_first and not is_local:
                    continue
                else:
                    model = m
                    break

            if not model:
                model = list(running_models)[0]
            is_local = not running_models[model].get("online_api")
            return model, is_local

        async def ret_async():
            running_models = await self.list_running_models()
            if not running_models:
                return "", False

            model = ""
            for m in LLM_MODELS:
                if m not in running_models:
                    continue
                is_local = not running_models[m].get("online_api")
                if local_first and not is_local:
                    continue
                else:
                    model = m
                    break

            if not model:
                model = list(running_models)[0]
            is_local = not running_models[model].get("online_api")
            return model, is_local

        if self._use_async:
            return ret_async()
        else:
            return ret_sync()

    def list_config_models(
        self,
        types: List[str] = ["local", "online"],
    ) -> Dict[str, Dict]:
        '''
        Sunucu yapılandırmasındaki model listesini getir: {"type": {model_name: config}, ...}
        '''
        data = {
            "types": types,
        }
        response = self.post(
            "/llm_model/list_config_models",
            json=data,
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", {}))

    def get_model_config(
        self,
        model_name: str = None,
    ) -> Dict:
        '''
        Sunucu model yapılandırmasını getir
        '''
        data={
            "model_name": model_name,
        }
        response = self.post(
            "/llm_model/get_model_config",
            json=data,
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", {}))

    def list_search_engines(self) -> List[str]:
        '''
        Desteklenen arama motorlarını getir
        '''
        response = self.post(
            "/server/list_search_engines",
        )
        return self._get_response_value(response, as_json=True, value_func=lambda r:r.get("data", {}))

    def stop_llm_model(
        self,
        model_name: str,
        controller_address: str = None,
    ):
        '''
        Bir LLM modelini durdur.
        Not: FastChat implementasyonu nedeniyle ilgili model_worker durdurulur.
        '''
        data = {
            "model_name": model_name,
            "controller_address": controller_address,
        }

        response = self.post(
            "/llm_model/stop",
            json=data,
        )
        return self._get_response_value(response, as_json=True)

    def change_llm_model(
        self,
        model_name: str,
        new_model_name: str,
        controller_address: str = None,
    ):
        '''
        FastChat controller'a LLM model değiştirme isteği gönder.
        '''
        if not model_name or not new_model_name:
            return {
                "code": 500,
                "msg": f"Model adı belirtilmedi"
            }

        def ret_sync():
            running_models = self.list_running_models()
            if new_model_name == model_name or new_model_name in running_models:
                return {
                    "code": 200,
                    "msg": "Değiştirme gerekmiyor"
                }

            if model_name not in running_models:
                return {
                    "code": 500,
                    "msg": f"Belirtilen model '{model_name}' çalışmıyor. Çalışan modeller: {running_models}"
                }

            config_models = self.list_config_models()
            if new_model_name not in config_models.get("local", {}):
                return {
                    "code": 500,
                    "msg": f"The model to switch to '{new_model_name}' is not configured."
                }

            data = {
                "model_name": model_name,
                "new_model_name": new_model_name,
                "controller_address": controller_address,
            }

            response = self.post(
                "/llm_model/change",
                json=data,
            )
            return self._get_response_value(response, as_json=True)

        async def ret_async():
            running_models = await self.list_running_models()
            if new_model_name == model_name or new_model_name in running_models:
                return {
                    "code": 200,
                    "msg": "Değiştirme gerekmiyor"
                }

            if model_name not in running_models:
                return {
                    "code": 500,
                    "msg": f"Belirtilen model '{model_name}' çalışmıyor. Çalışan modeller: {running_models}"
                }

            config_models = await self.list_config_models()
            if new_model_name not in config_models.get("local", {}):
                return {
                    "code": 500,
                    "msg": f"The model to switch to '{new_model_name}' is not configured."
                }

            data = {
                "model_name": model_name,
                "new_model_name": new_model_name,
                "controller_address": controller_address,
            }

            response = self.post(
                "/llm_model/change",
                json=data,
            )
            return self._get_response_value(response, as_json=True)

        if self._use_async:
            return ret_async()
        else:
            return ret_sync()

    def embed_texts(
        self,
        texts: List[str],
        embed_model: str = EMBEDDING_MODEL,
        to_query: bool = False,
    ) -> List[List[float]]:
        '''
        Metni vektörleştir (yerel embed_models veya online embedding destekli modeller)
        '''
        data = {
            "texts": texts,
            "embed_model": embed_model,
            "to_query": to_query,
        }
        resp = self.post(
            "/other/embed_texts",
            json=data,
        )
        return self._get_response_value(resp, as_json=True, value_func=lambda r: r.get("data"))

    def chat_feedback(
        self,
        message_id: str,
        score: int,
        reason: str = "",
    ) -> int:
        '''
        Sohbet değerlendirmesi gönder
        '''
        data = {
            "message_id": message_id,
            "score": score,
            "reason": reason,
        }
        resp = self.post("/chat/feedback", json=data)
        return self._get_response_value(resp)


class AsyncApiRequest(ApiRequest):
    def __init__(self, base_url: str = api_address(), timeout: float = HTTPX_DEFAULT_TIMEOUT):
        super().__init__(base_url, timeout)
        self._use_async = True


def check_error_msg(data: Union[str, dict, list], key: str = "errorMsg") -> str:
    '''
    return error message if error occured when requests API
    '''
    if isinstance(data, dict):
        if key in data:
            return data[key]
        if "code" in data and data["code"] != 200:
            return data["msg"]
    return ""


def check_success_msg(data: Union[str, dict, list], key: str = "msg") -> str:
    '''
    return error message if error occured when requests API
    '''
    if (isinstance(data, dict)
        and key in data
        and "code" in data
        and data["code"] == 200):
        return data[key]
    return ""


if __name__ == "__main__":
    api = ApiRequest()
    aapi = AsyncApiRequest()

    # print(api.chat_fastchat(
    #     messages=[{"role": "user", "content": "hello"}]
    # ))

    #     for t in r.iter_text(None):
    #         print(t)

    # for t in r:
    #     print(t)

    # for t in r:
    #     print(t)

    # print(api.list_knowledge_bases())
