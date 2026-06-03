"""B3: Hybrid empty-patch deep dive.

Reviewer asks (R1-gap-2, R2-major-3, R3#6): Concretely characterize the 18
Hybrid runs that produced empty final_patch. Categorize the failure mode
(no Coder output, partial diff in intermediate patches[], hallucinated file
path, etc.) and report context-length statistics.

Inputs:
    - data/results/sequential_hybrid/*.json (final_patch, blackboard_final_state)

Outputs:
    - data/analysis/revision/b3_empty_patch_cases.json
    - data/analysis/revision/b3_empty_patch_cases.md
"""

from __future__ import annotations

import json
import os
import re
from glob import glob
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def files_in_patch(patch: str) -> set[str]:
    files: set[str] = set()
    for m in re.finditer(r"^(?:---|\+\+\+)\s+[ab]/(\S+)", patch, re.M):
        if m.group(1) != "/dev/null":
            files.add(m.group(1))
    return files


def main() -> None:
    hybrid_dir = os.path.join(ROOT, "data", "results", "sequential_hybrid")
    bb_dir = os.path.join(ROOT, "data", "results", "sequential_blackboard")
    mp_dir = os.path.join(ROOT, "data", "results", "sequential_message_passing")
    files = sorted(glob(os.path.join(hybrid_dir, "*.json")))
    files = [f for f in files if "_summary" not in os.path.basename(f)]

    cases: list[dict] = []
    all_input_tokens_empty: list[int] = []
    all_input_tokens_nonempty: list[int] = []

    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            r = json.load(f)
        iid = r.get("issue_id", os.path.basename(fpath).replace(".json", ""))
        patch = r.get("final_patch", "") or ""
        coder_input_tokens = 0
        for trace in r.get("agent_traces", []):
            if trace.get("agent_role") == "Coder":
                coder_input_tokens = max(coder_input_tokens, int(trace.get("input_tokens", 0)))

        if patch.strip():
            all_input_tokens_nonempty.append(coder_input_tokens)
            continue

        all_input_tokens_empty.append(coder_input_tokens)
        bb = r.get("blackboard_final_state") or {}
        patches = bb.get("patches", []) if bb else []
        reviews = bb.get("reviews", []) if bb else []

        # Categorize
        category = "unknown"
        notes = ""
        if not patches:
            category = "no_coder_output"
            notes = "blackboard_final_state.patches is empty: the Coder never produced a patch object."
        else:
            # Inspect the latest patch
            last = patches[-1]
            diff = last.get("diff", "") or ""
            if not diff.strip():
                category = "blank_diff"
                notes = "Coder emitted a patch object but the diff body is empty."
            elif len(diff) < 80:
                category = "stub_diff"
                notes = f"Coder emitted a very short stub diff ({len(diff)} chars)."
            elif "---" not in diff and "+++" not in diff:
                category = "no_diff_headers"
                notes = "Output is non-empty but lacks unified-diff headers (likely commentary)."
            else:
                category = "diff_present_but_lost_after_review"
                # If reviews rejected and the patch was discarded, final_patch ends empty
                rejected = sum(1 for rv in reviews if "reject" in str(rv.get("verdict","")).lower())
                notes = f"Patches present but final_patch is empty; reject verdicts={rejected}."

        cases.append({
            "issue_id": iid,
            "iterations": r.get("iterations"),
            "resolved": r.get("resolved"),
            "coder_input_tokens": coder_input_tokens,
            "n_patch_versions": len(patches),
            "n_reviews": len(reviews),
            "category": category,
            "notes": notes,
        })

    # Compare with the same issue under BB / MP for context
    bb_resolved_for_same: dict[str, bool] = {}
    mp_resolved_for_same: dict[str, bool] = {}
    for c in cases:
        iid = c["issue_id"]
        for d, store in ((bb_dir, bb_resolved_for_same), (mp_dir, mp_resolved_for_same)):
            p = os.path.join(d, f"{iid}.json")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    rr = json.load(f)
                store[iid] = bool(rr.get("resolved"))

    cat_counter: dict[str, int] = {}
    for c in cases:
        cat_counter[c["category"]] = cat_counter.get(c["category"], 0) + 1

    summary = {
        "n_empty_patch_hybrid_runs": len(cases),
        "category_distribution": cat_counter,
        "coder_input_tokens_mean_empty": (
            round(mean(all_input_tokens_empty), 1) if all_input_tokens_empty else 0
        ),
        "coder_input_tokens_mean_nonempty": (
            round(mean(all_input_tokens_nonempty), 1) if all_input_tokens_nonempty else 0
        ),
        "context_overhead_ratio": (
            round(
                mean(all_input_tokens_empty) / mean(all_input_tokens_nonempty), 3
            )
            if all_input_tokens_empty and all_input_tokens_nonempty
            else None
        ),
        "cases": cases,
        "comparison_resolved_same_issue": {
            "bb": bb_resolved_for_same,
            "mp": mp_resolved_for_same,
        },
    }

    out_dir = os.path.join(ROOT, "data", "analysis", "revision")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "b3_empty_patch_cases.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    lines = ["# B3: Hybrid Empty-Patch Deep Dive", ""]
    lines.append(f"Total Hybrid runs with empty final_patch: **{summary['n_empty_patch_hybrid_runs']}**")
    lines.append("")
    lines.append("## Category breakdown")
    for cat, cnt in sorted(cat_counter.items(), key=lambda x: -x[1]):
        lines.append(f"- **{cat}**: {cnt}")
    lines.append("")
    lines.append("## Coder input-token context length")
    lines.append(f"- Mean Coder input tokens in empty-patch runs: **{summary['coder_input_tokens_mean_empty']:,.0f}**")
    lines.append(f"- Mean Coder input tokens in non-empty runs: **{summary['coder_input_tokens_mean_nonempty']:,.0f}**")
    if summary["context_overhead_ratio"]:
        lines.append(f"- Empty-run context is {summary['context_overhead_ratio']:.2f}x non-empty-run context")
    lines.append("")
    lines.append("## Per-case detail")
    lines.append("| Issue | Iter | nPatches | nReviews | Coder in-tokens | Category | BB-resolved? | MP-resolved? |")
    lines.append("|---|---:|---:|---:|---:|---|---|---|")
    for c in cases:
        iid = c["issue_id"]
        bbr = bb_resolved_for_same.get(iid)
        mpr = mp_resolved_for_same.get(iid)
        lines.append(
            f"| {iid} | {c['iterations']} | {c['n_patch_versions']} | {c['n_reviews']} | "
            f"{c['coder_input_tokens']:,} | {c['category']} | "
            f"{'yes' if bbr else 'no' if bbr is False else '-'} | "
            f"{'yes' if mpr else 'no' if mpr is False else '-'} |"
        )

    md_path = os.path.join(out_dir, "b3_empty_patch_cases.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
