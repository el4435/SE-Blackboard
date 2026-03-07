"""Analyze experiment results and generate comparison tables.

Reads results from data/results/ and produces summary tables comparing the
6 configurations (2 topologies x 3 communication modes).

Features:
- Overall statistics (resolve rate, avg tokens, avg latency, avg iterations)
- Per-difficulty breakdown (easy / medium / hard)
- Per-repo breakdown
- Failure analysis with categorization
- _summary.json generation
- JSONL log consolidation

Usage:
    python experiments/analyze_results.py
    python experiments/analyze_results.py --config sequential_message_passing
    python experiments/analyze_results.py --save-summary
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.table import Table

from src.blackboard.schema import ExperimentResult

console = Console()

RESULTS_DIR = Path("data/results")
ISSUES_FILE = Path("data/selected_issues.json")
LOGS_DIR = Path("data/logs")
# Loading

def load_all_results() -> dict[str, list[ExperimentResult]]:
    """Load all results grouped by config name (topology_communication)."""
    grouped: dict[str, list[ExperimentResult]] = defaultdict(list)

    if not RESULTS_DIR.exists():
        return grouped

    for config_dir in sorted(RESULTS_DIR.iterdir()):
        if not config_dir.is_dir():
            continue
        for result_file in config_dir.glob("*.json"):
            if result_file.name.startswith("_"):
                continue  # Skip _summary.json etc.
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                result = ExperimentResult.model_validate(data)
                grouped[config_dir.name].append(result)
            except Exception as exc:
                console.print(f"[yellow]Skipping {result_file}: {exc}[/yellow]")

    return grouped


def load_issue_metadata() -> dict[str, dict[str, Any]]:
    """Load issue metadata (difficulty, repo, etc.) from selected_issues.json."""
    if not ISSUES_FILE.exists():
        return {}
    data = json.loads(ISSUES_FILE.read_text(encoding="utf-8"))
    return {item["instance_id"]: item for item in data}
# Display: Overall summary

def print_summary_table(grouped: dict[str, list[ExperimentResult]]) -> None:
    """Print a rich table summarizing all configurations."""
    table = Table(title="Experiment Results Summary")
    table.add_column("Config", style="cyan", min_width=25)
    table.add_column("Issues", justify="right")
    table.add_column("Resolved", justify="right", style="green")
    table.add_column("Resolve %", justify="right", style="bold")
    table.add_column("Avg Iterations", justify="right")
    table.add_column("Avg Tokens", justify="right")
    table.add_column("Avg Latency (s)", justify="right")

    for config_name in sorted(grouped.keys()):
        results = grouped[config_name]
        n = len(results)
        if n == 0:
            continue

        resolved = sum(1 for r in results if r.resolved)
        avg_iter = sum(r.iterations for r in results) / n
        avg_tok = sum(r.total_input_tokens + r.total_output_tokens for r in results) / n
        avg_lat = sum(r.total_latency_ms for r in results) / n / 1000

        table.add_row(
            config_name,
            str(n),
            str(resolved),
            f"{resolved / n * 100:.1f}%",
            f"{avg_iter:.1f}",
            f"{avg_tok:.0f}",
            f"{avg_lat:.1f}",
        )

    console.print(table)
# Display: Per-difficulty breakdown

def print_difficulty_table(
    results: list[ExperimentResult],
    issue_meta: dict[str, dict[str, Any]],
    config_name: str,
) -> None:
    """Print resolve rate and token cost grouped by difficulty."""
    table = Table(title=f"By Difficulty — {config_name}")
    table.add_column("Difficulty", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Resolved", justify="right", style="green")
    table.add_column("Resolve %", justify="right", style="bold")
    table.add_column("Avg Tokens", justify="right")
    table.add_column("Avg Iterations", justify="right")

    by_diff: dict[str, list[ExperimentResult]] = defaultdict(list)
    for r in results:
        meta = issue_meta.get(r.issue_id, {})
        diff = meta.get("difficulty", "unknown")
        by_diff[diff].append(r)

    for diff in ("easy", "medium", "hard", "unknown"):
        subset = by_diff.get(diff, [])
        if not subset:
            continue
        n = len(subset)
        resolved = sum(1 for r in subset if r.resolved)
        avg_tok = sum(r.total_input_tokens + r.total_output_tokens for r in subset) / n
        avg_iter = sum(r.iterations for r in subset) / n
        table.add_row(
            diff,
            str(n),
            str(resolved),
            f"{resolved / n * 100:.1f}%",
            f"{avg_tok:.0f}",
            f"{avg_iter:.1f}",
        )

    console.print(table)
# Display: Per-repo breakdown

def print_repo_table(
    results: list[ExperimentResult],
    issue_meta: dict[str, dict[str, Any]],
    config_name: str,
) -> None:
    """Print resolve rate grouped by repository."""
    table = Table(title=f"By Repository — {config_name}")
    table.add_column("Repository", style="cyan", min_width=25)
    table.add_column("Count", justify="right")
    table.add_column("Resolved", justify="right", style="green")
    table.add_column("Resolve %", justify="right", style="bold")

    by_repo: dict[str, list[ExperimentResult]] = defaultdict(list)
    for r in results:
        meta = issue_meta.get(r.issue_id, {})
        repo = meta.get("repo", "unknown")
        by_repo[repo].append(r)

    for repo in sorted(by_repo.keys(), key=lambda r: -len(by_repo[r])):
        subset = by_repo[repo]
        n = len(subset)
        resolved = sum(1 for r in subset if r.resolved)
        table.add_row(
            repo,
            str(n),
            str(resolved),
            f"{resolved / n * 100:.1f}%",
        )

    console.print(table)
# Display: Failure analysis

def classify_failure(result: ExperimentResult) -> str:
    """Classify why a result failed."""
    if result.resolved:
        return "resolved"

    patch = result.final_patch
    traces = result.agent_traces

    # Check for agent crash / error
    has_error = any(
        "ERROR" in str(t.get("agent_role", "")) or "error" in str(t).lower()
        for t in traces
    ) if traces else False

    # Check for empty patch (agent couldn't generate one)
    if not patch or patch.strip() == "":
        return "empty_patch"

    # Check for patch format issues (no unified diff headers)
    if "---" not in patch and "+++" not in patch:
        return "patch_format_error"

    # Default: patch was generated but tests failed → logic error
    return "patch_logic_error"


def print_failure_analysis(
    results: list[ExperimentResult],
    config_name: str,
) -> None:
    """Print failure categorization."""
    failed = [r for r in results if not r.resolved]
    if not failed:
        console.print(f"[green]No failures in {config_name}![/green]")
        return

    categories: dict[str, list[str]] = defaultdict(list)
    for r in failed:
        cat = classify_failure(r)
        categories[cat].append(r.issue_id)

    table = Table(title=f"Failure Analysis — {config_name}")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Issue IDs", style="dim")

    cat_labels = {
        "empty_patch": "Empty patch (agent error)",
        "patch_format_error": "Patch format error",
        "patch_logic_error": "Patch logic error (tests failed)",
        "agent_crash": "Agent crash/timeout",
    }

    for cat, issue_ids in sorted(categories.items(), key=lambda x: -len(x[1])):
        label = cat_labels.get(cat, cat)
        ids_str = ", ".join(sorted(issue_ids)[:10])
        if len(issue_ids) > 10:
            ids_str += f" ... (+{len(issue_ids) - 10} more)"
        table.add_row(label, str(len(issue_ids)), ids_str)

    console.print(table)
# Display: Per-issue table

def print_per_issue_table(grouped: dict[str, list[ExperimentResult]]) -> None:
    """Print a per-issue comparison across configs."""
    all_issues: set[str] = set()
    for results in grouped.values():
        for r in results:
            all_issues.add(r.issue_id)

    if not all_issues:
        return

    configs = sorted(grouped.keys())
    table = Table(title="Per-Issue Results")
    table.add_column("Issue ID", style="cyan")
    for cfg in configs:
        table.add_column(cfg, justify="center")

    for issue_id in sorted(all_issues):
        row = [issue_id]
        for cfg in configs:
            match = [r for r in grouped.get(cfg, []) if r.issue_id == issue_id]
            if match:
                r = match[0]
                cell = "[green]PASS[/green]" if r.resolved else "[red]FAIL[/red]"
                cell += f" (i={r.iterations})"
            else:
                cell = "-"
            row.append(cell)
        table.add_row(*row)

    console.print(table)
# Summary JSON generation

def generate_summary(
    config_name: str,
    results: list[ExperimentResult],
    issue_meta: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Generate a summary dict for a single configuration."""
    n = len(results)
    if n == 0:
        return {"config": config_name, "total": 0}

    resolved = sum(1 for r in results if r.resolved)
    total_tok = sum(r.total_input_tokens + r.total_output_tokens for r in results)
    total_lat = sum(r.total_latency_ms for r in results)
    total_iter = sum(r.iterations for r in results)

    # By difficulty
    by_diff: dict[str, dict[str, Any]] = {}
    diff_groups: dict[str, list[ExperimentResult]] = defaultdict(list)
    for r in results:
        meta = issue_meta.get(r.issue_id, {})
        diff = meta.get("difficulty", "unknown")
        diff_groups[diff].append(r)

    for diff, subset in diff_groups.items():
        sn = len(subset)
        sr = sum(1 for r in subset if r.resolved)
        st = sum(r.total_input_tokens + r.total_output_tokens for r in subset)
        by_diff[diff] = {
            "count": sn,
            "resolved": sr,
            "resolve_rate": round(sr / sn * 100, 1) if sn else 0,
            "avg_tokens": round(st / sn) if sn else 0,
        }

    # By repo
    by_repo: dict[str, dict[str, Any]] = {}
    repo_groups: dict[str, list[ExperimentResult]] = defaultdict(list)
    for r in results:
        meta = issue_meta.get(r.issue_id, {})
        repo = meta.get("repo", "unknown")
        repo_groups[repo].append(r)

    for repo, subset in repo_groups.items():
        sn = len(subset)
        sr = sum(1 for r in subset if r.resolved)
        by_repo[repo] = {
            "count": sn,
            "resolved": sr,
            "resolve_rate": round(sr / sn * 100, 1) if sn else 0,
        }

    # Failure analysis
    failures: list[dict[str, str]] = []
    for r in results:
        if not r.resolved:
            failures.append({
                "issue_id": r.issue_id,
                "category": classify_failure(r),
                "iterations": r.iterations,
            })

    return {
        "config": config_name,
        "total_issues": n,
        "resolved": resolved,
        "resolve_rate": round(resolved / n * 100, 1),
        "avg_tokens": round(total_tok / n),
        "avg_latency_s": round(total_lat / n / 1000, 1),
        "avg_iterations": round(total_iter / n, 1),
        "total_input_tokens": sum(r.total_input_tokens for r in results),
        "total_output_tokens": sum(r.total_output_tokens for r in results),
        "by_difficulty": by_diff,
        "by_repo": by_repo,
        "failures": failures,
        "per_issue": [
            {
                "issue_id": r.issue_id,
                "resolved": r.resolved,
                "iterations": r.iterations,
                "tokens": r.total_input_tokens + r.total_output_tokens,
                "latency_ms": r.total_latency_ms,
            }
            for r in sorted(results, key=lambda r: r.issue_id)
        ],
    }


