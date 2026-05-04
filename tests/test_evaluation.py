import json
from pathlib import Path

from second_brain.evaluation.dataset_factory import EvaluationDatasetFactory, GoldStandardSample
from second_brain.evaluation.evaluator import RAGASEvaluator
from second_brain.orchestration.orchestrator import RAGResponse
from second_brain.retrieval.models import RetrievalResult


class FakeOrchestrator:
    def answer(self, user_query: str) -> RAGResponse:
        return RAGResponse(
            question=user_query,
            answer="Qdrant stores embeddings and payloads for vector retrieval.",
            context="Document 1\nQdrant stores embeddings and payloads.",
            retrieved_chunks=[
                RetrievalResult(
                    id="1",
                    content="Qdrant stores embeddings and payloads.",
                    source="qdrant.md",
                    score=0.9,
                )
            ],
        )


def fake_ragas_runner(rows: list[dict[str, object]]) -> dict[str, float]:
    assert rows[0]["answer"]
    assert rows[0]["contexts"]
    return {"faithfulness": 0.9, "answer_relevancy": 0.8, "context_precision": 0.7}


def test_dataset_factory_round_trips_json(tmp_path: Path) -> None:
    path = tmp_path / "gold.json"
    samples = [
        GoldStandardSample(
            question="What does Qdrant store?",
            ground_truth="Qdrant stores embeddings and payloads.",
            context=["Qdrant stores embeddings and payloads."],
        )
    ]

    EvaluationDatasetFactory.save_json(samples, path)
    loaded = EvaluationDatasetFactory.load(path)

    assert loaded == samples


def test_evaluator_runs_orchestrator_scores_and_saves_report(tmp_path: Path) -> None:
    output = tmp_path / "evaluation_results.json"
    evaluator = RAGASEvaluator(
        orchestrator=FakeOrchestrator(),  # type: ignore[arg-type]
        output_path=output,
        ragas_runner=fake_ragas_runner,
    )

    report = evaluator.evaluate(
        [
            GoldStandardSample(
                question="What does Qdrant store?",
                ground_truth="Qdrant stores embeddings and payloads.",
                context=["Qdrant stores embeddings and payloads."],
            )
        ]
    )

    assert report.overall_rag_score == 0.8
    assert report.failed_count == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["metrics"]["faithfulness"] == 0.9
