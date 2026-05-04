from datetime import UTC, datetime
from uuid import uuid4

from dev_rag.ingestion.schemas import DocumentChunk
from dev_rag.retrieval.hybrid_search import HybridSearchEngine
from dev_rag.retrieval.models import RetrievalResult
from dev_rag.retrieval.pipeline import RetrievalPipeline


class FakeVectorStore:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self.results = results

    def search(self, query_vector: list[float], limit: int = 10) -> list[RetrievalResult]:
        return self.results[:limit]


class FakeReranker:
    def rerank(
        self,
        query: str,
        documents: list[RetrievalResult],
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        scores = {
            "python async await concurrency": 0.95,
            "banana bread recipe": 0.05,
        }
        reranked = sorted(
            (
                document.with_scores(
                    score=scores.get(document.content, 0.1),
                    rerank_score=scores.get(document.content, 0.1),
                )
                for document in documents
            ),
            key=lambda result: result.rerank_score or 0,
            reverse=True,
        )
        return reranked[:top_k] if top_k is not None else reranked


def test_retrieval_pipeline_reranking_changes_document_order() -> None:
    first = RetrievalResult(id="1", content="banana bread recipe", source="a.md", score=0.99)
    second = RetrievalResult(id="2", content="python async await concurrency", source="b.md", score=0.80)
    vector_store = FakeVectorStore([first, second])

    hybrid = HybridSearchEngine(
        vector_store=vector_store,  # type: ignore[arg-type]
        documents=[],
        embed_query=lambda query: [0.1, 0.2],
    )
    pipeline = RetrievalPipeline(hybrid_search=hybrid, reranker=FakeReranker())  # type: ignore[arg-type]

    results = pipeline.retrieve("How does async await work in Python?", hybrid_limit=2, final_limit=2)

    assert [result.id for result in results] == ["2", "1"]
    assert results[0].rerank_score is not None


def test_hybrid_search_rrf_merges_bm25_and_vector_results() -> None:
    document_id = uuid4()
    now = datetime.now(UTC)
    chunk = DocumentChunk(
        document_id=document_id,
        content="qdrant hybrid search with bm25 retrieval",
        source="retrieval.md",
        chunk_index=0,
        timestamp=now,
    )
    other_chunk = DocumentChunk(
        document_id=document_id,
        content="python asyncio event loop coroutine",
        source="retrieval.md",
        chunk_index=1,
        timestamp=now,
    )
    third_chunk = DocumentChunk(
        document_id=document_id,
        content="docker compose qdrant vector database",
        source="retrieval.md",
        chunk_index=2,
        timestamp=now,
    )
    vector_result = RetrievalResult(id=str(chunk.id), content=chunk.content, source=chunk.source, score=0.7)
    hybrid = HybridSearchEngine(
        vector_store=FakeVectorStore([vector_result]),  # type: ignore[arg-type]
        documents=[chunk, other_chunk, third_chunk],
        embed_query=lambda query: [0.1, 0.2],
    )

    results = hybrid.search("bm25 retrieval", limit=3)

    assert len(results) == 1
    assert results[0].vector_score == 0.7
    assert results[0].bm25_score is not None
