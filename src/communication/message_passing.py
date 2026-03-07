"""Message-passing communication mode: agents communicate via natural language."""

from __future__ import annotations

import json
from typing import Any

from src.agents.base import BaseAgent
from src.utils.logger import ExperimentLogger


class MessagePassingCommunication:
    """Traditional message-passing mode.

    Each agent receives the full natural-language output of the previous agent
    as its context.  No shared state is maintained.
    """

    def __init__(self, logger: ExperimentLogger | None = None) -> None:
        self.logger = logger

    async def run_agent(
        self,
        agent: BaseAgent,
        previous_output: str,
    ) -> tuple[str, dict[str, Any]]:
        """Run *agent* with the previous agent's text output.

        Before calling ``agent.execute``, this method sets the agent's
        ``communication_mode`` to ``"message_passing"`` so that the agent
        can pick the correct prompt template section.

        Args:
            agent: The agent to execute.
            previous_output: Natural-language output from the preceding agent.

        Returns:
            A tuple of (natural-language output for the next agent,
            structured result dict).
        """
        agent.communication_mode = "message_passing"
        result = await agent.execute(previous_output)
        summary = self._result_to_text(agent.role, result)
        return summary, result

    @staticmethod
    def _result_to_text(role: str, result: dict[str, Any]) -> str:
        """Convert a structured agent result into a human-readable summary."""
        return f"[{role} Output]\n{json.dumps(result, indent=2, default=str)}"
