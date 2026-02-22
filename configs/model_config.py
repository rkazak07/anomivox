import os

MODEL_ROOT_PATH = ""

EMBEDDING_MODEL = "text-embedding-ada-002"  # m3e-base

EMBEDDING_DEVICE = "auto"

EMBEDDING_KEYWORD_FILE = "keywords.txt"

EMBEDDING_MODEL_OUTPUT_PATH = "output"

LLM_MODELS = ["openai-api"] # ["chatglm3-6b", "zhipu-api", "openai-api"] # "Qwen-1_8B-Chat",

Agent_MODEL = None

LLM_DEVICE = "auto"

HISTORY_LEN = 3

MAX_TOKENS = None

TEMPERATURE = 0.7

ONLINE_LLM_MODEL = {
    "openai-api": {
        "model_name": "gpt-4-0613",
        "api_base_url": "https://api.openai.com/v1",
        "api_key": "",
        "openai_proxy": "",
    },
    # advise vLLM>=0.3.0, start the server with a chat model
    # python -m vllm.entrypoints.openai.api_server --served-model-name Qwen1.5-14B-Chat --model your_local_qwen_model_path
    "qwen1.5-vllm": {
        "model_name": "Qwen1.5-14B-Chat",
        "api_base_url": "http://127.0.0.1:8000/v1",
        "api_key": "EMPTY"
    }
}

#           - text2vec
#           - GanymedeNil/text2vec-large-chinese
#           - text2vec-large-chinese
MODEL_PATH = {
    "embed_model": {
        "text-embedding-ada-002": "your OPENAI_API_KEY",
    },

    "llm_model": {
        "chatglm2-6b": "THUDM/chatglm2-6b"
    },
}



NLTK_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nltk_data")

VLLM_MODEL_DICT = {
    "chatglm2-6b": "THUDM/chatglm2-6b"
}


SUPPORT_AGENT_MODEL = []