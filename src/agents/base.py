"""Abstract base class for all agents."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.utils.llm_client import LLMClient
from src.utils.logger import ExperimentLogger


class BaseAgent(ABC):
    """Abstract base for every agent in the pipeline.

    Subclasses must implement :meth:`execute` which receives a context string
    (whose content depends on the communication mode) and returns a dict with
    the structured output of the agent.
    """

    def __init__(self, role: str, llm_client: LLMClient, logger: ExperimentLogger) -> None:
        self.role = role
        self.llm = llm_client
        self.logger = logger
        self._prompt_template_raw: str | None = None

        # Mutable state set by the communication layer before each run
        self.issue_id: str = ""
        self.config_label: str = ""
        self.communication_mode: str = ""
        self.current_iteration: int = 0

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def execute(self, context: str) -> dict[str, Any]:
        """Execute the agent's core task.

        Args:
            context: Depends on the communication mode:
                - Message-Passing: natural-language output from the previous agent.
                - Blackboard: ``blackboard.get_state_for_agent(self.role)`` output.
                - Hybrid: combination of both.

        Returns:
            Structured output whose shape depends on the concrete role.
        """
        ...

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    async def _call_llm(
        self, system_prompt: str, user_message: str, *, max_tokens: int | None = None,
    ) -> tuple[str, int, int]:
        """Call the LLM, log the interaction, and return (response, in_tok, out_tok).

        Args:
            max_tokens: Override the default max_tokens for this call.
        """
        start = time.perf_counter()
        text, in_tok, out_tok = await self.llm.call(
            system_prompt, user_message, max_tokens=max_tokens,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        self.logger.log(
            issue_id=self.issue_id,
            config=self.config_label,
            agent_role=self.role,
            communication_mode=self.communication_mode,
            iteration=self.current_iteration,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
        )
        return text, in_tok, out_tok

    async def _call_llm_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type,
    ) -> tuple[Any, int, int]:
        """Call the LLM with structured output parsing, log the interaction.

        Returns (parsed_model_instance, total_input_tokens, total_output_tokens).
        """
        start = time.perf_counter()
        parsed, in_tok, out_tok = await self.llm.call_structured(
            system_prompt, user_message, response_model
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        self.logger.log(
            issue_id=self.issue_id,
            config=self.config_label,
            agent_role=self.role,
            communication_mode=self.communication_mode,
            iteration=self.current_iteration,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
        )
        return parsed, in_tok, out_tok

    # ------------------------------------------------------------------
    # Prompt template helpers
    # ------------------------------------------------------------------

    def _load_prompt_template(self) -> str:
        """Load the raw prompt template from ``config/prompts/{role}.txt``."""
        if self._prompt_template_raw is None:
            path = Path("config") / "prompts" / f"{self.role.lower()}.txt"
            self._prompt_template_raw = path.read_text(encoding="utf-8")
        return self._prompt_template_raw

    def _get_prompt_section(self, mode: str) -> str:
        """Extract the prompt section for the given communication *mode*.

        Args:
            mode: ``"message_passing"`` or ``"blackboard"``.

        Returns:
            The text between the relevant ``## …_VERSION`` header and the next
            header (or end of file).
        """
        raw = self._load_prompt_template()
        if mode in ("blackboard", "hybrid"):
            # Hybrid uses Blackboard prompt (combined context already embeds BB state)
            marker = "## BLACKBOARD_VERSION"
        else:
            marker = "## MESSAGE_PASSING_VERSION"

        sections = raw.split("## ")
        for section in sections:
            header_line = section.split("\n", 1)[0].strip()
            if header_line == marker.replace("## ", ""):
                # Return everything after the header line
                return section.split("\n", 1)[1].strip()

        # Fallback: return the whole template
        return raw
