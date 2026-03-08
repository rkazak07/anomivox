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


def _run_db_migrations():
    """Apply incremental DB migrations (safe to run on every startup)."""
    from server.db.base import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        # v2: email column on app_user
        try:
            conn.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS email VARCHAR(255)"))
            conn.commit()
        except Exception:
            conn.rollback()
        # v2: password_reset_token table
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS password_reset_token (
                    id SERIAL PRIMARY KEY,
                    token VARCHAR(64) UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT FALSE
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_password_reset_token_token ON password_reset_token(token)"))
            conn.commit()
        except Exception:
            conn.rollback()


def create_app(run_mode: str = None):
    from server.knowledge_base.migrate import create_tables
    create_tables()
    _run_db_migrations()
    # Initialize default admin user
    from server.db.repository.user_repository import init_admin_user
    init_admin_user()
    # Apply any saved KB settings overrides from JSON
    from configs.kb_settings_config import load_kb_settings_on_startup
    load_kb_settings_on_startup()

    app = FastAPI(
        title="Datachat API Server",
        version=VERSION
    )
    MakeFastAPIOffline(app)
    # Add CORS middleware to allow all origins
    # For CORS settings, see configs/server_config.py
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
            summary="Swagger Documentation")(document)

    # Tag: Auth / User Management
    mount_auth_routes(app)

    # Tag: Chat
    app.post("/chat/fastchat",
             tags=["Chat"],
             summary="Chat with LLM model (via FastChat API)",
             )(openai_chat)

    app.post("/chat/chat",
             tags=["Chat"],
             summary="Chat with LLM model (via LLMChain)",
             )(chat)

    app.post("/chat/search_engine_chat",
             tags=["Chat"],
             summary="Arama motoru ile chat",
             )(search_engine_chat)

    app.post("/chat/feedback",
             tags=["Chat"],
             summary="Return LLM model response score",
             )(chat_feedback)

    mount_knowledge_routes(app)
    mount_kb_auto_ingest_routes(app)
    mount_kb_settings_routes(app)
    mount_filename_summary_routes(app)
    mount_alert_routes(app)
    mount_diagnose_routes(app)
    mount_mail_routes(app)
    mount_telegram_alert_routes(app)
    mount_litellm_routes(app)
    mount_db_target_routes(app)
    mount_dashboard_routes(app)

    from server.utils import all_embed_models

    app.get("/llm_model/list_models",
            response_model=BaseResponse,
            tags=["LLM Model Management"],
            summary="List all configured LLM models",
            )(llm_model)

    app.get("/llm_model/embed_models",
            response_model=BaseResponse,
            tags=["LLM Model Management"],
            summary="List all embedding models",
            )(all_embed_models)

    app.post("/llm_model/list_running_models",
             tags=["LLM Model Management"],
             summary="List loaded models",
             )(list_running_models)

    app.post("/llm_model/list_config_models",
             tags=["LLM Model Management"],
             summary="List configured models",
             )(list_config_models)

    app.post("/llm_model/get_model_config",
             tags=["LLM Model Management"],
             summary="Get model configuration",
             )(get_model_config)

    app.post("/llm_model/stop",
             tags=["LLM Model Management"],
             summary="Belirtilen LLM modelini durdur (Model Worker)",
             )(stop_llm_model)

    app.post("/llm_model/change",
             tags=["LLM Model Management"],
             summary="Switch specified LLM model (Model Worker)",
             )(change_llm_model)

    app.post("/server/configs",
             tags=["Server State"],
             summary="Get server configuration information",
             )(get_server_configs)

    app.post("/server/list_search_engines",
             tags=["Server State"],
             summary="Get supported search engines",
             )(list_search_engines)

    @app.post("/server/get_prompt_template",
              tags=["Server State"],
              summary="Get configured prompt templates")
    def get_server_prompt_template(type: Literal["llm_chat", "structured_data_chat", "knowledge_base_chat", "search_engine_chat", "agent_chat"] = Body(
            "llm_chat", description="Template type: llm_chat, knowledge_base_chat, search_engine_chat, agent_chat"), name: str = Body("default", description="Template name"), ) -> str:
        return get_prompt_template(type=type, name=name)

    app.post("/oteach/completion",
             tags=["Oteach"],
             summary="LLM tamamlama isteği (LLMChain)",
             )(completion)

    app.post("/oteach/embed_texts",
             tags=["Oteach"],
             summary="Metni vektörleştir (yerel ve online model desteği)",
             )(embed_texts_endpoint)


