"""Patch Mode Analysis: Fallback Apply + Whole-File Rewrite experiments.

Reads the CSV produced by collect_patch_mode_results.py and generates:
1. Resolve rate + 95% CI per config combination
2. Apply success rate comparison (strict vs fallback, diff vs whole_file)
3. McNemar's test: BB vs MP (within same patch_mode + apply_strategy)
4. Apply method distribution statistics
5. Token consumption comparison (whole_file vs diff)
6. Patch quality decomposition (Table 5 format)

Usage:
    python experiments/analyze_patch_modes.py
    python experiments/analyze_patch_modes.py --csv data/analysis/day10_results.csv
    python experiments/analyze_patch_modes.py --save data/analysis/day10_analysis.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.table import Table

console = Console()

DEFAULT_CSV = Path("data/analysis/day10_results.csv")
# Data loading

def load_csv(path: Path) -> list[dict[str, Any]]:
    """Load results CSV into list of dicts with proper types."""
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert types
            row["apply_success"] = row["apply_success"].lower() == "true"
            row["patch_empty"] = row["patch_empty"].lower() == "true"
            row["correct_file"] = row["correct_file"].lower() == "true"
            row["resolved"] = row["resolved"].lower() == "true"
            row["tokens"] = int(row["tokens"])
            row["latency_s"] = float(row["latency_s"])
            row["iterations"] = int(row["iterations"])
            rows.append(row)
    return rows
# Statistical helpers

def wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for binomial proportion (95% CI by default)."""
    if total == 0:
        return (0.0, 0.0)
    p_hat = successes / total
    denom = 1 + z**2 / total
    center = (p_hat + z**2 / (2 * total)) / denom
    spread = z * math.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * total)) / total) / denom
    lo = max(0.0, center - spread)
    hi = min(1.0, center + spread)
    return (lo, hi)


def mcnemar_test(
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
) -> dict[str, Any]:
    """McNemar's test comparing two configs on paired issues.

    Returns dict with contingency table, chi2, and p-value.
    """
    # Build issue -> resolved mapping
    a_map = {r["issue_id"]: r["resolved"] for r in rows_a}
    b_map = {r["issue_id"]: r["resolved"] for r in rows_b}

    # Paired issues
    common = set(a_map.keys()) & set(b_map.keys())
    if not common:
        return {"error": "no common issues", "n_common": 0}

    # Contingency: (a_pass & b_fail), (a_fail & b_pass)
    b_only = 0  # a fail, b pass (discordant pair favoring b)
    c_only = 0  # a pass, b fail (discordant pair favoring a)
    both_pass = 0
    both_fail = 0

    for iid in common:
        a = a_map[iid]
        b = b_map[iid]
        if a and b:
            both_pass += 1
        elif not a and not b:
            both_fail += 1
        elif not a and b:
            b_only += 1
        else:
            c_only += 1

    # McNemar's chi-squared (with continuity correction)
    n_disc = b_only + c_only
    if n_disc == 0:
        chi2 = 0.0
        p_value = 1.0
    else:
        chi2 = (abs(b_only - c_only) - 1) ** 2 / n_disc
        # Approximate p-value from chi2(1) distribution
        # Using a simple approximation
        try:
            from scipy.stats import chi2 as chi2_dist
            p_value = 1 - chi2_dist.cdf(chi2, df=1)
        except ImportError:
            # Rough approximation without scipy
            if chi2 > 10.828:
                p_value = 0.001
            elif chi2 > 6.635:
                p_value = 0.01
            elif chi2 > 3.841:
                p_value = 0.05
            elif chi2 > 2.706:
                p_value = 0.1
            else:
                p_value = 0.5

    return {
        "n_common": len(common),
        "both_pass": both_pass,
        "both_fail": both_fail,
        "a_only": c_only,
        "b_only": b_only,
        "chi2": round(chi2, 3),
        "p_value": round(p_value, 4),
    }
# Analysis 1: Resolve rate + 95% CI

def analyze_resolve_rates(rows: list[dict[str, Any]]) -> None:
    """Print resolve rate with 95% Wilson CI per config combination."""
    table = Table(title="1. Resolve Rate by Configuration (95% Wilson CI)")
    table.add_column("Config", style="cyan", min_width=12)
    table.add_column("Patch Mode", min_width=10)
    table.add_column("Apply Strategy", min_width=10)
    table.add_column("N", justify="right")
    table.add_column("Resolved", justify="right", style="green")
    table.add_column("Rate", justify="right", style="bold")
    table.add_column("95% CI", justify="right")

    # Group by (config, patch_mode, apply_strategy)
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in rows:
        key = (r["config"], r["patch_mode"], r["apply_strategy"])
        groups[key].append(r)

    for key in sorted(groups.keys()):
        subset = groups[key]
        n = len(subset)
        resolved = sum(1 for r in subset if r["resolved"])
        rate = resolved / n * 100 if n else 0
        lo, hi = wilson_ci(resolved, n)

        table.add_row(
            key[0], key[1], key[2],
            str(n), str(resolved),
            f"{rate:.1f}%",
            f"[{lo*100:.1f}%, {hi*100:.1f}%]",
        )

    console.print(table)
