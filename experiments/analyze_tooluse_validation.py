"""Analyze tool-use validation results vs v3 baselines.

Compares 10 issues across MP and BB configs, with and without tool-use.
Outputs: resolve rate, token consumption, patch apply success, tool-use stats.

Usage:
    python experiments/analyze_tooluse_validation.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.table import Table

console = Console()

RESULTS_DIR = Path("data/results")

# The 10 validation issues
VALIDATION_ISSUES = [
    # Success group (4 — should stay resolved)
    "django__django-11179",
    "django__django-13028",
    "django__django-12915",
    "pytest-dev__pytest-11143",
    # Challenge group (6 — all failed in v3)
    "django__django-14155",
    "django__django-13220",
    "django__django-15388",
    "django__django-11620",
    "django__django-13321",
    "sphinx-doc__sphinx-8713",
]

SUCCESS_GROUP = set(VALIDATION_ISSUES[:4])
CHALLENGE_GROUP = set(VALIDATION_ISSUES[4:])

# Config directories
CONFIGS = {
    "MP_baseline": "sequential_message_passing",
    "BB_baseline": "sequential_blackboard",
    "MP_tooluse": "sequential_message_passing_tooluse_val",
    "BB_tooluse": "sequential_blackboard_tooluse_val",
}


def load_results(config_dir: str) -> dict[str, dict[str, Any]]:
    """Load results for the 10 validation issues from a config directory."""
    d = RESULTS_DIR / config_dir
    results: dict[str, dict[str, Any]] = {}

    if not d.exists():
        console.print(f"[yellow]Directory not found: {d}[/yellow]")
        return results

    for issue_id in VALIDATION_ISSUES:
        path = d / f"{issue_id}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                results[issue_id] = data
            except (json.JSONDecodeError, KeyError) as exc:
                console.print(f"[yellow]Error loading {path}: {exc}[/yellow]")
        else:
            console.print(f"[dim]Missing: {path}[/dim]")

    return results


def get_resolved(data: dict[str, Any]) -> bool:
    return data.get("resolved", False)


def get_tokens(data: dict[str, Any]) -> int:
    return data.get("total_input_tokens", 0) + data.get("total_output_tokens", 0)


def get_latency_s(data: dict[str, Any]) -> float:
    return data.get("total_latency_ms", 0) / 1000


def has_patch(data: dict[str, Any]) -> bool:
    """Check if a non-empty patch was produced."""
    patch = data.get("final_patch", "")
    return bool(patch and patch.strip())


def has_diff_headers(data: dict[str, Any]) -> bool:
    """Check if patch has proper unified diff headers (proxy for apply success)."""
    patch = data.get("final_patch", "")
    return "---" in patch and "+++" in patch


def get_tool_stats(data: dict[str, Any]) -> dict[str, Any]:
    """Extract tool-use statistics from agent traces."""
    traces = data.get("agent_traces", [])
    tool_calls = 0
    validate_calls = 0
    validate_success = 0

    for trace in traces:
        role = trace.get("agent_role", "")
        if role != "Coder":
            continue
        # Check for tool trace in the output
        output = str(trace.get("output", ""))
        # Count tool calls from trace
        if "tool_trace" in trace:
            tool_trace = trace["tool_trace"]
            if isinstance(tool_trace, list):
                tool_calls += len(tool_trace)
                for call in tool_trace:
                    if isinstance(call, dict) and call.get("tool") == "validate_patch":
                        validate_calls += 1
                        result = call.get("result", "")
                        if "applies cleanly" in str(result).lower() or "success" in str(result).lower():
                            validate_success += 1
            elif isinstance(tool_trace, str):
                # Count lines that look like tool calls
                tool_calls += tool_trace.count("→")

    return {
        "tool_calls": tool_calls,
        "validate_calls": validate_calls,
        "validate_success": validate_success,
    }
# Display

def print_resolve_comparison(
    mp_base: dict[str, dict], bb_base: dict[str, dict],
    mp_tu: dict[str, dict], bb_tu: dict[str, dict],
) -> None:
    """Print resolve rate comparison table."""
    table = Table(title="Tool Use Validation - Resolve Rate (10 issues)")
    table.add_column("Config", style="cyan", min_width=15)
    table.add_column("No Tool Use", justify="center")
    table.add_column("Tool Use", justify="center")
    table.add_column("Delta", justify="center", style="bold")

    for label, base, tu in [("MP", mp_base, mp_tu), ("BB", bb_base, bb_tu)]:
        base_resolved = sum(1 for iid in VALIDATION_ISSUES if iid in base and get_resolved(base[iid]))
        tu_resolved = sum(1 for iid in VALIDATION_ISSUES if iid in tu and get_resolved(tu[iid]))
        tu_total = sum(1 for iid in VALIDATION_ISSUES if iid in tu)
        delta = tu_resolved - base_resolved
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        if delta > 0:
            delta_str = f"[green]{delta_str}[/green]"
        elif delta < 0:
            delta_str = f"[red]{delta_str}[/red]"

        table.add_row(
            label,
            f"{base_resolved}/10",
            f"{tu_resolved}/{tu_total}" if tu_total > 0 else "N/A",
            delta_str,
        )

    console.print(table)


def print_per_issue_comparison(
    mp_base: dict[str, dict], bb_base: dict[str, dict],
    mp_tu: dict[str, dict], bb_tu: dict[str, dict],
) -> None:
    """Print per-issue comparison table."""
    table = Table(title="Per-Issue Comparison")
    table.add_column("Issue ID", style="cyan", min_width=30)
    table.add_column("Group", justify="center")
    table.add_column("MP Base", justify="center")
    table.add_column("MP TU", justify="center")
    table.add_column("BB Base", justify="center")
    table.add_column("BB TU", justify="center")

    for iid in VALIDATION_ISSUES:
        group = "Success" if iid in SUCCESS_GROUP else "Challenge"
        group_style = "[green]Success[/green]" if iid in SUCCESS_GROUP else "[yellow]Challenge[/yellow]"

        cells = []
        for source in [mp_base, mp_tu, bb_base, bb_tu]:
            if iid in source:
                resolved = get_resolved(source[iid])
                cells.append("[green]PASS[/green]" if resolved else "[red]FAIL[/red]")
            else:
                cells.append("[dim]N/A[/dim]")

        table.add_row(iid, group_style, *cells)

    console.print(table)


def print_token_comparison(
    mp_base: dict[str, dict], bb_base: dict[str, dict],
    mp_tu: dict[str, dict], bb_tu: dict[str, dict],
) -> None:
    """Print token consumption comparison."""
    table = Table(title="Token Consumption Comparison (averages)")
    table.add_column("Config", style="cyan", min_width=15)
    table.add_column("No TU Avg Tokens", justify="right")
    table.add_column("TU Avg Tokens", justify="right")
    table.add_column("Ratio", justify="right", style="bold")
    table.add_column("No TU Avg Latency", justify="right")
    table.add_column("TU Avg Latency", justify="right")

    for label, base, tu in [("MP", mp_base, mp_tu), ("BB", bb_base, bb_tu)]:
        base_issues = [iid for iid in VALIDATION_ISSUES if iid in base]
        tu_issues = [iid for iid in VALIDATION_ISSUES if iid in tu]

        if base_issues:
            base_avg_tok = sum(get_tokens(base[iid]) for iid in base_issues) / len(base_issues)
            base_avg_lat = sum(get_latency_s(base[iid]) for iid in base_issues) / len(base_issues)
        else:
            base_avg_tok = base_avg_lat = 0

        if tu_issues:
            tu_avg_tok = sum(get_tokens(tu[iid]) for iid in tu_issues) / len(tu_issues)
            tu_avg_lat = sum(get_latency_s(tu[iid]) for iid in tu_issues) / len(tu_issues)
        else:
            tu_avg_tok = tu_avg_lat = 0

        ratio = f"{tu_avg_tok / base_avg_tok:.1f}x" if base_avg_tok else "N/A"

        table.add_row(
            label,
            f"{base_avg_tok:,.0f}",
            f"{tu_avg_tok:,.0f}" if tu_issues else "N/A",
            ratio,
            f"{base_avg_lat:.0f}s",
            f"{tu_avg_lat:.0f}s" if tu_issues else "N/A",
        )

    console.print(table)


def print_patch_apply_comparison(
    mp_base: dict[str, dict], bb_base: dict[str, dict],
    mp_tu: dict[str, dict], bb_tu: dict[str, dict],
) -> None:
    """Print patch apply success rate comparison."""
    table = Table(title="Patch Apply Success Rate Comparison")
    table.add_column("Config", style="cyan", min_width=15)
    table.add_column("No TU: Has Patch", justify="center")
    table.add_column("No TU: Has Diff Headers", justify="center")
    table.add_column("TU: Has Patch", justify="center")
    table.add_column("TU: Has Diff Headers", justify="center")

    for label, base, tu in [("MP", mp_base, mp_tu), ("BB", bb_base, bb_tu)]:
        base_issues = [iid for iid in VALIDATION_ISSUES if iid in base]
        tu_issues = [iid for iid in VALIDATION_ISSUES if iid in tu]

        base_has_patch = sum(1 for iid in base_issues if has_patch(base[iid]))
        base_has_diff = sum(1 for iid in base_issues if has_diff_headers(base[iid]))
        tu_has_patch = sum(1 for iid in tu_issues if has_patch(tu[iid]))
        tu_has_diff = sum(1 for iid in tu_issues if has_diff_headers(tu[iid]))

        bn = len(base_issues)
        tn = len(tu_issues)

        table.add_row(
            label,
            f"{base_has_patch}/{bn}",
            f"{base_has_diff}/{bn}",
            f"{tu_has_patch}/{tn}" if tn else "N/A",
            f"{tu_has_diff}/{tn}" if tn else "N/A",
        )

    console.print(table)


def print_tool_stats(
    mp_tu: dict[str, dict], bb_tu: dict[str, dict],
) -> None:
    """Print tool-use statistics."""
    table = Table(title="Tool Use Statistics")
    table.add_column("Config", style="cyan", min_width=15)
    table.add_column("Avg Tool Calls", justify="right")
    table.add_column("Avg Validate Calls", justify="right")
    table.add_column("Validate Success Rate", justify="right")

    for label, tu in [("MP+TU", mp_tu), ("BB+TU", bb_tu)]:
        tu_issues = [iid for iid in VALIDATION_ISSUES if iid in tu]
        if not tu_issues:
            table.add_row(label, "N/A", "N/A", "N/A")
            continue

        all_stats = [get_tool_stats(tu[iid]) for iid in tu_issues]
        avg_calls = sum(s["tool_calls"] for s in all_stats) / len(all_stats)
        avg_validate = sum(s["validate_calls"] for s in all_stats) / len(all_stats)
        total_validate = sum(s["validate_calls"] for s in all_stats)
        total_success = sum(s["validate_success"] for s in all_stats)
        val_rate = f"{total_success}/{total_validate} ({total_success/total_validate*100:.0f}%)" if total_validate else "N/A"

        table.add_row(
            label,
            f"{avg_calls:.1f}",
            f"{avg_validate:.1f}",
            val_rate,
        )

    console.print(table)


def print_decision(
    mp_base: dict[str, dict], bb_base: dict[str, dict],
    mp_tu: dict[str, dict], bb_tu: dict[str, dict],
) -> None:
    """Evaluate the three decision criteria and print recommendation."""
    console.rule("[bold]Decision Criteria")

    # Criterion 1: Challenge flips ≥ 3/6
    challenge_flips_mp = sum(
        1 for iid in CHALLENGE_GROUP
        if iid in mp_tu and get_resolved(mp_tu[iid])
        and (iid not in mp_base or not get_resolved(mp_base[iid]))
    )
    challenge_flips_bb = sum(
        1 for iid in CHALLENGE_GROUP
        if iid in bb_tu and get_resolved(bb_tu[iid])
        and (iid not in bb_base or not get_resolved(bb_base[iid]))
    )
    total_challenge_flips = len(set(
        iid for iid in CHALLENGE_GROUP
        if (iid in mp_tu and get_resolved(mp_tu[iid]) and (iid not in mp_base or not get_resolved(mp_base[iid])))
        or (iid in bb_tu and get_resolved(bb_tu[iid]) and (iid not in bb_base or not get_resolved(bb_base[iid])))
    ))

    c1_pass = total_challenge_flips >= 3
    console.print(f"\n  1. Challenge flips >= 3/6: {total_challenge_flips}/6 "
                  f"(MP: {challenge_flips_mp}, BB: {challenge_flips_bb}) "
                  f"{'[green]PASS[/green]' if c1_pass else '[red]FAIL[/red]'}")

    # Criterion 2: BB+TU > MP+TU by 2+ issues
    bb_tu_resolved = sum(1 for iid in VALIDATION_ISSUES if iid in bb_tu and get_resolved(bb_tu[iid]))
    mp_tu_resolved = sum(1 for iid in VALIDATION_ISSUES if iid in mp_tu and get_resolved(mp_tu[iid]))
    bb_advantage = bb_tu_resolved - mp_tu_resolved

    c2_pass = bb_advantage >= 2
    console.print(f"  2. BB+TU > MP+TU by 2+: BB={bb_tu_resolved}, MP={mp_tu_resolved}, delta={bb_advantage} "
                  f"{'[green]PASS[/green]' if c2_pass else '[red]FAIL[/red]'}")

    # Criterion 3: Patch apply success rate +20pp
    # Compare patch quality (has proper diff headers) across all configs
    base_diff_rate = 0
    tu_diff_rate = 0
    base_count = 0
    tu_count = 0
    for configs_base, configs_tu in [(mp_base, mp_tu), (bb_base, bb_tu)]:
        for iid in VALIDATION_ISSUES:
            if iid in configs_base:
                base_count += 1
                if has_diff_headers(configs_base[iid]):
                    base_diff_rate += 1
            if iid in configs_tu:
                tu_count += 1
                if has_diff_headers(configs_tu[iid]):
                    tu_diff_rate += 1

    base_pct = (base_diff_rate / base_count * 100) if base_count else 0
    tu_pct = (tu_diff_rate / tu_count * 100) if tu_count else 0
    delta_pp = tu_pct - base_pct

    c3_pass = delta_pp >= 20
    console.print(f"  3. Patch apply success +20pp: base={base_pct:.0f}%, TU={tu_pct:.0f}%, delta={delta_pp:+.0f}pp "
                  f"{'[green]PASS[/green]' if c3_pass else '[red]FAIL[/red]'}")

    # Check for regressions in success group
    success_regressions = []
    for iid in SUCCESS_GROUP:
        for label, base, tu in [("MP", mp_base, mp_tu), ("BB", bb_base, bb_tu)]:
            if iid in base and get_resolved(base[iid]):
                if iid in tu and not get_resolved(tu[iid]):
                    success_regressions.append(f"{label}:{iid}")

    if success_regressions:
        console.print(f"\n  [red]Regressions in success group: {', '.join(success_regressions)}[/red]")

    # Decision
    criteria_met = sum([c1_pass, c2_pass, c3_pass])
    console.print(f"\n  Criteria met: {criteria_met}/3")

    if criteria_met >= 2:
        console.print("\n  [bold green]GOOD[/bold green] -> Run full 50 x 2 configs (MP+BB) with tool-use")
    elif criteria_met == 1:
        console.print("\n  [bold yellow]NEUTRAL[/bold yellow] -> Run full 50 x BB+TU only")
    else:
        if success_regressions:
            console.print("\n  [bold red]BAD (with regressions)[/bold red] -> Rollback, use v3 data")
        else:
            console.print("\n  [bold red]BAD[/bold red] -> Rollback, use v3 data")


def save_comparison_json(
    mp_base: dict[str, dict], bb_base: dict[str, dict],
    mp_tu: dict[str, dict], bb_tu: dict[str, dict],
) -> Path:
    """Save comparison data as JSON for reference."""
    comparison = {
        "validation_issues": VALIDATION_ISSUES,
        "success_group": list(SUCCESS_GROUP),
        "challenge_group": list(CHALLENGE_GROUP),
        "per_issue": {},
    }

    for iid in VALIDATION_ISSUES:
        entry: dict[str, Any] = {"group": "success" if iid in SUCCESS_GROUP else "challenge"}
        for label, source in [
            ("mp_baseline", mp_base), ("bb_baseline", bb_base),
            ("mp_tooluse", mp_tu), ("bb_tooluse", bb_tu),
        ]:
            if iid in source:
                d = source[iid]
                entry[label] = {
                    "resolved": get_resolved(d),
                    "tokens": get_tokens(d),
                    "latency_s": round(get_latency_s(d), 1),
                    "iterations": d.get("iterations", 0),
                    "has_patch": has_patch(d),
                    "has_diff_headers": has_diff_headers(d),
                }
            else:
                entry[label] = None
        comparison["per_issue"][iid] = entry

    # Summary stats
    for label, source in [
        ("mp_baseline", mp_base), ("bb_baseline", bb_base),
        ("mp_tooluse", mp_tu), ("bb_tooluse", bb_tu),
    ]:
        issues = [iid for iid in VALIDATION_ISSUES if iid in source]
        if issues:
            comparison[f"{label}_summary"] = {
                "resolved": sum(1 for iid in issues if get_resolved(source[iid])),
                "total": len(issues),
                "avg_tokens": round(sum(get_tokens(source[iid]) for iid in issues) / len(issues)),
                "avg_latency_s": round(sum(get_latency_s(source[iid]) for iid in issues) / len(issues), 1),
            }

    out_path = Path("data/analysis") / "tooluse_validation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def main() -> None:
    console.rule("[bold blue]Tool Use Validation Analysis[/bold blue]")

    # Load all four result sets
    mp_base = load_results(CONFIGS["MP_baseline"])
    bb_base = load_results(CONFIGS["BB_baseline"])
    mp_tu = load_results(CONFIGS["MP_tooluse"])
    bb_tu = load_results(CONFIGS["BB_tooluse"])

    console.print(f"\nLoaded: MP_base={len(mp_base)}, BB_base={len(bb_base)}, "
                  f"MP_TU={len(mp_tu)}, BB_TU={len(bb_tu)}")
    console.print()

    if not mp_tu and not bb_tu:
        console.print("[red]No tool-use results found. Run experiments first.[/red]")
        console.print("  python experiments/run_experiment.py --topology sequential "
                      "--communication message_passing --tool-use --result-suffix tooluse_val")
        return

    # 1. Resolve rate comparison
    print_resolve_comparison(mp_base, bb_base, mp_tu, bb_tu)
    console.print()

    # 2. Per-issue comparison
    print_per_issue_comparison(mp_base, bb_base, mp_tu, bb_tu)
    console.print()

    # 3. Token consumption
    print_token_comparison(mp_base, bb_base, mp_tu, bb_tu)
    console.print()

    # 4. Patch apply success
    print_patch_apply_comparison(mp_base, bb_base, mp_tu, bb_tu)
    console.print()

    # 5. Tool-use statistics
    print_tool_stats(mp_tu, bb_tu)
    console.print()

    # 6. Decision
    print_decision(mp_base, bb_base, mp_tu, bb_tu)

    # 7. Save JSON
    out_path = save_comparison_json(mp_base, bb_base, mp_tu, bb_tu)
    console.print(f"\n[green]Saved comparison: {out_path}[/green]")


if __name__ == "__main__":
    main()
