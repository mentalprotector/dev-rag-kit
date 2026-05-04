"""OpenAI-compatible LM Studio client."""

from __future__ import annotations

import logging

from openai import APIConnectionError, APITimeoutError, OpenAI, OpenAIError

logger = logging.getLogger(__name__)


class LLMClientError(RuntimeError):
    """Raised when the LLM API call fails."""


class LLMClient:
    """Client for an OpenAI-compatible LM Studio chat completions API."""

    def __init__(
        self,
        api_base_url: str = "http://172.19.0.1:1234/v1",
        model_name: str | None = None,
        timeout_seconds: float = 60.0,
        api_key: str = "lm-studio",
    ) -> None:
        """Initialize the LM Studio client."""

        if not model_name:
            raise ValueError("model_name must be provided from configuration")
        self.model_name = model_name
        self.api_base_url = api_base_url
        self._client = OpenAI(
            base_url=api_base_url,
            api_key=api_key,
            timeout=timeout_seconds,
        )

    def generate_answer(self, prompt: str) -> str:
        """Generate an answer from a fully formatted prompt."""

        if not prompt.strip():
            raise ValueError("prompt must not be empty")

        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
        except (APIConnectionError, APITimeoutError) as exc:
            logger.exception("LM Studio connection failed base_url=%s", self.api_base_url)
            raise LLMClientError("LM Studio API is unavailable or timed out") from exc
        except OpenAIError as exc:
            logger.exception("LM Studio API returned an error model=%s", self.model_name)
            raise LLMClientError("LM Studio API returned an error") from exc

        message = response.choices[0].message.content if response.choices else None
        if not message:
            raise LLMClientError("LM Studio returned an empty response")
        return message.strip()

    def list_models(self) -> list[str]:
        """Return model ids available from the configured LM Studio endpoint."""

        try:
            response = self._client.models.list()
        except (APIConnectionError, APITimeoutError) as exc:
            logger.exception("LM Studio model listing failed base_url=%s", self.api_base_url)
            raise LLMClientError("LM Studio API is unavailable or timed out") from exc
        except OpenAIError as exc:
            logger.exception("LM Studio API returned an error while listing models")
            raise LLMClientError("LM Studio API returned an error") from exc
        return [model.id for model in response.data]
