"""Anthropic API wrapper with retry logic and token tracking."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Async wrapper around the Anthropic Messages API.

    Features:
    - Automatic retry with exponential back-off (up to 3 attempts)
    - Per-call input / output token tracking
    - Structured output: parse LLM response into a Pydantic model
    """

    def __init__(
        self,
        model: str = settings.MODEL,
        temperature: float = settings.TEMPERATURE,
        max_tokens: int = settings.MAX_TOKENS_PER_CALL,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
        self.cumulative_input_tokens: int = 0
        self.cumulative_output_tokens: int = 0
    # Core call

    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_retries: int = 3,
        max_tokens: int | None = None,
    ) -> tuple[str, int, int]:
        """Send a message and return (response_text, input_tokens, output_tokens).

        Retries on transient API errors with exponential back-off.

        Args:
            max_tokens: Override the default max_tokens for this call.
                        If None, uses ``self.max_tokens``.
        """
        effective_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                response = await self._client.messages.create(
                    model=self.model,
                    max_tokens=effective_max_tokens,
                    temperature=self.temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                text = response.content[0].text
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens

                self.cumulative_input_tokens += input_tokens
                self.cumulative_output_tokens += output_tokens

                return text, input_tokens, output_tokens

            except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError) as exc:
                last_error = exc
                wait = 2 ** attempt
                logger.warning("LLM call attempt %d failed (%s), retrying in %ds…", attempt, exc, wait)
                await asyncio.sleep(wait)

        raise RuntimeError(f"LLM call failed after {max_retries} attempts: {last_error}")
    # Structured output

    async def call_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[T],
        max_retries: int = 3,
    ) -> tuple[T, int, int]:
        """Call the LLM and parse the response into a Pydantic model.

        If the initial response cannot be parsed, one additional retry is made
        with a corrective prompt appended.
        """
        text, in_tok, out_tok = await self.call(system_prompt, user_message, max_retries=max_retries)

        # First parse attempt
        parsed = self._try_parse(text, response_model)
        if parsed is not None:
            return parsed, in_tok, out_tok

        # Retry with a correction hint
        correction = (
            "Your previous response was not valid JSON or did not match the expected schema. "
            "Please respond ONLY with a valid JSON object matching this schema:\n"
            f"{json.dumps(response_model.model_json_schema(), indent=2)}"
        )
        retry_message = f"{user_message}\n\n{correction}\n\nYour previous (invalid) response:\n{text}"
        text2, in_tok2, out_tok2 = await self.call(system_prompt, retry_message, max_retries=max_retries)
        in_tok += in_tok2
        out_tok += out_tok2

        parsed = self._try_parse(text2, response_model)
        if parsed is not None:
            return parsed, in_tok, out_tok

        raise ValueError(f"Failed to parse LLM output into {response_model.__name__} after correction retry.")
    # Helpers

    @staticmethod
    def _try_parse(text: str, model: type[T]) -> T | None:
        """Attempt to parse *text* as JSON into a Pydantic model."""
        try:
            # Strip markdown code fences if present
            cleaned = text.strip()
            if cleaned.startswith("```"):
                first_newline = cleaned.index("\n")
                last_fence = cleaned.rfind("```")
                cleaned = cleaned[first_newline + 1 : last_fence].strip()
            return model.model_validate_json(cleaned)
        except Exception:
            return None
    # Tool-use call

    async def call_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str = "",
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> Any:
        """Call Claude API with tool use.

        Returns the full API response object (with .content, .stop_reason, .usage).
        Token usage is tracked cumulatively.
        """
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                response = await self._client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=self.temperature,
                    system=system,
                    messages=messages,
                    tools=tools,
                )
                self.cumulative_input_tokens += response.usage.input_tokens
                self.cumulative_output_tokens += response.usage.output_tokens
                return response
            except (
                anthropic.APIConnectionError,
                anthropic.RateLimitError,
                anthropic.InternalServerError,
            ) as exc:
                last_error = exc
                wait = 2 ** attempt
                logger.warning(
                    "LLM tool call attempt %d failed (%s), retrying in %ds…",
                    attempt, exc, wait,
                )
                await asyncio.sleep(wait)

        raise RuntimeError(f"LLM tool call failed after {max_retries} attempts: {last_error}")

    def reset_token_counts(self) -> None:
        """Reset cumulative token counters."""
        self.cumulative_input_tokens = 0
        self.cumulative_output_tokens = 0
