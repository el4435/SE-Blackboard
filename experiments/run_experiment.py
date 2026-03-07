"""Main experiment entry point.

Usage:
    python experiments/run_experiment.py --topology sequential --communication blackboard --issues data/selected_issues.json
    python experiments/run_experiment.py --all
    python experiments/run_experiment.py --topology sequential --communication message_passing --issue-id django__django-11099
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from config import settings
from src.blackboard.board import Blackboard
from src.blackboard.schema import ExperimentResult, IssueInfo
from src.agents.planner import PlannerAgent
from src.agents.coder import CoderAgent
from src.agents.reviewer import ReviewerAgent
from src.agents.tester import TesterAgent
from src.communication.message_passing import MessagePassingCommunication
from src.communication.blackboard_comm import BlackboardCommunication
from src.communication.hybrid_comm import HybridCommunication
from src.topologies.sequential import SequentialPipeline
from src.topologies.debate import PeerDebate
from src.evaluation.swebench_runner import MockSWEBenchRunner, SWEBenchRunner
from src.utils.llm_client import LLMClient
from src.utils.logger import ExperimentLogger

load_dotenv()
console = Console()

ALL_TOPOLOGIES = ["sequential", "debate"]
ALL_COMMUNICATIONS = ["message_passing", "blackboard", "hybrid"]
# CLI

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SE-Blackboard experiment runner")
    parser.add_argument("--topology", choices=ALL_TOPOLOGIES, help="Pipeline topology")
    parser.add_argument("--communication", choices=ALL_COMMUNICATIONS, help="Communication mode")
    parser.add_argument("--issues", type=str, default="data/selected_issues.json", help="Path to issues JSON")
    parser.add_argument("--issue-id", type=str, help="Run a single issue by ID (for debugging)")
    parser.add_argument("--all", action="store_true", help="Run all 6 configurations")
    parser.add_argument("--mock", action="store_true", default=False, help="Use MockSWEBenchRunner")
    parser.add_argument("--no-mock", dest="mock", action="store_false", help="Use real SWEBenchRunner (default)")
    parser.add_argument("--result-suffix", type=str, default="", help="Suffix appended to result directory name (e.g. 'fewshot')")
    parser.add_argument("--tool-use", action="store_true", default=False, help="Enable tool use for Coder agent (read_file, validate_patch, etc.)")
    parser.add_argument("--patch-mode", choices=["diff", "whole_file"], default="diff", help="Coder patch generation mode: 'diff' (default) or 'whole_file'")
    parser.add_argument("--fallback-apply", action="store_true", default=True, help="Enable fallback patch apply: git apply -> patch -F0 -> patch -F3 (default: on)")
    parser.add_argument("--no-fallback-apply", dest="fallback_apply", action="store_false", help="Disable fallback, use strict git apply only")
    return parser.parse_args()
# Result persistence

_RESULT_SUFFIX: str = ""


def result_dir(topology: str, communication: str) -> Path:
    name = f"{topology}_{communication}"
    if _RESULT_SUFFIX:
        name += f"_{_RESULT_SUFFIX}"
    d = Path("data") / "results" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_result(result: ExperimentResult) -> Path:
    d = result_dir(result.topology, result.communication)
    path = d / f"{result.issue_id}.json"
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_completed_ids(topology: str, communication: str) -> set[str]:
    """Load IDs of issues that already have results (for resume support)."""
    d = result_dir(topology, communication)
    completed: set[str] = set()
    for p in d.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            completed.add(data["issue_id"])
        except (json.JSONDecodeError, KeyError):
            pass
    return completed
# Factory helpers

def build_agents(
    llm_client: LLMClient,
    logger: ExperimentLogger,
    topology: str,
) -> dict[str, Any]:
    """Create the agent dict expected by the topology."""
    agents: dict[str, Any] = {
        "planner": PlannerAgent(llm_client=llm_client, logger=logger),
        "coder": CoderAgent(llm_client=llm_client, logger=logger),
        "reviewer": ReviewerAgent(llm_client=llm_client, logger=logger),
        "tester": TesterAgent(llm_client=llm_client, logger=logger),
    }
    if topology == "debate":
        agents["coder_a"] = CoderAgent(llm_client=llm_client, logger=logger)
        agents["coder_b"] = CoderAgent(llm_client=llm_client, logger=logger)
    return agents


def build_communication(
    mode: str,
    issue: IssueInfo,
    logger: ExperimentLogger,
) -> MessagePassingCommunication | BlackboardCommunication | HybridCommunication:
    """Instantiate the communication layer."""
    if mode == "blackboard":
        return BlackboardCommunication(Blackboard(issue), logger=logger)
    if mode == "hybrid":
        return HybridCommunication(Blackboard(issue), logger=logger)
    return MessagePassingCommunication(logger=logger)


def build_pipeline(
    topology: str,
    agents: dict[str, Any],
    communication: Any,
    logger: ExperimentLogger,
    runner: Any = None,
    tool_use: bool = False,
    patch_mode: str = "diff",
    fallback_apply: bool = True,
) -> SequentialPipeline | PeerDebate:
    if topology == "sequential":
        return SequentialPipeline(
            agents=agents,
            communication=communication,
            logger=logger,
            max_iterations=settings.MAX_ITERATIONS,
            runner=runner,
            tool_use=tool_use,
            patch_mode=patch_mode,
            fallback_apply=fallback_apply,
        )
    return PeerDebate(
        agents=agents,
        communication=communication,
        logger=logger,
        max_iterations=settings.MAX_ITERATIONS,
        runner=runner,
        patch_mode=patch_mode,
        fallback_apply=fallback_apply,
    )
# Issue loading

def load_issues(path: str, issue_id: str | None = None) -> list[dict[str, Any]]:
    """Load issues from JSON file, optionally filtering by a single ID."""
    p = Path(path)
    if not p.exists():
        console.print(f"[red]Issues file not found: {path}[/red]")
        console.print("Run `python experiments/select_issues.py` first.")
        sys.exit(1)

    data = json.loads(p.read_text(encoding="utf-8"))
    if not data:
        console.print("[yellow]Issues file is empty. Using fallback demo issue.[/yellow]")
        data = [_demo_issue()]

    if issue_id:
        data = [item for item in data if item["instance_id"] == issue_id]
        if not data:
            console.print(f"[yellow]Issue {issue_id} not found in {path}. Using it as a demo.[/yellow]")
            data = [_demo_issue(issue_id)]

    return data


def _demo_issue(instance_id: str = "django__django-11099") -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "problem_statement": "UsernameValidator allows trailing newline in usernames.",
        "repo": "django/django",
        "base_commit": "d5276b9e65fdd0473e8fa50fad1b6fdb5e9891be",
    }
# Single-issue runner

async def run_single_issue(
    topology: str,
    communication: str,
    issue_data: dict[str, Any],
    use_mock: bool = True,
    issues_path: str = "data/selected_issues.json",
    tool_use: bool = False,
    patch_mode: str = "diff",
    fallback_apply: bool = True,
) -> ExperimentResult:
    """Run a single issue through a topology + communication configuration."""
    issue = IssueInfo(
        instance_id=issue_data["instance_id"],
        problem_statement=issue_data.get("problem_statement", ""),
        repo=issue_data.get("repo", ""),
        base_commit=issue_data.get("base_commit", ""),
    )

    exp_id = f"{topology}_{communication}_{issue.instance_id}"
    logger = ExperimentLogger(experiment_id=exp_id)
    llm_client = LLMClient()
    agents = build_agents(llm_client, logger, topology)

    # Create runner
    runner: Any = None
    if use_mock:
        runner = MockSWEBenchRunner(pass_rate=0.4)
    else:
        runner = SWEBenchRunner(issues_path=issues_path)

    # Enable fallback apply on runner
    runner.fallback_apply = fallback_apply

    # Inject runner into tester agents
    for agent in agents.values():
        if hasattr(agent, "set_runner"):
            agent.set_runner(runner)

    comm = build_communication(communication, issue, logger)
    pipeline = build_pipeline(
        topology, agents, comm, logger, runner=runner,
        tool_use=tool_use, patch_mode=patch_mode, fallback_apply=fallback_apply,
    )
    result = await pipeline.run(issue)
    return result
# Batch runner

async def run_experiment_config(
    topology: str,
    communication: str,
    issues: list[dict[str, Any]],
    use_mock: bool = True,
    issues_path: str = "data/selected_issues.json",
    tool_use: bool = False,
    patch_mode: str = "diff",
    fallback_apply: bool = True,
) -> list[ExperimentResult]:
    """Run a full experiment configuration with progress bar and resume support."""
    completed_ids = load_completed_ids(topology, communication)
    remaining = [i for i in issues if i["instance_id"] not in completed_ids]

    if completed_ids:
        console.print(
            f"  [cyan]Resuming:[/cyan] {len(completed_ids)} already done, {len(remaining)} remaining."
        )

    results: list[ExperimentResult] = []
    success_count = 0
    fail_count = 0
    error_count = 0
    total_tokens = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[green]{task.fields[success]}[/green]/[red]{task.fields[fail]}[/red]/[yellow]{task.fields[errors]}[/yellow]"),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]{topology}/{communication}",
            total=len(remaining),
            success=0,
            fail=0,
            errors=0,
        )

        for idx, issue_data in enumerate(remaining, 1):
            iid = issue_data["instance_id"]
            progress.update(
                task,
                description=f"[cyan]{topology}/{communication} - {iid}",
            )

            try:
                result = await run_single_issue(
                    topology, communication, issue_data, use_mock, issues_path,
                    tool_use=tool_use, patch_mode=patch_mode,
                    fallback_apply=fallback_apply,
                )
                results.append(result)
                path = save_result(result)

                tokens = result.total_input_tokens + result.total_output_tokens
                total_tokens += tokens

                if result.resolved:
                    success_count += 1
                    status = "[green]RESOLVED[/green]"
                else:
                    fail_count += 1
                    status = "[red]FAILED[/red]"

                console.print(
                    f"  {iid}: {status}  "
                    f"(iter={result.iterations}, tokens={tokens})"
                )
            except Exception as exc:
                error_count += 1
                console.print(f"  [red]{iid}: ERROR - {exc}[/red]")

            progress.update(
                task,
                success=success_count,
                fail=fail_count,
                errors=error_count,
            )
            progress.advance(task)

            # Intermediate stats every 10 issues
            completed_so_far = idx
            if completed_so_far > 0 and completed_so_far % 10 == 0:
                total_done = success_count + fail_count
                rate = f"{success_count / total_done * 100:.1f}%" if total_done else "N/A"
                avg_tok = total_tokens // max(total_done, 1)
                console.print(
                    f"\n  [bold]--- Checkpoint ({completed_so_far}/{len(remaining)}) ---[/bold]"
                )
                console.print(
                    f"  Resolve rate: {rate}  |  "
                    f"Avg tokens: {avg_tok}  |  "
                    f"Success: {success_count}  Fail: {fail_count}  Error: {error_count}\n"
                )

    return results
# Main

async def main() -> None:
    global _RESULT_SUFFIX
    args = parse_args()
    _RESULT_SUFFIX = args.result_suffix

    console.rule("[bold blue]SE-Blackboard Experiment Runner[/bold blue]")

    if args.all:
        configs = [
            (t, c)
            for t in ALL_TOPOLOGIES
            for c in ALL_COMMUNICATIONS
        ]
    elif args.topology and args.communication:
        configs = [(args.topology, args.communication)]
    else:
        console.print("[red]Specify --topology and --communication, or use --all[/red]")
        sys.exit(1)

    issues = load_issues(args.issues, args.issue_id)
    console.print(
        f"Issues: {len(issues)}  |  Configs: {len(configs)}  |  Mock: {args.mock}"
        f"  |  Tool-use: {args.tool_use}  |  Patch-mode: {args.patch_mode}"
        f"  |  Fallback-apply: {args.fallback_apply}\n"
    )

    all_results: dict[str, list[ExperimentResult]] = {}

    for topology, communication in configs:
        console.rule(f"[bold]{topology} / {communication}[/bold]")
        results = await run_experiment_config(
            topology, communication, issues, args.mock, args.issues,
            tool_use=args.tool_use, patch_mode=args.patch_mode,
            fallback_apply=args.fallback_apply,
        )
        all_results[f"{topology}_{communication}"] = results

    # ---- Summary table ----
    console.print()
    console.rule("[bold blue]Summary[/bold blue]")
    table = Table(title="Experiment Results")
    table.add_column("Config", style="cyan")
    table.add_column("Issues", justify="right")
    table.add_column("Resolved", justify="right", style="green")
    table.add_column("Rate", justify="right")
    table.add_column("Avg Tokens", justify="right")
    table.add_column("Avg Latency", justify="right")

    for config_name, results in all_results.items():
        total = len(results)
        resolved = sum(1 for r in results if r.resolved)
        rate = f"{resolved/total*100:.1f}%" if total else "N/A"
        avg_tok = sum(r.total_input_tokens + r.total_output_tokens for r in results) // max(total, 1)
        avg_lat = sum(r.total_latency_ms for r in results) // max(total, 1)
        table.add_row(
            config_name,
            str(total),
            str(resolved),
            rate,
            str(avg_tok),
            f"{avg_lat}ms",
        )

    console.print(table)


if __name__ == "__main__":
    asyncio.run(main())
