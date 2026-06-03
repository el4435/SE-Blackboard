"""B6: Detailed cost-efficiency: tokens-per-resolved and per-stage cost.

Reviewer asks (R3#7, R2-cost): Conduct detailed analysis of compute cost and
token consumption per agent, including tokens-per-resolved-issue.

Outputs:
    - data/analysis/revision/b6_cost.json
    - data/analysis/revision/b6_cost.md
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from glob import glob
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONFIGS = [
    ("sequential_message_passing", "MP"),
    ("sequential_blackboard", "BB"),
    ("sequential_hybrid", "Hybrid"),
]
STAGES = ["Planner", "Coder", "Reviewer", "Tester"]


def main() -> None:
    out: dict = {}
    for cfg_key, label in CONFIGS:
        config_dir = os.path.join(ROOT, "data", "results", cfg_key)
        files = sorted(glob(os.path.join(config_dir, "*.json")))
        files = [f for f in files if "_summary" not in os.path.basename(f)]

        total_in = total_out = total_lat_ms = 0
        n = 0
        n_resolved = 0
        stage_tokens: dict[str, list[int]] = defaultdict(list)
        per_run_tokens: list[int] = []
        per_run_resolved: list[bool] = []
        per_run_lat: list[float] = []

        for fpath in files:
            with open(fpath, encoding="utf-8") as f:
                r = json.load(f)
            n += 1
            tin = r.get("total_input_tokens", 0)
            tout = r.get("total_output_tokens", 0)
            lat = r.get("total_latency_ms", 0)
            total_in += tin
            total_out += tout
            total_lat_ms += lat
            per_run_tokens.append(tin + tout)
            per_run_lat.append(lat / 1000.0)
            resolved = bool(r.get("resolved"))
            per_run_resolved.append(resolved)
            if resolved:
                n_resolved += 1

            # Per-stage tokens summed across iterations
            per_stage: dict[str, int] = defaultdict(int)
            for trace in r.get("agent_traces", []):
                role = trace.get("agent_role")
                if role in STAGES:
                    per_stage[role] += int(trace.get("input_tokens", 0)) + int(
                        trace.get("output_tokens", 0)
                    )
            for s in STAGES:
                stage_tokens[s].append(per_stage[s])

        tokens_per_run_mean = (total_in + total_out) / n if n else 0
        tokens_per_resolved = (
            (total_in + total_out) / n_resolved if n_resolved else None
        )
        resolved_token_means = [
            t for t, ok in zip(per_run_tokens, per_run_resolved) if ok
        ]
        unresolved_token_means = [
            t for t, ok in zip(per_run_tokens, per_run_resolved) if not ok
        ]

        out[label] = {
            "n_runs": n,
            "n_resolved": n_resolved,
            "total_tokens_all_runs": total_in + total_out,
            "tokens_per_run_mean": round(tokens_per_run_mean, 1),
            "tokens_per_resolved": (
                round(tokens_per_resolved, 1) if tokens_per_resolved else None
            ),
            "latency_per_run_mean_sec": round(total_lat_ms / 1000.0 / n, 1) if n else 0,
            "per_stage_tokens_mean": {
                s: round(mean(stage_tokens[s]), 1) if stage_tokens[s] else 0
                for s in STAGES
            },
            "tokens_in_resolved_runs_mean": (
                round(mean(resolved_token_means), 1) if resolved_token_means else None
            ),
            "tokens_in_unresolved_runs_mean": (
                round(mean(unresolved_token_means), 1)
                if unresolved_token_means
                else None
            ),
        }

    out_dir = os.path.join(ROOT, "data", "analysis", "revision")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "b6_cost.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    lines = ["# B6: Cost-Efficiency Detailed Analysis", ""]
    lines.append("## Summary by configuration")
    lines.append("| Config | N | Resolved | Tokens/run | Tokens/resolved | Lat/run (s) |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for label in ("MP", "BB", "Hybrid"):
        d = out[label]
        tpr = f"{d['tokens_per_resolved']:,.0f}" if d["tokens_per_resolved"] else "n/a"
        lines.append(
            f"| {label} | {d['n_runs']} | {d['n_resolved']} | "
            f"{d['tokens_per_run_mean']:,.0f} | {tpr} | {d['latency_per_run_mean_sec']:.1f} |"
        )

    lines.append("")
    lines.append("## Per-stage token consumption (mean per run)")
    lines.append("| Config | Planner | Coder | Reviewer | Tester |")
    lines.append("|---|---:|---:|---:|---:|")
    for label in ("MP", "BB", "Hybrid"):
        st = out[label]["per_stage_tokens_mean"]
        lines.append(
            f"| {label} | {st['Planner']:,.0f} | {st['Coder']:,.0f} | "
            f"{st['Reviewer']:,.0f} | {st['Tester']:,.0f} |"
        )

    lines.append("")
    lines.append("## Resolved vs unresolved cost")
    lines.append("| Config | Resolved-run tokens | Unresolved-run tokens |")
    lines.append("|---|---:|---:|")
    for label in ("MP", "BB", "Hybrid"):
        d = out[label]
        r_str = f"{d['tokens_in_resolved_runs_mean']:,.0f}" if d["tokens_in_resolved_runs_mean"] else "n/a"
        u_str = f"{d['tokens_in_unresolved_runs_mean']:,.0f}" if d["tokens_in_unresolved_runs_mean"] else "n/a"
        lines.append(f"| {label} | {r_str} | {u_str} |")

    md_path = os.path.join(out_dir, "b6_cost.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
