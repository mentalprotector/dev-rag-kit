"""Application factories shared by CLI entry points."""

from __future__ import annotations

from second_brain.config import AppConfig
from second_brain.evaluation.evaluator import RAGASEvaluator
from second_brain.orchestration.orchestrator import RAGOrchestrator
from second_brain.orchestration.prompt_manager import PromptManager


def build_orchestrator(config: AppConfig) -> RAGOrchestrator:
    """Build the production RAG orchestrator from app configuration."""

    from second_brain.ingestion.embeddings import EmbeddingService
    from second_brain.orchestration.llm_client import LLMClient
    from second_brain.retrieval.hybrid_search import HybridSearchEngine
    from second_brain.retrieval.manifest import load_chunk_manifest
    from second_brain.retrieval.pipeline import RetrievalPipeline
    from second_brain.retrieval.reranker import CrossEncoderReranker
    from second_brain.retrieval.vector_store import QdrantClientWrapper

    embedding_service = EmbeddingService(
        model_name=config.embedding.model_name,
        batch_size=config.embedding.batch_size,
    )
    vector_store = QdrantClientWrapper(
        qdrant_url=str(config.qdrant.url),
        collection_name=config.qdrant.collection,
    )
    hybrid_search = HybridSearchEngine(
        vector_store=vector_store,
        documents=load_chunk_manifest(config.chunking.manifest_path),
        embed_query=lambda query: embedding_service.embed_texts([query])[0],
    )
    retrieval_pipeline = RetrievalPipeline(
        hybrid_search=hybrid_search,
        reranker=CrossEncoderReranker(),
    )
    return RAGOrchestrator(
        retrieval_pipeline=retrieval_pipeline,
        llm_client=LLMClient(
            api_base_url=str(config.llm.api_base_url),
            model_name=config.llm.model_name,
            timeout_seconds=config.llm.timeout_seconds,
        ),
        prompt_manager=PromptManager(),
    )


def build_evaluator(config: AppConfig, output_path: str) -> RAGASEvaluator:
    """Build the RAGAS evaluator from app configuration."""

    return RAGASEvaluator(orchestrator=build_orchestrator(config), output_path=output_path)