# Analysis 2: Apply success rate comparison

def analyze_apply_rates(rows: list[dict[str, Any]]) -> None:
    """Compare apply success rates across strategies and modes."""
    table = Table(title="2. Patch Apply Success Rate")
    table.add_column("Config", style="cyan")
    table.add_column("Patch Mode")
    table.add_column("Apply Strategy")
    table.add_column("N", justify="right")
    table.add_column("Apply OK", justify="right", style="green")
    table.add_column("Apply %", justify="right", style="bold")
    table.add_column("Empty Patch", justify="right", style="yellow")

    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in rows:
        key = (r["config"], r["patch_mode"], r["apply_strategy"])
        groups[key].append(r)

    for key in sorted(groups.keys()):
        subset = groups[key]
        n = len(subset)
        non_empty = [r for r in subset if not r["patch_empty"]]
        apply_ok = sum(1 for r in non_empty if r["apply_success"])
        empty = sum(1 for r in subset if r["patch_empty"])

        apply_rate = apply_ok / len(non_empty) * 100 if non_empty else 0

        table.add_row(
            key[0], key[1], key[2],
            str(n), str(apply_ok),
            f"{apply_rate:.1f}%",
            str(empty),
        )

    console.print(table)
# Analysis 3: McNemar's test (BB vs MP)

def analyze_mcnemar(rows: list[dict[str, Any]]) -> None:
    """McNemar's test comparing BB vs MP within same patch_mode + apply_strategy."""
    console.print("\n[bold]3. McNemar's Test: BB vs MP[/bold]\n")

    # Group by (patch_mode, apply_strategy)
    mode_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        key = (r["patch_mode"], r["apply_strategy"])
        mode_groups[key].append(r)

    for mode_key in sorted(mode_groups.keys()):
        subset = mode_groups[mode_key]
        mp_rows = [r for r in subset if r["config"] == "MP"]
        bb_rows = [r for r in subset if r["config"] == "BB"]

        if not mp_rows or not bb_rows:
            continue

        result = mcnemar_test(mp_rows, bb_rows)

        console.print(f"  {mode_key[0]} + {mode_key[1]}:")
        if "error" in result:
            console.print(f"    {result['error']}")
            continue

        console.print(f"    Common issues: {result['n_common']}")
        console.print(f"    Both pass: {result['both_pass']}, Both fail: {result['both_fail']}")
        console.print(f"    MP-only pass: {result['a_only']}, BB-only pass: {result['b_only']}")
        console.print(f"    Chi2 = {result['chi2']}, p = {result['p_value']}")

        sig = "significant" if result["p_value"] < 0.05 else "not significant"
        console.print(f"    -> {sig} at alpha=0.05\n")
# Analysis 4: Apply method distribution

def analyze_apply_methods(rows: list[dict[str, Any]]) -> None:
    """Distribution of apply methods used across configs."""
    table = Table(title="4. Apply Method Distribution")
    table.add_column("Config", style="cyan")
    table.add_column("git_apply", justify="right")
    table.add_column("patch_strict", justify="right")
    table.add_column("patch_fuzz3", justify="right")
    table.add_column("failed", justify="right", style="red")
    table.add_column("none/empty", justify="right", style="yellow")
    table.add_column("unknown", justify="right", style="dim")

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        key = f"{r['config']}/{r['patch_mode']}/{r['apply_strategy']}"
        groups[key].append(r)

    for key in sorted(groups.keys()):
        subset = groups[key]
        methods = Counter(r["apply_method_used"] for r in subset)
        table.add_row(
            key,
            str(methods.get("git_apply", 0)),
            str(methods.get("patch_strict", 0)),
            str(methods.get("patch_fuzz3", 0)),
            str(methods.get("failed", 0)),
            str(methods.get("none", 0)),
            str(methods.get("unknown", 0) + methods.get("", 0)),
        )

    console.print(table)
# Analysis 5: Token comparison

