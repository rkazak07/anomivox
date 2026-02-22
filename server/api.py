from typing import List, Literal
from server.utils import (
    BaseResponse,
    ListResponse,
    FastAPI,
    MakeFastAPIOffline,
    get_server_configs,
    get_prompt_template)
from server.llm_api import (list_running_models, list_config_models,
                            change_llm_model, stop_llm_model,
                            get_model_config, list_search_engines, llm_model)
from server.embeddings_api import embed_texts_endpoint
from server.chat.feedback import chat_feedback
from server.chat.completion import completion
from server.chat.search_engine_chat import search_engine_chat
from server.chat.openai_chat import openai_chat
from server.chat.chat import chat
from starlette.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
import uvicorn
import argparse
from configs.server_config import OPEN_CROSS_DOMAIN
from configs.model_config import NLTK_DATA_PATH
from configs import VERSION
import nltk
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


nltk.data.path = [NLTK_DATA_PATH] + nltk.data.path


async def document():
    return RedirectResponse(url="/docs")


def create_app(run_mode: str = None):
    app = FastAPI(
        title="Datachat API Server",
        version=VERSION
    )
    MakeFastAPIOffline(app)
    # Add CORS middleware to allow all origins
    # CORS ayarları için configs/server_config.py dosyasına bakın
    # set OPEN_DOMAIN=True in config.py to allow cross-domain
    if OPEN_CROSS_DOMAIN:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    mount_app_routes(app, run_mode=run_mode)
    return app


def mount_app_routes(app: FastAPI, run_mode: str = None):
    app.get("/",
            response_model=BaseResponse,
            summary="Swagger Dokümantasyonu")(document)

    # Tag: Chat
    app.post("/chat/fastchat",
             tags=["Chat"],
             summary="LLM modeli ile sohbet (FastChat API üzerinden)",
             )(openai_chat)

    app.post("/chat/chat",
             tags=["Chat"],
             summary="LLM modeli ile sohbet (LLMChain üzerinden)",
             )(chat)

    app.post("/chat/search_engine_chat",
             tags=["Chat"],
             summary="Arama motoru ile sohbet",
             )(search_engine_chat)

    app.post("/chat/feedback",
             tags=["Chat"],
             summary="LLM modeli yanıt puanını döndür",
             )(chat_feedback)

    mount_knowledge_routes(app)
    mount_filename_summary_routes(app)
    mount_alert_routes(app)
    mount_diagnose_routes(app)

    from server.utils import all_embed_models

    app.get("/llm_model/list_models",
            response_model=BaseResponse,
            tags=["LLM Model Management"],
            summary="Yapılandırılmış tüm LLM modellerini listele",
            )(llm_model)

    app.get("/llm_model/embed_models",
            response_model=BaseResponse,
            tags=["LLM Model Management"],
            summary="Tüm Embedding modellerini listele",
            )(all_embed_models)

    app.post("/llm_model/list_running_models",
             tags=["LLM Model Management"],
             summary="Yüklü modelleri listele",
             )(list_running_models)

    app.post("/llm_model/list_config_models",
             tags=["LLM Model Management"],
             summary="Yapılandırılmış modelleri listele",
             )(list_config_models)

    app.post("/llm_model/get_model_config",
             tags=["LLM Model Management"],
             summary="Model yapılandırmasını getir",
             )(get_model_config)

    app.post("/llm_model/stop",
             tags=["LLM Model Management"],
             summary="Belirtilen LLM modelini durdur (Model Worker)",
             )(stop_llm_model)

    app.post("/llm_model/change",
             tags=["LLM Model Management"],
             summary="Belirtilen LLM modelini değiştir (Model Worker)",
             )(change_llm_model)

    app.post("/server/configs",
             tags=["Server State"],
             summary="Sunucu yapılandırma bilgisini getir",
             )(get_server_configs)

    app.post("/server/list_search_engines",
             tags=["Server State"],
             summary="Desteklenen arama motorlarını getir",
             )(list_search_engines)

    @app.post("/server/get_prompt_template",
              tags=["Server State"],
              summary="Yapılandırılmış prompt şablonlarını getir")
    def get_server_prompt_template(type: Literal["llm_chat", "structured_data_chat", "knowledge_base_chat", "search_engine_chat", "agent_chat"] = Body(
            "llm_chat", description="Şablon türü: llm_chat, knowledge_base_chat, search_engine_chat, agent_chat"), name: str = Body("default", description="Şablon adı"), ) -> str:
        return get_prompt_template(type=type, name=name)

    app.post("/other/completion",
             tags=["Other"],
             summary="LLM tamamlama isteği (LLMChain)",
             )(completion)

    app.post("/other/embed_texts",
             tags=["Other"],
             summary="Metni vektörleştir (yerel ve online model desteği)",
             )(embed_texts_endpoint)


