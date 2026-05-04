"""Gold-standard dataset loading for RAG evaluation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class GoldStandardSample(BaseModel):
    """Single evaluation item with expected answer and expected context."""

    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=1)
    ground_truth: str = Field(min_length=1)
    context: list[str] = Field(default_factory=list)


class EvaluationDatasetFactory:
    """Load and save gold-standard evaluation datasets as JSON or CSV."""

    @staticmethod
    def load(path: str | Path) -> list[GoldStandardSample]:
        """Load a gold-standard dataset from a JSON or CSV file."""

        dataset_path = Path(path)
        if not dataset_path.exists():
            raise FileNotFoundError(f"Evaluation dataset not found: {dataset_path}")

        suffix = dataset_path.suffix.lower()
        if suffix == ".json":
            return EvaluationDatasetFactory._load_json(dataset_path)
        if suffix == ".csv":
            return EvaluationDatasetFactory._load_csv(dataset_path)
        raise ValueError("Evaluation dataset must be a .json or .csv file")

    @staticmethod
    def save_json(samples: list[GoldStandardSample], path: str | Path) -> None:
        """Save a gold-standard dataset to JSON."""

        dataset_path = Path(path)
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [sample.model_dump(mode="json") for sample in samples]
        dataset_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _load_json(path: Path) -> list[GoldStandardSample]:
        """Load samples from JSON."""

        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("JSON evaluation dataset must be a list of objects")
        return [GoldStandardSample.model_validate(item) for item in raw]

    @staticmethod
    def _load_csv(path: Path) -> list[GoldStandardSample]:
        """Load samples from CSV with question, ground_truth, and context columns."""

        samples: list[GoldStandardSample] = []
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                raw_context = row.get("context", "")
                contexts = [part.strip() for part in raw_context.split("||") if part.strip()]
                samples.append(
                    GoldStandardSample(
                        question=row.get("question", ""),
                        ground_truth=row.get("ground_truth", ""),
                        context=contexts,
                    )
                )
        return samples
