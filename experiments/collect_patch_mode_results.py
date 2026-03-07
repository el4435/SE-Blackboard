"""Collect patch mode experiment results into a CSV file.

Reads results from data/results/ for all experiment configs (including
fallback-apply and whole-file variants) and outputs a standardized CSV
suitable for statistical analysis.

Usage:
    python experiments/collect_patch_mode_results.py
    python experiments/collect_patch_mode_results.py --output data/analysis/patch_mode_results.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console

from src.blackboard.schema import ExperimentResult

console = Console()

RESULTS_DIR = Path("data/results")
ISSUES_FILE = Path("data/selected_issues.json")
# Issue metadata

def load_issue_metadata() -> dict[str, dict[str, Any]]:
    """Load issue metadata keyed by instance_id."""
    if not ISSUES_FILE.exists():
        return {}
    data = json.loads(ISSUES_FILE.read_text(encoding="utf-8"))
    return {item["instance_id"]: item for item in data}


def get_gold_files(issue_meta: dict[str, Any]) -> set[str]:
    """Extract the set of files modified in the gold patch."""
    gold_patch = issue_meta.get("patch", "")
    if not gold_patch:
        return set()
    files: set[str] = set()
    for line in gold_patch.splitlines():
        if line.startswith("--- a/"):
            files.add(line[6:].strip())
        elif line.startswith("+++ b/"):
            files.add(line[6:].strip())
    return files


def get_patch_files(patch: str) -> set[str]:
    """Extract files touched by a unified diff patch."""
    files: set[str] = set()
    for line in patch.splitlines():
        if line.startswith("--- a/"):
            files.add(line[6:].strip())
        elif line.startswith("+++ b/"):
            files.add(line[6:].strip())
    return files
# Infer config metadata from directory name

def infer_config_metadata(dir_name: str) -> dict[str, str]:
    """Infer topology, communication, patch_mode, apply_strategy from dir name.

    Examples:
        sequential_blackboard -> (sequential, blackboard, diff, strict)
        sequential_blackboard_fallback -> (sequential, blackboard, diff, fallback)
        sequential_blackboard_whole_file -> (sequential, blackboard, whole_file, fallback)
    """
    parts = dir_name.split("_")

    topology = parts[0] if parts else "unknown"

    # Communication mode
    comm = "unknown"
    if "message_passing" in dir_name:
        comm = "MP"
    elif "blackboard" in dir_name:
        comm = "BB"
    elif "hybrid" in dir_name:
        comm = "Hybrid"

    # Patch mode
    patch_mode = "diff"
    if "whole_file" in dir_name:
        patch_mode = "whole_file"

    # Apply strategy
    apply_strategy = "strict"
    if "fallback" in dir_name:
        apply_strategy = "fallback"
    # Whole-file mode defaults to fallback
    if patch_mode == "whole_file":
        apply_strategy = "fallback"

    return {
        "topology": topology,
        "communication": comm,
        "patch_mode": patch_mode,
        "apply_strategy": apply_strategy,
    }
# Main collection

def collect_results(output_path: Path) -> None:
    """Collect all results and write CSV."""
    issue_meta = load_issue_metadata()

    if not RESULTS_DIR.exists():
        console.print("[red]No results directory found.[/red]")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "issue_id", "config", "patch_mode", "apply_strategy",
        "apply_method_used", "apply_success", "patch_empty",
        "correct_file", "resolved", "tokens", "latency_s",
        "iterations", "difficulty",
    ]

    rows: list[dict[str, Any]] = []

    for config_dir in sorted(RESULTS_DIR.iterdir()):
        if not config_dir.is_dir():
            continue

        dir_name = config_dir.name
        meta = infer_config_metadata(dir_name)

        for result_file in sorted(config_dir.glob("*.json")):
            if result_file.name.startswith("_"):
                continue

            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                result = ExperimentResult.model_validate(data)
            except Exception as exc:
                console.print(f"[yellow]Skipping {result_file}: {exc}[/yellow]")
                continue

            # Determine apply method
            apply_method = result.apply_method or ""
            if not apply_method and result.final_patch:
                apply_method = "unknown"  # Pre-Day10 result
            if not result.final_patch or not result.final_patch.strip():
                apply_method = "none"

            apply_success = apply_method not in ("failed", "none", "unknown", "")

            # Check if patch targets correct files
            patch_files = get_patch_files(result.final_patch)
            issue_data = issue_meta.get(result.issue_id, {})
            gold_files = get_gold_files(issue_data)
            correct_file = bool(patch_files & gold_files) if gold_files else False

            # Patch empty check
            patch_empty = not result.final_patch or not result.final_patch.strip()

            # Difficulty
            difficulty = issue_data.get("difficulty", "unknown")

            tokens = result.total_input_tokens + result.total_output_tokens
            latency_s = round(result.total_latency_ms / 1000, 1)

            rows.append({
                "issue_id": result.issue_id,
                "config": meta["communication"],
                "patch_mode": meta["patch_mode"],
                "apply_strategy": meta["apply_strategy"],
                "apply_method_used": apply_method,
                "apply_success": apply_success,
                "patch_empty": patch_empty,
                "correct_file": correct_file,
                "resolved": result.resolved,
                "tokens": tokens,
                "latency_s": latency_s,
                "iterations": result.iterations,
                "difficulty": difficulty,
            })

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    console.print(f"[green]Collected {len(rows)} results -> {output_path}[/green]")

    # Print summary
    from collections import Counter
    configs = Counter(r["config"] + "/" + r["patch_mode"] + "/" + r["apply_strategy"] for r in rows)
    console.print("\nResults by config:")
    for cfg, count in sorted(configs.items()):
        resolved = sum(1 for r in rows if r["config"] + "/" + r["patch_mode"] + "/" + r["apply_strategy"] == cfg and r["resolved"])
        console.print(f"  {cfg}: {count} issues, {resolved} resolved ({resolved/count*100:.1f}%)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect patch mode results to CSV")
    parser.add_argument(
        "--output", type=str,
        default="data/analysis/patch_mode_results.csv",
        help="Output CSV path",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    collect_results(Path(args.output))
