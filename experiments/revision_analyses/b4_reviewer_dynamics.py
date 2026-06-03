"""B4: Reviewer agent accept/reject dynamics.

Reviewer asks (R1-gap-3, R2-comprehensive-1): Quantify the Reviewer's
accept/reject behavior across the pipeline (up to 3 iterations allowed),
and whether BB's higher IFS translates into fewer Reviewer rejections.

For BB and Hybrid, blackboard_final_state.reviews[] gives explicit verdicts.
For MP, only `iterations` is recorded; we infer accept-on-iteration patterns
from iteration count (acceptance terminates the loop early; reaching
iterations==3 implies either accept-on-3 or never-accepted; both rejected by
the test, but we cannot disambiguate from the persisted MP data).

Outputs:
    - data/analysis/revision/b4_reviewer.json
    - data/analysis/revision/b4_reviewer.md
"""

from __future__ import annotations

import json
import os
from collections import Counter
from glob import glob
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONFIGS = [
    ("sequential_message_passing", "MP"),
    ("sequential_blackboard", "BB"),
    ("sequential_hybrid", "Hybrid"),
]


def main() -> None:
    out: dict = {}
    for cfg_key, label in CONFIGS:
        config_dir = os.path.join(ROOT, "data", "results", cfg_key)
        files = sorted(glob(os.path.join(config_dir, "*.json")))
        files = [f for f in files if "_summary" not in os.path.basename(f)]

        # From iterations
        iter_dist: Counter = Counter()
        n = 0
        n_resolved = 0
        sum_iters = 0

        # From verdicts (BB/Hybrid only)
        n_explicit_accept = 0
        n_explicit_reject = 0
        accept_at: Counter = Counter()   # which iteration first accepted
        reject_only_runs = 0
        runs_with_review = 0
        per_run_verdicts: list[list[str]] = []

        for fpath in files:
            with open(fpath, encoding="utf-8") as f:
                r = json.load(f)
            n += 1
            it = int(r.get("iterations", 0) or 0)
            sum_iters += it
            iter_dist[it] += 1
            if r.get("resolved"):
                n_resolved += 1

            bb = r.get("blackboard_final_state") or {}
            reviews = bb.get("reviews", []) if bb else []
            if reviews:
                runs_with_review += 1
                verdicts = [str(rv.get("verdict", "")).lower() for rv in reviews]
                per_run_verdicts.append(verdicts)
                accept_idx = None
                for i, v in enumerate(verdicts, 1):
                    if "approve" in v or "accept" in v:
                        if accept_idx is None:
                            accept_idx = i
                        n_explicit_accept += 1
                    elif v:
                        n_explicit_reject += 1
                if accept_idx:
                    accept_at[accept_idx] += 1
                else:
                    reject_only_runs += 1

        out[label] = {
            "n_runs": n,
            "n_resolved": n_resolved,
            "mean_iterations": round(sum_iters / n, 3) if n else 0,
            "iteration_distribution": dict(sorted(iter_dist.items())),
            "verdict_data_available_runs": runs_with_review,
            "n_explicit_accept_verdicts": n_explicit_accept,
            "n_explicit_reject_verdicts": n_explicit_reject,
            "first_accept_iteration_distribution": dict(sorted(accept_at.items())),
            "runs_no_accept_ever": reject_only_runs,
        }

    out_dir = os.path.join(ROOT, "data", "analysis", "revision")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "b4_reviewer.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    lines = ["# B4: Reviewer Accept/Reject Dynamics", ""]
    lines.append("## Iteration distribution (terminates on first accept or max=3)")
    lines.append("| Config | N | Mean iters | iters=1 | iters=2 | iters=3 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for label in ("MP", "BB", "Hybrid"):
        d = out[label]
        i1 = d["iteration_distribution"].get(1, 0)
        i2 = d["iteration_distribution"].get(2, 0)
        i3 = d["iteration_distribution"].get(3, 0)
        lines.append(
            f"| {label} | {d['n_runs']} | {d['mean_iterations']} | {i1} | {i2} | {i3} |"
        )

    lines.append("")
    lines.append("## Explicit Reviewer verdicts (BB and Hybrid only)")
    lines.append("| Config | Runs w/ verdicts | Accepts | Rejects | First-accept @1 | @2 | @3 | Never |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for label in ("MP", "BB", "Hybrid"):
        d = out[label]
        fa = d["first_accept_iteration_distribution"]
        lines.append(
            f"| {label} | {d['verdict_data_available_runs']} | "
            f"{d['n_explicit_accept_verdicts']} | {d['n_explicit_reject_verdicts']} | "
            f"{fa.get(1,0)} | {fa.get(2,0)} | {fa.get(3,0)} | {d['runs_no_accept_ever']} |"
        )

    md_path = os.path.join(out_dir, "b4_reviewer.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
