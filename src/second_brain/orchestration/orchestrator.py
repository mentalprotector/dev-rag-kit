"""Main RAG orchestration entry point."""

from __future__ import annotations

import logging
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from second_brain.orchestration.llm_client import LLMClient
from second_brain.orchestration.prompt_manager import PromptManager
from second_brain.retrieval.models import RetrievalResult
from second_brain.retrieval.pipeline import RetrievalPipeline

logger = logging.getLogger(__name__)


class RetrievalBackend(Protocol):
    """Protocol for retrieval pipelines used by the orchestrator."""

    def retrieve(
        self,
        query: str,
        hybrid_limit: int = 20,
        final_limit: int = 5,
    ) -> list[RetrievalResult]:
        """Return final retrieval results for a query."""


class LLMBackend(Protocol):
    """Protocol for LLM clients used by the orchestrator."""

    def generate_answer(self, prompt: str) -> str:
        """Generate an answer from a prompt."""


class RAGResponse(BaseModel):
    """Full RAG response including debug context."""

    model_config = ConfigDict(frozen=True)

    question: str
    answer: str
    context: str
    retrieved_chunks: list[RetrievalResult] = Field(default_factory=list)


class RAGOrchestrator:
    """Connect retrieval, prompt construction, and LLM answer generation."""

    def __init__(
        self,
        retrieval_pipeline: RetrievalPipeline | RetrievalBackend,
        llm_client: LLMClient | LLMBackend,
        prompt_manager: PromptManager | None = None,
    ) -> None:
        """Initialize the RAG orchestrator."""

        self.retrieval_pipeline = retrieval_pipeline
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager or PromptManager()

    def answer(
        self,
        user_query: str,
        hybrid_limit: int = 20,
        final_limit: int = 5,
    ) -> RAGResponse:
        """Run the full RAG workflow and return the final answer with context."""

        if not user_query.strip():
            raise ValueError("user_query must not be empty")

        retrieved_chunks = self.retrieval_pipeline.retrieve(
            query=user_query,
            hybrid_limit=hybrid_limit,
            final_limit=final_limit,
        )
        context = self.format_context(retrieved_chunks)
        prompt = self.prompt_manager.build_prompt(context=context, question=user_query)
        answer = self.llm_client.generate_answer(prompt)
        logger.info("RAG answer generated chunks=%s", len(retrieved_chunks))
        return RAGResponse(
            question=user_query,
            answer=answer,
            context=context,
            retrieved_chunks=retrieved_chunks,
        )

    def format_context(self, chunks: list[RetrievalResult]) -> str:
        """Format retrieved chunks into a readable context block."""

        lines: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            source = chunk.source
            chunk_label = "unknown" if chunk.chunk_index is None else str(chunk.chunk_index)
            lines.append(
                f"Document {index} "
                f"(source: {source}, chunk: {chunk_label}, score: {chunk.score:.4f})\n"
                f"{chunk.content}"
            )
        return "\n\n".join(lines)
