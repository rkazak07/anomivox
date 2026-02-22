from langchain.docstore.document import Document
from configs import EMBEDDING_MODEL, logger
from server.model_workers.base import ApiEmbeddingsParams
from server.utils import BaseResponse, get_model_worker_config, list_embed_models, list_online_embed_models
from fastapi import Body
from typing import Dict, List


online_embed_models = list_online_embed_models()


def embed_texts(
    texts: List[str],
    embed_model: str = EMBEDDING_MODEL,
    to_query: bool = False,
) -> BaseResponse:
    '''
    Vectorize text. Return format: BaseResponse(data=List[List[float]])
    '''
    try:
        if embed_model in list_embed_models():
            from server.utils import load_local_embeddings

            embeddings = load_local_embeddings(model=embed_model)
            return BaseResponse(data=embeddings.embed_documents(texts))

        if embed_model in list_online_embed_models():
            config = get_model_worker_config(embed_model)
            worker_class = config.get("worker_class")
            worker = worker_class()
            if worker_class.can_embedding():
                params = ApiEmbeddingsParams(texts=texts, to_query=to_query)
                resp = worker.do_embeddings(params)
                return BaseResponse(**resp)

        return BaseResponse(code=500, msg=f"The specified model {embed_model} does not support Embeddings.")
    except Exception as e:
        logger.error(e)
        return BaseResponse(code=500, msg=f"Error occurred during text vectorization: {e}")

def embed_texts_endpoint(
    texts: List[str] = Body(..., description="List of texts to embed", examples=[["hello", "world"]]),
    embed_model: str = Body(EMBEDDING_MODEL, description=f"Embedding model to use. Supports local Embedding models and online API ({online_embed_models}) embedding services."),
    to_query: bool = Body(False, description="Whether the vector is for querying. Some models like Minimax optimize storage/query vectors differently."),
) -> BaseResponse:
    '''
    Vectorize text, returns BaseResponse(data=List[List[float]])
    '''
    return embed_texts(texts=texts, embed_model=embed_model, to_query=to_query)


def embed_documents(
    docs: List[Document],
    embed_model: str = EMBEDDING_MODEL,
    to_query: bool = False,
) -> Dict:
    """
    Vectorize List[Document], converting to parameters accepted by VectorStore.add_embeddings
    """
    texts = [x.page_content for x in docs]
    metadatas = [x.metadata for x in docs]
    embeddings = embed_texts(texts=texts, embed_model=embed_model, to_query=to_query).data
    if embeddings is not None:
        return {
            "texts": texts,
            "embeddings": embeddings,
            "metadatas": metadatas,
        }