def save_summary(config_name: str, summary: dict[str, Any]) -> Path:
    """Save _summary.json to the config's results directory."""
    d = RESULTS_DIR / config_name
    d.mkdir(parents=True, exist_ok=True)
    path = d / "_summary.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
# Log consolidation

def consolidate_logs(config_name: str, results: list[ExperimentResult]) -> Path:
    """Consolidate all agent traces into a single JSONL log file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"{config_name}_experiment.jsonl"

    with open(log_path, "w", encoding="utf-8") as f:
        for r in sorted(results, key=lambda r: r.issue_id):
            for trace in r.agent_traces:
                entry = {
                    "issue_id": r.issue_id,
                    "config": config_name,
                    "resolved": r.resolved,
                    **trace,
                }
                f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")

    return log_path
# CLI and main

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze SE-Blackboard experiment results")
    parser.add_argument("--config", type=str, help="Analyze only this config (e.g. sequential_message_passing)")
    parser.add_argument("--save-summary", action="store_true", help="Save _summary.json and JSONL logs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    console.rule("[bold blue]SE-Blackboard Result Analysis[/bold blue]")

    grouped = load_all_results()
    if not grouped:
        console.print("[red]No results found in data/results/. Run experiments first.[/red]")
        return

    issue_meta = load_issue_metadata()
    total_results = sum(len(v) for v in grouped.values())
    console.print(f"Loaded {total_results} results across {len(grouped)} configurations.\n")

    # Filter to specific config if requested
    if args.config:
        if args.config not in grouped:
            console.print(f"[red]Config '{args.config}' not found. Available: {list(grouped.keys())}[/red]")
            return
        grouped = {args.config: grouped[args.config]}

    # 1. Overall summary table
    print_summary_table(grouped)
    console.print()

    # 2. Per-config detailed analysis
    for config_name, results in sorted(grouped.items()):
        console.rule(f"[bold]{config_name}[/bold]")
        console.print()

        # Overall stats
        n = len(results)
        resolved = sum(1 for r in results if r.resolved)
        avg_tok = sum(r.total_input_tokens + r.total_output_tokens for r in results) / max(n, 1)
        avg_lat = sum(r.total_latency_ms for r in results) / max(n, 1) / 1000
        avg_iter = sum(r.iterations for r in results) / max(n, 1)

        console.print(f"  Resolve Rate: {resolved}/{n} ({resolved/max(n,1)*100:.1f}%)")
        console.print(f"  Avg Token Cost: {avg_tok:.0f} tokens/issue")
        console.print(f"  Avg Latency: {avg_lat:.1f} seconds/issue")
        console.print(f"  Avg Iterations: {avg_iter:.1f}")
        console.print()

        # By difficulty
        if issue_meta:
            print_difficulty_table(results, issue_meta, config_name)
            console.print()
            print_repo_table(results, issue_meta, config_name)
            console.print()

        # Failure analysis
        print_failure_analysis(results, config_name)
        console.print()

        # Save summary if requested
        if args.save_summary:
            summary = generate_summary(config_name, results, issue_meta)
            summary_path = save_summary(config_name, summary)
            console.print(f"  [green]Saved summary: {summary_path}[/green]")

            log_path = consolidate_logs(config_name, results)
            console.print(f"  [green]Saved logs: {log_path}[/green]")
            console.print()

    # 3. Per-issue comparison (only if multiple configs)
    if len(grouped) > 1:
        console.print()
        print_per_issue_table(grouped)


if __name__ == "__main__":
    main()
