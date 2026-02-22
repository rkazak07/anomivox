import os
import urllib
from fastapi import File, Form, Body, Query, UploadFile
from configs import (EMBEDDING_MODEL,
                     VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD,
                     CHUNK_SIZE, OVERLAP_SIZE, ZH_TITLE_ENHANCE,
                     logger, log_verbose, DEFAULT_VS_TYPES)
from server.utils import BaseResponse, ListResponse, run_in_thread_pool
from server.knowledge_base.utils import (validate_kb_name, list_files_from_folder, get_file_path,
                                         files2docs_in_thread, KnowledgeFile)
from fastapi.responses import StreamingResponse, FileResponse
from server.knowledge_base.kb_service.base import get_kb_details
from pydantic import Json
import json
from server.knowledge_base.kb_service.base import KBServiceFactory, get_kb_file_details
from server.db.repository.knowledge_file_repository import get_file_detail
from langchain.docstore.document import Document
from typing import List


class DocumentWithScore(Document):
    score: float = None

def api_search_docs(
        query: str = Body(..., description="User input", examples=["Hello"]),
        knowledge_base_name: str = Body(..., description="Knowledge base name", examples=["samples"]),
        top_k: int = Body(VECTOR_SEARCH_TOP_K, description="Number of matching vectors"),
        score_threshold: float = Body(SCORE_THRESHOLD,
                                      description="Match threshold, 0-1. Lower SCORE means higher relevance. 1 means no filter, 0.5 is recommended",
                                      ge=0, le=1),
) -> List[DocumentWithScore]:
    data = search_docs(query, knowledge_base_name, top_k, score_threshold)
    return BaseResponse(code=200, msg="Success", data=data)

def search_docs(
        query: str = Body(..., description="User input", examples=["Hello"]),
        knowledge_base_name: str = Body(..., description="Knowledge base name", examples=["samples"]),
        top_k: int = Body(VECTOR_SEARCH_TOP_K, description="Number of matching vectors"),
        score_threshold: float = Body(SCORE_THRESHOLD,
                                      description="Match threshold, 0-1. Lower SCORE means higher relevance. 1 means no filter, 0.5 is recommended",
                                      ge=0, le=1),
) -> List[DocumentWithScore]:
    # kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    # if kb is None:
    #     return []
    #
    # docs = kb.search_docs(query, top_k, score_threshold)
    #
    # # remove elements with the same content in docs
    # no_replicate_docs = []
    # for i, doc in enumerate(docs):
    #     if i == 0 or ('content' not in doc[0].metadata) or (
    #             doc[0].metadata['content'] != docs[i - 1][0].metadata['content']):
    #         no_replicate_docs.append(doc)
    #
    # data = [DocumentWithScore(page_content=x[0].page_content, metadata=x[0].dict()['metadata'], score=x[1]) for x in
    #         docs]

    data = []
    for vs_type in DEFAULT_VS_TYPES:
        kb = KBServiceFactory.get_service(knowledge_base_name, vs_type)
        if kb is None:
            continue
        docs = kb.search_docs(query, top_k * 2, score_threshold)

        no_replicate_docs = []
        # import pdb; pdb.set_trace()
        for i, doc in enumerate(docs):
            if 'cause_name' in doc[0].metadata:
                not_exist = True
                for compare_doc in no_replicate_docs:
                    if doc[0].metadata['cause_name'] == compare_doc[0].metadata['cause_name']:
                        not_exist = False
                        break
                
                if not_exist == True:
                    no_replicate_docs.append(doc)

        if len(no_replicate_docs) > top_k:
            no_replicate_docs = no_replicate_docs[:top_k]

        data.extend([DocumentWithScore(page_content=x[0].page_content, metadata=x[0].dict()['metadata'], score=x[1]) for x in no_replicate_docs])

        print(f"Number of documents used from knowledge base: {len(no_replicate_docs)}")
        # print no_replicate_docs separated by \n
        for doc in no_replicate_docs:
            print(doc[0].metadata)
        print('*' * 100)
    
    return data


