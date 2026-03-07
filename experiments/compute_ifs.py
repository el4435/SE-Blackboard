"""Compute Information Fidelity Score (IFS) for all 50 issues x 6 configs.

Usage:
    python experiments/compute_ifs.py                    # Rule-based entities
    python experiments/compute_ifs.py --use-llm          # LLM-based entities
    python experiments/compute_ifs.py --entities-only     # Only extract entities

IFS measures how well key entities from the original issue are preserved
through each agent stage. The expected pattern:
- Message-Passing: IFS declines from Planner to Tester (information decay)
- Blackboard: IFS remains relatively stable (shared state prevents decay)
- Hybrid: Between the two
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evaluation.ifs import (
    STAGES,
    compute_ifs_for_text,
    extract_agent_outputs,
    extract_key_entities_llm,
    extract_key_entities_rule_based,
    point_biserial_correlation,
)
# Configuration

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIGS = [
    "sequential_message_passing",
    "sequential_blackboard",
    "sequential_hybrid",
    "debate_message_passing",
    "debate_blackboard",
    "debate_hybrid",
]

CONFIG_LABELS = {
    "sequential_message_passing": "Seq-MP",
    "sequential_blackboard": "Seq-BB",
    "sequential_hybrid": "Seq-Hybrid",
    "debate_message_passing": "Deb-MP",
    "debate_blackboard": "Deb-BB",
    "debate_hybrid": "Deb-Hybrid",
}

TOPOLOGY_MAP = {
    "sequential_message_passing": "Sequential",
    "sequential_blackboard": "Sequential",
    "sequential_hybrid": "Sequential",
    "debate_message_passing": "Debate",
    "debate_blackboard": "Debate",
    "debate_hybrid": "Debate",
}

COMM_MAP = {
    "sequential_message_passing": "Message-Passing",
    "sequential_blackboard": "Blackboard",
    "sequential_hybrid": "Hybrid",
    "debate_message_passing": "Message-Passing",
    "debate_blackboard": "Blackboard",
    "debate_hybrid": "Hybrid",
}
# Entity Extraction


async def extract_all_entities(
    issues: list[dict],
    output_path: str,
    use_llm: bool = False,
) -> dict[str, list[str]]:
    """Extract key entities for all issues.

    Checks cache first. If entities already exist, loads from file.
    """
    if os.path.exists(output_path):
        with open(output_path, encoding="utf-8") as f:
            cached = json.load(f)
        print(f"  Loaded cached entities for {len(cached)} issues from {output_path}")
        # Check if all issues are covered
        missing = [i for i in issues if i["instance_id"] not in cached]
        if not missing:
            return cached
        print(f"  {len(missing)} issues need entity extraction")
    else:
        cached = {}
        missing = issues

    all_entities = dict(cached)

    if use_llm:
        from src.utils.llm_client import LLMClient

        llm = LLMClient()
        for i, issue in enumerate(missing, 1):
            iid = issue["instance_id"]
            print(f"  [{i}/{len(missing)}] Extracting entities (LLM): {iid}")
            entities = await extract_key_entities_llm(
                issue["problem_statement"], llm
            )
            all_entities[iid] = entities
    else:
        for i, issue in enumerate(missing, 1):
            iid = issue["instance_id"]
            entities = extract_key_entities_rule_based(issue["problem_statement"])
            all_entities[iid] = entities
            if i % 10 == 0 or i == len(missing):
                print(f"  [{i}/{len(missing)}] Extracted entities (rule-based)")

    # Save to cache
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_entities, f, indent=2, ensure_ascii=False)
    print(f"  Saved entities for {len(all_entities)} issues to {output_path}")

    return all_entities
# IFS Computation


def compute_ifs_all_configs(
    issues: list[dict],
    all_entities: dict[str, list[str]],
    results_dir: str,
) -> dict[str, dict[str, dict]]:
    """Compute IFS for all configs x issues x stages.

    Returns:
        {config: {issue_id: {
            "stage_ifs": {"Planner": 0.85, "Coder": 0.62, ...},
            "end_to_end_ifs": 0.55,
            "resolved": True/False,
            "entity_count": 12,
            "data_available": {"Planner": True, "Coder": True, ...}
        }}}
    """
    ifs_results: dict[str, dict[str, dict]] = {}

    for config in CONFIGS:
        label = CONFIG_LABELS[config]
        config_dir = os.path.join(results_dir, config)
        config_results: dict[str, dict] = {}
        available_count = 0

        for issue in issues:
            iid = issue["instance_id"]
            result_path = os.path.join(config_dir, f"{iid}.json")

            if not os.path.exists(result_path):
                continue

            with open(result_path, encoding="utf-8") as f:
                result = json.load(f)

            entities = all_entities.get(iid, [])
            if not entities:
                continue

            # Extract per-stage outputs
            outputs = extract_agent_outputs(result)

            # Compute per-stage IFS
            stage_ifs: dict[str, float | None] = {}
            data_available: dict[str, bool] = {}

            for stage in STAGES:
                output_text = outputs.get(stage, "")
                if output_text:
                    stage_ifs[stage] = round(
                        compute_ifs_for_text(entities, output_text), 4
                    )
                    data_available[stage] = True
                else:
                    stage_ifs[stage] = None
                    data_available[stage] = False

            # End-to-end IFS (based on final_patch — available for all configs)
            final_patch = result.get("final_patch", "")
            e2e_ifs = round(compute_ifs_for_text(entities, final_patch), 4) if final_patch else 0.0

            config_results[iid] = {
                "stage_ifs": stage_ifs,
                "end_to_end_ifs": e2e_ifs,
                "resolved": result.get("resolved", False),
                "entity_count": len(entities),
                "data_available": data_available,
            }
            available_count += 1

        ifs_results[config] = config_results
        print(f"  {label}: computed IFS for {available_count} issues")

    return ifs_results
# Summary Statistics


def compute_summary(
    ifs_results: dict[str, dict[str, dict]],
) -> dict[str, Any]:
    """Compute IFS summary statistics across all configs."""
    summary: dict[str, Any] = {}

    # 1. Per-stage average IFS by config
    stage_avg: dict[str, dict[str, float | str]] = {}
    for config in CONFIGS:
        label = CONFIG_LABELS[config]
        config_data = ifs_results.get(config, {})

        stage_scores: dict[str, list[float]] = {s: [] for s in STAGES}
        for issue_data in config_data.values():
            for stage in STAGES:
                val = issue_data["stage_ifs"].get(stage)
                if val is not None:
                    stage_scores[stage].append(val)

        stage_means: dict[str, float | str] = {}
        for stage in STAGES:
            scores = stage_scores[stage]
            if scores:
                stage_means[stage] = round(sum(scores) / len(scores), 4)
            else:
                stage_means[stage] = "N/A"

        stage_avg[label] = stage_means

    summary["stage_average_ifs"] = stage_avg

    # 2. End-to-end average IFS by config
    e2e_avg: dict[str, dict[str, float]] = {}
    for config in CONFIGS:
        label = CONFIG_LABELS[config]
        config_data = ifs_results.get(config, {})
        e2e_scores = [d["end_to_end_ifs"] for d in config_data.values()]
        if e2e_scores:
            e2e_avg[label] = {
                "mean": round(sum(e2e_scores) / len(e2e_scores), 4),
                "min": round(min(e2e_scores), 4),
                "max": round(max(e2e_scores), 4),
                "count": len(e2e_scores),
            }
    summary["end_to_end_ifs"] = e2e_avg

    # 3. IFS by topology x comm mode (for the paper table)
    topology_comm: dict[str, dict[str, dict[str, float | str]]] = {}
    for topology in ["Sequential", "Debate"]:
        topology_comm[topology] = {}
        for comm in ["Message-Passing", "Blackboard", "Hybrid"]:
            # Find matching config
            matching = [
                c
                for c in CONFIGS
                if TOPOLOGY_MAP[c] == topology and COMM_MAP[c] == comm
            ]
            if not matching:
                continue
            config = matching[0]
            label = CONFIG_LABELS[config]
            if label in stage_avg:
                topology_comm[topology][comm] = stage_avg[label]

    summary["topology_comm_matrix"] = topology_comm

    # 4. Correlation: IFS vs resolved
    correlations: dict[str, dict[str, Any]] = {}
    for config in CONFIGS:
        label = CONFIG_LABELS[config]
        config_data = ifs_results.get(config, {})

        # End-to-end IFS vs resolved
        e2e_ifs_list = []
        resolved_list = []
        for d in config_data.values():
            e2e_ifs_list.append(d["end_to_end_ifs"])
            resolved_list.append(1 if d["resolved"] else 0)

        if len(e2e_ifs_list) >= 10:
            r, sig = point_biserial_correlation(e2e_ifs_list, resolved_list)
            # Also compute group means
            resolved_ifs = [
                e2e_ifs_list[i]
                for i in range(len(e2e_ifs_list))
                if resolved_list[i] == 1
            ]
            unresolved_ifs = [
                e2e_ifs_list[i]
                for i in range(len(e2e_ifs_list))
                if resolved_list[i] == 0
            ]
            correlations[label] = {
                "r": r,
                "significance": sig,
                "mean_ifs_resolved": (
                    round(sum(resolved_ifs) / len(resolved_ifs), 4)
                    if resolved_ifs
                    else "N/A"
                ),
                "mean_ifs_unresolved": (
                    round(sum(unresolved_ifs) / len(unresolved_ifs), 4)
                    if unresolved_ifs
                    else "N/A"
                ),
                "n_resolved": len(resolved_ifs),
                "n_unresolved": len(unresolved_ifs),
            }

    summary["ifs_resolve_correlation"] = correlations

    # 5. Blackboard effect on IFS (BB - MP delta)
    bb_effect: dict[str, dict[str, Any]] = {}
    for topology in ["Sequential", "Debate"]:
        mp_key = f"{'Seq' if topology == 'Sequential' else 'Deb'}-MP"
        bb_key = f"{'Seq' if topology == 'Sequential' else 'Deb'}-BB"

        if mp_key in e2e_avg and bb_key in e2e_avg:
            mp_mean = e2e_avg[mp_key]["mean"]
            bb_mean = e2e_avg[bb_key]["mean"]
            bb_effect[topology] = {
                "mp_e2e_ifs": mp_mean,
                "bb_e2e_ifs": bb_mean,
                "delta": round(bb_mean - mp_mean, 4),
            }

    summary["blackboard_effect_on_ifs"] = bb_effect

    return summary
# Output Formatting


def print_summary(summary: dict[str, Any]) -> None:
    """Print formatted IFS summary tables."""
    print("\n" + "=" * 70)
    print("IFS (Information Fidelity Score) Analysis Results")
    print("=" * 70)

    # Table 1: Per-stage IFS (Sequential)
    print("\n--- Per-Stage IFS: Sequential Pipeline (averaged over 50 issues) ---")
    _print_stage_table("Sequential", summary)

    # Table 2: Per-stage IFS (Debate)
    print("\n--- Per-Stage IFS: Debate Pipeline (averaged over 50 issues) ---")
    _print_stage_table("Debate", summary)

    # Table 3: End-to-end IFS comparison
    print("\n--- End-to-End IFS (based on final_patch, all configs) ---")
    e2e = summary.get("end_to_end_ifs", {})
    print(f"  {'Config':<15} {'Mean':>8} {'Min':>8} {'Max':>8} {'N':>5}")
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*8} {'-'*5}")
    for label in ["Seq-MP", "Seq-BB", "Seq-Hybrid", "Deb-MP", "Deb-BB", "Deb-Hybrid"]:
        if label in e2e:
            d = e2e[label]
            print(
                f"  {label:<15} {d['mean']:>8.4f} {d['min']:>8.4f} "
                f"{d['max']:>8.4f} {d['count']:>5}"
            )

    # Table 4: Blackboard effect on IFS
    print("\n--- Blackboard Effect on End-to-End IFS ---")
    bb_effect = summary.get("blackboard_effect_on_ifs", {})
    for topology, data in bb_effect.items():
        print(
            f"  {topology}: MP={data['mp_e2e_ifs']:.4f} -> "
            f"BB={data['bb_e2e_ifs']:.4f} (delta={data['delta']:+.4f})"
        )

    # Table 5: IFS-Resolve correlation
    print("\n--- IFS vs Resolve Rate Correlation (point-biserial) ---")
    corr = summary.get("ifs_resolve_correlation", {})
    print(
        f"  {'Config':<15} {'r':>8} {'Sig':>8} "
        f"{'IFS(res)':>10} {'IFS(unres)':>10}"
    )
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*10} {'-'*10}")
    for label in ["Seq-MP", "Seq-BB", "Seq-Hybrid", "Deb-MP", "Deb-BB", "Deb-Hybrid"]:
        if label in corr:
            c = corr[label]
            r_str = f"{c['r']:.4f}" if isinstance(c["r"], (int, float)) else str(c["r"])
            res_str = (
                f"{c['mean_ifs_resolved']:.4f}"
                if isinstance(c["mean_ifs_resolved"], (int, float))
                else str(c["mean_ifs_resolved"])
            )
            unres_str = (
                f"{c['mean_ifs_unresolved']:.4f}"
                if isinstance(c["mean_ifs_unresolved"], (int, float))
                else str(c["mean_ifs_unresolved"])
            )
            print(
                f"  {label:<15} {r_str:>8} {c['significance']:>8} "
                f"{res_str:>10} {unres_str:>10}"
            )

    print()


def _print_stage_table(topology: str, summary: dict[str, Any]) -> None:
    """Print per-stage IFS table for a topology."""
    matrix = summary.get("topology_comm_matrix", {}).get(topology, {})
    if not matrix:
        print("  (no data available)")
        return

    comm_modes = ["Message-Passing", "Blackboard", "Hybrid"]
    header = f"  {'Stage':<12}"
    for cm in comm_modes:
        header += f" {cm:>16}"
    print(header)
    print(f"  {'-'*12}" + f" {'-'*16}" * len(comm_modes))

    for stage in STAGES:
        row = f"  {stage:<12}"
        for cm in comm_modes:
            val = matrix.get(cm, {}).get(stage, "N/A")
            if isinstance(val, (int, float)):
                row += f" {val:>16.4f}"
            else:
                row += f" {str(val):>16}"
        print(row)
# Main


async def main() -> None:
    parser = argparse.ArgumentParser(description="Compute IFS for all experiments")
    parser.add_argument(
        "--issues",
        default=os.path.join(PROJECT_ROOT, "data", "selected_issues.json"),
        help="Path to selected_issues.json",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use LLM for entity extraction (costs ~$3-5)",
    )
    parser.add_argument(
        "--entities-only",
        action="store_true",
        help="Only extract entities, don't compute IFS",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(PROJECT_ROOT, "data", "ifs"),
        help="Output directory for IFS results",
    )
    args = parser.parse_args()

    results_dir = os.path.join(PROJECT_ROOT, "data", "results")
    os.makedirs(args.output_dir, exist_ok=True)

    # 1. Load issues
    print(f"Loading issues from {args.issues}...")
    with open(args.issues, encoding="utf-8") as f:
        issues = json.load(f)
    print(f"  Loaded {len(issues)} issues")

    # 2. Extract entities
    entities_path = os.path.join(args.output_dir, "entities.json")
    print(f"\nExtracting key entities ({'LLM' if args.use_llm else 'rule-based'})...")
    all_entities = await extract_all_entities(issues, entities_path, args.use_llm)

    # Print entity stats
    counts = [len(v) for v in all_entities.values()]
    avg_count = sum(counts) / len(counts) if counts else 0
    print(f"  Entity stats: avg={avg_count:.1f}, min={min(counts)}, max={max(counts)}")

    if args.entities_only:
        print("\n--entities-only flag set, skipping IFS computation.")
        return

    # 3. Compute IFS for all configs
    print("\nComputing IFS for all configs...")
    ifs_results = compute_ifs_all_configs(issues, all_entities, results_dir)

    # 4. Save detailed results
    ifs_results_path = os.path.join(args.output_dir, "ifs_results.json")
    with open(ifs_results_path, "w", encoding="utf-8") as f:
        json.dump(ifs_results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved detailed IFS results to {ifs_results_path}")

    # 5. Compute and save summary
    print("\nComputing summary statistics...")
    summary = compute_summary(ifs_results)

    summary_path = os.path.join(args.output_dir, "ifs_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Saved IFS summary to {summary_path}")

    # 6. Print summary tables
    print_summary(summary)


if __name__ == "__main__":
    asyncio.run(main())
