"""ReviewerAgent: reviews a patch and provides a verdict with feedback."""

from __future__ import annotations

import json
from typing import Any

from src.blackboard.schema import Review
from .base import BaseAgent


class ReviewerAgent(BaseAgent):
    """Reviews a code patch and returns approve / needs_revision / reject.

    Input (varies by communication mode):
        - Message-Passing: natural-language context with issue, analysis, and patch.
        - Blackboard: formatted blackboard state string for Reviewer.
        - Hybrid: both combined.

    Output: ``Review`` serialized as a dict.

    Prompt strategy:
        - Check whether the patch truly fixes the described issue.
        - Look for logical errors and missed edge cases.
        - Provide concrete, actionable suggestions.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(role="Reviewer", **kwargs)

    async def execute(self, context: str) -> dict[str, Any]:
        """Review the latest patch and return a Review dict.

        Args:
            context: Issue + analysis + patch (natural language or blackboard state).

        Returns:
            ``Review`` model serialized as a dict.
        """
        schema_json = json.dumps(Review.model_json_schema(), indent=2)
        prompt_section = self._get_prompt_section(self.communication_mode)

        system_prompt = (
            "You are a meticulous code reviewer for a multi-agent automated code repair system. "
            "Always respond with valid JSON only, no extra text."
        )

        if self.communication_mode in ("blackboard", "hybrid"):
            user_message = prompt_section.format(schema=schema_json, state=context)
        else:
            user_message = prompt_section.format(schema=schema_json, context=context)

        review, in_tok, out_tok = await self._call_llm_structured(
            system_prompt, user_message, Review
        )
        return review.model_dump()