def mount_diagnose_routes(app: FastAPI):

    from server.diagnose.diagnose import run_diagnose, get_diagnose_terminal_output, get_diagnose_serialization_output, diagnose_user_feedback, stop_diagnose, save_diagnose_file, diagnose_status

    app.post("/diagnose/save_diagnose_file",
             tags=["Diagnose"],
             response_model=BaseResponse,
             summary="Tanı anomali dosyasını yükle")(save_diagnose_file)

    app.get("/diagnose/diagnose_status",
            tags=["Diagnose"],
            response_model=BaseResponse,
            summary="Tanı durumu")(diagnose_status)

    app.post("/diagnose/run_diagnose",
             tags=["Diagnose"],
             response_model=BaseResponse,
             summary="Anomali dosyasını tanı")(run_diagnose)

    app.get("/diagnose/terminal_output",
            tags=["Diagnose"],
            response_model=BaseResponse,
            summary="Tanı terminal çıktısını getir")(get_diagnose_terminal_output)

    app.get("/diagnose/serialization_output",
            tags=["Diagnose"],
            response_model=BaseResponse,
            summary="Tanı biçimlendirilmiş çıktısını getir")(get_diagnose_serialization_output)

    app.post("/diagnose/stop_diagnose",
             tags=["Diagnose"],
             response_model=BaseResponse,
             summary="Anomali tanısını sonlandır")(stop_diagnose)

    app.post("/diagnose/user_feedback",
             tags=["Diagnose"],
             response_model=BaseResponse,
             summary="Kullanıcı geri bildirimi ekle")(diagnose_user_feedback)


def mount_alert_routes(app: FastAPI):
    from server.report.report import histories, history_detail, diagnose_llm_model_list

    app.post("/report/histories",
             tags=["Alert"],
             response_model=BaseResponse,
             summary="Tüm anomali tanı dosyalarını listele")(histories)

    app.post("/report/history_detail",
             tags=["Alert"],
             response_model=BaseResponse,
             summary="Anomali tanı dosyası detayını getir")(history_detail)

    app.post("/report/diagnose_llm_model_list",
             tags=["Alert"],
             response_model=BaseResponse,
             summary="Anomali tanı model listesini getir")(diagnose_llm_model_list)


