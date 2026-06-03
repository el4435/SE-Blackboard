"""B2: Per-repository IFS and file-targeting breakdown.

Reviewer asks (R1-gap-1, R2-major-1): Is BB's IFS advantage pervasive across
repositories, or is it driven by Django overrepresentation?

Inputs:
    - data/ifs/ifs_results_real.json  (per-issue Coder/Planner/Reviewer/Tester IFS)
    - data/results/sequential_*/<issue>.json  (final_patch -> file targeting)
    - data/selected_issues.json  (gold patch -> correct files)

Outputs:
    - data/analysis/revision/b2_per_repo.json
    - data/analysis/revision/b2_per_repo.md
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from statistics import mean, stdev

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

CONFIGS = [
    ("sequential_message_passing", "MP"),
    ("sequential_blackboard", "BB"),
    ("sequential_hybrid", "Hybrid"),
]


def repo_of(issue_id: str) -> str:
    return issue_id.split("__")[0]


def files_in_patch(patch: str) -> set[str]:
    files: set[str] = set()
    for m in re.finditer(r"^(?:---|\+\+\+)\s+[ab]/(\S+)", patch, re.M):
        path = m.group(1)
        if path != "/dev/null":
            files.add(path)
    return files


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    ifs_path = os.path.join(ROOT, "data", "ifs", "ifs_results_real.json")
    issues_path = os.path.join(ROOT, "data", "selected_issues.json")
    results_dir = os.path.join(ROOT, "data", "results")
    out_dir = os.path.join(ROOT, "data", "analysis", "revision")
    os.makedirs(out_dir, exist_ok=True)

    ifs_data = load_json(ifs_path)
    issues = load_json(issues_path)
    gold_files: dict[str, set[str]] = {}
    for issue in issues:
        iid = issue["instance_id"]
        gold_files[iid] = files_in_patch(issue.get("patch", ""))

    # Aggregate per repo, per config: Coder IFS, file-targeting (non-empty-only)
    repo_stats: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {
        "n_total": 0,
        "n_resolved": 0,
        "coder_ifs": [],
        "n_nonempty": 0,
        "n_correct_file": 0,
    }))

    for cfg_key, label in CONFIGS:
        per_issue = ifs_data.get(cfg_key, {})
        for iid, d in per_issue.items():
            repo = repo_of(iid)
            s = repo_stats[repo][label]
            s["n_total"] += 1
            if d.get("resolved"):
                s["n_resolved"] += 1
            coder = d.get("stage_ifs", {}).get("Coder")
            if coder is not None:
                s["coder_ifs"].append(coder)

            # File targeting
            result_path = os.path.join(results_dir, cfg_key, f"{iid}.json")
            if not os.path.exists(result_path):
                continue
            r = load_json(result_path)
            patch = r.get("final_patch", "")
            if patch.strip():
                s["n_nonempty"] += 1
                modified = files_in_patch(patch)
                gold = gold_files.get(iid, set())
                if gold and (modified & gold):
                    s["n_correct_file"] += 1

    # Format output
    output = {}
    for repo in sorted(repo_stats.keys()):
        repo_out = {}
        for label in ("MP", "BB", "Hybrid"):
            s = repo_stats[repo].get(label)
            if not s or s["n_total"] == 0:
                continue
            coder_ifs_list = s["coder_ifs"]
            repo_out[label] = {
                "n_issues": s["n_total"],
                "resolved": s["n_resolved"],
                "resolve_rate": round(s["n_resolved"] / s["n_total"], 4),
                "coder_ifs_mean": round(mean(coder_ifs_list), 4) if coder_ifs_list else None,
                "coder_ifs_n": len(coder_ifs_list),
                "nonempty": s["n_nonempty"],
                "correct_file": s["n_correct_file"],
                "file_targeting_rate": (
                    round(s["n_correct_file"] / s["n_nonempty"], 4)
                    if s["n_nonempty"]
                    else None
                ),
            }
        output[repo] = repo_out

    out_json = os.path.join(out_dir, "b2_per_repo.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Markdown summary table
    lines = ["# B2: Per-Repository IFS and File-Targeting Breakdown", ""]
    lines.append("| Repo | Config | N | Resolve | Coder IFS (n) | File targeting |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for repo in sorted(output):
        for label in ("MP", "BB", "Hybrid"):
            d = output[repo].get(label)
            if not d:
                continue
            ifs_str = (
                f"{d['coder_ifs_mean']:.3f} ({d['coder_ifs_n']})"
                if d["coder_ifs_mean"] is not None
                else "-"
            )
            ft_str = (
                f"{d['file_targeting_rate']*100:.1f}% ({d['correct_file']}/{d['nonempty']})"
                if d["file_targeting_rate"] is not None
                else "-"
            )
            lines.append(
                f"| {repo} | {label} | {d['n_issues']} | {d['resolved']}/{d['n_issues']} | {ifs_str} | {ft_str} |"
            )

    out_md = os.path.join(out_dir, "b2_per_repo.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