def mount_auth_routes(app: FastAPI):
    from server.auth.auth_api import (
        login, logout, current_user_info, api_list_users, api_create_user,
        api_toggle_user, api_delete_user, api_change_password, api_change_my_password,
        api_update_user_email, api_forgot_password, api_reset_password,
    )
    app.post("/auth/login", tags=["Auth"], response_model=BaseResponse, summary="Kullanici girisi")(login)
    app.post("/auth/logout", tags=["Auth"], response_model=BaseResponse, summary="Kullanici cikisi")(logout)
    app.get("/auth/me", tags=["Auth"], response_model=BaseResponse, summary="Mevcut kullanici bilgisi")(current_user_info)
    app.get("/auth/list_users", tags=["Auth"], response_model=BaseResponse, summary="Kullanicilari listele (admin)")(api_list_users)
    app.post("/auth/create_user", tags=["Auth"], response_model=BaseResponse, summary="Yeni kullanici olustur (admin)")(api_create_user)
    app.post("/auth/toggle_user", tags=["Auth"], response_model=BaseResponse, summary="Kullaniciyi aktif/deaktif et (admin)")(api_toggle_user)
    app.post("/auth/delete_user", tags=["Auth"], response_model=BaseResponse, summary="Kullaniciyi sil (admin)")(api_delete_user)
    app.post("/auth/change_password", tags=["Auth"], response_model=BaseResponse, summary="Kullanici sifresini degistir (admin)")(api_change_password)
    app.post("/auth/change_my_password", tags=["Auth"], response_model=BaseResponse, summary="Kendi sifresini degistir")(api_change_my_password)
    app.post("/auth/update_user_email", tags=["Auth"], response_model=BaseResponse, summary="Kullanici e-postasini guncelle (admin)")(api_update_user_email)
    app.post("/auth/forgot_password", tags=["Auth"], response_model=BaseResponse, summary="Parola sifirlama maili gonder")(api_forgot_password)
    app.post("/auth/reset_password", tags=["Auth"], response_model=BaseResponse, summary="Parola sifirla")(api_reset_password)

    # Conversation yönetimi
    from server.chat.conversation_api import (
        api_create_conversation, api_list_conversations,
        api_conversation_messages, api_rename_conversation, api_delete_conversation,
    )
    app.post("/chat/conversations", tags=["Chat"], response_model=BaseResponse, summary="Yeni konuşma oluştur")(api_create_conversation)
    app.get("/chat/conversations", tags=["Chat"], response_model=BaseResponse, summary="Konuşmaları listele")(api_list_conversations)
    app.get("/chat/conversations/{conversation_id}/messages", tags=["Chat"], response_model=BaseResponse, summary="Konuşma mesajları")(api_conversation_messages)
    app.post("/chat/conversations/rename", tags=["Chat"], response_model=BaseResponse, summary="Konuşmayı yeniden adlandır")(api_rename_conversation)
    app.post("/chat/conversations/delete", tags=["Chat"], response_model=BaseResponse, summary="Konuşmayı sil")(api_delete_conversation)





def mount_mail_routes(app: FastAPI):
    from server.mail_service.mail_config_api import (
        get_mail_config, save_mail_config, test_mail_connection
    )
    app.get("/mail/config", tags=["Mail"], response_model=BaseResponse, summary="Mail ayarlarını getir (admin)")(get_mail_config)
    app.post("/mail/config", tags=["Mail"], response_model=BaseResponse, summary="Mail ayarlarını kaydet (admin)")(save_mail_config)
    app.post("/mail/test", tags=["Mail"], response_model=BaseResponse, summary="SMTP bağlantı testi (admin)")(test_mail_connection)


def mount_telegram_alert_routes(app: FastAPI):
    from server.telegram.telegram_alert_api import (
        get_telegram_alert_config, save_telegram_alert_config,
        test_telegram_alert, telegram_get_chat_id
    )
    app.get("/telegram/config", tags=["Telegram"], response_model=BaseResponse, summary="Telegram alert ayarlarını getir")(get_telegram_alert_config)
    app.post("/telegram/config", tags=["Telegram"], response_model=BaseResponse, summary="Telegram alert ayarlarını kaydet")(save_telegram_alert_config)
    app.post("/telegram/test", tags=["Telegram"], response_model=BaseResponse, summary="Telegram test mesajı gönder")(test_telegram_alert)
    app.get("/telegram/chatid", tags=["Telegram"], response_model=BaseResponse, summary="Telegram chat ID bul")(telegram_get_chat_id)


