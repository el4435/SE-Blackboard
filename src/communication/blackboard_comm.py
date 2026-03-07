"""Blackboard communication mode: agents read/write via shared state."""

from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent
from src.blackboard.board import Blackboard
from src.blackboard.schema import Analysis, Patch, Review, TestResult
from src.utils.logger import ExperimentLogger


class BlackboardCommunication:
    """Blackboard communication mode.

    Agents read relevant state from the blackboard before execution and write
    their results back.  There is no direct agent-to-agent messaging.
    """

    def __init__(self, blackboard: Blackboard, logger: ExperimentLogger | None = None) -> None:
        self.blackboard = blackboard
        self.logger = logger

    async def run_agent(self, agent: BaseAgent) -> dict[str, Any]:
        """Read state for *agent*, execute, and write the result back.

        Before calling ``agent.execute``, this method sets the agent's
        ``communication_mode`` to ``"blackboard"`` and provides the
        blackboard-filtered context.

        Args:
            agent: The agent to execute.

        Returns:
            The structured result dict produced by the agent.
        """
        agent.communication_mode = "blackboard"
        context = self.blackboard.get_state_for_agent(agent.role)
        result = await agent.execute(context)
        self._write_result(agent.role, result)
        return result

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
