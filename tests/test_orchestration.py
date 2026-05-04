from dev_rag.orchestration.orchestrator import RAGOrchestrator
from dev_rag.orchestration.prompt_manager import PromptManager
from dev_rag.retrieval.models import RetrievalResult


class FakeRetrievalPipeline:
    def retrieve(
        self,
        query: str,
        hybrid_limit: int = 20,
        final_limit: int = 5,
    ) -> list[RetrievalResult]:
        return [
            RetrievalResult(
                id="chunk-1",
                content="Qdrant stores vectors and payload metadata for retrieval.",
                source="docs/qdrant.md",
                chunk_index=0,
                score=0.91,
            ),
            RetrievalResult(
                id="chunk-2",
                content="Hybrid search combines sparse keyword retrieval with dense embeddings.",
                source="docs/rag.md",
                chunk_index=2,
                score=0.87,
            ),
        ][:final_limit]


class FakeLLMClient:
    def __init__(self) -> None:
        self.last_prompt: str | None = None

    def generate_answer(self, prompt: str) -> str:
        self.last_prompt = prompt
        return "Use Qdrant for vector payload retrieval and combine it with BM25 for hybrid search."


def test_orchestrator_runs_retrieval_prompt_and_llm_flow() -> None:
    llm_client = FakeLLMClient()
    orchestrator = RAGOrchestrator(
        retrieval_pipeline=FakeRetrievalPipeline(),
        llm_client=llm_client,
        prompt_manager=PromptManager(),
    )

    response = orchestrator.answer("How should retrieval work?", hybrid_limit=10, final_limit=2)

    assert "Use Qdrant" in response.answer
    assert "Document 1" in response.context
    assert "docs/qdrant.md" in response.context
    assert len(response.retrieved_chunks) == 2
    assert llm_client.last_prompt is not None
    assert "How should retrieval work?" in llm_client.last_prompt
    assert "Hybrid search combines sparse keyword retrieval" in llm_client.last_prompt


def test_prompt_manager_requires_context_and_question_placeholders() -> None:
    manager = PromptManager(user_prompt_template="Question only: {question}")

    try:
        manager.build_prompt(context="ctx", question="q")
    except ValueError as exc:
        assert "{context}" in str(exc)
    else:
        raise AssertionError("Expected invalid prompt template to raise ValueError")