def mount_litellm_routes(app: FastAPI):
    from server.litellm.litellm_api import (
        litellm_health, litellm_list_models, litellm_add_model,
        litellm_remove_model, litellm_test_model, dba_agent_health,
        litellm_get_config, litellm_update_settings,
    )
    app.get("/litellm/health", tags=["LiteLLM"], response_model=BaseResponse, summary="LiteLLM Proxy durumu")(litellm_health)
    app.get("/litellm/models", tags=["LiteLLM"], response_model=BaseResponse, summary="Model listesi")(litellm_list_models)
    app.post("/litellm/models/add", tags=["LiteLLM"], response_model=BaseResponse, summary="Model ekle/güncelle")(litellm_add_model)
    app.post("/litellm/models/remove", tags=["LiteLLM"], response_model=BaseResponse, summary="Model sil")(litellm_remove_model)
    app.post("/litellm/models/test", tags=["LiteLLM"], response_model=BaseResponse, summary="Model test et")(litellm_test_model)
    app.get("/litellm/config", tags=["LiteLLM"], response_model=BaseResponse, summary="LiteLLM config getir")(litellm_get_config)
    app.post("/litellm/settings", tags=["LiteLLM"], response_model=BaseResponse, summary="Genel ayarları güncelle")(litellm_update_settings)
    app.get("/litellm/dba-agent/health", tags=["LiteLLM"], response_model=BaseResponse, summary="DBA Agent durumu")(dba_agent_health)


def mount_db_target_routes(app: FastAPI):
    from server.db_targets.db_target_api import (
        list_db_targets, add_db_target, update_db_target,
        delete_db_target, test_db_target, set_primary_db_target,
        test_ssh_target,
    )
    app.get("/db-targets/list", tags=["DB Targets"], response_model=BaseResponse, summary="DB bağlantılarını listele")(list_db_targets)
    app.post("/db-targets/add", tags=["DB Targets"], response_model=BaseResponse, summary="DB bağlantısı ekle")(add_db_target)
    app.post("/db-targets/update", tags=["DB Targets"], response_model=BaseResponse, summary="DB bağlantısı güncelle")(update_db_target)
    app.post("/db-targets/delete", tags=["DB Targets"], response_model=BaseResponse, summary="DB bağlantısı sil")(delete_db_target)
    app.post("/db-targets/test", tags=["DB Targets"], response_model=BaseResponse, summary="DB bağlantısını test et")(test_db_target)
    app.post("/db-targets/test-ssh", tags=["DB Targets"], response_model=BaseResponse, summary="SSH bağlantısını test et")(test_ssh_target)
    app.post("/db-targets/set-primary", tags=["DB Targets"], response_model=BaseResponse, summary="Primary DB ayarla")(set_primary_db_target)


def mount_diagnose_routes(app: FastAPI):

    from server.diagnose.diagnose import run_diagnose, get_diagnose_terminal_output, get_diagnose_serialization_output, diagnose_user_feedback, stop_diagnose, save_diagnose_file, diagnose_status

    app.post("/diagnose/save_diagnose_file",
             tags=["Diagnose"],
             response_model=BaseResponse,
             summary="Tanı anomali filenı load")(save_diagnose_file)

    app.get("/diagnose/diagnose_status",
            tags=["Diagnose"],
            response_model=BaseResponse,
            summary="Tanı durumu")(diagnose_status)

    app.post("/diagnose/run_diagnose",
             tags=["Diagnose"],
             response_model=BaseResponse,
             summary="Diagnose anomaly file")(run_diagnose)

    app.get("/diagnose/terminal_output",
            tags=["Diagnose"],
            response_model=BaseResponse,
            summary="Tanı terminal çıktısını getir")(get_diagnose_terminal_output)

    app.get("/diagnose/serialization_output",
            tags=["Diagnose"],
            response_model=BaseResponse,
            summary="Tanı formatlendirilmiş çıktısını getir")(get_diagnose_serialization_output)

    app.post("/diagnose/stop_diagnose",
             tags=["Diagnose"],
             response_model=BaseResponse,
             summary="Stop anomaly diagnosis")(stop_diagnose)

    app.post("/diagnose/user_feedback",
             tags=["Diagnose"],
             response_model=BaseResponse,
             summary="Kullanıcı geri bildirimi ekle")(diagnose_user_feedback)


def mount_dashboard_routes(app: FastAPI):
    from server.dashboard.dashboard_api import (
        dashboard_overview, dashboard_health, dashboard_pipeline_status
    )
    app.post("/dashboard/overview",
             tags=["Dashboard"],
             response_model=BaseResponse,
             summary="Platform genel bakış — skor, KPI, altyapı, aktivite")(dashboard_overview)
    app.get("/dashboard/health",
            tags=["Dashboard"],
            response_model=BaseResponse,
            summary="Servis sağlık durumu")(dashboard_health)
    app.get("/dashboard/pipeline_status",
            tags=["Dashboard"],
            response_model=BaseResponse,
            summary="Pipeline zincir durumu")(dashboard_pipeline_status)