def kb_file_details(
        knowledge_base_name: str
) -> ListResponse:
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me", data=[])

    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)

    details = get_kb_file_details(knowledge_base_name)

    if not details:
        return BaseResponse(code=404, msg=f"Knowledge base not found: file for {knowledge_base_name}", data=[])
    else:
        return BaseResponse(code=200, msg=f"Successfully queried files for knowledge base {knowledge_base_name}", data=details)


def list_files(
        knowledge_base_name: str
) -> ListResponse:
    if not validate_kb_name(knowledge_base_name):
        return ListResponse(code=403, msg="Don't attack me", data=[])

    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)
    all_doc_names = []
    for vs_type in DEFAULT_VS_TYPES:
        kb = KBServiceFactory.get_service(knowledge_base_name, vs_type)
        if kb is not None:
            all_doc_names.extend(kb.list_files())

    if not all_doc_names:
        return ListResponse(code=404, msg=f"Knowledge base not found: files for {knowledge_base_name}", data=[])
    else:
        return ListResponse(data=list(set(all_doc_names)))


def _save_files_in_thread(files: List[UploadFile],
                          knowledge_base_name: str,
                          override: bool):
    """
    Save uploaded files to the corresponding knowledge base directory in multi-threaded mode.
    Producer returns save results: {"code":200, "msg": "xxx", "data": {"knowledge_base_name":"xxx", "file_name": "xxx"}}
    """

    def save_file(file: UploadFile, knowledge_base_name: str, override: bool) -> dict:
        '''
        Save a single file.
        '''
        try:
            filename = file.filename
            file_path = get_file_path(knowledge_base_name=knowledge_base_name, doc_name=filename)
            data = {"knowledge_base_name": knowledge_base_name, "file_name": filename}

            file_content = file.file.read()
            if (os.path.isfile(file_path)
                    and not override
                    and os.path.getsize(file_path) == len(file_content)
            ):
                file_status = f"File {filename} already exists."
                logger.warn(file_status)
                return dict(code=404, msg=file_status, data=data)

            if not os.path.isdir(os.path.dirname(file_path)):
                os.makedirs(os.path.dirname(file_path))
            with open(file_path, "wb") as f:
                f.write(file_content)
            return dict(code=200, msg=f"File {filename} uploaded successfully", data=data)
        except Exception as e:
            msg = f"Failed to upload file {filename}, error: {e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                         exc_info=e if log_verbose else None)
            return dict(code=500, msg=msg, data=data)

    params = [{"file": file, "knowledge_base_name": knowledge_base_name, "override": override} for file in files]
    for result in run_in_thread_pool(save_file, params=params):
        yield result


#                 knowledge_base_name: str = Form(..., description="Knowledge base name", examples=["samples"]),
#     '''
#     '''
#     def generate(files, knowledge_base_name, override):
#         for result in _save_files_in_thread(files, knowledge_base_name=knowledge_base_name, override=override):
#             yield json.dumps(result, ensure_ascii=False)

#     return StreamingResponse(generate(files, knowledge_base_name=knowledge_base_name, override=override), media_type="text/event-stream")


#                 knowledge_base_name: str = Form(..., description="Knowledge base name", examples=["samples"]),
#     def save_files(files, knowledge_base_name, override):
#         for result in _save_files_in_thread(files, knowledge_base_name=knowledge_base_name, override=override):
#             yield json.dumps(result, ensure_ascii=False)

#     def files_to_docs(files):
#         for result in files2docs_in_thread(files):
#             yield json.dumps(result, ensure_ascii=False)


