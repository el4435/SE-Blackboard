"""Unit tests for agents and communication modes using a mock LLM client."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.blackboard.board import Blackboard
from src.blackboard.schema import (
    Analysis,
    IssueInfo,
    Patch,
    Review,
    TestResult,
)
from src.agents.planner import PlannerAgent
from src.agents.coder import CoderAgent
from src.agents.reviewer import ReviewerAgent
from src.agents.tester import TesterAgent
from src.communication.message_passing import MessagePassingCommunication
from src.communication.blackboard_comm import BlackboardCommunication
from src.communication.hybrid_comm import HybridCommunication
from src.utils.logger import ExperimentLogger


# ---------------------------------------------------------------------------
# Mock LLM Client
# ---------------------------------------------------------------------------

class MockLLMClient:
    """Mock LLM client that returns pre-configured structured responses."""

    def __init__(self) -> None:
        self.cumulative_input_tokens: int = 0
        self.cumulative_output_tokens: int = 0
        self._responses: dict[str, str] = {}
        self._default_responses: dict[str, str] = {
            "Planner": json.dumps({
                "root_cause": "Missing null check in handler",
                "relevant_files": ["src/handler.py"],
                "relevant_functions": ["handle_request"],
                "fix_strategy": "Add null check before processing",
                "confidence": 0.9,
            }),
            "Coder": json.dumps({
                "version": 1,
                "author": "Coder",
                "diff": "--- a/src/handler.py\n+++ b/src/handler.py\n@@ -1 +1 @@\n-old\n+new",
                "description": "Add null check",
                "timestamp": "2026-02-13T10:00:00Z",
            }),
            "Reviewer": json.dumps({
                "patch_version": 1,
                "author": "Reviewer",
                "verdict": "approve",
                "issues": [],
                "suggestions": ["Consider adding a test."],
            }),
            "Tester": json.dumps({
                "patch_version": 1,
                "passed": True,
                "pass_count": 10,
                "fail_count": 0,
                "failing_tests": [],
                "error_traces": [],
            }),
        }

    def set_response(self, role: str, response_json: str) -> None:
        """Pre-configure the response for a given agent role."""
        self._responses[role] = response_json

    def _get_response(self, system_prompt: str) -> str:
        """Pick the right mock response based on the system prompt (agent identity)."""
        sp = system_prompt.lower()
        # Map system-prompt keywords to roles
        role_keywords = {
            "Planner": ["analyzing a github issue", "analysis"],
            "Coder": ["generating a code patch", "code patch"],
            "Reviewer": ["code reviewer", "review"],
            "Tester": ["test analysis", "test"],
        }
        for role, keywords in role_keywords.items():
            if any(kw in sp for kw in keywords):
                if role in self._responses:
                    return self._responses[role]
                return self._default_responses[role]
        # Last resort: return first default
        return list(self._default_responses.values())[0]

    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_retries: int = 3,
    ) -> tuple[str, int, int]:
        """Mock LLM call: returns preconfigured response with fake token counts."""
        response = self._get_response(system_prompt)
        in_tok, out_tok = 100, 50
        self.cumulative_input_tokens += in_tok
        self.cumulative_output_tokens += out_tok
        return response, in_tok, out_tok

    async def call_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type,
        max_retries: int = 3,
    ) -> tuple[Any, int, int]:
        """Mock structured call: parse pre-configured JSON into the model."""
        text, in_tok, out_tok = await self.call(system_prompt, user_message, max_retries)
        parsed = response_model.model_validate_json(text)
        return parsed, in_tok, out_tok

    def reset_token_counts(self) -> None:
        self.cumulative_input_tokens = 0
        self.cumulative_output_tokens = 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm() -> MockLLMClient:
    return MockLLMClient()


@pytest.fixture
def mock_logger(tmp_path) -> ExperimentLogger:
    return ExperimentLogger(experiment_id="test_exp", log_dir=str(tmp_path))


@pytest.fixture
def sample_issue() -> IssueInfo:
    return IssueInfo(
        instance_id="django__django-11099",
        problem_statement="QuerySet.union() crashes with values_list().",
        repo="django/django",
        base_commit="abc1234",
    )


@pytest.fixture
def board(sample_issue: IssueInfo) -> Blackboard:
    return Blackboard(sample_issue)


def _make_agent(agent_cls, mock_llm, mock_logger, **extra):
    """Helper to create an agent with mock dependencies."""
    agent = agent_cls(llm_client=mock_llm, logger=mock_logger, **extra)
    agent.issue_id = "django__django-11099"
    agent.config_label = "test"
    agent.communication_mode = "message_passing"
    agent.current_iteration = 0
    return agent


# ---------------------------------------------------------------------------
# PlannerAgent tests
# ---------------------------------------------------------------------------

class TestPlannerAgent:
    @pytest.mark.asyncio
    async def test_execute_returns_analysis_dict(self, mock_llm, mock_logger) -> None:
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)
        result = await planner.execute("Some issue text about a bug")

        assert isinstance(result, dict)
        assert "root_cause" in result
        assert "relevant_files" in result
        assert "fix_strategy" in result
        assert "confidence" in result
        assert isinstance(result["relevant_files"], list)
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_execute_result_validates_as_analysis(self, mock_llm, mock_logger) -> None:
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)
        result = await planner.execute("Bug in query processing")
        analysis = Analysis.model_validate(result)
        assert analysis.root_cause != ""

    @pytest.mark.asyncio
    async def test_logs_interaction(self, mock_llm, mock_logger) -> None:
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)
        await planner.execute("test issue")
        entries = mock_logger.get_entries()
        assert len(entries) == 1
        assert entries[0]["agent_role"] == "Planner"
        assert entries[0]["input_tokens"] == 100
        assert entries[0]["output_tokens"] == 50


# ---------------------------------------------------------------------------
# CoderAgent tests
# ---------------------------------------------------------------------------

class TestCoderAgent:
    @pytest.mark.asyncio
    async def test_execute_returns_patch_dict(self, mock_llm, mock_logger) -> None:
        coder = _make_agent(CoderAgent, mock_llm, mock_logger)
        result = await coder.execute("Analysis says to fix handler.py")

        assert isinstance(result, dict)
        assert "version" in result
        assert "diff" in result
        assert "description" in result
        assert "timestamp" in result
        assert result["author"] == "Coder"

    @pytest.mark.asyncio
    async def test_version_increments(self, mock_llm, mock_logger) -> None:
        coder = _make_agent(CoderAgent, mock_llm, mock_logger)
        r1 = await coder.execute("First iteration")
        r2 = await coder.execute("Second iteration with review feedback")
        assert r1["version"] == 1
        assert r2["version"] == 2

    @pytest.mark.asyncio
    async def test_execute_result_validates_as_patch(self, mock_llm, mock_logger) -> None:
        coder = _make_agent(CoderAgent, mock_llm, mock_logger)
        result = await coder.execute("Fix the bug")
        patch = Patch.model_validate(result)
        assert patch.diff != ""


# ---------------------------------------------------------------------------
# ReviewerAgent tests
# ---------------------------------------------------------------------------

class TestReviewerAgent:
    @pytest.mark.asyncio
    async def test_execute_returns_review_dict(self, mock_llm, mock_logger) -> None:
        reviewer = _make_agent(ReviewerAgent, mock_llm, mock_logger)
        result = await reviewer.execute("Here is the patch to review...")

        assert isinstance(result, dict)
        assert "verdict" in result
        assert result["verdict"] in ("approve", "needs_revision", "reject")
        assert "issues" in result
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_execute_result_validates_as_review(self, mock_llm, mock_logger) -> None:
        reviewer = _make_agent(ReviewerAgent, mock_llm, mock_logger)
        result = await reviewer.execute("Review this patch")
        review = Review.model_validate(result)
        assert review.verdict == "approve"


# ---------------------------------------------------------------------------
# TesterAgent tests
# ---------------------------------------------------------------------------

class TestTesterAgent:
    @pytest.mark.asyncio
    async def test_execute_with_json_context(self, mock_llm, mock_logger) -> None:
        """TesterAgent should parse JSON test results from context."""
        tester = _make_agent(TesterAgent, mock_llm, mock_logger)
        json_context = json.dumps({
            "patch_version": 1,
            "passed": True,
            "pass_count": 5,
            "fail_count": 0,
            "failing_tests": [],
            "error_traces": [],
        })
        result = await tester.execute(json_context)

        assert isinstance(result, dict)
        assert result["passed"] is True
        assert result["pass_count"] == 5

    @pytest.mark.asyncio
    async def test_execute_with_plain_text_pass(self, mock_llm, mock_logger) -> None:
        """TesterAgent should detect 'passed' keyword in plain text."""
        tester = _make_agent(TesterAgent, mock_llm, mock_logger)
        result = await tester.execute("All tests passed successfully!")
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_execute_with_plain_text_fail(self, mock_llm, mock_logger) -> None:
        """TesterAgent should detect 'failed' keyword in plain text."""
        tester = _make_agent(TesterAgent, mock_llm, mock_logger)
        result = await tester.execute("3 tests failed with errors")
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_execute_result_validates_as_test_result(self, mock_llm, mock_logger) -> None:
        tester = _make_agent(TesterAgent, mock_llm, mock_logger)
        result = await tester.execute('{"patch_version": 1, "passed": false, "fail_count": 2}')
        tr = TestResult.model_validate(result)
        assert tr.passed is False

    @pytest.mark.asyncio
    async def test_execute_with_mock_runner(self, mock_llm, mock_logger) -> None:
        """TesterAgent should use injected runner when available."""
        tester = _make_agent(TesterAgent, mock_llm, mock_logger)
        mock_runner = MagicMock()
        mock_runner.run_tests = AsyncMock(return_value=TestResult(
            patch_version=1, passed=True, pass_count=10, fail_count=0
        ))
        tester.set_runner(mock_runner)

        result = await tester.execute("some patch diff")
        assert result["passed"] is True
        assert result["pass_count"] == 10
        mock_runner.run_tests.assert_awaited_once()


# ---------------------------------------------------------------------------
# Communication mode tests
# ---------------------------------------------------------------------------

class TestMessagePassingCommunication:
    @pytest.mark.asyncio
    async def test_run_agent_sets_communication_mode(self, mock_llm, mock_logger) -> None:
        comm = MessagePassingCommunication(logger=mock_logger)
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)
        planner.communication_mode = "blackboard"  # intentionally wrong

        summary, result = await comm.run_agent(planner, "issue text")
        assert planner.communication_mode == "message_passing"

    @pytest.mark.asyncio
    async def test_run_agent_returns_tuple(self, mock_llm, mock_logger) -> None:
        comm = MessagePassingCommunication(logger=mock_logger)
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)

        summary, result = await comm.run_agent(planner, "issue text")
        assert isinstance(summary, str)
        assert isinstance(result, dict)
        assert "[Planner Output]" in summary

    @pytest.mark.asyncio
    async def test_chain_two_agents(self, mock_llm, mock_logger) -> None:
        """Planner output can be passed to Coder."""
        comm = MessagePassingCommunication(logger=mock_logger)
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)
        coder = _make_agent(CoderAgent, mock_llm, mock_logger)

        planner_text, _ = await comm.run_agent(planner, "issue text")
        coder_text, coder_result = await comm.run_agent(coder, planner_text)
        assert "diff" in coder_result


class TestBlackboardCommunication:
    @pytest.mark.asyncio
    async def test_run_agent_sets_communication_mode(
        self, mock_llm, mock_logger, board
    ) -> None:
        comm = BlackboardCommunication(blackboard=board, logger=mock_logger)
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)

        await comm.run_agent(planner)
        assert planner.communication_mode == "blackboard"

    @pytest.mark.asyncio
    async def test_planner_writes_to_blackboard(
        self, mock_llm, mock_logger, board
    ) -> None:
        comm = BlackboardCommunication(blackboard=board, logger=mock_logger)
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)

        await comm.run_agent(planner)
        state = board.get_state()
        assert state.analysis.root_cause != ""

    @pytest.mark.asyncio
    async def test_coder_writes_patch_to_blackboard(
        self, mock_llm, mock_logger, board
    ) -> None:
        comm = BlackboardCommunication(blackboard=board, logger=mock_logger)
        coder = _make_agent(CoderAgent, mock_llm, mock_logger)

        await comm.run_agent(coder)
        state = board.get_state()
        assert len(state.patches) == 1

    @pytest.mark.asyncio
    async def test_reviewer_writes_review_to_blackboard(
        self, mock_llm, mock_logger, board
    ) -> None:
        comm = BlackboardCommunication(blackboard=board, logger=mock_logger)
        # Add a patch first so reviewer context makes sense
        board.add_patch(Patch(
            version=1, diff="some diff", description="fix",
            timestamp=datetime.now(timezone.utc),
        ))
        reviewer = _make_agent(ReviewerAgent, mock_llm, mock_logger)

        await comm.run_agent(reviewer)
        state = board.get_state()
        assert len(state.reviews) == 1
        assert state.reviews[0].verdict == "approve"


class TestHybridCommunication:
    @pytest.mark.asyncio
    async def test_run_agent_sets_communication_mode(
        self, mock_llm, mock_logger, board
    ) -> None:
        comm = HybridCommunication(blackboard=board, logger=mock_logger)
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)

        await comm.run_agent(planner, "some prior context")
        assert planner.communication_mode == "hybrid"

    @pytest.mark.asyncio
    async def test_run_agent_returns_tuple_and_writes_blackboard(
        self, mock_llm, mock_logger, board
    ) -> None:
        comm = HybridCommunication(blackboard=board, logger=mock_logger)
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)

        summary, result = await comm.run_agent(planner, "issue text")
        assert isinstance(summary, str)
        assert "[Planner Output]" in summary
        # Also wrote to blackboard
        state = board.get_state()
        assert state.analysis.root_cause != ""


# ---------------------------------------------------------------------------
# Prompt template tests
# ---------------------------------------------------------------------------

class TestPromptTemplates:
    def test_get_message_passing_section(self, mock_llm, mock_logger) -> None:
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)
        section = planner._get_prompt_section("message_passing")
        assert "{schema}" in section
        assert "{issue_text}" in section
        assert "BLACKBOARD" not in section

    def test_get_blackboard_section(self, mock_llm, mock_logger) -> None:
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)
        section = planner._get_prompt_section("blackboard")
        assert "{schema}" in section
        assert "{state}" in section

    def test_hybrid_uses_blackboard_section(self, mock_llm, mock_logger) -> None:
        """Hybrid mode uses the Blackboard prompt template (with BB state + previous output)."""
        planner = _make_agent(PlannerAgent, mock_llm, mock_logger)
        bb_section = planner._get_prompt_section("blackboard")
        hybrid_section = planner._get_prompt_section("hybrid")
        assert bb_section == hybrid_section

    def test_all_agents_have_both_sections(self, mock_llm, mock_logger) -> None:
        for cls in [PlannerAgent, CoderAgent, ReviewerAgent, TesterAgent]:
            agent = _make_agent(cls, mock_llm, mock_logger)
            mp = agent._get_prompt_section("message_passing")
            bb = agent._get_prompt_section("blackboard")
            assert len(mp) > 0
            assert len(bb) > 0
            assert mp != bb  # They should be different sections
