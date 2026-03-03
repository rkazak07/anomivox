import os

DEFAULT_KNOWLEDGE_BASE = "samples"

DEFAULT_VS_TYPE = "chromadb"

DEFAULT_VS_TYPES = ["chromadb"] # ["es", "chromadb"]

VS_TYPE_PROMPT_TOTAL_BYTE_SIZE = 3000

KNOWLEDGE_USE_CACHE = False

CACHED_VS_NUM = 1

CACHED_MEMO_VS_NUM = 10

CHUNK_SIZE = 500

OVERLAP_SIZE = 50

VECTOR_SEARCH_TOP_K = 3

SCORE_THRESHOLD = 2.0

DEFAULT_SEARCH_ENGINE = "duckduckgo"

SEARCH_ENGINE_TOP_K = 3


# https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/create-bing-search-service-resource
# https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/quickstarts/rest/python
BING_SEARCH_URL = "https://api.bing.microsoft.com/v7.0/search"

BING_SUBSCRIPTION_KEY = ""

METAPHOR_API_KEY = ""


KB_INFO = {
    "samples": "Answers to issues about this project",
}



ORIGINAL_KNOWLEDGE_FILES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "doc2knowledge/uploaded")
if not os.path.exists(ORIGINAL_KNOWLEDGE_FILES_PATH):
    os.mkdir(ORIGINAL_KNOWLEDGE_FILES_PATH)


KB_ROOT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base")
if not os.path.exists(KB_ROOT_PATH):
    os.mkdir(KB_ROOT_PATH)

DB_ROOT_PATH = os.path.join(KB_ROOT_PATH, "info.db")
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_ROOT_PATH}"

kbs_config = {
    "chromadb": {
        "persist_directory": os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
    },
    "es": {
        "host": "127.0.0.1",
        "port": "9200",
        "index_name": "test_index",
        "user": "elastic",
        "password": "xxxxxxxxxxxxxx"
    }
}

text_splitter_dict = {
    "SpacyTextSplitter": {
        "source": "huggingface",
        "tokenizer_name_or_path": "gpt2",
    },
    "RecursiveCharacterTextSplitter": {
        "source": "tiktoken",
        "tokenizer_name_or_path": "cl100k_base",
    },
    "MarkdownHeaderTextSplitter": {
        "headers_to_split_on":
            [
                ("#", "head1"),
                ("##", "head2"),
                ("###", "head3"),
                ("####", "head4"),
                ("\n", "head5"),
            ]
    },
}

TEXT_SPLITTER_NAME = "RecursiveCharacterTextSplitter"

EMBEDDING_KEYWORD_FILE = "embedding_keywords.txt"

ZH_TITLE_ENHANCE = False
