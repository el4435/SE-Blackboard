"""CoderAgent: generates a unified-diff patch to fix the issue."""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings
from src.blackboard.schema import Patch
from .base import BaseAgent

logger = logging.getLogger(__name__)

# Maximum characters for context to avoid token overflow.
# Raised from 12000 to 24000: hybrid mode combines blackboard state
# (issue + analysis + code) with previous agent output, requiring
# a larger budget to avoid losing critical source code context.
MAX_CONTEXT_CHARS = 24000


def validate_diff(diff: str) -> bool:
    """Check whether *diff* looks like a valid unified diff.

    Returns True if the diff contains at least one file header and one hunk.
    """
    if not diff or not diff.strip():
        return False
    has_file_header = bool(re.search(r"^---\s", diff, re.MULTILINE))
    has_hunk = bool(re.search(r"^@@\s", diff, re.MULTILINE))
    has_changes = bool(re.search(r"^[+-]", diff, re.MULTILINE))
    return has_file_header and has_hunk and has_changes


def fix_hunk_counts(diff: str) -> str:
    """Recalculate @@ hunk line counts to match actual content.

    LLMs frequently miscount context/change lines in unified diffs.
    This fixes the counts so ``git apply`` doesn't reject the patch
    for a trivially wrong header.
    """
    lines = diff.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)", lines[i])
        if m:
            old_start = int(m.group(1))
            new_start = int(m.group(2))
            rest = m.group(3)
            # Scan hunk body to count actual lines
            j = i + 1
            old_count = 0
            new_count = 0
            while j < len(lines):
                ln = lines[j]
                if (
                    ln.startswith("@@")
                    or ln.startswith("diff --git")
                    or ln.startswith("--- ")
                    or ln.startswith("+++ ")
                ):
                    break
                if ln.startswith("-"):
                    old_count += 1
                elif ln.startswith("+"):
                    new_count += 1
                else:
                    # Context line (space prefix or empty)
                    old_count += 1
                    new_count += 1
                j += 1
            result.append(
                f"@@ -{old_start},{old_count} +{new_start},{new_count} @@{rest}"
            )
        else:
            result.append(lines[i])
        i += 1
    return "\n".join(result)


