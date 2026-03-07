"""Unit tests for the Blackboard module."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.blackboard.schema import (
    Analysis,
    IssueInfo,
    Metadata,
    Patch,
    Review,
    SEBlackboardState,
    TestResult,
)
from src.blackboard.board import Blackboard
# Fixtures

@pytest.fixture
def sample_issue() -> IssueInfo:
    return IssueInfo(
        instance_id="django__django-11099",
        problem_statement="Fix crash when using QuerySet.union() with values_list().",
        repo="django/django",
        base_commit="abc1234",
        key_entities=["QuerySet", "union", "values_list"],
    )


@pytest.fixture
def board(sample_issue: IssueInfo) -> Blackboard:
    return Blackboard(sample_issue)


@pytest.fixture
def sample_analysis() -> Analysis:
    return Analysis(
        root_cause="QuerySet.union() does not preserve field ordering for values_list().",
        relevant_files=["django/db/models/query.py"],
        relevant_functions=["QuerySet.union", "QuerySet.values_list"],
        fix_strategy="Preserve the column order when combining queries via UNION.",
        confidence=0.85,
    )


@pytest.fixture
def sample_patch() -> Patch:
    return Patch(
        version=1,
        author="Coder",
        diff="--- a/django/db/models/query.py\n+++ b/django/db/models/query.py\n@@ -1 +1 @@\n-old\n+new",
        description="Fix column ordering in union queries.",
        timestamp=datetime(2026, 2, 13, 10, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_review() -> Review:
    return Review(
        patch_version=1,
        author="Reviewer",
        verdict="approve",
        issues=[],
        suggestions=["Consider adding a regression test."],
    )


@pytest.fixture
def sample_test_result() -> TestResult:
    return TestResult(
        patch_version=1,
        passed=True,
        pass_count=42,
        fail_count=0,
    )
# Schema tests

class TestSchema:
    """Tests for Pydantic schema models."""

    def test_issue_info_creation(self, sample_issue: IssueInfo) -> None:
        assert sample_issue.instance_id == "django__django-11099"
        assert sample_issue.repo == "django/django"
        assert len(sample_issue.key_entities) == 3

    def test_analysis_defaults(self) -> None:
        a = Analysis()
        assert a.root_cause == ""
        assert a.confidence == 0.0
        assert a.relevant_files == []

    def test_patch_serialization(self, sample_patch: Patch) -> None:
        data = sample_patch.model_dump()
        assert data["version"] == 1
        assert "old" in data["diff"]
        restored = Patch.model_validate(data)
        assert restored.version == sample_patch.version

    def test_review_verdict_literal(self) -> None:
        r = Review(patch_version=1, verdict="needs_revision")
        assert r.verdict == "needs_revision"
        with pytest.raises(Exception):
            Review(patch_version=1, verdict="invalid_verdict")  # type: ignore[arg-type]

    def test_test_result(self, sample_test_result: TestResult) -> None:
        assert sample_test_result.passed is True
        assert sample_test_result.pass_count == 42

    def test_metadata_defaults(self) -> None:
        m = Metadata()
        assert m.status == "initialized"
        assert m.current_iteration == 0
        assert m.total_input_tokens == 0

    def test_full_state(self, sample_issue: IssueInfo) -> None:
        state = SEBlackboardState(issue=sample_issue)
        assert state.issue.instance_id == "django__django-11099"
        assert state.analysis.root_cause == ""
        assert state.patches == []
        assert state.metadata.status == "initialized"

    def test_state_json_round_trip(self, sample_issue: IssueInfo, sample_patch: Patch) -> None:
        state = SEBlackboardState(issue=sample_issue, patches=[sample_patch])
        json_str = state.model_dump_json()
        restored = SEBlackboardState.model_validate_json(json_str)
        assert restored.issue.instance_id == state.issue.instance_id
        assert len(restored.patches) == 1
        assert restored.patches[0].version == 1
# Blackboard tests

class TestBlackboard:
    """Tests for the Blackboard read/write manager."""

    def test_initial_state(self, board: Blackboard, sample_issue: IssueInfo) -> None:
        state = board.get_state()
        assert state.issue.instance_id == sample_issue.instance_id
        assert state.patches == []
        assert state.metadata.status == "initialized"

    def test_get_state_returns_deep_copy(self, board: Blackboard) -> None:
        s1 = board.get_state()
        s2 = board.get_state()
        assert s1 is not s2
        assert s1.issue is not s2.issue

    def test_update_analysis(self, board: Blackboard, sample_analysis: Analysis) -> None:
        board.update_analysis(sample_analysis)
        state = board.get_state()
        assert state.analysis.root_cause == sample_analysis.root_cause
        assert state.analysis.confidence == 0.85
        assert state.metadata.status == "planning"

    def test_add_patch(self, board: Blackboard, sample_patch: Patch) -> None:
        board.add_patch(sample_patch)
        state = board.get_state()
        assert len(state.patches) == 1
        assert state.patches[0].version == 1
        assert state.metadata.status == "coding"

    def test_add_review(self, board: Blackboard, sample_review: Review) -> None:
        board.add_review(sample_review)
        state = board.get_state()
        assert len(state.reviews) == 1
        assert state.reviews[0].verdict == "approve"
        assert state.metadata.status == "reviewing"

    def test_add_test_result_pass(self, board: Blackboard, sample_test_result: TestResult) -> None:
        board.add_test_result(sample_test_result)
        state = board.get_state()
        assert len(state.test_results) == 1
        assert state.metadata.status == "resolved"

    def test_add_test_result_fail(self, board: Blackboard) -> None:
        fail_result = TestResult(patch_version=1, passed=False, fail_count=3)
        board.add_test_result(fail_result)
        state = board.get_state()
        assert state.metadata.status == "testing"

    def test_update_metadata(self, board: Blackboard) -> None:
        board.update_metadata(input_tokens=100, output_tokens=50, latency_ms=500, iteration=1)
        state = board.get_state()
        assert state.metadata.total_input_tokens == 100
        assert state.metadata.total_output_tokens == 50
        assert state.metadata.total_latency_ms == 500
        assert state.metadata.current_iteration == 1

    def test_metadata_accumulates(self, board: Blackboard) -> None:
        board.update_metadata(input_tokens=100, output_tokens=50)
        board.update_metadata(input_tokens=200, output_tokens=100)
        state = board.get_state()
        assert state.metadata.total_input_tokens == 300
        assert state.metadata.total_output_tokens == 150

    def test_history_tracking(self, board: Blackboard, sample_analysis: Analysis) -> None:
        board.update_analysis(sample_analysis)
        history = board.get_history()
        # init + update_analysis = 2 entries
        assert len(history) == 2
        assert history[0]["action"] == "init"
        assert history[1]["action"] == "update_analysis"

    def test_history_is_deep_copy(self, board: Blackboard) -> None:
        h1 = board.get_history()
        h2 = board.get_history()
        assert h1 is not h2

    def test_to_json(self, board: Blackboard, sample_analysis: Analysis) -> None:
        board.update_analysis(sample_analysis)
        json_str = board.to_json()
        data = json.loads(json_str)
        assert data["issue"]["instance_id"] == "django__django-11099"
        assert data["analysis"]["confidence"] == 0.85

    def test_get_state_for_planner(self, board: Blackboard) -> None:
        ctx = board.get_state_for_agent("Planner")
        assert "## Issue" in ctx
        assert "django__django-11099" in ctx
        assert "## Analysis" not in ctx

    def test_get_state_for_coder(
        self,
        board: Blackboard,
        sample_analysis: Analysis,
        sample_review: Review,
    ) -> None:
        board.update_analysis(sample_analysis)
        board.add_review(sample_review)
        ctx = board.get_state_for_agent("Coder")
        assert "## Issue" in ctx
        assert "## Analysis" in ctx
        assert "## Latest Review" in ctx

    def test_get_state_for_reviewer(
        self,
        board: Blackboard,
        sample_analysis: Analysis,
        sample_patch: Patch,
    ) -> None:
        board.update_analysis(sample_analysis)
        board.add_patch(sample_patch)
        ctx = board.get_state_for_agent("Reviewer")
        assert "## Issue" in ctx
        assert "## Analysis" in ctx
        assert "## Latest Patch" in ctx

    def test_get_state_for_tester(self, board: Blackboard, sample_patch: Patch) -> None:
        board.add_patch(sample_patch)
        ctx = board.get_state_for_agent("Tester")
        assert "## Issue" in ctx
        assert "## Latest Patch" in ctx
        assert "## Analysis" not in ctx

    def test_get_state_for_unknown_role(self, board: Blackboard) -> None:
        with pytest.raises(ValueError, match="Unknown agent role"):
            board.get_state_for_agent("Unknown")

    def test_full_workflow(
        self,
        board: Blackboard,
        sample_analysis: Analysis,
        sample_patch: Patch,
        sample_review: Review,
        sample_test_result: TestResult,
    ) -> None:
        """Simulate a complete fix-review-test cycle."""
        board.update_analysis(sample_analysis)
        board.add_patch(sample_patch)
        board.add_review(sample_review)
        board.add_test_result(sample_test_result)

        state = board.get_state()
        assert state.metadata.status == "resolved"
        assert len(state.patches) == 1
        assert len(state.reviews) == 1
        assert len(state.test_results) == 1

        history = board.get_history()
        actions = [h["action"] for h in history]
        assert actions == ["init", "update_analysis", "add_patch", "add_review", "add_test_result"]
