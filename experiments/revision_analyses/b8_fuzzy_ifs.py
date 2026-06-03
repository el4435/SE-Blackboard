"""B8: IFS sensitivity to matcher choice (rule-based vs. fuzzy).

Reviewer ask (R2-major-2): Spot-check using fuzzy matching on a 15-20 issue
subset to verify IFS robustness.

Strategy: take a 20-issue stratified subset (mix of Django, sympy, other),
recompute Coder IFS for MP and BB using a fuzzy matcher built on stdlib
difflib.SequenceMatcher (no rapidfuzz dependency), then compare to the
existing rule-based values from data/ifs/ifs_results_real.json.

A higher fuzzy IFS implies the rule-based matcher undercounts entities;
similar values imply the 62%% Coder IFS gap is robust to fuzzy matching.

Inputs:
    - data/ifs/entities.json
    - data/ifs/ifs_results_real.json (existing rule-based numbers)
    - data/results/sequential_message_passing/<issue>.json (final_patch as Coder text)
    - data/results/sequential_blackboard/<issue>.json (blackboard_final_state -> Coder text)

Outputs:
    - data/analysis/revision/b8_fuzzy_ifs.json
    - data/analysis/revision/b8_fuzzy_ifs.md
"""

from __future__ import annotations

import difflib
import json
import os
import re
import sys
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.evaluation.ifs import detect_entities, extract_agent_outputs


SUBSET = [
    # Django (10)
    "django__django-11179",
    "django__django-12700",
    "django__django-12908",
    "django__django-12915",
    "django__django-13028",
    "django__django-13230",
    "django__django-13321",
    "django__django-14238",
    "django__django-15347",
    "django__django-16379",
    # sympy (5)
    "sympy__sympy-13895",
    "sympy__sympy-15345",
    "sympy__sympy-20049",
    "sympy__sympy-21171",
    "sympy__sympy-24213",
    # Other repos (5)
    "pytest-dev__pytest-11143",
    "sphinx-doc__sphinx-8713",
    "astropy__astropy-14182",
    "pallets__flask-4045",
    "pydata__xarray-3364",
]


