"""Peer Debate topology: two Coders generate competing patches."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from src.agents.base import BaseAgent
from src.blackboard.board import Blackboard
from src.blackboard.schema import ExperimentResult, IssueInfo
from src.communication.blackboard_comm import BlackboardCommunication
from src.communication.hybrid_comm import HybridCommunication
from src.communication.message_passing import MessagePassingCommunication
from src.utils.logger import ExperimentLogger

_logger = logging.getLogger(__name__)


class PeerDebate:
    """Peer Debate: two Coders independently generate patches, Reviewer picks the best.

    Flow:
        1. Planner analyses the issue.
        2. Loop (up to *max_iterations*):
            a. Coder_A and Coder_B independently generate patches.
            b. Reviewer evaluates both, selects the better one (or merges).
            c. Tester tests the chosen patch.
            d. Pass -> resolved; Fail -> feed back to both Coders.
    """

    def __init__(
        self,
        agents: dict[str, BaseAgent],
        communication: MessagePassingCommunication | BlackboardCommunication | HybridCommunication,
        logger: ExperimentLogger,
        max_iterations: int = 3,
        runner: Any = None,
        patch_mode: str = "diff",
        fallback_apply: bool = True,
    ) -> None:
        self.planner = agents["planner"]
        self.coder_a = agents["coder_a"]
        self.coder_b = agents["coder_b"]
        self.reviewer = agents["reviewer"]
        self.tester = agents["tester"]

        # Differentiate authors for blackboard patches
        self.coder_a.coder_label = "Coder_A"
        self.coder_b.coder_label = "Coder_B"
        self.comm = communication
        self.logger = logger
        self.max_iterations = max_iterations
        self.runner = runner
        self.patch_mode = patch_mode
        self.fallback_apply = fallback_apply

    async def run(self, issue: IssueInfo) -> ExperimentResult:
        start_ms = _now_ms()
        comm_name = self._comm_name()
        config_label = f"Deb-{comm_name[:1].upper()}"

        all_agents = [
            self.planner, self.coder_a, self.coder_b, self.reviewer, self.tester,
        ]
        for agent in all_agents:
            agent.issue_id = issue.instance_id
            agent.config_label = config_label

        blackboard: Blackboard | None = None
        if isinstance(self.comm, (BlackboardCommunication, HybridCommunication)):
            blackboard = self.comm.blackboard

        # ---- Step 1: Planner ----
        planner_text, planner_result = await self._run_agent(
            self.planner, issue.problem_statement, iteration=0
        )

        # ---- Step 1.5: Fetch source file contents for Coders ----
        code_context = await self._fetch_code_context(issue, planner_result)

        # ---- Step 1.6: Configure Coder mode ----
        workspace = getattr(self.runner, "current_workspace", None) if self.runner else None
        for coder in (self.coder_a, self.coder_b):
            coder.patch_mode = self.patch_mode
            coder.workspace = workspace or ""

        # For whole_file mode: provide full file content
        if self.patch_mode == "whole_file" and workspace:
            from src.topologies.sequential import SequentialPipeline
            # Reuse the sequential pipeline's full-file fetch method via a temporary instance trick
            full_parts: list[str] = []
            relevant_files = planner_result.get("relevant_files", [])
            from src.agents.coder import WHOLE_FILE_MAX_LINES
            for fpath in relevant_files[:3]:
                try:
                    content = await self.runner.get_file_content(workspace, fpath)
                    lines = content.splitlines()
                    if len(lines) > WHOLE_FILE_MAX_LINES:
                        numbered = [f"{i+1:>4}| {line}" for i, line in enumerate(lines[:500])]
                        content = "\n".join(numbered)
                        full_parts.append(
                            f"**File: {fpath}** ({len(lines)} lines — TOO LARGE)\n"
                            f"```python\n{content}\n```"
                        )
                    else:
                        numbered = [f"{i+1:>4}| {line}" for i, line in enumerate(lines)]
                        content = "\n".join(numbered)
                        full_parts.append(
                            f"**File: {fpath}** ({len(lines)} lines — COMPLETE)\n"
                            f"```python\n{content}\n```"
                        )
                except Exception:
                    continue
            if full_parts:
                code_context = "## Complete Source Files (for whole-file rewrite)\n\n" + "\n\n".join(full_parts)
                if isinstance(self.comm, (BlackboardCommunication, HybridCommunication)):
                    bb = self.comm.blackboard
                    state = bb.get_state()
                    state.analysis.relevant_code = code_context
                    bb.update_analysis(state.analysis)

        resolved = False
        final_patch = ""
        iterations_used = 0
        previous_output = planner_text

        # In hybrid mode, code_context is already on the blackboard
        is_hybrid = isinstance(self.comm, HybridCommunication)
        append_code_ctx = code_context and not is_hybrid

        if append_code_ctx:
            previous_output = f"{previous_output}\n\n{code_context}"

        for iteration in range(1, self.max_iterations + 1):
            iterations_used = iteration
            is_last = iteration == self.max_iterations
            for agent in all_agents:
                agent.current_iteration = iteration

            # 2a. Two Coders in parallel
            coder_a_text, coder_a_result = await self._run_agent(
                self.coder_a, previous_output, iteration=iteration
            )
            coder_b_text, coder_b_result = await self._run_agent(
                self.coder_b, previous_output, iteration=iteration
            )

            # Combine both patches for the Reviewer
            combined_for_review = (
                f"## Patch A\n{coder_a_text}\n\n"
                f"## Patch B\n{coder_b_text}"
            )

            # 2b. Reviewer picks the best
            reviewer_text, reviewer_result = await self._run_agent(
                self.reviewer, combined_for_review, iteration=iteration
            )

            verdict = reviewer_result.get("verdict", "needs_revision")
            # Use Patch A by default; if reviewer mentions B, use B
            chosen_patch_text = coder_a_text
            chosen_patch_result = coder_a_result
            review_text_lower = json.dumps(reviewer_result).lower()
            if "patch b" in review_text_lower or "b is better" in review_text_lower:
                chosen_patch_text = coder_b_text
                chosen_patch_result = coder_b_result

            new_diff = chosen_patch_result.get("diff", "")
            if new_diff:
                final_patch = new_diff

            if verdict == "reject" and not is_last:
                previous_output = reviewer_text
                if append_code_ctx:
                    previous_output = f"{previous_output}\n\n{code_context}"
                continue

            if verdict == "approve" or is_last:
                # 2c. Tester — always run on last iteration
                tester_text, tester_result = await self._run_agent(
                    self.tester, chosen_patch_text, iteration=iteration
                )
                if tester_result.get("passed", False):
                    resolved = True
                    break

                if is_last:
                    break

                previous_output = (
                    f"## Review Feedback\n{reviewer_text}\n\n"
                    f"## Test Results\n{tester_text}"
                )
                if append_code_ctx:
                    previous_output = f"{previous_output}\n\n{code_context}"
            else:
                previous_output = reviewer_text
                if append_code_ctx:
                    previous_output = f"{previous_output}\n\n{code_context}"

        # ---- Pre-apply patch locally to record apply method ----
        apply_method = ""
        if final_patch and self.runner and hasattr(self.runner, "apply_patch_with_fallback"):
            try:
                workspace = getattr(self.runner, "current_workspace", None)
                if workspace:
                    import subprocess as _sp
                    _sp.run(["git", "checkout", "."], cwd=workspace,
                            capture_output=True, check=False)
                    apply_info = await self.runner.apply_patch_with_fallback(
                        workspace, final_patch,
                    )
                    apply_method = apply_info["method"]
                    if apply_info.get("patch_output"):
                        _logger.info(
                            "Local apply result for %s: method=%s output=%s",
                            issue.instance_id, apply_method,
                            apply_info["patch_output"],
                        )
                    _sp.run(["git", "checkout", "."], cwd=workspace,
                            capture_output=True, check=False)
            except Exception as exc:
                _logger.warning("Local apply check failed: %s", exc)

        elapsed = _now_ms() - start_ms
        entries = self.logger.get_entries()
        total_in = sum(e["input_tokens"] for e in entries)
        total_out = sum(e["output_tokens"] for e in entries)

        bb_state = None
        if blackboard is not None:
            bb_state = json.loads(blackboard.to_json())

        return ExperimentResult(
            experiment_id=f"deb_{comm_name}_{issue.instance_id}_{uuid.uuid4().hex[:8]}",
            issue_id=issue.instance_id,
            topology="debate",
            communication=comm_name,
            resolved=resolved,
            iterations=iterations_used,
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            total_latency_ms=elapsed,
            final_patch=final_patch,
            apply_method=apply_method,
            agent_traces=entries,
            blackboard_final_state=bb_state,
        )

    # ------------------------------------------------------------------
    # Code context retrieval (shared logic with SequentialPipeline)
    # ------------------------------------------------------------------

    async def _fetch_code_context(
        self,
        issue: IssueInfo,
        planner_result: dict[str, Any],
    ) -> str:
        """Fetch source file contents — delegates to SequentialPipeline's implementation."""
        from src.topologies.sequential import SequentialPipeline

        # Reuse the static helpers; only need runner + comm for the method
        if self.runner is None:
            return ""

        relevant_files = planner_result.get("relevant_files", [])
        relevant_functions = planner_result.get("relevant_functions", [])

        try:
            workspace = await self.runner.setup_instance(issue.instance_id)
        except Exception:
            return ""

        parts: list[str] = []
        files_found = 0

        for fpath in relevant_files[:5]:
            try:
                content = await self.runner.get_file_content(workspace, fpath)
                lines = content.splitlines()

                if len(lines) > 500 and relevant_functions:
                    extracted = SequentialPipeline._extract_function_regions(
                        lines, relevant_functions, context_lines=20
                    )
                    if extracted:
                        content = extracted
                    else:
                        content = "\n".join(lines[:500]) + "\n\n... [truncated at 500 lines] ..."
                elif len(lines) > 500:
                    content = "\n".join(lines[:500]) + "\n\n... [truncated at 500 lines] ..."

                parts.append(f"## File: {fpath}\n```python\n{content}\n```")
                files_found += 1
            except (FileNotFoundError, Exception):
                continue

        # Fallback: grep for issue keywords
        if files_found == 0 and hasattr(self.runner, "search_code"):
            keywords = SequentialPipeline._extract_issue_keywords(
                issue.problem_statement, relevant_functions
            )
            for query in keywords[:5]:
                try:
                    matches = await self.runner.search_code(workspace, query)
                    if matches:
                        seen_files: set[str] = set()
                        for m in matches[:5]:
                            mfile = m.get("file", "")
                            if mfile and mfile not in seen_files:
                                seen_files.add(mfile)
                                try:
                                    fcontent = await self.runner.get_file_content(workspace, mfile)
                                    flines = fcontent.splitlines()
                                    if len(flines) > 300:
                                        mline = m.get("line", 0)
                                        start = max(0, mline - 30)
                                        end = min(len(flines), mline + 30)
                                        fcontent = (
                                            f"... [lines {start+1}-{end}] ...\n"
                                            + "\n".join(flines[start:end])
                                        )
                                    parts.append(
                                        f"## File: {mfile} (found via search '{query}')\n"
                                        f"```python\n{fcontent}\n```"
                                    )
                                    files_found += 1
                                except Exception:
                                    pass
                        if files_found > 0:
                            break
                except Exception:
                    continue

        if not parts:
            return ""

        code_context = "## Source Code Context\n\n" + "\n\n".join(parts)

        # Write to blackboard for blackboard/hybrid modes
        if isinstance(self.comm, (BlackboardCommunication, HybridCommunication)):
            bb = self.comm.blackboard
            state = bb.get_state()
            state.analysis.relevant_code = code_context
            bb.update_analysis(state.analysis)

        return code_context

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_agent(
        self,
        agent: BaseAgent,
        context: str,
        *,
        iteration: int,
    ) -> tuple[str, dict[str, Any]]:
        agent.current_iteration = iteration

        try:
            if isinstance(self.comm, BlackboardCommunication):
                result = await self.comm.run_agent(agent)
                text = f"[{agent.role} Output]\n{json.dumps(result, indent=2, default=str)}"
                return text, result

            if isinstance(self.comm, HybridCommunication):
                return await self.comm.run_agent(agent, context)

            return await self.comm.run_agent(agent, context)

        except Exception as exc:
            fallback = self._fallback_result(agent.role)
            text = f"[{agent.role} Output - ERROR]\n{exc}"
            return text, fallback

    @staticmethod
    def _fallback_result(role: str) -> dict[str, Any]:
        """Return a minimal fallback result when an agent fails."""
        if role == "Planner":
            return {"root_cause": "Error", "relevant_files": [], "relevant_functions": [], "fix_strategy": "", "confidence": 0.0}
        if role == "Coder":
            return {"version": 0, "author": "Coder", "diff": "", "description": "Error", "timestamp": ""}
        if role == "Reviewer":
            return {"patch_version": 0, "author": "Reviewer", "verdict": "needs_revision", "issues": ["Agent error"], "suggestions": []}
        if role == "Tester":
            return {"patch_version": 0, "passed": False, "error_traces": ["Agent error"]}
        return {}

    def _comm_name(self) -> str:
        if isinstance(self.comm, BlackboardCommunication):
            return "blackboard"
        if isinstance(self.comm, HybridCommunication):
            return "hybrid"
        return "message_passing"


def _now_ms() -> int:
    return int(time.perf_counter() * 1000)
