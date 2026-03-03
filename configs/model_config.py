import os

MODEL_ROOT_PATH = ""

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

EMBEDDING_DEVICE = "auto"

EMBEDDING_KEYWORD_FILE = "keywords.txt"

EMBEDDING_MODEL_OUTPUT_PATH = "output"

LLM_MODELS = ["groq-api"] # ["openai-api", "gemini-api", "chatglm3-6b"]

Agent_MODEL = None

LLM_DEVICE = "auto"

HISTORY_LEN = 3

MAX_TOKENS = None

TEMPERATURE = 0.7

ONLINE_LLM_MODEL = {
    "groq-api": {
        "model_name": "llama-3.3-70b-versatile",
        "api_base_url": "https://api.groq.com/openai/v1",
        "api_key": "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",
    },
    "openai-api": {
        "model_name": "gpt-4-0613",
        "api_base_url": "https://api.openai.com/v1",
        "api_key": "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",
        "openai_proxy": "",
    },
    "gemini-api": {
        "model_name": "gemini-2.0-flash",
        "api_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": "",
    },
    # advise vLLM>=0.3.0, start the server with a chat model
    # python -m vllm.entrypoints.openai.api_server --served-model-name Qwen1.5-14B-Chat --model your_local_qwen_model_path
    "qwen1.5-vllm": {
        "model_name": "Qwen1.5-14B-Chat",
        "api_base_url": "http://127.0.0.1:8000/v1",
        "api_key": "EMPTY"
    }
}

MODEL_PATH = {
    "embed_model": {
        "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
        "all-MiniLM-L12-v2": "sentence-transformers/all-MiniLM-L12-v2",
        "all-mpnet-base-v2": "sentence-transformers/all-mpnet-base-v2",
        "paraphrase-multilingual-MiniLM-L12-v2": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "paraphrase-multilingual-mpnet-base-v2": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    },

    "llm_model": {},
}



NLTK_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nltk_data")

VLLM_MODEL_DICT = {}


SUPPORT_AGENT_MODEL = []

# ─────────────────────────────────────────
# Environment Variable Configuration
# ─────────────────────────────────────────

# Load API keys from environment variables
if os.getenv("OPENAI_API_KEY"):
    ONLINE_LLM_MODEL["openai-api"]["api_key"] = os.getenv("OPENAI_API_KEY")

if os.getenv("GEMINI_API_KEY"):
    ONLINE_LLM_MODEL["gemini-api"]["api_key"] = os.getenv("GEMINI_API_KEY")

if os.getenv("GROQ_API_KEY"):
    ONLINE_LLM_MODEL["groq-api"]["api_key"] = os.getenv("GROQ_API_KEY")
