"""RAG 检索服务：ChromaDB 向量存储与语义检索"""
import asyncio
import threading

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings as ChromaSettings

from app.config import settings

COLLECTION_NAME = "knowledge_base"

_client = None
_collection = None
_init_lock = threading.Lock()


class _LiteLLMEmbedding(EmbeddingFunction):
    """自定义 Embedding 函数：走 LiteLLM（需配置 EMBEDDING_MODEL）"""

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002
        import litellm
        from app.services import llm

        model, api_key, api_base = llm._resolve(settings.embedding_model)
        response = litellm.embedding(
            model=model, input=list(input), api_key=api_key, api_base=api_base, timeout=60
        )
        data = sorted(response.data, key=lambda x: x.get("index", 0))
        return [d["embedding"] for d in data]

    def name(self) -> str:
        return "litellm"

    def get_config(self) -> dict:
        return {}

    def build_from_config(self, config: dict) -> None:
        pass


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    with _init_lock:
        if _collection is None:
            _client = chromadb.PersistentClient(
                path=settings.chroma_dir,
                settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
            )
            ef = _LiteLLMEmbedding() if settings.embedding_model else None
            _collection = _client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
    return _collection


async def add_documents(doc_id: str, chunks: list[str], filename: str = "") -> None:
    """将文档切片向量化后写入向量库（幂等 upsert）"""
    if not chunks:
        return
    collection = await asyncio.to_thread(_get_collection)
    ids = [f"{doc_id}:{i}" for i in range(len(chunks))]
    metadatas = [
        {"doc_id": doc_id, "chunk_index": i, "filename": filename}
        for i in range(len(chunks))
    ]

    def _add():
        batch = 64
        for s in range(0, len(chunks), batch):
            collection.upsert(
                ids=ids[s : s + batch],
                documents=chunks[s : s + batch],
                metadatas=metadatas[s : s + batch],
            )

    await asyncio.to_thread(_add)


async def search(query: str, top_k: int | None = None) -> list[dict]:
    """语义检索，返回最相关的片段列表"""
    collection = await asyncio.to_thread(_get_collection)
    total = collection.count()
    if total == 0:
        return []
    n = min(top_k or settings.rag_top_k, total)
    result = await asyncio.to_thread(
        collection.query, query_texts=[query], n_results=n
    )
    out: list[dict] = []
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        out.append(
            {
                "content": doc,
                "doc_id": meta.get("doc_id"),
                "filename": meta.get("filename", ""),
                "score": round(1 - dist, 4) if dist is not None else None,
            }
        )
    return out


async def delete_documents(doc_id: str) -> None:
    """删除指定文档的全部向量"""
    collection = await asyncio.to_thread(_get_collection)
    await asyncio.to_thread(collection.delete, where={"doc_id": doc_id})


async def count() -> int:
    """向量库中的切片总数"""
    collection = await asyncio.to_thread(_get_collection)
    return collection.count()