def mount_alert_routes(app: FastAPI):
    from server.report.report import histories, history_detail, diagnose_llm_model_list

    app.post("/report/histories",
             tags=["Alert"],
             response_model=BaseResponse,
             summary="Tüm anomali diagnosis dosyalarını list")(histories)

    app.post("/report/history_detail",
             tags=["Alert"],
             response_model=BaseResponse,
             summary="Get anomaly diagnosis file details")(history_detail)

    app.post("/report/diagnose_llm_model_list",
             tags=["Alert"],
             response_model=BaseResponse,
             summary="Get anomaly diagnosis model list")(diagnose_llm_model_list)


def mount_kb_auto_ingest_routes(app: FastAPI):
    from server.knowledge_base.kb_auto_ingest_api import (
        api_get_auto_ingest_config,
        api_save_auto_ingest_config,
        api_manual_ingest,
        api_ingest_stats,
    )
    app.get("/knowledge_base/auto_ingest/config",
            tags=["Knowledge Base Auto-Ingest"],
            response_model=BaseResponse,
            summary="Get auto-ingest configuration")(api_get_auto_ingest_config)
    app.post("/knowledge_base/auto_ingest/config",
             tags=["Knowledge Base Auto-Ingest"],
             response_model=BaseResponse,
             summary="Save auto-ingest configuration")(api_save_auto_ingest_config)
    app.post("/knowledge_base/auto_ingest/manual",
             tags=["Knowledge Base Auto-Ingest"],
             response_model=BaseResponse,
             summary="Manually ingest a diagnosis file into KB")(api_manual_ingest)
    app.get("/knowledge_base/auto_ingest/stats",
            tags=["Knowledge Base Auto-Ingest"],
            response_model=BaseResponse,
            summary="Get auto-ingest statistics")(api_ingest_stats)


def mount_kb_settings_routes(app: FastAPI):
    from server.knowledge_base.kb_settings_api import (
        api_get_kb_settings,
        api_save_kb_settings,
    )
    app.get("/knowledge_base/settings/config",
            tags=["Knowledge Base Settings"],
            response_model=BaseResponse,
            summary="Get KB general settings")(api_get_kb_settings)
    app.post("/knowledge_base/settings/config",
             tags=["Knowledge Base Settings"],
             response_model=BaseResponse,
             summary="Save KB general settings")(api_save_kb_settings)


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
             summary="Knowledge base ile chat")(knowledge_base_chat)

    app.post("/chat/file_chat",
             tags=["Knowledge Base Management"],
             summary="Dosya Sohbeti"
             )(file_chat)

    app.post("/chat/agent_chat",
             tags=["Chat"],
             summary="Agent ile chat")(agent_chat)

    app.get("/knowledge_base/kb_file_details",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="Knowledge base filenı getir")(kb_file_details)

    app.get("/knowledge_base/list_knowledge_bases",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="Knowledge base list ofni getir")(list_kbs)

    app.post("/knowledge_base/create_knowledge_base",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Create knowledge base"
             )(create_kb)

    app.post("/knowledge_base/delete_knowledge_base",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Knowledge basenı delete"
             )(delete_kb)

    app.get("/knowledge_base/detail",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="Knowledge base detayı"
            )(kb_detail)

    app.get("/knowledge_base/list_files",
            tags=["Knowledge Base Management"],
            response_model=ListResponse,
            summary="Knowledge basendaki dosya list ofni getir"
            )(list_files)

    app.post("/knowledge_base/search_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Knowledge basenda search yap"
             )(api_search_docs)

    app.post("/knowledge_base/upload_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Load file to knowledge base and/or vectorize"
             )(upload_docs)

    app.post("/knowledge_base/delete_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Knowledge basendaki belirtilen dosyayı delete"
             )(delete_docs)

    app.post("/knowledge_base/update_info",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Update knowledge base description"
             )(update_info)
    app.post("/knowledge_base/update_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="Mevcut dosyaları bilgi tabanında update"
             )(update_docs)

    app.get("/knowledge_base/download_doc",
            tags=["Knowledge Base Management"],
            summary="İlgili bilgi filenı download")(download_doc)

    app.post("/knowledge_base/docs_text_split_content",
             tags=["Knowledge Base Management"],
             summary="İlgili bilgi filenın dilim içeriğini download")(docs_text_split_content)

    app.post("/knowledge_base/recreate_vector_store",
             tags=["Knowledge Base Management"],
             summary="İçerikteki belgelerden vektör deposunu yeniden oluştur, akış çıktısı ile ilerlemeyi göster."
             )(recreate_vector_store)

    app.post("/knowledge_base/upload_temp_docs",
             tags=["Knowledge Base Management"],
             summary="Load file to temporary directory, Use for File Chat"
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
