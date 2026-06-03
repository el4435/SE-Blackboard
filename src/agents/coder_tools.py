"""Tool handler for CoderAgent tool-use mode.

Provides tools for reading files, searching code, validating patches,
and submitting final patches. Each tool delegates to SWEBenchRunner methods.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Any

logger = logging.getLogger(__name__)


class CoderToolHandler:
    """Manages tool definitions and execution for the Coder agent.

    Args:
        runner: SWEBenchRunner instance (real or mock).
        workspace: Absolute path to the checked-out repository.
    """

    def __init__(self, runner: Any, workspace: str) -> None:
        self.runner = runner
        self.workspace = workspace
        self.tool_call_count: int = 0
        self.max_tool_calls: int = 15
        self.tool_trace: list[dict[str, Any]] = []
        self._validate_fail_count: int = 0

    # ------------------------------------------------------------------
    # Tool definitions (Claude API format)
    # ------------------------------------------------------------------

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return tool definitions in Claude API tool-use format."""
        return [
            {
                "name": "read_file",
                "description": (
                    "Read the content of a file (first 200 lines). "
                    "For longer files, use read_lines for specific ranges."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "File path relative to repository root, e.g. 'django/db/models/query.py'",
                        }
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "search_code",
                "description": (
                    "Search for code patterns in the repository using grep. "
                    "Returns matching file paths and line numbers."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search string or pattern to find in the codebase",
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "Optional file glob pattern, e.g. '*.py'. Defaults to all Python files.",
                            "default": "*.py",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "validate_patch",
                "description": (
                    "Test whether a unified diff patch can be successfully applied to the codebase. "
                    "Returns success or the exact error message from git apply. "
                    "Use this BEFORE submitting your final patch to catch context line mismatches."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patch_diff": {
                            "type": "string",
                            "description": "The complete unified diff to validate",
                        }
                    },
                    "required": ["patch_diff"],
                },
            },
            {
                "name": "read_lines",
                "description": (
                    "Read specific line range from a file. "
                    "Use this to get exact context lines for your patch."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "File path relative to repository root",
                        },
                        "start_line": {
                            "type": "integer",
                            "description": "Starting line number (1-indexed)",
                        },
                        "end_line": {
                            "type": "integer",
                            "description": "Ending line number (inclusive)",
                        },
                    },
                    "required": ["file_path", "start_line", "end_line"],
                },
            },
            {
                "name": "submit_patch",
                "description": (
                    "Submit your final patch. Call this when you are confident the patch is correct. "
                    "You should validate_patch first."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patch_diff": {
                            "type": "string",
                            "description": "The final unified diff patch to submit",
                        },
                        "description": {
                            "type": "string",
                            "description": "Brief description of what this patch fixes",
                        },
                    },
                    "required": ["patch_diff", "description"],
                },
            },
        ]

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def handle_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a single tool call and return the result string."""
        self.tool_call_count += 1

        # Build trace entry
        trace_entry: dict[str, Any] = {
            "call_number": self.tool_call_count,
            "tool": tool_name,
            "input_summary": self._summarize_input(tool_name, tool_input),
        }

        try:
            result = await self._dispatch(tool_name, tool_input)
        except Exception as exc:
            result = f"Error: {exc}"

        trace_entry["output_summary"] = self._summarize_output(tool_name, result)
        self.tool_trace.append(trace_entry)
        logger.info(
            "Tool call #%d: %s -> %s",
            self.tool_call_count,
            trace_entry["input_summary"],
            trace_entry["output_summary"],
        )
        return result

    async def _dispatch(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name == "read_file":
            return await self._read_file(tool_input)
        if tool_name == "search_code":
            return await self._search_code(tool_input)
        if tool_name == "validate_patch":
            return self._validate_patch(tool_input)
        if tool_name == "read_lines":
            return await self._read_lines(tool_input)
        if tool_name == "submit_patch":
            return "SUBMITTED"
        return f"Unknown tool: {tool_name}"

    # ------------------------------------------------------------------
    # Individual tool implementations
    # ------------------------------------------------------------------

    async def _read_file(self, tool_input: dict[str, Any]) -> str:
        content = await self.runner.get_file_content(
            self.workspace, tool_input["file_path"]
        )
        lines = content.split("\n")
        numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
        if len(numbered) > 200:
            return (
                f"File has {len(lines)} lines. Showing first 200:\n"
                + "\n".join(numbered[:200])
                + f"\n\n... [{len(lines) - 200} more lines] "
                "Use read_lines(file, start, end) for specific ranges."
            )
        return "\n".join(numbered)

    async def _search_code(self, tool_input: dict[str, Any]) -> str:
        results = await self.runner.search_code(
            self.workspace, tool_input["query"]
        )
        if not results:
            return "No matches found."
        results = results[:15]
        formatted = [
            f"{r['file']}:{r['line']}: {r['content']}" for r in results
        ]
        return "\n".join(formatted)

    def _validate_patch(self, tool_input: dict[str, Any]) -> str:
        from src.agents.coder import fix_hunk_counts

        patch_diff = tool_input["patch_diff"]
        # Auto-fix hunk line counts (LLMs frequently miscount)
        patch_diff = fix_hunk_counts(patch_diff)
        abs_workspace = os.path.abspath(self.workspace)
        patch_file = os.path.join(abs_workspace, "_validate_temp.diff")
        try:
            with open(patch_file, "w", newline="\n", encoding="utf-8") as f:
                f.write(patch_diff.replace("\r\n", "\n"))

            # 1. Strict check
            result = subprocess.run(
                ["git", "apply", "--check", patch_file],
                cwd=abs_workspace,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                self._validate_fail_count = 0
                return "VALID: Patch applies cleanly. Call submit_patch now."

            # 2. Lenient: ignore whitespace differences
            result2 = subprocess.run(
                ["git", "apply", "--check", "--ignore-whitespace", patch_file],
                cwd=abs_workspace,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result2.returncode == 0:
                self._validate_fail_count = 0
                return (
                    "VALID (lenient): Patch applies with whitespace tolerance. "
                    "Good enough — call submit_patch now."
                )

            # Failed both checks
            self._validate_fail_count += 1
            error = result.stderr.strip()

            if self._validate_fail_count >= 2:
                return (
                    f"FAILED {self._validate_fail_count}x. STOP retrying. "
                    "The evaluation harness uses fuzz-matching (patch --fuzz=5) "
                    "which is much more lenient than git apply. "
                    "Your patch is likely close enough. Call submit_patch NOW."
                )

            return (
                f"INVALID: {error}\n"
                f"Hint: Use read_lines for exact context lines, then retry once."
            )
        except Exception as exc:
            return f"Error validating patch: {exc}"
        finally:
            if os.path.exists(patch_file):
                os.remove(patch_file)

    async def _read_lines(self, tool_input: dict[str, Any]) -> str:
        content = await self.runner.get_file_content(
            self.workspace, tool_input["file_path"]
        )
        lines = content.split("\n")
        start = max(0, tool_input["start_line"] - 1)
        end = min(len(lines), tool_input["end_line"])
        numbered = [f"{i + 1:4d} | {lines[i]}" for i in range(start, end)]
        return "\n".join(numbered)

    # ------------------------------------------------------------------
    # Trace helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize_input(tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name == "read_file":
            return f"read_file({tool_input.get('file_path', '?')})"
        if tool_name == "search_code":
            return f"search_code('{tool_input.get('query', '?')}')"
        if tool_name == "validate_patch":
            diff = tool_input.get("patch_diff", "")
            return f"validate_patch({len(diff)} chars)"
        if tool_name == "read_lines":
            return (
                f"read_lines({tool_input.get('file_path', '?')}, "
                f"{tool_input.get('start_line', '?')}-{tool_input.get('end_line', '?')})"
            )
        if tool_name == "submit_patch":
            diff = tool_input.get("patch_diff", "")
            return f"submit_patch({len(diff)} chars)"
        return f"{tool_name}({tool_input})"

    @staticmethod
    def _summarize_output(tool_name: str, result: str) -> str:
        if tool_name == "validate_patch":
            return result.split("\n")[0]  # First line: VALID or INVALID
        if len(result) > 100:
            return f"{result[:100]}..."
        return result