def upload_docs(
        files: List[UploadFile] = File(..., description="Upload files, multiple files supported"),
        knowledge_base_name: str = Form(..., description="Knowledge base name", examples=["samples"]),
        override: bool = Form(False, description="Overwrite existing files"),
        to_vector_store: bool = Form(True, description="Vectorize files after upload"),
        chunk_size: int = Form(CHUNK_SIZE, description="Maximum length of a single text segment in knowledge base"),
        chunk_overlap: int = Form(OVERLAP_SIZE, description="Overlapping length of neighboring text"),
        zh_title_enhance: bool = Form(ZH_TITLE_ENHANCE, description="Enable title enhancement"),
        docs: Json = Form({}, description="Custom docs, must be converted to JSON string",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}]),
        not_refresh_vs_cache: bool = Form(False, description="Do not save vector store yet (for FAISS)"),
) -> BaseResponse:
    """
    API: Upload files and/or vectorize
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    failed_files = {}
    file_names = list(docs.keys())

    for result in _save_files_in_thread(files, knowledge_base_name=knowledge_base_name, override=override):
        filename = result["data"]["file_name"]
        if result["code"] != 200:
            failed_files[filename] = result["msg"]

        if filename not in file_names:
            file_names.append(filename)

    if to_vector_store:
        for vs_type in DEFAULT_VS_TYPES:
            kb = KBServiceFactory.get_service(knowledge_base_name, vs_type)
            if kb is None:
                continue

            result = update_docs(
                knowledge_base_name=knowledge_base_name,
                file_names=file_names,
                override_custom_docs=True,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                zh_title_enhance=zh_title_enhance,
                docs=docs,
                not_refresh_vs_cache=True,
            )
            failed_files.update(result.data["failed_files"])
            if not not_refresh_vs_cache:
                kb.save_vector_store()

    return BaseResponse(code=200, msg="File upload and vectorization completed", data={"failed_files": failed_files})


def delete_docs(
        knowledge_base_name: str = Body(..., examples=["samples"]),
        file_names: List[str] = Body(..., examples=[["file_name.md", "test.txt"]]),
        delete_content: bool = Body(False),
        not_refresh_vs_cache: bool = Body(False, description="Do not save vector store yet (for FAISS)"),
) -> BaseResponse:
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)
    failed_files = {}

    for vs_type in DEFAULT_VS_TYPES:
        kb = KBServiceFactory.get_service(knowledge_base_name, vs_type)
        if kb is None:
            continue

        for file_name in file_names:
            if not kb.exist_doc(file_name):
                failed_files[file_name] = f"File not found: {file_name}"

            try:
                kb_file = KnowledgeFile(filename=file_name,
                                        knowledge_base_name=knowledge_base_name)
                kb.delete_doc(kb_file, delete_content, not_refresh_vs_cache=True)
            except Exception as e:
                msg = f"Failed to delete file {file_name}, error: {e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                             exc_info=e if log_verbose else None)
                failed_files[file_name] = msg

        if not not_refresh_vs_cache:
            kb.save_vector_store()

    return BaseResponse(code=200, msg=f"File deletion completed", data={"failed_files": failed_files})


def update_info(
        knowledge_base_name: str = Body(..., description="Knowledge base name", examples=["samples"]),
        kb_info: str = Body(..., description="Knowledge base description", examples=["This is a knowledge base"]),
):
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    for vs_type in DEFAULT_VS_TYPES:
        kb = KBServiceFactory.get_service(knowledge_base_name, vs_type)
        if kb is None:
            continue

        kb.update_info(kb_info)

    return BaseResponse(code=200, msg=f"Knowledge base description updated", data={"kb_info": kb_info})


def update_docs(
        knowledge_base_name: str = Body(..., description="Knowledge base name", examples=["samples"]),
        file_names: List[str] = Body(..., description="File names, multiple files supported", examples=[["file_name1", "text.txt"]]),
        chunk_size: int = Body(CHUNK_SIZE, description="Maximum length of a single text segment in knowledge base"),
        chunk_overlap: int = Body(OVERLAP_SIZE, description="Overlapping length of neighboring text"),
        zh_title_enhance: bool = Body(ZH_TITLE_ENHANCE, description="Enable title enhancement"),
        override_custom_docs: bool = Body(False, description="Override previous custom docs"),
        docs: Json = Body({}, description="Custom docs, must be converted to JSON string",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}]),
        not_refresh_vs_cache: bool = Body(False, description="Do not save vector store yet (for FAISS)"),
) -> BaseResponse:
    """
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    failed_files = {}
    kb_files = []

    for file_name in file_names:
        file_detail = get_file_detail(kb_name=knowledge_base_name, filename=file_name)
        if file_detail.get("custom_docs") and not override_custom_docs:
            continue
        if file_name not in docs:
            try:
                kb_files.append(KnowledgeFile(filename=file_name, knowledge_base_name=knowledge_base_name))
            except Exception as e:
                msg = f"Error loading document {file_name}: {e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                             exc_info=e if log_verbose else None)
                failed_files[file_name] = msg

    for vs_type in DEFAULT_VS_TYPES:
        kb = KBServiceFactory.get_service(knowledge_base_name, vs_type)
        if kb is None:
            continue

        for status, result in files2docs_in_thread(kb_files,
                                                   chunk_size=chunk_size,
                                                   chunk_overlap=chunk_overlap,
                                                   zh_title_enhance=zh_title_enhance):
            if status:
                kb_name, file_name, new_docs = result
                kb_file = KnowledgeFile(filename=file_name,
                                        knowledge_base_name=knowledge_base_name)
                kb_file.splited_docs = new_docs
                kb.update_doc(kb_file, not_refresh_vs_cache=True)
            else:
                kb_name, file_name, error = result
                failed_files[file_name] = error

        for file_name, v in docs.items():
            try:
                v = [x if isinstance(x, Document) else Document(**x) for x in v]
                kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=knowledge_base_name)
                kb.update_doc(kb_file, docs=v, not_refresh_vs_cache=True)
            except Exception as e:
                msg = f"{file_name} Error adding custom docs for: {e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                             exc_info=e if log_verbose else None)
                failed_files[file_name] = msg

        if not not_refresh_vs_cache:
            kb.save_vector_store()

    return BaseResponse(code=200, msg=f"Document update completed", data={"failed_files": failed_files})


