"""Hybrid communication mode: message-passing + blackboard."""

from __future__ import annotations

import json
from typing import Any

from src.agents.base import BaseAgent
from src.blackboard.board import Blackboard
from src.blackboard.schema import Analysis, Patch, Review, TestResult
from src.utils.logger import ExperimentLogger


class HybridCommunication:
    """Hybrid communication mode.

    Agents receive both the blackboard state subset **and** the previous
    agent's natural-language output.  Results are written to the blackboard
    and forwarded as text to the next agent.
    """

    def __init__(self, blackboard: Blackboard, logger: ExperimentLogger | None = None) -> None:
        self.blackboard = blackboard
        self.logger = logger

    async def run_agent(
        self,
        agent: BaseAgent,
        previous_output: str,
    ) -> tuple[str, dict[str, Any]]:
        """Run *agent* with combined blackboard + message-passing context.

        The agent's ``communication_mode`` is set to ``"hybrid"`` which
        makes it use the message-passing prompt template (since the hybrid
        context already embeds blackboard data).

        Args:
            agent: The agent to execute.
            previous_output: Natural-language output from the preceding agent.

        Returns:
            A tuple of (text for next agent, structured result dict).
        """
        agent.communication_mode = "hybrid"
        bb_context = self.blackboard.get_state_for_agent(agent.role)
        combined = f"{bb_context}\n\n## Previous Agent Output\n{previous_output}"

        result = await agent.execute(combined)
        self._write_result(agent.role, result)
        summary = f"[{agent.role} Output]\n{json.dumps(result, indent=2, default=str)}"
        return summary, result

    def _write_result(self, role: str, result: dict[str, Any]) -> None:
        """Dispatch the result to the appropriate blackboard update method."""
        if role == "Planner":
            self.blackboard.update_analysis(Analysis.model_validate(result))
        elif role == "Coder":
            self.blackboard.add_patch(Patch.model_validate(result))
        elif role == "Reviewer":
            self.blackboard.add_review(Review.model_validate(result))
        elif role == "Tester":
            self.blackboard.add_test_result(TestResult.model_validate(result))
