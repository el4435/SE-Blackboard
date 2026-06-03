"""B5: IFS variance per configuration.

Reviewer ask (R3#5): Report variance statistics for IFS at each stage and
configuration.

Outputs std, IQR, min, max alongside the means already reported in Table IV.
"""

from __future__ import annotations

import json
import os
from statistics import mean, stdev


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIGS = [
    ("sequential_message_passing", "MP"),
    ("sequential_blackboard", "BB"),
    ("sequential_hybrid", "Hybrid"),
]
STAGES = ["Planner", "Coder", "Reviewer", "Tester"]


def quartiles(xs: list[float]) -> tuple[float, float, float]:
    s = sorted(xs)
    n = len(s)

    def q(p: float) -> float:
        if n == 1:
            return s[0]
        idx = p * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return s[lo] * (1 - frac) + s[hi] * frac

    return q(0.25), q(0.5), q(0.75)


def main() -> None:
    ifs_path = os.path.join(ROOT, "data", "ifs", "ifs_results_real.json")
    with open(ifs_path, encoding="utf-8") as f:
        ifs_data = json.load(f)

    out: dict = {}
    for cfg_key, label in CONFIGS:
        per_issue = ifs_data.get(cfg_key, {})
        cfg_stats: dict = {}
        for stage in STAGES:
            values: list[float] = []
            for d in per_issue.values():
                v = d.get("stage_ifs", {}).get(stage)
                if v is not None:
                    values.append(float(v))
            if not values:
                cfg_stats[stage] = None
                continue
            q1, q2, q3 = quartiles(values)
            cfg_stats[stage] = {
                "n": len(values),
                "mean": round(mean(values), 4),
                "std": round(stdev(values), 4) if len(values) >= 2 else 0.0,
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "q1": round(q1, 4),
                "median": round(q2, 4),
                "q3": round(q3, 4),
                "iqr": round(q3 - q1, 4),
            }
        out[label] = cfg_stats

    out_dir = os.path.join(ROOT, "data", "analysis", "revision")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "b5_ifs_variance.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    lines = ["# B5: IFS Variance Per Configuration", ""]
    lines.append("| Config | Stage | N | Mean | Std | Median | IQR | Min | Max |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for label in ("MP", "BB", "Hybrid"):
        for stage in STAGES:
            d = out[label].get(stage)
            if not d:
                lines.append(f"| {label} | {stage} | - | N/A | - | - | - | - | - |")
                continue
            lines.append(
                f"| {label} | {stage} | {d['n']} | {d['mean']:.3f} | {d['std']:.3f} | "
                f"{d['median']:.3f} | {d['iqr']:.3f} | {d['min']:.3f} | {d['max']:.3f} |"
            )

    md_path = os.path.join(out_dir, "b5_ifs_variance.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