def truncate_context(context: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Truncate context to avoid token overflow, keeping the beginning."""
    if len(context) <= max_chars:
        return context
    return context[:max_chars] + "\n\n... [truncated — context too long] ..."
# Whole-file rewrite helpers

# Maximum file line count for whole-file mode; beyond this, fall back to diff.
WHOLE_FILE_MAX_LINES = 2000


def extract_file_blocks(coder_output: str) -> list[dict[str, str]]:
    """Extract file path + content blocks from Coder's whole-file output.

    Expected format::

        ```path/to/file.py
        <complete file content>
        ```

    Returns a list of ``{"path": str, "content": str}`` dicts.
    """
    pattern = r"```(\S+)\n(.*?)```"
    matches = re.findall(pattern, coder_output, re.DOTALL)
    blocks: list[dict[str, str]] = []
    for path, content in matches:
        # Skip common false-positive language tags
        if path.lower() in ("diff", "patch", "python", "json", "bash", "text"):
            continue
        # Must look like a file path (contains / or \\ or ends with .py etc.)
        if "/" in path or "\\" in path or "." in path:
            blocks.append({"path": path, "content": content})
    return blocks


def generate_diff_from_rewrite(
    repo_dir: str,
    file_path: str,
    new_content: str,
) -> str:
    """Generate a unified diff by comparing the original file with new content.

    Uses Python's ``difflib`` for cross-platform compatibility (no external
    ``diff`` binary required).

    Returns a unified diff string with ``a/`` and ``b/`` prefixes, or empty
    string if the files are identical.
    """
    original_path = os.path.join(repo_dir, file_path)
    try:
        with open(original_path, "r", encoding="utf-8", errors="replace") as f:
            original_content = f.read()
    except FileNotFoundError:
        logger.warning("Original file not found: %s", original_path)
        return ""

    # Normalize line endings to LF for consistent diffing
    original_content = original_content.replace("\r\n", "\n").replace("\r", "\n")
    new_content = new_content.replace("\r\n", "\n").replace("\r", "\n")

    # Strip line-number prefixes the LLM may have copied (e.g. "   1| ")
    new_lines_raw = new_content.split("\n")
    if new_lines_raw and re.match(r"^\s*\d+\| ", new_lines_raw[0]):
        new_lines_raw = [re.sub(r"^\s*\d+\| ", "", line) for line in new_lines_raw]
        new_content = "\n".join(new_lines_raw)

    # Ensure final newline
    if not original_content.endswith("\n"):
        original_content += "\n"
    if not new_content.endswith("\n"):
        new_content += "\n"

    original_lines = original_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff_lines = list(difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    ))

    if not diff_lines:
        return ""

    return "".join(diff_lines)


def whole_file_to_patch(repo_dir: str, coder_output: str) -> str:
    """Convert Coder's whole-file rewrite output to a unified diff patch.

    Extracts `````file_path ... ``` `` blocks, diffs each against the original
    file, and concatenates the results.

    Returns a combined unified diff string, or empty string on failure.
    """
    file_blocks = extract_file_blocks(coder_output)

    if not file_blocks:
        logger.warning("No file blocks extracted from whole-file output")
        return ""

    patches: list[str] = []
    for block in file_blocks:
        diff = generate_diff_from_rewrite(repo_dir, block["path"], block["content"])
        if diff.strip():
            patches.append(diff)

    return "\n".join(patches)


class CoderAgent(BaseAgent):
    """Generates a code patch based on the analysis and optional review feedback.

    Input (varies by communication mode):
        - Message-Passing: natural-language context including analysis, code
          snippets, and optionally previous review feedback / test failures.
        - Blackboard: formatted blackboard state string for Coder.
        - Hybrid: both combined.

    Output: ``Patch`` serialized as a dict.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(role="Coder", **kwargs)
        self._patch_version: int = 0
        self.coder_label: str = "Coder"
        self.tool_handler: Any = None  # Injected by pipeline when tool-use is enabled
        self.patch_mode: str = "diff"  # "diff" (default) or "whole_file"
        self.workspace: str = ""  # Set by pipeline for whole_file mode

    async def execute(self, context: str) -> dict[str, Any]:
        """Generate a patch and return it as a Patch dict.

        Args:
            context: Analysis + code context (+ review feedback on iterations > 1).

        Returns:
            ``Patch`` model serialized as a dict.
        """
        self._patch_version += 1

        # Tool-use mode: multi-turn conversation with tool calls
        if self.tool_handler is not None:
            return await self._execute_with_tools(context)

        # Whole-file rewrite mode
        if self.patch_mode == "whole_file":
            return await self._execute_whole_file(context)

        return await self._execute_direct(context)

    async def _execute_direct(self, context: str) -> dict[str, Any]:
        """Original single-shot patch generation (no tools)."""
        schema_json = json.dumps(Patch.model_json_schema(), indent=2)
        prompt_section = self._get_prompt_section(self.communication_mode)

        system_prompt = (
            "You are an expert software engineer tasked with generating a code patch "
            "to fix a GitHub issue. Always respond with valid JSON only, no extra text."
        )

        # Truncate overly long context to stay within token limits
        context = truncate_context(context)

        if self.communication_mode in ("blackboard", "hybrid"):
            user_message = prompt_section.format(schema=schema_json, state=context)
        else:
            user_message = prompt_section.format(schema=schema_json, context=context)

        # First attempt
        patch, in_tok, out_tok = await self._call_llm_structured(
            system_prompt, user_message, Patch
        )

        # Validate diff format — retry once if invalid
        if not validate_diff(patch.diff):
            retry_msg = (
                f"{user_message}\n\n"
                "IMPORTANT: Your previous patch had an invalid diff format. "
                "The diff field MUST be a valid unified diff starting with "
                "'--- a/...' and '+++ b/...' headers, followed by @@ hunks. "
                "Please generate a corrected patch."
            )
            patch, in_tok2, out_tok2 = await self._call_llm_structured(
                system_prompt, retry_msg, Patch
            )
            in_tok += in_tok2
            out_tok += out_tok2

        # Override version and timestamp to ensure consistency
        patch_dict = patch.model_dump()
        patch_dict["diff"] = fix_hunk_counts(patch_dict.get("diff", ""))
        patch_dict["version"] = self._patch_version
        patch_dict["author"] = self.coder_label
        patch_dict["timestamp"] = datetime.now(timezone.utc)
        return patch_dict
    # Whole-file rewrite mode

    async def _execute_whole_file(self, context: str) -> dict[str, Any]:
        """Whole-file rewrite mode: Coder outputs complete file as free-form text.

        Uses ``_call_llm`` (not structured JSON) because embedding entire file
        contents inside a JSON string value reliably causes parse failures.
        The framework extracts file blocks from the raw text and generates
        the unified diff programmatically via :func:`whole_file_to_patch`.
        """
        system_prompt = (
            "You are an expert software engineer tasked with fixing a GitHub issue. "
            "You must output the COMPLETE modified file content so the framework "
            "can automatically generate a correct diff.\n\n"
            "RULES:\n"
            "1. Output the ENTIRE file with your fix applied — every single line.\n"
            "2. Wrap each file in a fenced code block whose info-string is the file path:\n"
            "   ```path/to/file.py\n"
            "   <complete file content>\n"
            "   ```\n"
            "3. Do NOT output a diff. Do NOT output partial content.\n"
            "4. Do NOT include line numbers in the output (no '  1| ' prefix).\n"
            "5. Be minimal: only change what is necessary to fix the issue.\n"
            "6. You may output multiple files if needed."
        )

        context = truncate_context(context, max_chars=MAX_CONTEXT_CHARS * 2)

        # Strip line-number prefixes from the context hint so the LLM
        # doesn't parrot them back into the output.
        context_clean = re.sub(r"^\s*\d+\| ", "", context, flags=re.MULTILINE)

        user_message = (
            "Fix the issue described below by outputting the complete modified file(s).\n\n"
            f"{context_clean}"
        )

        raw_text, in_tok, out_tok = await self._call_llm(
            system_prompt, user_message,
            max_tokens=settings.WHOLE_FILE_MAX_TOKENS,
        )

        # ---- Convert whole-file blocks to unified diff ----
        diff_result = ""

        if self.workspace and raw_text:
            diff_result = whole_file_to_patch(self.workspace, raw_text)
            if diff_result:
                logger.info(
                    "Whole-file mode: generated diff (%d chars) from file blocks",
                    len(diff_result),
                )

        # Fallback: LLM may have output a diff despite instructions
        if not diff_result and raw_text:
            if validate_diff(raw_text):
                diff_result = fix_hunk_counts(raw_text)
                logger.info("Whole-file mode: LLM returned a diff instead, using directly")
            else:
                # Try extracting diff from code blocks
                extracted = self._extract_diff_from_text(raw_text)
                if extracted:
                    diff_result = fix_hunk_counts(extracted)
                    logger.info("Whole-file mode: extracted diff from text")
                else:
                    logger.warning(
                        "Whole-file mode: could not convert output to diff "
                        "(text length=%d)", len(raw_text),
                    )

        if diff_result:
            diff_result = fix_hunk_counts(diff_result)

        return {
            "diff": diff_result,
            "description": "Generated via whole-file rewrite mode",
            "version": self._patch_version,
            "author": self.coder_label,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    # Tool-use mode

    async def _execute_with_tools(self, context: str) -> dict[str, Any]:
        """Tool-use mode: Coder can read files, search code, and validate patches."""
        import time as _time

        tools = self.tool_handler.get_tool_definitions()
        system_prompt = self._get_system_prompt_for_tooluse()

        # Strip verbose code context — tool-use mode can read files directly
        context = self._strip_code_context_for_tooluse(context)

        messages: list[dict[str, Any]] = [{"role": "user", "content": context}]

        final_patch: str | None = None
        final_description: str | None = None
        last_validate_patch: str = ""  # Fallback: last patch attempted via validate_patch
        response = None
        total_in_tok = 0
        total_out_tok = 0
        start = _time.perf_counter()

        for turn in range(self.tool_handler.max_tool_calls):
            response = await self.llm.call_with_tools(
                messages=messages,
                tools=tools,
                system=system_prompt,
            )
            total_in_tok += response.usage.input_tokens
            total_out_tok += response.usage.output_tokens

            # Collect tool_use blocks
            tool_use_blocks = [
                b for b in response.content
                if hasattr(b, "type") and b.type == "tool_use"
            ]

            # Log turn details
            tool_names = [b.name for b in tool_use_blocks]
            logger.info(
                "Tool-use turn %d: stop_reason=%s, tools=%s, in=%d out=%d",
                turn + 1, response.stop_reason, tool_names,
                response.usage.input_tokens, response.usage.output_tokens,
            )

            # Check for submit_patch; track validate_patch attempts as fallback
            for block in tool_use_blocks:
                if block.name == "submit_patch":
                    final_patch = block.input.get("patch_diff", "")
                    final_description = block.input.get("description", "")
                elif block.name == "validate_patch":
                    candidate = block.input.get("patch_diff", "")
                    if candidate and validate_diff(candidate):
                        last_validate_patch = candidate

            if not tool_use_blocks:
                # No tool calls — model is done
                break

            # Compress old tool results to save tokens (keep last 5 turns full)
            self._compress_history(messages, keep_recent=5)

            # Process all tool calls and build results
            messages.append({"role": "assistant", "content": response.content})
            tool_results: list[dict[str, Any]] = []
            for block in tool_use_blocks:
                if block.name == "submit_patch":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "SUBMITTED",
                    })
                else:
                    result = await self.tool_handler.handle_tool_call(
                        block.name, block.input
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})

            if final_patch is not None:
                break

        # Log aggregate token usage to ExperimentLogger
        latency_ms = int((_time.perf_counter() - start) * 1000)
        self.logger.log(
            issue_id=self.issue_id,
            config=self.config_label,
            agent_role=self.role,
            communication_mode=self.communication_mode,
            iteration=self.current_iteration,
            input_tokens=total_in_tok,
            output_tokens=total_out_tok,
            latency_ms=latency_ms,
        )

        # Fallback chain if submit_patch was never called
        if final_patch is None:
            # 1. Try extracting from last text output
            if response is not None:
                text_content = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text_content += block.text
                extracted = self._extract_diff_from_text(text_content)
                if extracted:
                    final_patch = extracted
                    final_description = "Extracted from text output"

            # 2. Use last validate_patch attempt as fallback
            if not final_patch and last_validate_patch:
                final_patch = last_validate_patch
                final_description = "Fallback: last validate_patch attempt (not submitted)"
                logger.info("Using last validate_patch attempt as fallback patch")

        # Log tool trace
        if self.tool_handler.tool_trace:
            logger.info(
                "Coder tool trace (%d calls): %s",
                self.tool_handler.tool_call_count,
                json.dumps(self.tool_handler.tool_trace, indent=2),
            )

        # Auto-fix hunk line counts before returning
        if final_patch:
            final_patch = fix_hunk_counts(final_patch)

        return {
            "diff": final_patch or "",
            "description": final_description or "",
            "version": self._patch_version,
            "author": self.coder_label,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _get_system_prompt_for_tooluse() -> str:
        """System prompt for tool-use mode."""
        return (
            "You are an expert software engineer fixing a bug. "
            "You have tools to explore code and validate patches.\n\n"
            "WORKFLOW — be efficient, you have only 15 tool calls:\n"
            "1. Read the issue and analysis (already provided below)\n"
            "2. Use read_lines to get the EXACT lines you need to change (not read_file for large files)\n"
            "3. Write a minimal unified diff patch with 1-2 context lines\n"
            "4. validate_patch to check it applies\n"
            "5. If INVALID: read_lines for exact context, fix diff, re-validate (max 2 retries)\n"
            "6. submit_patch — ALWAYS call this, even if validation failed\n\n"
            "DIFF RULES:\n"
            "- Paths: a/ and b/ prefixes. Hunks: @@ -start,count +start,count @@\n"
            "- Context lines: one space + EXACT source text. Never guess — use read_lines.\n"
            "- Keep context minimal (1-2 lines before/after change)\n\n"
            "You MUST call submit_patch before your tool calls run out."
        )

    @staticmethod
    def _strip_code_context_for_tooluse(context: str) -> str:
        """Remove verbose source code from context since tool-use can read files.

        Finds the ``"relevant_code"`` key in the JSON and replaces the value
        with a short placeholder.  Falls back to hard truncation at 6000 chars.
        """
        marker = '"relevant_code": "'
        idx = context.find(marker)
        if idx != -1:
            # Find the end of the JSON string value (handle escaped quotes)
            val_start = idx + len(marker)
            i = val_start
            while i < len(context):
                ch = context[i]
                if ch == "\\":
                    i += 2  # skip escaped character
                    continue
                if ch == '"':
                    break
                i += 1
            # Replace the value
            replacement = "[Code omitted — use read_file/read_lines tools to view source]"
            context = context[:val_start] + replacement + context[i:]

        # Hard cap: tool-use mode doesn't need more than ~6000 chars
        if len(context) > 6000:
            context = context[:6000] + "\n\n[context truncated — use tools to read files]"

        return context

    @staticmethod
    def _compress_history(messages: list[dict[str, Any]], keep_recent: int = 5) -> None:
        """Truncate old tool_result content in-place to reduce token usage.

        Keeps the first message (initial user context) and the most recent
        *keep_recent* assistant/user turn-pairs intact.  Older tool_result
        entries are replaced with a short summary.
        """
        # Count turn-pairs (assistant + user with tool_results) after the first message
        # Each pair = 2 messages.  Total turn messages = len(messages) - 1.
        turn_messages = len(messages) - 1  # exclude initial user message
        turns = turn_messages // 2
        if turns <= keep_recent:
            return

        # Number of turn-pairs to compress
        compress_count = turns - keep_recent
        # Turn-pair messages start at index 1, each pair = [assistant, user]
        for i in range(compress_count):
            user_idx = 1 + i * 2 + 1  # user message with tool_results
            if user_idx >= len(messages):
                break
            msg = messages[user_idx]
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    old = item.get("content", "")
                    if isinstance(old, str) and len(old) > 200:
                        item["content"] = old[:100] + "\n... [truncated]"

    @staticmethod
    def _extract_diff_from_text(text: str) -> str:
        """Extract a unified diff from free-form text output."""
        # Try to extract from code block
        match = re.search(r"```(?:diff|patch)?\s*\n(.*?)```", text, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            if validate_diff(candidate):
                return candidate

        # Try to find raw diff starting with --- a/ or diff --git
        match = re.search(
            r"((?:diff --git|--- a/).*?)(?:\n\n|\Z)",
            text,
            re.DOTALL,
        )
        if match:
            candidate = match.group(1).strip()
            if validate_diff(candidate):
                return candidate

        return ""
