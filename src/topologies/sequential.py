"""Sequential Pipeline topology: Planner -> Coder -> Reviewer -> Tester."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from src.agents.base import BaseAgent
from src.blackboard.board import Blackboard
from src.blackboard.schema import (
    ExperimentResult,
    IssueInfo,
    Patch,
    Review,
    TestResult,
)
from src.communication.blackboard_comm import BlackboardCommunication
from src.communication.hybrid_comm import HybridCommunication
from src.communication.message_passing import MessagePassingCommunication
from src.utils.logger import ExperimentLogger

logger = logging.getLogger(__name__)


class SequentialPipeline:
    """Sequential Pipeline: Planner -> Coder -> Reviewer -> Tester.

    If the Tester reports failure, the loop restarts from the Coder (with
    feedback from the review and test results), up to *max_iterations* rounds.
    """

    def __init__(
        self,
        agents: dict[str, BaseAgent],
        communication: MessagePassingCommunication | BlackboardCommunication | HybridCommunication,
        logger: ExperimentLogger,
        max_iterations: int = 3,
        runner: Any = None,
        tool_use: bool = False,
        patch_mode: str = "diff",
        fallback_apply: bool = True,
    ) -> None:
        self.planner = agents["planner"]
        self.coder = agents["coder"]
        self.reviewer = agents["reviewer"]
        self.tester = agents["tester"]
        self.comm = communication
        self.logger = logger
        self.max_iterations = max_iterations
        self.runner = runner  # SWEBenchRunner or MockSWEBenchRunner
        self.tool_use = tool_use  # Enable tool-use mode for Coder
        self.patch_mode = patch_mode
        self.fallback_apply = fallback_apply

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, issue: IssueInfo) -> ExperimentResult:
        """Execute the full sequential pipeline for a single issue."""
        start_ms = _now_ms()
        comm_name = self._comm_name()
        config_label = f"Seq-{comm_name[:1].upper()}"

        # Prepare agent metadata
        for agent in (self.planner, self.coder, self.reviewer, self.tester):
            agent.issue_id = issue.instance_id
            agent.config_label = config_label

        # Optional: create a Blackboard for blackboard / hybrid modes
        blackboard: Blackboard | None = None
        if isinstance(self.comm, (BlackboardCommunication, HybridCommunication)):
            blackboard = self.comm.blackboard

        # ---- Step 1: Planner ----
        planner_text, planner_result = await self._run_agent(
            self.planner, issue.problem_statement, iteration=0
        )

        # ---- Step 1.5: Fetch source file contents for Coder ----
        code_context = await self._fetch_code_context(
            issue, planner_result
        )

        # ---- Step 1.6: Configure Coder mode ----
        # Set patch mode on Coder
        self.coder.patch_mode = self.patch_mode
        workspace = getattr(self.runner, "current_workspace", None) if self.runner else None
        self.coder.workspace = workspace or ""

        # Inject tool handler for Coder (if tool-use enabled)
        if self.tool_use and self.runner and workspace:
            from src.agents.coder_tools import CoderToolHandler
            tool_handler = CoderToolHandler(self.runner, workspace)
            self.coder.tool_handler = tool_handler
            logger.info("Tool-use enabled for Coder (workspace: %s)", workspace)
        else:
            self.coder.tool_handler = None

        # For whole_file mode: provide full file content to Coder
        if self.patch_mode == "whole_file" and workspace:
            full_file_context = await self._fetch_full_file_content(
                workspace, planner_result
            )
            if full_file_context:
                code_context = full_file_context

        # ---- Step 2: Iterative Coder -> Reviewer -> Tester ----
        resolved = False
        final_patch = ""
        iterations_used = 0
        previous_output = planner_text  # seed for message-passing chain

        # In hybrid/blackboard mode, code_context is already stored on the
        # blackboard (analysis.relevant_code) so we skip appending it to
        # previous_output to avoid duplication that wastes context budget.
        is_hybrid = isinstance(self.comm, HybridCommunication)
        append_code_ctx = code_context and not is_hybrid

        # Prepend code context on first iteration (MP only; hybrid has it in BB)
        if append_code_ctx:
            previous_output = f"{previous_output}\n\n{code_context}"

        for iteration in range(1, self.max_iterations + 1):
            iterations_used = iteration
            is_last = iteration == self.max_iterations
            for agent in (self.planner, self.coder, self.reviewer, self.tester):
                agent.current_iteration = iteration

            # Reset tool handler state for fresh iteration
            if self.coder.tool_handler is not None:
                self.coder.tool_handler.tool_call_count = 0
                self.coder.tool_handler.tool_trace = []
                self.coder.tool_handler._validate_fail_count = 0

            # 2a. Coder
            coder_text, coder_result = await self._run_agent(
                self.coder, previous_output, iteration=iteration
            )
            # Only update final_patch if Coder produced a non-empty diff;
            # avoids overwriting a valid earlier patch with a crash fallback.
            new_diff = coder_result.get("diff", "")
            if new_diff:
                final_patch = new_diff

            # 2b. Reviewer
            reviewer_text, reviewer_result = await self._run_agent(
                self.reviewer, coder_text, iteration=iteration
            )
            verdict = reviewer_result.get("verdict", "needs_revision")

            if verdict == "reject" and not is_last:
                # Non-final iteration: let Coder retry with feedback
                previous_output = reviewer_text
                if append_code_ctx:
                    previous_output = f"{previous_output}\n\n{code_context}"
                continue

            if verdict == "approve" or is_last:
                # Run Tester: either reviewer approved OR this is the last
                # iteration — always evaluate the patch so it doesn't go
                # untested just because the reviewer was strict.
                tester_text, tester_result = await self._run_agent(
                    self.tester, coder_text, iteration=iteration
                )
                if tester_result.get("passed", False):
                    resolved = True
                    break

                if is_last:
                    break  # No more iterations available

                # Test failed — feedback to next iteration
                previous_output = self._build_feedback(
                    reviewer_text, tester_text
                )
                if append_code_ctx:
                    previous_output = f"{previous_output}\n\n{code_context}"
            else:
                # needs_revision, not last — feedback without testing
                previous_output = reviewer_text
                if append_code_ctx:
                    previous_output = f"{previous_output}\n\n{code_context}"

        # ---- Pre-apply patch locally to record apply method ----
        apply_method = ""
        if final_patch and self.runner and hasattr(self.runner, "apply_patch_with_fallback"):
            try:
                workspace = getattr(self.runner, "current_workspace", None)
                if workspace:
                    # Reset workspace before apply attempt
                    import subprocess as _sp
                    _sp.run(["git", "checkout", "."], cwd=workspace,
                            capture_output=True, check=False)
                    apply_info = await self.runner.apply_patch_with_fallback(
                        workspace, final_patch,
                    )
                    apply_method = apply_info["method"]
                    if apply_info.get("patch_output"):
                        logger.info(
                            "Local apply result for %s: method=%s output=%s",
                            issue.instance_id, apply_method,
                            apply_info["patch_output"],
                        )
                    # Reset workspace after local apply check
                    _sp.run(["git", "checkout", "."], cwd=workspace,
                            capture_output=True, check=False)
            except Exception as exc:
                logger.warning("Local apply check failed: %s", exc)

        # ---- Build result ----
        elapsed = _now_ms() - start_ms
        entries = self.logger.get_entries()
        total_in = sum(e["input_tokens"] for e in entries)
        total_out = sum(e["output_tokens"] for e in entries)

        bb_state = None
        if blackboard is not None:
            import json as _json
            bb_state = _json.loads(blackboard.to_json())

        return ExperimentResult(
            experiment_id=f"seq_{comm_name}_{issue.instance_id}_{uuid.uuid4().hex[:8]}",
            issue_id=issue.instance_id,
            topology="sequential",
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
    # Code context retrieval
    # ------------------------------------------------------------------

    async def _fetch_code_context(
        self,
        issue: IssueInfo,
        planner_result: dict[str, Any],
    ) -> str:
        """Fetch source file contents identified by the Planner.

        Strategy:
        1. Read files from planner's relevant_files list.
        2. For files > 500 lines, extract regions around relevant_functions
           (each function +-20 lines) instead of the full file.
        3. If no files found, fallback: grep issue keywords (class names,
           function names, error messages) to locate relevant files.

        The result is also written to blackboard's analysis.relevant_code
        (for blackboard/hybrid modes) so Coder can access it directly.

        Returns a formatted string with file contents, or empty string.
        """
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
                    # Extract regions around relevant functions
                    extracted = self._extract_function_regions(
                        lines, relevant_functions, context_lines=20
                    )
                    if extracted:
                        content = extracted
                    else:
                        # No functions matched — take first 500 lines
                        content = "\n".join(lines[:500]) + "\n\n... [truncated at 500 lines] ..."
                elif len(lines) > 500:
                    content = "\n".join(lines[:500]) + "\n\n... [truncated at 500 lines] ..."

                parts.append(f"## File: {fpath}\n```python\n{content}\n```")
                files_found += 1
            except (FileNotFoundError, Exception):
                continue

        # Fallback: grep for issue keywords if no files found
        if files_found == 0 and hasattr(self.runner, "search_code"):
            keywords = self._extract_issue_keywords(
                issue.problem_statement, relevant_functions
            )
            for query in keywords[:5]:
                try:
                    matches = await self.runner.search_code(workspace, query)
                    if matches:
                        # Try to read the matched files
                        seen_files: set[str] = set()
                        for m in matches[:5]:
                            mfile = m.get("file", "")
                            if mfile and mfile not in seen_files:
                                seen_files.add(mfile)
                                try:
                                    fcontent = await self.runner.get_file_content(
                                        workspace, mfile
                                    )
                                    flines = fcontent.splitlines()
                                    if len(flines) > 300:
                                        # Extract around the match line
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
                            break  # Got some files, stop searching
                except Exception:
                    continue

            # Last resort: just report search matches
            if files_found == 0:
                for query in keywords[:3]:
                    try:
                        matches = await self.runner.search_code(workspace, query)
                        if matches:
                            match_text = "\n".join(
                                f"  {m['file']}:{m['line']}: {m['content']}"
                                for m in matches[:10]
                            )
                            parts.append(f"## Search results for '{query}':\n{match_text}")
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

    async def _fetch_full_file_content(
        self,
        workspace: str,
        planner_result: dict[str, Any],
    ) -> str:
        """Fetch COMPLETE file contents for whole-file rewrite mode.

        Unlike :meth:`_fetch_code_context`, this returns the full file (with
        line numbers) so the Coder can output a complete rewrite.  Files over
        2000 lines fall back to the standard truncated context.
        """
        from src.agents.coder import WHOLE_FILE_MAX_LINES

        relevant_files = planner_result.get("relevant_files", [])
        if not relevant_files:
            return ""

        parts: list[str] = []
        for fpath in relevant_files[:3]:  # Limit to 3 files to stay within token budget
            try:
                content = await self.runner.get_file_content(workspace, fpath)
                lines = content.splitlines()

                if len(lines) > WHOLE_FILE_MAX_LINES:
                    logger.info(
                        "File %s has %d lines (> %d), too large for whole-file mode",
                        fpath, len(lines), WHOLE_FILE_MAX_LINES,
                    )
                    # Provide truncated version with note
                    numbered = [f"{i+1:>4}| {line}" for i, line in enumerate(lines[:500])]
                    content = "\n".join(numbered)
                    parts.append(
                        f"**File: {fpath}** ({len(lines)} lines — TOO LARGE for full rewrite, "
                        f"showing first 500 lines. Use diff mode for this file.)\n"
                        f"```python\n{content}\n```"
                    )
                else:
                    # Provide full file with line numbers
                    numbered = [f"{i+1:>4}| {line}" for i, line in enumerate(lines)]
                    content = "\n".join(numbered)
                    parts.append(
                        f"**File: {fpath}** ({len(lines)} lines — COMPLETE)\n"
                        f"```python\n{content}\n```"
                    )
            except (FileNotFoundError, Exception):
                continue

        if not parts:
            return ""

        result = "## Complete Source Files (for whole-file rewrite)\n\n" + "\n\n".join(parts)

        # Also write to blackboard for BB/hybrid modes
        if isinstance(self.comm, (BlackboardCommunication, HybridCommunication)):
            bb = self.comm.blackboard
            state = bb.get_state()
            state.analysis.relevant_code = result
            bb.update_analysis(state.analysis)

        return result

    @staticmethod
    def _extract_function_regions(
        lines: list[str],
        function_names: list[str],
        context_lines: int = 20,
    ) -> str:
        """Extract code regions around named functions/classes.

        Searches for ``def func_name`` or ``class ClassName`` and returns
        the surrounding region (+-context_lines).
        """
        import re

        regions: list[tuple[int, int]] = []
        for fname in function_names:
            # Escape for regex, search for def/class declarations
            escaped = re.escape(fname)
            pattern = re.compile(
                rf"^\s*(def|class)\s+{escaped}\s*[\(:]", re.IGNORECASE
            )
            for i, line in enumerate(lines):
                if pattern.match(line):
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    regions.append((start, end))

        if not regions:
            return ""

        # Merge overlapping regions
        regions.sort()
        merged: list[tuple[int, int]] = [regions[0]]
        for start, end in regions[1:]:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

        # Build output
        parts: list[str] = []
        for start, end in merged:
            parts.append(
                f"... [lines {start+1}-{end}] ...\n"
                + "\n".join(lines[start:end])
            )
        return "\n\n".join(parts)

    @staticmethod
    def _extract_issue_keywords(
        problem_statement: str,
        relevant_functions: list[str],
    ) -> list[str]:
        """Extract searchable keywords from the issue text.

        Looks for CamelCase class names, function-like identifiers, and
        uses the planner's relevant_functions as primary keywords.
        """
        import re

        keywords: list[str] = []

        # Use planner's functions first
        keywords.extend(relevant_functions)

        # Extract CamelCase identifiers (likely class names)
        camel = re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", problem_statement)
        keywords.extend(camel[:3])

        # Extract snake_case function names
        snake = re.findall(r"\b[a-z_][a-z0-9_]{3,}\b", problem_statement)
        # Filter common English words
        common = {"with", "from", "this", "that", "have", "will", "when", "should",
                  "could", "would", "were", "been", "into", "also", "some", "than",
                  "then", "only", "just", "like", "more", "does", "each", "other",
                  "make", "made", "very", "after", "before", "about", "which", "their",
                  "there", "first", "last", "over", "such", "because", "through",
                  "between", "same", "test", "tests", "true", "false", "none"}
        snake = [s for s in snake if s not in common and len(s) >= 4]
        keywords.extend(snake[:5])

        # Deduplicate while preserving order
        seen: set[str] = set()
        result: list[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                result.append(kw)
        return result

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
        """Run a single agent through the configured communication mode.

        On failure (e.g. LLM parse error), returns a fallback result instead
        of crashing the entire pipeline.
        """
        agent.current_iteration = iteration

        try:
            if isinstance(self.comm, BlackboardCommunication):
                result = await self.comm.run_agent(agent)
                text = f"[{agent.role} Output]\n{json.dumps(result, indent=2, default=str)}"
                return text, result

            if isinstance(self.comm, HybridCommunication):
                return await self.comm.run_agent(agent, context)

            # MessagePassingCommunication
            return await self.comm.run_agent(agent, context)

        except Exception as exc:
            logger.warning("Agent %s failed at iteration %d: %s", agent.role, iteration, exc)
            fallback = self._fallback_result(agent.role)
            text = f"[{agent.role} Output - ERROR]\n{exc}"
            return text, fallback

    def _comm_name(self) -> str:
        if isinstance(self.comm, BlackboardCommunication):
            return "blackboard"
        if isinstance(self.comm, HybridCommunication):
            return "hybrid"
        return "message_passing"

    @staticmethod
    def _fallback_result(role: str) -> dict[str, Any]:
        """Return a minimal fallback result when an agent fails."""
        if role == "Planner":
            return {"root_cause": "Error during analysis", "relevant_files": [], "relevant_functions": [], "fix_strategy": "", "confidence": 0.0}
        if role == "Coder":
            return {"version": 0, "author": "Coder", "diff": "", "description": "Error during patch generation", "timestamp": ""}
        if role == "Reviewer":
            return {"patch_version": 0, "author": "Reviewer", "verdict": "needs_revision", "issues": ["Agent error"], "suggestions": []}
        if role == "Tester":
            return {"patch_version": 0, "passed": False, "error_traces": ["Agent error"]}
        return {}

    @staticmethod
    def _build_feedback(reviewer_text: str, tester_text: str) -> str:
        return (
            f"## Review Feedback\n{reviewer_text}\n\n"
            f"## Test Results\n{tester_text}"
        )


def _now_ms() -> int:
    return int(time.perf_counter() * 1000)