def docs_text_split_content(
        knowledge_base_name: str = Body(..., description="Knowledge base name", examples=["samples"]),
        file_names: List[str] = Body(..., description="File names, multiple files supported", examples=[["file_name1", "text.txt"]]),
):
    """
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    results = []
    for vs_type in DEFAULT_VS_TYPES:
        kb = KBServiceFactory.get_service(knowledge_base_name, vs_type)
        if kb is None:
            continue
        kb_results = []
        try:
            for file_name in file_names:
                kb_file = KnowledgeFile(filename=file_name,
                                        knowledge_base_name=knowledge_base_name)
                if not os.path.exists(kb_file.filepath):
                    continue
                text_splitter = None
                splited_docs = kb_file.file2text(text_splitter=text_splitter)
                splited_doc_page_contents = []
                for i, doc in enumerate(splited_docs):
                    splited_doc_page_contents.append(doc.page_content)
                kb_results.append({"file_name": kb_file.filename, "contents": splited_doc_page_contents})
        except Exception as e:
            msg = f"Failed to read file {kb_file.filename}, error: {e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                         exc_info=e if log_verbose else None)
            return BaseResponse(code=500, msg=msg)
        results.append({"vs_type": vs_type, "data": kb_results})
    return BaseResponse(code=200, msg=f"Successfully retrieved document split content", data=results)


def download_doc(
        knowledge_base_name: str = Query(..., description="Knowledge base name", examples=["samples"]),
        file_name: str = Query(..., description="File name", examples=["test.txt"]),
        preview: bool = Query(False, description="True: preview in browser; False: download"),
):
    """
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service(knowledge_base_name, DEFAULT_VS_TYPES[0])
    if kb is None:
        return BaseResponse(code=404, msg=f"Knowledge base not found: {knowledge_base_name}")

    if preview:
        content_disposition_type = "inline"
    else:
        content_disposition_type = None

    try:
        kb_file = KnowledgeFile(filename=file_name,
                                knowledge_base_name=knowledge_base_name)

        if os.path.exists(kb_file.filepath):
            return FileResponse(
                path=kb_file.filepath,
                filename=kb_file.filename,
                media_type="multipart/form-data",
                content_disposition_type=content_disposition_type,
            )
        except Exception as e:
            msg = f"Failed to read file {kb_file.filename}, error: {e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                         exc_info=e if log_verbose else None)
            return BaseResponse(code=500, msg=msg)

    return BaseResponse(code=500, msg=f"Could not read file {kb_file.filename}")
