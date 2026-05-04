"""RAGAS-based quality audit for the RAG pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol
from pydantic import BaseModel, ConfigDict, Field

from dev_rag.evaluation.dataset_factory import EvaluationDatasetFactory, GoldStandardSample
from dev_rag.orchestration.llm_client import LLMClientError
from dev_rag.orchestration.orchestrator import RAGOrchestrator, RAGResponse

logger = logging.getLogger(__name__)


class RAGASRunner(Protocol):
    """Protocol for injectable RAGAS scoring implementations."""

    def __call__(self, rows: list[dict[str, Any]]) -> dict[str, float]:
        """Score prepared evaluation rows."""


class EvaluationReport(BaseModel):
    """Stakeholder-readable RAG evaluation report."""

    model_config = ConfigDict(frozen=True)

    overall_rag_score: float
    metrics: dict[str, float] = Field(default_factory=dict)
    sample_count: int
    failed_count: int
    output_path: str


class RAGASEvaluator:
    """Run a gold-standard dataset through RAG and score it with RAGAS."""

    def __init__(
        self,
        orchestrator: RAGOrchestrator,
        output_path: str | Path = "evaluation_results.json",
        ragas_runner: RAGASRunner | None = None,
    ) -> None:
        """Initialize evaluator with an orchestrator and optional RAGAS runner."""

        self.orchestrator = orchestrator
        self.output_path = Path(output_path)
        self.ragas_runner = ragas_runner or self._run_ragas

    def evaluate_file(self, dataset_path: str | Path) -> EvaluationReport:
        """Load a gold-standard dataset file and evaluate it."""

        return self.evaluate(EvaluationDatasetFactory.load(dataset_path))

    def evaluate(self, samples: list[GoldStandardSample]) -> EvaluationReport:
        """Run RAG, score results, print a summary, and save a JSON report."""

        if not samples:
            raise ValueError("evaluation dataset must contain at least one sample")

        rows: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for sample in samples:
            try:
                response = self.orchestrator.answer(sample.question)
            except (LLMClientError, ValueError, RuntimeError) as exc:
                logger.exception("Evaluation sample failed question=%s", sample.question)
                failures.append({"question": sample.question, "error": str(exc)})
                response = RAGResponse(
                    question=sample.question,
                    answer="",
                    context="",
                    retrieved_chunks=[],
                )

            contexts = [chunk.content for chunk in response.retrieved_chunks]
            if not contexts:
                contexts = sample.context
            rows.append(
                {
                    "question": sample.question,
                    "answer": response.answer,
                    "contexts": contexts,
                    "ground_truth": sample.ground_truth,
                    "expected_context": sample.context,
                }
            )

        metrics = self.ragas_runner(rows)
        overall_score = self._overall_score(metrics)
        report = EvaluationReport(
            overall_rag_score=overall_score,
            metrics=metrics,
            sample_count=len(samples),
            failed_count=len(failures),
            output_path=str(self.output_path),
        )
        self._save_report(report=report, rows=rows, failures=failures)
        self._print_report(report)
        return report

    def _run_ragas(self, rows: list[dict[str, Any]]) -> dict[str, float]:
        """Run RAGAS metrics over prepared evaluation rows."""

        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.llms import LangchainLLMWrapper
            from ragas.metrics import answer_relevancy, context_precision, faithfulness
            from langchain_openai import ChatOpenAI
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError(
                "RAGAS evaluation dependencies are missing. Install project dependencies first."
            ) from exc

        llm_config = self.orchestrator.llm_client
        judge_llm = LangchainLLMWrapper(
            ChatOpenAI(
                base_url=getattr(llm_config, "api_base_url", "http://localhost:1234/v1"),
                api_key="lm-studio",
                model=getattr(llm_config, "model_name", "unsloth/gemma-4-26b-a4b-it"),
                temperature=0,
            )
        )
        dataset = Dataset.from_pandas(pd.DataFrame(rows))
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision],
            llm=judge_llm,
        )
        raw_scores = result.to_pandas().mean(numeric_only=True).to_dict()
        return {str(key): float(value) for key, value in raw_scores.items()}

    def _save_report(
        self,
        report: EvaluationReport,
        rows: list[dict[str, Any]],
        failures: list[dict[str, str]],
    ) -> None:
        """Persist evaluation report to JSON."""

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "summary": report.model_dump(mode="json"),
            "samples": rows,
            "failures": failures,
        }
        self.output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _overall_score(metrics: dict[str, float]) -> float:
        """Calculate a simple average over available RAGAS metric scores."""

        valid_scores = [score for score in metrics.values() if 0.0 <= score <= 1.0]
        if not valid_scores:
            return 0.0
        return round(sum(valid_scores) / len(valid_scores), 4)

    @staticmethod
    def _print_report(report: EvaluationReport) -> None:
        """Print a clean stakeholder-readable evaluation summary."""

        print("\nRAG Evaluation Report")
        print("=" * 72)
        print(f"Overall RAG Score: {report.overall_rag_score:.2f}")
        print(f"Samples Evaluated: {report.sample_count}")
        print(f"Failed Samples: {report.failed_count}")
        for name, value in report.metrics.items():
            print(f"{name}: {value:.3f}")
        print(f"Saved Report: {report.output_path}")
