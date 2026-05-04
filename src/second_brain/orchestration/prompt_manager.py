"""Prompt template management for RAG answers."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_SYSTEM_PROMPT = """You are Second Brain for Devs, a senior developer knowledge assistant.
Answer strictly from the provided context. If the context is insufficient, say what is missing.
Prefer concise, practical answers with concrete implementation details when available."""

DEFAULT_USER_PROMPT = """Context:
{context}

Question:
{question}

Answer:"""


@dataclass(frozen=True)
class PromptManager:
    """Manage system and user prompt templates."""

    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    user_prompt_template: str = DEFAULT_USER_PROMPT

    def build_prompt(self, context: str, question: str) -> str:
        """Construct the final prompt from context and user question."""

        if "{context}" not in self.user_prompt_template or "{question}" not in self.user_prompt_template:
            raise ValueError("user_prompt_template must contain {context} and {question} placeholders")
        if not question.strip():
            raise ValueError("question must not be empty")

        user_prompt = self.user_prompt_template.format(
            context=context.strip() or "No relevant context was retrieved.",
            question=question.strip(),
        )
        return f"{self.system_prompt.strip()}\n\n{user_prompt}"
