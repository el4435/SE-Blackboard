"""Blackboard read/write manager for the shared SE state."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any

from .schema import (
    Analysis,
    IssueInfo,
    Metadata,
    Patch,
    Review,
    SEBlackboardState,
    TestResult,
)


class Blackboard:
    """Blackboard read/write manager.

    Provides controlled access to the shared SE state. All mutations are
    tracked in an internal history log for post-hoc analysis.
    """

    def __init__(self, issue: IssueInfo) -> None:
        """Initialize the blackboard from an issue.

        Args:
            issue: The SWE-bench issue information.
        """
        self._state = SEBlackboardState(issue=issue)
        self._history: list[dict[str, Any]] = []
        self._record("init", {"issue_id": issue.instance_id})

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_state(self) -> SEBlackboardState:
        """Return a deep copy of the full state (prevents accidental mutation)."""
        return self._state.model_copy(deep=True)

    def get_state_for_agent(self, role: str) -> str:
        """Return a formatted string with the state subset relevant to *role*.

        Visibility rules:
        - Planner: issue full text
        - Coder:   issue + analysis + latest review feedback
        - Reviewer: issue + analysis + latest patch
        - Tester:  issue + latest patch
        """
        state = self._state
        sections: list[str] = []

        # Every role sees the issue
        sections.append(f"## Issue\n{state.issue.model_dump_json(indent=2)}")

        if role == "Planner":
            pass  # only issue

        elif role == "Coder":
            sections.append(f"## Analysis\n{state.analysis.model_dump_json(indent=2)}")
            if state.analysis.relevant_code:
                sections.append(f"## Source Code Context\n{state.analysis.relevant_code}")
            if state.reviews:
                latest_review = state.reviews[-1]
                sections.append(f"## Latest Review\n{latest_review.model_dump_json(indent=2)}")
            if state.test_results:
                latest_test = state.test_results[-1]
                sections.append(f"## Latest Test Result\n{latest_test.model_dump_json(indent=2)}")

        elif role == "Reviewer":
            sections.append(f"## Analysis\n{state.analysis.model_dump_json(indent=2)}")
            if state.patches:
                if len(state.patches) == 1:
                    sections.append(f"## Latest Patch\n{state.patches[-1].model_dump_json(indent=2)}")
                else:
                    # Show all patches (supports Debate topology with multiple Coders)
                    patches_json = "\n\n".join(
                        f"### Patch by {p.author} (v{p.version})\n{p.model_dump_json(indent=2)}"
                        for p in state.patches
                    )
                    sections.append(f"## All Patches\n{patches_json}")

        elif role == "Tester":
            if state.patches:
                latest_patch = state.patches[-1]
                sections.append(f"## Latest Patch\n{latest_patch.model_dump_json(indent=2)}")

        else:
            raise ValueError(f"Unknown agent role: {role}")

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def update_analysis(self, analysis: Analysis) -> None:
        """Replace the current analysis with a new one."""
        self._state.analysis = analysis
        self._state.metadata.status = "planning"
        self._record("update_analysis", analysis.model_dump())

    def add_patch(self, patch: Patch) -> None:
        """Append a new patch version."""
        self._state.patches.append(patch)
        self._state.metadata.status = "coding"
        self._record("add_patch", {"version": patch.version})

    def add_review(self, review: Review) -> None:
        """Append a review for a patch."""
        self._state.reviews.append(review)
        self._state.metadata.status = "reviewing"
        self._record("add_review", {"patch_version": review.patch_version, "verdict": review.verdict})

    def add_test_result(self, result: TestResult) -> None:
        """Append a test result for a patch."""
        self._state.test_results.append(result)
        if result.passed:
            self._state.metadata.status = "resolved"
        else:
            self._state.metadata.status = "testing"
        self._record("add_test_result", {"patch_version": result.patch_version, "passed": result.passed})

    def update_metadata(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        iteration: int | None = None,
        status: str | None = None,
    ) -> None:
        """Accumulate token usage and optionally update iteration / status."""
        self._state.metadata.total_input_tokens += input_tokens
        self._state.metadata.total_output_tokens += output_tokens
        self._state.metadata.total_latency_ms += latency_ms
        if iteration is not None:
            self._state.metadata.current_iteration = iteration
        if status is not None:
            self._state.metadata.status = status  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Serialization & history
    # ------------------------------------------------------------------

    def get_history(self) -> list[dict[str, Any]]:
        """Return the full operation timeline (deep copy)."""
        return copy.deepcopy(self._history)

    def to_json(self) -> str:
        """Serialize the current state to a JSON string."""
        return self._state.model_dump_json(indent=2)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record(self, action: str, details: dict[str, Any]) -> None:
        """Append an entry to the history log."""
        self._history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "details": details,
            }
        )
