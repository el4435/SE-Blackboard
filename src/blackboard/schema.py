"""SE State Schema: Pydantic v2 models for the Blackboard shared state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class IssueInfo(BaseModel):
    """Issue original information (read-only after initialization)."""

    instance_id: str
    """SWE-bench issue ID, e.g. 'django__django-11099'."""

    problem_statement: str
    """Original issue text."""

    repo: str
    """Repository name, e.g. 'django/django'."""

    base_commit: str
    """Base commit hash to apply patches against."""

    key_entities: list[str] = Field(default_factory=list)
    """Key entities extracted by LLM (used for IFS calculation)."""


class Analysis(BaseModel):
    """Planner's analysis result."""

    root_cause: str = ""
    """Identified root cause of the issue."""

    relevant_files: list[str] = Field(default_factory=list)
    """File paths that need to be modified."""

    relevant_functions: list[str] = Field(default_factory=list)
    """Specific functions/classes involved."""

    fix_strategy: str = ""
    """Step-by-step plan to fix the issue."""

    confidence: float = 0.0
    """Confidence in the analysis (0.0 - 1.0)."""

    relevant_code: str = ""
    """Source code context fetched from the repository (populated by the pipeline)."""


class Patch(BaseModel):
    """Coder-generated patch."""

    version: int
    """Patch version number (1-indexed)."""

    author: str = "Coder"
    """Agent that generated this patch."""

    diff: str
    """Unified diff format patch content."""

    description: str
    """Human-readable description of the changes."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """When this patch was created."""


class Review(BaseModel):
    """Reviewer's assessment of a patch."""

    patch_version: int
    """Which patch version this review is for."""

    author: str = "Reviewer"
    """Agent that produced this review."""

    verdict: Literal["approve", "needs_revision", "reject"]
    """Review verdict."""

    issues: list[str] = Field(default_factory=list)
    """Issues found in the patch."""

    suggestions: list[str] = Field(default_factory=list)
    """Suggested improvements."""


class TestResult(BaseModel):
    """Tester's test execution result."""

    patch_version: int
    """Which patch version was tested."""

    passed: bool
    """Whether all tests passed."""

    pass_count: int = 0
    """Number of passing tests."""

    fail_count: int = 0
    """Number of failing tests."""

    failing_tests: list[str] = Field(default_factory=list)
    """Names of failing test cases."""

    error_traces: list[str] = Field(default_factory=list)
    """Error tracebacks from failing tests."""


class Metadata(BaseModel):
    """Experiment metadata tracked alongside the blackboard state."""

    status: Literal["initialized", "planning", "coding", "reviewing", "testing", "resolved", "failed"] = "initialized"
    """Current pipeline status."""

    current_iteration: int = 0
    """Current fix-review-test iteration number."""

    total_input_tokens: int = 0
    """Cumulative input tokens consumed."""

    total_output_tokens: int = 0
    """Cumulative output tokens consumed."""

    total_latency_ms: int = 0
    """Cumulative latency in milliseconds."""

    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """When this experiment run started."""

    end_time: datetime | None = None
    """When this experiment run ended."""


class SEBlackboardState(BaseModel):
    """Complete Blackboard state for a single issue resolution attempt."""

    issue: IssueInfo
    """The issue being resolved."""

    analysis: Analysis = Field(default_factory=Analysis)
    """Planner's analysis of the issue."""

    patches: list[Patch] = Field(default_factory=list)
    """All patch versions generated."""

    reviews: list[Review] = Field(default_factory=list)
    """All review records."""

    test_results: list[TestResult] = Field(default_factory=list)
    """All test execution results."""

    metadata: Metadata = Field(default_factory=Metadata)
    """Experiment metadata."""


class ExperimentResult(BaseModel):
    """Result of running a single issue through one topology + communication config."""

    experiment_id: str
    """Unique experiment run identifier."""

    issue_id: str
    """SWE-bench issue ID."""

    topology: str
    """Topology used: 'sequential' or 'debate'."""

    communication: str
    """Communication mode: 'message_passing', 'blackboard', or 'hybrid'."""

    resolved: bool
    """Whether the patch passed all tests."""

    iterations: int
    """Number of fix-review-test iterations used."""

    total_input_tokens: int = 0
    """Total input tokens consumed across all agent calls."""

    total_output_tokens: int = 0
    """Total output tokens consumed across all agent calls."""

    total_latency_ms: int = 0
    """Total wall-clock latency in milliseconds."""

    final_patch: str = ""
    """The final unified diff patch produced."""

    apply_method: str = ""
    """How the patch was applied: 'git_apply', 'patch_strict', 'patch_fuzz3', 'failed', or '' (not attempted)."""

    agent_traces: list[dict] = Field(default_factory=list)
    """Complete log of all agent interactions."""

    blackboard_final_state: dict | None = None
    """Final blackboard state snapshot (only for blackboard/hybrid modes)."""