def mount_knowledge_routes(app: FastAPI):
    from server.chat.knowledge_base_chat import knowledge_base_chat
    from server.chat.file_chat import upload_temp_docs, file_chat
    from server.chat.agent_chat import agent_chat
    from server.knowledge_base.kb_api import list_kbs, create_kb, delete_kb, kb_detail
    from server.knowledge_base.kb_doc_api import (
        list_files,
        kb_file_details,
        upload_docs,
        delete_docs,
        update_docs,
        download_doc,
        recreate_vector_store,
        api_search_docs,
        update_info,
        docs_text_split_content)

    app.post("/chat/knowledge_base_chat",
             tags=["Chat"],
             summary="Bilgi tabanı ile sohbet")(knowledge_base_chat)

    app.post("/chat/file_chat",
             tags=["Knowledge Base Management"],
             summary="Dosya Sohbeti"
             )(file_chat)

    app.post("/chat/agent_chat",
             tags=["Chat"],
             summary="Agent ile sohbet")(agent_chat)

    app.get("/knowledge_base/kb_file_details",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="Bilgi tabanı dosyasını getir")(kb_file_details)

    app.get("/knowledge_base/list_knowledge_bases",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="Bilgi tabanı listesini getir")(list_kbs)

    app.post("/knowledge_base/create_knowledge_base",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Bilgi tabanı oluştur"
             )(create_kb)

    app.post("/knowledge_base/delete_knowledge_base",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Bilgi tabanını sil"
             )(delete_kb)

    app.get("/knowledge_base/detail",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="Bilgi tabanı detayı"
            )(kb_detail)

    app.get("/knowledge_base/list_files",
            tags=["Knowledge Base Management"],
            response_model=ListResponse,
            summary="Bilgi tabanındaki dosya listesini getir"
            )(list_files)

    app.post("/knowledge_base/search_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Bilgi tabanında arama yap"
             )(api_search_docs)

    app.post("/knowledge_base/upload_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Dosyayı bilgi tabanına yükle ve/veya vektörleştir"
             )(upload_docs)

    app.post("/knowledge_base/delete_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Bilgi tabanındaki belirtilen dosyayı sil"
             )(delete_docs)

    app.post("/knowledge_base/update_info",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Bilgi tabanı açıklamasını güncelle"
             )(update_info)
    app.post("/knowledge_base/update_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Mevcut dosyaları bilgi tabanında güncelle"
             )(update_docs)

    app.get("/knowledge_base/download_doc",
            tags=["Knowledge Base Management"],
            summary="İlgili bilgi dosyasını indir")(download_doc)

    app.post("/knowledge_base/docs_text_split_content",
             tags=["Knowledge Base Management"],
             summary="İlgili bilgi dosyasının dilim içeriğini indir")(docs_text_split_content)

    app.post("/knowledge_base/recreate_vector_store",
             tags=["Knowledge Base Management"],
             summary="İçerikteki belgelerden vektör deposunu yeniden oluştur, akış çıktısı ile ilerlemeyi göster."
             )(recreate_vector_store)

    app.post("/knowledge_base/upload_temp_docs",
             tags=["Knowledge Base Management"],
             summary="Dosyayı geçici dizine yükle, Dosya Sohbeti için kullan."
             )(upload_temp_docs)


def mount_filename_summary_routes(app: FastAPI):
    from server.knowledge_base.kb_summary_api import (
        summary_file_to_vector_store,
        recreate_summary_vector_store,
        summary_doc_ids_to_vector_store)

    app.post("/knowledge_base/kb_summary_api/summary_file_to_vector_store",
             tags=["Knowledge kb_summary_api Management"],
             summary="Tek bilgi tabanını dosya adına göre özetle"
             )(summary_file_to_vector_store)
    app.post("/knowledge_base/kb_summary_api/summary_doc_ids_to_vector_store",
             tags=["Knowledge kb_summary_api Management"],
             summary="Tek bilgi tabanını doc_ids'e göre özetle",
             response_model=BaseResponse,
             )(summary_doc_ids_to_vector_store)
    app.post("/knowledge_base/kb_summary_api/recreate_summary_vector_store",
             tags=["Knowledge kb_summary_api Management"],
             summary="Tek bilgi tabanı dosya özetini yeniden oluştur"
             )(recreate_summary_vector_store)


def run_api(host, port, **kwargs):
    if kwargs.get("ssl_keyfile") and kwargs.get("ssl_certfile"):
        uvicorn.run(app,
                    host=host,
                    port=port,
                    ssl_keyfile=kwargs.get("ssl_keyfile"),
                    ssl_certfile=kwargs.get("ssl_certfile"),
                    )
    else:
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='langchain-ChatGLM',
        description='About langchain-ChatGLM, local knowledge based ChatGLM with langchain'
         ' | Yerel bilgi tabanı tabanlı ChatGLM soru-cevap')
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7861)
    parser.add_argument("--ssl_keyfile", type=str)
    parser.add_argument("--ssl_certfile", type=str)
    args = parser.parse_args()
    args_dict = vars(args)

    app = create_app()

    run_api(host=args.host,
            port=args.port,
            ssl_keyfile=args.ssl_keyfile,
            ssl_certfile=args.ssl_certfile,
            )
