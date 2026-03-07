"""Unit tests for SequentialPipeline and PeerDebate topologies."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from src.blackboard.board import Blackboard
from src.blackboard.schema import (
    Analysis,
    ExperimentResult,
    IssueInfo,
    Patch,
    Review,
    TestResult,
)
from src.agents.planner import PlannerAgent
from src.agents.coder import CoderAgent
from src.agents.reviewer import ReviewerAgent
from src.agents.tester import TesterAgent
from src.evaluation.swebench_runner import MockSWEBenchRunner
from src.communication.message_passing import MessagePassingCommunication
from src.communication.blackboard_comm import BlackboardCommunication
from src.communication.hybrid_comm import HybridCommunication
from src.topologies.sequential import SequentialPipeline
from src.topologies.debate import PeerDebate
from src.utils.logger import ExperimentLogger
# Mock LLM Client (same as test_agents.py but standalone)

class MockLLMClient:
    def __init__(self) -> None:
        self.cumulative_input_tokens: int = 0
        self.cumulative_output_tokens: int = 0
        self._default_responses: dict[str, str] = {
            "Planner": json.dumps({
                "root_cause": "Missing null check",
                "relevant_files": ["src/handler.py"],
                "relevant_functions": ["handle_request"],
                "fix_strategy": "Add null check",
                "confidence": 0.9,
            }),
            "Coder": json.dumps({
                "version": 1,
                "author": "Coder",
                "diff": "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new",
                "description": "Fix null check",
                "timestamp": "2026-02-13T10:00:00Z",
            }),
            "Reviewer": json.dumps({
                "patch_version": 1,
                "author": "Reviewer",
                "verdict": "approve",
                "issues": [],
                "suggestions": [],
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

    def _get_response(self, system_prompt: str) -> str:
        sp = system_prompt.lower()
        role_keywords = {
            "Planner": ["analyzing a github issue", "analysis"],
            "Coder": ["generating a code patch", "code patch"],
            "Reviewer": ["code reviewer", "review"],
            "Tester": ["test analysis", "test"],
        }
        for role, keywords in role_keywords.items():
            if any(kw in sp for kw in keywords):
                return self._default_responses[role]
        return self._default_responses["Planner"]

    async def call(self, system_prompt: str, user_message: str, max_retries: int = 3) -> tuple[str, int, int]:
        response = self._get_response(system_prompt)
        self.cumulative_input_tokens += 100
        self.cumulative_output_tokens += 50
        return response, 100, 50

    async def call_structured(self, system_prompt: str, user_message: str, response_model: type, max_retries: int = 3) -> tuple[Any, int, int]:
        text, in_tok, out_tok = await self.call(system_prompt, user_message, max_retries)
        parsed = response_model.model_validate_json(text)
        return parsed, in_tok, out_tok

    def reset_token_counts(self) -> None:
        self.cumulative_input_tokens = 0
        self.cumulative_output_tokens = 0
# Fixtures

@pytest.fixture
def mock_llm() -> MockLLMClient:
    return MockLLMClient()

@pytest.fixture
def mock_logger(tmp_path) -> ExperimentLogger:
    return ExperimentLogger(experiment_id="test_topo", log_dir=str(tmp_path))

@pytest.fixture
def sample_issue() -> IssueInfo:
    return IssueInfo(
        instance_id="django__django-11099",
        problem_statement="QuerySet.union() crashes with values_list().",
        repo="django/django",
        base_commit="abc1234",
    )


def _make_agents(mock_llm, mock_logger, topology="sequential"):
    # Use MockSWEBenchRunner with 100% pass rate for deterministic tests
    runner = MockSWEBenchRunner(pass_rate=1.0)

    tester = TesterAgent(llm_client=mock_llm, logger=mock_logger)
    tester.set_runner(runner)

    agents = {
        "planner": PlannerAgent(llm_client=mock_llm, logger=mock_logger),
        "coder": CoderAgent(llm_client=mock_llm, logger=mock_logger),
        "reviewer": ReviewerAgent(llm_client=mock_llm, logger=mock_logger),
        "tester": tester,
    }
    if topology == "debate":
        agents["coder_a"] = CoderAgent(llm_client=mock_llm, logger=mock_logger)
        agents["coder_b"] = CoderAgent(llm_client=mock_llm, logger=mock_logger)
    return agents
# SequentialPipeline tests

class TestSequentialPipeline:
    @pytest.mark.asyncio
    async def test_run_message_passing(self, mock_llm, mock_logger, sample_issue) -> None:
        agents = _make_agents(mock_llm, mock_logger)
        comm = MessagePassingCommunication(logger=mock_logger)
        pipeline = SequentialPipeline(
            agents=agents, communication=comm, logger=mock_logger, max_iterations=2,
        )

        result = await pipeline.run(sample_issue)

        assert isinstance(result, ExperimentResult)
        assert result.topology == "sequential"
        assert result.communication == "message_passing"
        assert result.issue_id == "django__django-11099"
        assert result.iterations >= 1
        # With mock "approve" + "passed", should resolve on first iteration
        assert result.resolved is True

    @pytest.mark.asyncio
    async def test_run_blackboard(self, mock_llm, mock_logger, sample_issue) -> None:
        board = Blackboard(sample_issue)
        comm = BlackboardCommunication(blackboard=board, logger=mock_logger)
        agents = _make_agents(mock_llm, mock_logger)
        pipeline = SequentialPipeline(
            agents=agents, communication=comm, logger=mock_logger, max_iterations=2,
        )

        result = await pipeline.run(sample_issue)

        assert isinstance(result, ExperimentResult)
        assert result.topology == "sequential"
        assert result.communication == "blackboard"
        assert result.resolved is True
        assert result.blackboard_final_state is not None

    @pytest.mark.asyncio
    async def test_run_hybrid(self, mock_llm, mock_logger, sample_issue) -> None:
        board = Blackboard(sample_issue)
        comm = HybridCommunication(blackboard=board, logger=mock_logger)
        agents = _make_agents(mock_llm, mock_logger)
        pipeline = SequentialPipeline(
            agents=agents, communication=comm, logger=mock_logger, max_iterations=2,
        )

        result = await pipeline.run(sample_issue)

        assert isinstance(result, ExperimentResult)
        assert result.communication == "hybrid"
        assert result.resolved is True
        assert result.blackboard_final_state is not None

    @pytest.mark.asyncio
    async def test_result_has_agent_traces(self, mock_llm, mock_logger, sample_issue) -> None:
        agents = _make_agents(mock_llm, mock_logger)
        comm = MessagePassingCommunication(logger=mock_logger)
        pipeline = SequentialPipeline(
            agents=agents, communication=comm, logger=mock_logger, max_iterations=1,
        )

        result = await pipeline.run(sample_issue)
        assert len(result.agent_traces) > 0
        assert result.total_input_tokens > 0
        assert result.total_output_tokens > 0

    @pytest.mark.asyncio
    async def test_result_has_final_patch(self, mock_llm, mock_logger, sample_issue) -> None:
        agents = _make_agents(mock_llm, mock_logger)
        comm = MessagePassingCommunication(logger=mock_logger)
        pipeline = SequentialPipeline(
            agents=agents, communication=comm, logger=mock_logger, max_iterations=1,
        )

        result = await pipeline.run(sample_issue)
        assert result.final_patch != ""
        assert "---" in result.final_patch or "+++" in result.final_patch or len(result.final_patch) > 0

    @pytest.mark.asyncio
    async def test_result_serializable(self, mock_llm, mock_logger, sample_issue) -> None:
        agents = _make_agents(mock_llm, mock_logger)
        comm = MessagePassingCommunication(logger=mock_logger)
        pipeline = SequentialPipeline(
            agents=agents, communication=comm, logger=mock_logger, max_iterations=1,
        )

        result = await pipeline.run(sample_issue)
        json_str = result.model_dump_json()
        restored = ExperimentResult.model_validate_json(json_str)
        assert restored.issue_id == result.issue_id
        assert restored.resolved == result.resolved
# PeerDebate tests

class TestPeerDebate:
    @pytest.mark.asyncio
    async def test_run_message_passing(self, mock_llm, mock_logger, sample_issue) -> None:
        agents = _make_agents(mock_llm, mock_logger, topology="debate")
        comm = MessagePassingCommunication(logger=mock_logger)
        pipeline = PeerDebate(
            agents=agents, communication=comm, logger=mock_logger, max_iterations=2,
        )

        result = await pipeline.run(sample_issue)

        assert isinstance(result, ExperimentResult)
        assert result.topology == "debate"
        assert result.communication == "message_passing"
        assert result.issue_id == "django__django-11099"

    @pytest.mark.asyncio
    async def test_run_blackboard(self, mock_llm, mock_logger, sample_issue) -> None:
        board = Blackboard(sample_issue)
        comm = BlackboardCommunication(blackboard=board, logger=mock_logger)
        agents = _make_agents(mock_llm, mock_logger, topology="debate")
        pipeline = PeerDebate(
            agents=agents, communication=comm, logger=mock_logger, max_iterations=1,
        )

        result = await pipeline.run(sample_issue)
        assert result.topology == "debate"
        assert result.communication == "blackboard"
        assert result.blackboard_final_state is not None

    @pytest.mark.asyncio
    async def test_debate_has_more_traces_than_sequential(
        self, mock_llm, mock_logger, sample_issue
    ) -> None:
        """Debate should produce more agent traces (two coders per iteration)."""
        # Sequential
        seq_logger = ExperimentLogger(experiment_id="seq_test", log_dir=str(mock_logger._log_dir))
        seq_agents = _make_agents(mock_llm, seq_logger)
        seq_comm = MessagePassingCommunication(logger=seq_logger)
        seq_pipe = SequentialPipeline(
            agents=seq_agents, communication=seq_comm, logger=seq_logger, max_iterations=1,
        )
        seq_result = await seq_pipe.run(sample_issue)

        # Debate
        deb_logger = ExperimentLogger(experiment_id="deb_test", log_dir=str(mock_logger._log_dir))
        deb_agents = _make_agents(mock_llm, deb_logger, topology="debate")
        deb_comm = MessagePassingCommunication(logger=deb_logger)
        deb_pipe = PeerDebate(
            agents=deb_agents, communication=deb_comm, logger=deb_logger, max_iterations=1,
        )
        deb_result = await deb_pipe.run(sample_issue)

        # Debate has 2 coders, so more traces
        assert len(deb_result.agent_traces) > len(seq_result.agent_traces)
# ExperimentResult model tests

class TestExperimentResult:
    def test_creation(self) -> None:
        r = ExperimentResult(
            experiment_id="test_001",
            issue_id="django__django-11099",
            topology="sequential",
            communication="blackboard",
            resolved=True,
            iterations=2,
            total_input_tokens=500,
            total_output_tokens=200,
            total_latency_ms=3000,
            final_patch="--- a/f.py\n+++ b/f.py",
        )
        assert r.resolved is True
        assert r.iterations == 2

    def test_json_round_trip(self) -> None:
        r = ExperimentResult(
            experiment_id="test_002",
            issue_id="sympy__sympy-18087",
            topology="debate",
            communication="hybrid",
            resolved=False,
            iterations=3,
        )
        json_str = r.model_dump_json()
        restored = ExperimentResult.model_validate_json(json_str)
        assert restored.issue_id == r.issue_id
        assert restored.topology == "debate"
        assert restored.resolved is False