def _normalize_for_fuzzy(text: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    text = re.sub(r"[_./\\:]+", " ", text)
    return re.sub(r"\s+", " ", text.lower()).strip()


def fuzzy_present(entity: str, output: str, threshold: float = 0.80) -> bool:
    e_norm = _normalize_for_fuzzy(entity)
    o_norm = _normalize_for_fuzzy(output)
    if not e_norm or not o_norm:
        return False
    if e_norm in o_norm:
        return True
    # Sliding-window similarity using SequenceMatcher
    e_len = len(e_norm)
    if e_len < 3:
        return False
    # Examine candidate windows of similar length around each token start
    best = 0.0
    o_tokens = o_norm.split()
    for i, _ in enumerate(o_tokens):
        # Window of 1..3 tokens
        for span in (1, 2, 3):
            if i + span > len(o_tokens):
                break
            cand = " ".join(o_tokens[i : i + span])
            if abs(len(cand) - e_len) > max(8, e_len * 0.5):
                continue
            ratio = difflib.SequenceMatcher(None, e_norm, cand).ratio()
            if ratio > best:
                best = ratio
                if best >= threshold:
                    return True
    return False


def compute_ifs_fuzzy(entities: list[str], output: str) -> float:
    if not entities:
        return 1.0
    hits = sum(1 for e in entities if fuzzy_present(e, output))
    return hits / len(entities)


def main() -> None:
    entities_path = os.path.join(ROOT, "data", "ifs", "entities.json")
    ifs_results_path = os.path.join(ROOT, "data", "ifs", "ifs_results_real.json")
    with open(entities_path, encoding="utf-8") as f:
        all_entities = json.load(f)
    with open(ifs_results_path, encoding="utf-8") as f:
        rule_based = json.load(f)

    per_issue = []
    for iid in SUBSET:
        ents = all_entities.get(iid, [])
        if not ents:
            continue
        row = {"issue_id": iid, "n_entities": len(ents)}
        for cfg_key, label in (
            ("sequential_message_passing", "MP"),
            ("sequential_blackboard", "BB"),
        ):
            result_path = os.path.join(ROOT, "data", "results", cfg_key, f"{iid}.json")
            if not os.path.exists(result_path):
                row[f"{label}_rule"] = None
                row[f"{label}_fuzzy"] = None
                continue
            with open(result_path, encoding="utf-8") as f:
                r = json.load(f)
            outputs = extract_agent_outputs(r)
            coder_text = outputs.get("Coder", "") or ""
            # Rule-based: from ifs_results_real.json if available
            rb = rule_based.get(cfg_key, {}).get(iid, {}).get("stage_ifs", {}).get("Coder")
            row[f"{label}_rule"] = round(rb, 4) if rb is not None else None
            row[f"{label}_fuzzy"] = round(compute_ifs_fuzzy(ents, coder_text), 4)
        per_issue.append(row)

    # Aggregate
    def mean_safe(xs):
        xs = [x for x in xs if x is not None]
        return round(mean(xs), 4) if xs else None

    summary = {
        "subset_size": len(per_issue),
        "MP_rule_mean": mean_safe([r.get("MP_rule") for r in per_issue]),
        "MP_fuzzy_mean": mean_safe([r.get("MP_fuzzy") for r in per_issue]),
        "BB_rule_mean": mean_safe([r.get("BB_rule") for r in per_issue]),
        "BB_fuzzy_mean": mean_safe([r.get("BB_fuzzy") for r in per_issue]),
        "delta_fuzzy_minus_rule_MP": (
            round(mean_safe([r.get("MP_fuzzy") for r in per_issue]) - mean_safe([r.get("MP_rule") for r in per_issue]), 4)
            if mean_safe([r.get("MP_fuzzy") for r in per_issue]) is not None
            and mean_safe([r.get("MP_rule") for r in per_issue]) is not None
            else None
        ),
        "delta_fuzzy_minus_rule_BB": (
            round(mean_safe([r.get("BB_fuzzy") for r in per_issue]) - mean_safe([r.get("BB_rule") for r in per_issue]), 4)
            if mean_safe([r.get("BB_fuzzy") for r in per_issue]) is not None
            and mean_safe([r.get("BB_rule") for r in per_issue]) is not None
            else None
        ),
    }
    # Relative gap BB vs MP under each scheme
    if summary["MP_rule_mean"] and summary["BB_rule_mean"]:
        summary["bb_over_mp_rule_relative"] = round(
            summary["BB_rule_mean"] / summary["MP_rule_mean"] - 1, 4
        )
    if summary["MP_fuzzy_mean"] and summary["BB_fuzzy_mean"]:
        summary["bb_over_mp_fuzzy_relative"] = round(
            summary["BB_fuzzy_mean"] / summary["MP_fuzzy_mean"] - 1, 4
        )

    out_dir = os.path.join(ROOT, "data", "analysis", "revision")
    os.makedirs(out_dir, exist_ok=True)
    out_json = os.path.join(out_dir, "b8_fuzzy_ifs.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"per_issue": per_issue, "summary": summary}, f, indent=2, ensure_ascii=False)

    lines = ["# B8: IFS Sensitivity to Matcher Choice", ""]
    lines.append(f"Subset size: {summary['subset_size']} issues")
    lines.append("")
    lines.append("| Matcher | MP mean | BB mean | BB - MP (rel.) |")
    lines.append("|---|---:|---:|---:|")
    rule_rel = summary.get("bb_over_mp_rule_relative")
    fuzzy_rel = summary.get("bb_over_mp_fuzzy_relative")
    lines.append(
        f"| Rule-based | {summary['MP_rule_mean']} | {summary['BB_rule_mean']} | "
        f"{rule_rel*100:.1f}% |" if rule_rel is not None else "| Rule-based | - | - | - |"
    )
    lines.append(
        f"| Fuzzy (difflib >= 0.80) | {summary['MP_fuzzy_mean']} | {summary['BB_fuzzy_mean']} | "
        f"{fuzzy_rel*100:.1f}% |" if fuzzy_rel is not None else "| Fuzzy | - | - | - |"
    )
    lines.append("")
    lines.append(
        f"Fuzzy minus rule-based delta: MP {summary.get('delta_fuzzy_minus_rule_MP')}, "
        f"BB {summary.get('delta_fuzzy_minus_rule_BB')}."
    )

    out_md = os.path.join(out_dir, "b8_fuzzy_ifs.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
