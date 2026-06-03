"""TesterAgent: applies a patch, runs tests, and reports results."""

from __future__ import annotations

import json
import re
from typing import Any

from src.blackboard.schema import TestResult
from .base import BaseAgent


class TesterAgent(BaseAgent):
    """Applies the patch to the codebase, executes tests, and returns a TestResult.

    Unlike other agents, TesterAgent primarily invokes external tooling
    (SWE-bench Docker harness) rather than calling the LLM.  The LLM is
    optionally used to analyse failure traces and produce structured feedback.

    Workflow:
        1. Apply the patch to the code repository.
        2. Invoke the SWE-bench Docker environment to run tests.
        3. Parse the raw test output.
        4. (Optional) Call the LLM to analyse failure traces.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(role="Tester", **kwargs)
        self._swebench_runner: Any = None  # placeholder for SWEBenchRunner

    def set_runner(self, runner: Any) -> None:
        """Inject a SWEBenchRunner (or mock) for test execution."""
        self._swebench_runner = runner

    async def execute(self, context: str) -> dict[str, Any]:
        """Run tests for the latest patch and return a TestResult dict.

        Args:
            context: Depends on communication mode. In all modes the context
                     contains the patch diff and optionally test output.

        Returns:
            ``TestResult`` model serialized as a dict.
        """
        # ---- Step 1: attempt to run tests via SWEBenchRunner ----
        if self._swebench_runner is not None:
            # Real or mock runner injected — delegate
            result = await self._run_with_runner(context)
        else:
            # No runner available — try to parse raw test output from context
            result = self._parse_test_context(context)

        # ---- Step 2 (optional): LLM failure analysis ----
        if not result.passed and result.error_traces:
            result = await self._analyse_failures(result, context)

        return result.model_dump()

    # ------------------------------------------------------------------
    # Runner-based execution
    # ------------------------------------------------------------------

    async def _run_with_runner(self, context: str) -> TestResult:
        """Use the injected SWEBenchRunner to execute tests."""
        patch_diff = self._extract_diff(context)
        if not patch_diff:
            return TestResult(
                patch_version=0,
                passed=False,
                fail_count=1,
                error_traces=["Could not extract a diff from the context."],
            )
        try:
            test_result: TestResult = await self._swebench_runner.run_tests(
                self.issue_id, patch_diff
            )
            return test_result
        except Exception as exc:
            return TestResult(
                patch_version=0,
                passed=False,
                fail_count=1,
                error_traces=[f"SWEBenchRunner raised an exception: {exc}"],
            )

    @staticmethod
    def _extract_diff(context: str) -> str:
        """Extract a unified diff from agent context.

        Tries multiple strategies:
        1. Find all JSON objects in context, return the "diff" field from any.
        2. Search for a unified diff pattern (diff --git or --- a/).
        3. Return the entire context as a last resort (for mock runner).
        """
        # Strategy 1: Find JSON objects containing a "diff" field.
        # The context may have multiple JSON objects (e.g. Issue + Patch),
        # so we scan for each top-level {...} block.
        for match in re.finditer(r"\{", context):
            start = match.start()
            # Find matching closing brace by counting nesting
            depth = 0
            in_string = False
            escape_next = False
            end = -1
            for i in range(start, len(context)):
                ch = context[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\":
                    if in_string:
                        escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end == -1:
                continue
            try:
                data = json.loads(context[start:end])
                if isinstance(data, dict) and data.get("diff"):
                    return data["diff"]
            except (json.JSONDecodeError, ValueError):
                continue

        # Strategy 2: Find unified diff block
        # Look for "diff --git" header
        idx = context.find("diff --git ")
        if idx != -1:
            return context[idx:].strip()

        # Look for "--- a/" style diffs (without diff --git header)
        idx = context.find("--- a/")
        if idx != -1:
            return context[idx:].strip()

        # Strategy 3: return raw context (works with mock runner)
        return context.strip()

    # ------------------------------------------------------------------
    # Fallback: parse test output from context string
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_test_context(context: str) -> TestResult:
        """Best-effort parse of raw test output embedded in *context*.

        Returns a placeholder TestResult when no structured data is available.
        """
        # Try to extract JSON from context
        try:
            # Look for JSON block
            start = context.index("{")
            end = context.rindex("}") + 1
            data = json.loads(context[start:end])
            return TestResult.model_validate(data)
        except (ValueError, json.JSONDecodeError):
            pass

        # Heuristic: check for common pass/fail keywords
        lower = context.lower()
        passed = "passed" in lower and "failed" not in lower
        return TestResult(
            patch_version=0,
            passed=passed,
            error_traces=[] if passed else ["Could not parse test output."],
        )

    # ------------------------------------------------------------------
    # Optional LLM failure analysis
    # ------------------------------------------------------------------

    async def _analyse_failures(self, result: TestResult, context: str) -> TestResult:
        """Call the LLM to produce a structured analysis of test failures."""
        schema_json = json.dumps(TestResult.model_json_schema(), indent=2)
        prompt_section = self._get_prompt_section(self.communication_mode)

        system_prompt = (
            "You are a test analysis agent. Analyze the test failures and produce a "
            "structured TestResult in valid JSON."
        )

        error_summary = "\n".join(result.error_traces[:5])  # limit length
        if self.communication_mode in ("blackboard", "hybrid"):
            user_message = prompt_section.format(
                schema=schema_json,
                state=context,
                test_output=error_summary,
            )
        else:
            user_message = prompt_section.format(
                schema=schema_json,
                test_output=error_summary,
            )

        try:
            analysed, _, _ = await self._call_llm_structured(
                system_prompt, user_message, TestResult
            )
            # Preserve actual pass/fail counts from the real run
            analysed_dict = analysed.model_dump()
            analysed_dict["passed"] = result.passed
            analysed_dict["pass_count"] = result.pass_count
            analysed_dict["fail_count"] = result.fail_count
            analysed_dict["patch_version"] = result.patch_version
            return TestResult.model_validate(analysed_dict)
        except Exception:
            # LLM analysis failed — return original result
            return result
