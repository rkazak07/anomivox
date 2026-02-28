from fastapi import Body, Header
from fastapi.responses import StreamingResponse
from configs import LLM_MODELS, TEMPERATURE
from server.utils import wrap_done, get_ChatOpenAI
from langchain.chains import LLMChain
from langchain.callbacks import AsyncIteratorCallbackHandler
from typing import AsyncIterable
import asyncio
import json
from langchain.prompts.chat import ChatPromptTemplate
from typing import List, Optional, Union
from server.chat.utils import History
from langchain.prompts import PromptTemplate
from server.utils import get_prompt_template
from server.memory.conversation_db_buffer_memory import ConversationBufferDBMemory
from server.db.repository import add_message_to_db
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler


async def chat(query: str = Body(..., description="User input", examples=["hello"]),
               conversation_id: str = Body("", description="Conversation ID"),
               history_len: int = Body(-1, description="Number of history messages to retrieve from database"),
               history: Union[int, List[History]] = Body([],
                                                         description="Conversation history; if integer value is given, read from database",
                                                         examples=[[
                                                             {"role": "user", "content": "Hello"},
                                                             {"role": "assistant", "content": "Tigerly brave"}]]
                                                         ),
               stream: bool = Body(False, description="Stream output"),
               model_name: str = Body(LLM_MODELS[0], description="LLM model name"),
               temperature: float = Body(TEMPERATURE, description="LLM sampling temperature", ge=0.0, le=1.0),
               max_tokens: Optional[int] = Body(None, description="Limit LLM generated token count, None defaults to model maximum"),
               prompt_name: str = Body("default", description="Prompt template name used (configured in configs/prompt_config.py)"),
               authorization: Optional[str] = Header(None),
               ):
    async def chat_iterator() -> AsyncIterable[str]:
        nonlocal history, max_tokens
        callback = AsyncIteratorCallbackHandler()
        callbacks = [callback]
        memory = None

        if conversation_id:
            # Conversation sahibini bagla ve yetki kontrolu yap
            from server.auth.auth_api import _get_current_user
            from server.db.repository.conversation_repository import add_conversation_to_db, get_conversation_by_id
            current_user = _get_current_user(authorization)
            user_id = current_user["id"] if current_user else None
            is_admin = current_user.get("is_admin", False) if current_user else False

            existing = get_conversation_by_id(conversation_id)
            if existing is None:
                add_conversation_to_db(
                    chat_type="llm_chat",
                    name="",
                    conversation_id=conversation_id,
                    user_id=user_id,
                )
            else:
                conv_owner = existing.get("user_id")
                # Admin baska kullanicinin sohbetine yazamaz
                if is_admin and conv_owner is not None and conv_owner != user_id:
                    import json as _json
                    yield _json.dumps({
                        "answer": "[Hata: Yonetici baska kullanicilarin sohbetlerine mesaj yazamaz]",
                        "conversation_id": conversation_id,
                        "message_id": ""
                    }) + "\n"
                    return
                # Sahipsiz konusmayi sahiplendir
                if conv_owner is None and user_id is not None:
                    from server.db.session import with_session as _ws
                    from server.db.models.conversation_model import ConversationModel as _CM
                    @_ws
                    def _set_owner(session, cid=conversation_id, uid=user_id):
                        c = session.query(_CM).filter_by(id=cid).first()
                        if c:
                            c.user_id = uid
                    _set_owner()

            message_id = add_message_to_db(chat_type="llm_chat", query=query, conversation_id=conversation_id)
            conversation_callback = ConversationCallbackHandler(conversation_id=conversation_id, message_id=message_id,
                                                                chat_type="llm_chat",
                                                                query=query)
            callbacks.append(conversation_callback)
        else:
        # (Lyn)
            message_id = 0

        if isinstance(max_tokens, int) and max_tokens <= 0:
            max_tokens = None

        model = get_ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=callbacks,
        )

        if history:
            history = [History.from_data(h) for h in history]
            prompt_template = get_prompt_template("llm_chat", prompt_name)
            input_msg = History(role="user", content=prompt_template).to_msg_template(False)
            chat_prompt = ChatPromptTemplate.from_messages(
                [i.to_msg_template() for i in history] + [input_msg])
        elif conversation_id and history_len > 0:
            history_key = "with_history_tr" if prompt_name == "tr" else "with_history"
            prompt = get_prompt_template("llm_chat", history_key)
            chat_prompt = PromptTemplate.from_template(prompt)
            memory = ConversationBufferDBMemory(conversation_id=conversation_id,
                                                llm=model,
                                                message_limit=history_len)
        else:
            prompt_template = get_prompt_template("llm_chat", prompt_name)
            input_msg = History(role="user", content=prompt_template).to_msg_template(False)
            chat_prompt = ChatPromptTemplate.from_messages([input_msg])

        chain = LLMChain(prompt=chat_prompt, llm=model, memory=memory)

        # Begin a task that runs in the background.
        task = asyncio.create_task(wrap_done(
            chain.acall({"input": query}),
            callback.done),
        )

        if stream:
            async for token in callback.aiter():
                # Use server-sent-events to stream the response
                yield json.dumps(
                    {"text": token, "message_id": message_id},
                    ensure_ascii=False)
        else:
            answer = ""
            async for token in callback.aiter():
                answer += token
            yield json.dumps(
                {"text": answer, "message_id": message_id},
                ensure_ascii=False)

        await task

    return StreamingResponse(chat_iterator(), media_type="text/event-stream")