def analyze_tokens(rows: list[dict[str, Any]]) -> None:
    """Token consumption comparison between patch modes."""
    table = Table(title="5. Token Consumption by Patch Mode")
    table.add_column("Config", style="cyan")
    table.add_column("Patch Mode")
    table.add_column("N", justify="right")
    table.add_column("Avg Tokens", justify="right")
    table.add_column("Median Tokens", justify="right")
    table.add_column("Avg Latency (s)", justify="right")

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        key = (r["config"], r["patch_mode"])
        groups[key].append(r)

    for key in sorted(groups.keys()):
        subset = groups[key]
        n = len(subset)
        tokens = sorted(r["tokens"] for r in subset)
        avg_tok = sum(tokens) / n
        median_tok = tokens[n // 2]
        avg_lat = sum(r["latency_s"] for r in subset) / n

        table.add_row(
            key[0], key[1],
            str(n),
            f"{avg_tok:.0f}",
            f"{median_tok}",
            f"{avg_lat:.1f}",
        )

    console.print(table)
# Analysis 6: Patch quality decomposition (Table 5)

def analyze_patch_quality(rows: list[dict[str, Any]]) -> None:
    """Patch quality decomposition similar to Table 5 in the paper."""
    table = Table(title="6. Patch Quality Decomposition")
    table.add_column("Config", style="cyan", min_width=20)
    table.add_column("N", justify="right")
    table.add_column("Non-Empty", justify="right")
    table.add_column("Correct File", justify="right")
    table.add_column("Apply OK", justify="right")
    table.add_column("Resolved", justify="right", style="green")
    table.add_column("% Non-Empty", justify="right")
    table.add_column("% Correct", justify="right")
    table.add_column("% Apply", justify="right")
    table.add_column("% Resolved", justify="right", style="bold")

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        key = f"{r['config']}/{r['patch_mode']}/{r['apply_strategy']}"
        groups[key].append(r)

    for key in sorted(groups.keys()):
        subset = groups[key]
        n = len(subset)
        non_empty = sum(1 for r in subset if not r["patch_empty"])
        correct = sum(1 for r in subset if r["correct_file"])
        apply_ok = sum(1 for r in subset if r["apply_success"])
        resolved = sum(1 for r in subset if r["resolved"])

        table.add_row(
            key,
            str(n),
            str(non_empty),
            str(correct),
            str(apply_ok),
            str(resolved),
            f"{non_empty/n*100:.0f}%" if n else "-",
            f"{correct/n*100:.0f}%" if n else "-",
            f"{apply_ok/n*100:.0f}%" if n else "-",
            f"{resolved/n*100:.0f}%" if n else "-",
        )

    console.print(table)
# Save analysis JSON

def save_analysis(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Save analysis results as JSON."""
    analysis: dict[str, Any] = {}

    # Per-config summary
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        key = f"{r['config']}/{r['patch_mode']}/{r['apply_strategy']}"
        groups[key].append(r)

    configs: list[dict[str, Any]] = []
    for key in sorted(groups.keys()):
        subset = groups[key]
        n = len(subset)
        resolved = sum(1 for r in subset if r["resolved"])
        non_empty = sum(1 for r in subset if not r["patch_empty"])
        apply_ok = sum(1 for r in subset if r["apply_success"])
        correct = sum(1 for r in subset if r["correct_file"])
        lo, hi = wilson_ci(resolved, n)

        configs.append({
            "config": key,
            "n": n,
            "resolved": resolved,
            "resolve_rate": round(resolved / n * 100, 1) if n else 0,
            "ci_95": [round(lo * 100, 1), round(hi * 100, 1)],
            "non_empty": non_empty,
            "correct_file": correct,
            "apply_ok": apply_ok,
            "avg_tokens": round(sum(r["tokens"] for r in subset) / n) if n else 0,
            "avg_latency_s": round(sum(r["latency_s"] for r in subset) / n, 1) if n else 0,
            "apply_method_dist": dict(Counter(r["apply_method_used"] for r in subset)),
        })

    analysis["configs"] = configs

    # McNemar tests
    mcnemar_results: list[dict[str, Any]] = []
    mode_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        mode_groups[(r["patch_mode"], r["apply_strategy"])].append(r)

    for mode_key in sorted(mode_groups.keys()):
        subset = mode_groups[mode_key]
        mp_rows = [r for r in subset if r["config"] == "MP"]
        bb_rows = [r for r in subset if r["config"] == "BB"]
        if mp_rows and bb_rows:
            result = mcnemar_test(mp_rows, bb_rows)
            result["comparison"] = f"BB vs MP ({mode_key[0]}/{mode_key[1]})"
            mcnemar_results.append(result)

    analysis["mcnemar_tests"] = mcnemar_results

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    console.print(f"\n[green]Saved analysis -> {output_path}[/green]")
# CLI

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch mode experiment analysis")
    parser.add_argument(
        "--csv", type=str, default=str(DEFAULT_CSV),
        help="Path to results CSV",
    )
    parser.add_argument(
        "--save", type=str, default="",
        help="Save analysis JSON to this path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)

    if not csv_path.exists():
        console.print(f"[red]CSV not found: {csv_path}[/red]")
        console.print("Run `python experiments/collect_patch_mode_results.py` first.")
        return

    rows = load_csv(csv_path)
    console.rule("[bold blue]Patch Mode Experiment Analysis[/bold blue]")
    console.print(f"Loaded {len(rows)} result rows from {csv_path}\n")

    # 1. Resolve rates
    analyze_resolve_rates(rows)
    console.print()

    # 2. Apply success rates
    analyze_apply_rates(rows)
    console.print()

    # 3. McNemar's test
    analyze_mcnemar(rows)

    # 4. Apply method distribution
    analyze_apply_methods(rows)
    console.print()

    # 5. Token comparison
    analyze_tokens(rows)
    console.print()

    # 6. Patch quality decomposition
    analyze_patch_quality(rows)

    # Save JSON if requested
    if args.save:
        save_analysis(rows, Path(args.save))


if __name__ == "__main__":
    main()
