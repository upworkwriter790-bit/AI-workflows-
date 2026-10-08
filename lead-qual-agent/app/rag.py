"""RAG utilities: per-client ICP/playbook retrieval via Chroma + Ollama embeddings.

Chroma and embeddings are imported lazily. If RAG is disabled or the stack
isn't installed/reachable, retrieval degrades gracefully to "" and indexing
is a no-op, so the agent still runs end-to-end.
"""
from __future__ import annotations

from typing import List, Optional

from app import config


def _embeddings():
    from langchain_ollama import OllamaEmbeddings  # lazy

    return OllamaEmbeddings(model=config.EMBEDDING_MODEL, base_url=config.OLLAMA_BASE_URL)


def _vectorstore(client_id: str):
    from langchain_chroma import Chroma  # lazy (langchain-chroma is the maintained package)

    return Chroma(
        collection_name=f"icp_{client_id}",
        embedding_function=_embeddings(),
        persist_directory=config.CHROMA_PERSIST_DIR,
    )


def _chunk(text: str, size: int = 1600, overlap: int = 200) -> List[str]:
    """Rough char-based chunker (~300-500 tokens) with overlap."""
    text = text.strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def index_documents(client_id: str, docs: List[dict]) -> int:
    """Index per-client docs. Each doc: {"doc_type", "doc_id", "text"}.

    Returns number of chunks indexed, or 0 if RAG is unavailable.
    """
    if not config.RAG_ENABLED:
        return 0
    try:
        from langchain_core.documents import Document  # lazy

        vs = _vectorstore(client_id)
        out: List[Document] = []
        for d in docs:
            for i, ch in enumerate(_chunk(d.get("text", ""))):
                out.append(
                    Document(
                        page_content=ch,
                        metadata={
                            "client_id": client_id,
                            "doc_type": d.get("doc_type", "generic"),
                            "doc_id": d.get("doc_id", f"doc_{i}"),
                        },
                    )
                )
        if out:
            vs.add_documents(out)
        return len(out)
    except Exception as e:  # pragma: no cover - environment dependent
        print(f"[rag] index skipped ({e.__class__.__name__}: {e})")
        return 0


def retrieve(client_id: str, query: str, k: int = 5) -> str:
    if not config.RAG_ENABLED:
        return ""
    try:
        vs = _vectorstore(client_id)
        results = vs.similarity_search(query, k=k, filter={"client_id": client_id})
        return "\n\n".join(r.page_content for r in results)
    except Exception as e:  # pragma: no cover - environment dependent
        print(f"[rag] retrieve skipped ({e.__class__.__name__}: {e})")
        return ""