def recreate_vector_store(
        knowledge_base_name: str = Body(..., examples=["samples"]),
        allow_empty_kb: bool = Body(True),
        embed_model: str = Body(EMBEDDING_MODEL),
        chunk_size: int = Body(CHUNK_SIZE, description="Maximum length of a single text segment in knowledge base"),
        chunk_overlap: int = Body(OVERLAP_SIZE, description="Overlapping length of neighboring text"),
        zh_title_enhance: bool = Body(ZH_TITLE_ENHANCE, description="Enable title enhancement"),
        not_refresh_vs_cache: bool = Body(False, description="Do not save vector store yet (for FAISS)"),
):
    """
    recreate vector store from the content.
    this is usefull when user can copy files to content folder directly instead of upload through network.
    by default, get_service only return knowledge base in the info.db and having document files in it.
    set allow_empty_kb to True make it applied on empty knowledge base which it not in the info.db or having no documents.
    """

    def output():
        for vs_type in DEFAULT_VS_TYPES:
            kb = KBServiceFactory.get_service(knowledge_base_name, vs_type, embed_model)
            if kb is None or (not kb.exists() and not allow_empty_kb):
                continue

            if kb.exists():
                kb.clear_vs()
            kb.create_kb()
            files = list_files_from_folder(knowledge_base_name)
            kb_files = [(file, knowledge_base_name) for file in files]
            i = 0
            for status, result in files2docs_in_thread(kb_files,
                                                       chunk_size=chunk_size,
                                                       chunk_overlap=chunk_overlap,
                                                       zh_title_enhance=zh_title_enhance):
                if status:
                    kb_name, file_name, docs = result
                    kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=kb_name)
                    kb_file.splited_docs = docs
                    yield json.dumps({
                        "code": 200,
                        "msg": f"({i + 1} / {len(files)}): {file_name}",
                        "total": len(files),
                        "finished": i + 1,
                        "doc": file_name,
                    }, ensure_ascii=False)
                    kb.add_doc(kb_file, not_refresh_vs_cache=True)
                else:
                    kb_name, file_name, error = result
                    msg = f"Error adding file '{file_name}' to knowledge base '{knowledge_base_name}': {error}. Skipping."
                    logger.error(msg)
                    yield json.dumps({
                        "code": 500,
                        "msg": msg,
                    })
                i += 1
            if not not_refresh_vs_cache:
                kb.save_vector_store()

    return StreamingResponse(output(), media_type="text/event-stream")


def fetch_expert_kb_names() -> List[str]:
    kb_list = {x["kb_name"]: x for x in get_kb_details()}
    if kb_list is None:
        raise Exception("No knowledge base found!")
    kb_names = list(kb_list.keys())

    expert_kb_names = []
    for kb_name in kb_names:
        if "expert" in kb_name.lower():
            expert_kb_names.append(kb_name)

    if len(expert_kb_names) == 0:
        raise Exception("No expert knowledge base found!")

    return expert_kb_names