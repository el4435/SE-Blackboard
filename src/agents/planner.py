"""PlannerAgent: analyzes a GitHub issue and produces a structured Analysis."""

from __future__ import annotations

import json
from typing import Any

from src.blackboard.schema import Analysis
from .base import BaseAgent


class PlannerAgent(BaseAgent):
    """Reads the issue text and produces a root-cause analysis with a fix strategy.

    Input (varies by communication mode):
        - Message-Passing: issue raw text as natural language.
        - Blackboard: formatted blackboard state string for Planner.
        - Hybrid: both combined.

    Output: ``Analysis`` serialized as a dict.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(role="Planner", **kwargs)

    async def execute(self, context: str) -> dict[str, Any]:
        """Analyze the issue and return an Analysis dict.

        Args:
            context: Issue text (message-passing) or blackboard state string.

        Returns:
            ``Analysis`` model serialized as a dict.
        """
        schema_json = json.dumps(Analysis.model_json_schema(), indent=2)
        prompt_section = self._get_prompt_section(self.communication_mode)

        system_prompt = (
            "You are a senior software engineer tasked with analyzing a GitHub issue. "
            "Always respond with valid JSON only, no extra text."
        )

        # Build user message by filling in template placeholders
        if self.communication_mode in ("blackboard", "hybrid"):
            user_message = prompt_section.format(schema=schema_json, state=context)
        else:
            user_message = prompt_section.format(schema=schema_json, issue_text=context)

        analysis, in_tok, out_tok = await self._call_llm_structured(
            system_prompt, user_message, Analysis
        )
        return analysis.model_dump()
