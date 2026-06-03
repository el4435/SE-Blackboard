"""Structured JSON logger for experiment interactions."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ExperimentLogger:
    """Writes one JSON object per agent interaction to a log file.

    Each entry captures timing, token usage, agent role, communication mode,
    and an optional snapshot of the blackboard state.
    """

    def __init__(
        self,
        experiment_id: str,
        log_dir: str = "data/results",
    ) -> None:
        self.experiment_id = experiment_id
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / f"{experiment_id}.jsonl"
        self._entries: list[dict[str, Any]] = []

    def log(
        self,
        *,
        issue_id: str,
        config: str,
        agent_role: str,
        communication_mode: str,
        iteration: int,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        blackboard_state_snapshot: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Record a single agent interaction.

        Args:
            issue_id: SWE-bench issue ID.
            config: Experiment configuration label (e.g. "B-Seq").
            agent_role: Role of the agent (Planner, Coder, Reviewer, Tester).
            communication_mode: "blackboard", "message_passing", or "hybrid".
            iteration: Current iteration number.
            input_tokens: Input tokens consumed.
            output_tokens: Output tokens consumed.
            latency_ms: Wall-clock latency in milliseconds.
            blackboard_state_snapshot: Optional blackboard state dict.
            extra: Any additional fields to include.
        """
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "experiment_id": self.experiment_id,
            "issue_id": issue_id,
            "config": config,
            "agent_role": agent_role,
            "communication_mode": communication_mode,
            "iteration": iteration,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
        }
        if blackboard_state_snapshot is not None:
            entry["blackboard_state_snapshot"] = blackboard_state_snapshot
        if extra:
            entry.update(extra)

        self._entries.append(entry)
        self._append_to_file(entry)

    def get_entries(self) -> list[dict[str, Any]]:
        """Return all logged entries (in-memory copy)."""
        return list(self._entries)

    def total_tokens(self) -> tuple[int, int]:
        """Return (total_input_tokens, total_output_tokens) across all entries."""
        total_in = sum(e["input_tokens"] for e in self._entries)
        total_out = sum(e["output_tokens"] for e in self._entries)
        return total_in, total_out

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append_to_file(self, entry: dict[str, Any]) -> None:
        """Append a JSON line to the log file."""
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
