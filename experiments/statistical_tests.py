"""Day 6 — Statistical tests for SE-Blackboard paper.

Performs:
  a) McNemar's Test (paired binary comparison of resolve rates)
  b) Cohen's h (effect size for proportions)
  c) Wilcoxon Signed-Rank (token cost & latency comparisons)
  d) IFS comparison (paired t-test & Wilcoxon)
  e) Odds Ratio with 95% CI

Saves all results to data/analysis/statistical_tests.json.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binomtest, wilcoxon, ttest_rel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── helpers ──────────────────────────────────────────────────────────

def load_results(config_dir: str) -> list[dict]:
    """Load all per-issue result JSONs from a config directory."""
    results = []
    for f in sorted(os.listdir(config_dir)):
        if f.endswith(".json") and "_summary" not in f:
            data = json.loads(Path(config_dir, f).read_text(encoding="utf-8"))
            results.append(data)
    return results


def mcnemar_exact(a_resolved: list[bool], b_resolved: list[bool]):
    """Exact McNemar's test using binomial test."""
    a = sum(1 for x, y in zip(a_resolved, b_resolved) if x and y)
    b = sum(1 for x, y in zip(a_resolved, b_resolved) if x and not y)
    c = sum(1 for x, y in zip(a_resolved, b_resolved) if not x and y)
    d = sum(1 for x, y in zip(a_resolved, b_resolved) if not x and not y)

    if b + c == 0:
        return {"a": a, "b": b, "c": c, "d": d, "p_value": 1.0, "significant": False}

    result = binomtest(b, b + c, 0.5)
    p = result.pvalue
    return {"a": a, "b": b, "c": c, "d": d, "p_value": p, "significant": p < 0.05}


def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h for comparing two proportions."""
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))


def odds_ratio_ci(n_success_a: int, n_total_a: int,
                  n_success_b: int, n_total_b: int):
    """Odds ratio with 95% CI (log transform)."""
    n_fail_a = n_total_a - n_success_a
    n_fail_b = n_total_b - n_success_b
    odds_a = n_success_a / max(n_fail_a, 1)
    odds_b = n_success_b / max(n_fail_b, 1)
    or_val = odds_a / max(odds_b, 1e-10)
    log_or = math.log(or_val)
    se = math.sqrt(1 / max(n_success_a, 1) + 1 / max(n_fail_a, 1) +
                   1 / max(n_success_b, 1) + 1 / max(n_fail_b, 1))
    ci_lower = math.exp(log_or - 1.96 * se)
    ci_upper = math.exp(log_or + 1.96 * se)
    return {"odds_ratio": round(or_val, 4),
            "ci_95_lower": round(ci_lower, 4),
            "ci_95_upper": round(ci_upper, 4),
            "log_or": round(log_or, 4),
            "se": round(se, 4)}


# ── main ─────────────────────────────────────────────────────────────

def main():
    data_root = PROJECT_ROOT / "data"
    results_root = data_root / "results"

    # 1. Load results
    mp_results = load_results(str(results_root / "sequential_message_passing"))
    bb_results = load_results(str(results_root / "sequential_blackboard"))
    hy_results = load_results(str(results_root / "sequential_hybrid"))

    # Build issue-aligned arrays (sorted by issue_id)
    mp_by_id = {r["issue_id"]: r for r in mp_results}
    bb_by_id = {r["issue_id"]: r for r in bb_results}
    hy_by_id = {r["issue_id"]: r for r in hy_results}
    issues = sorted(set(mp_by_id) & set(bb_by_id) & set(hy_by_id))

    mp_resolved = [mp_by_id[i].get("resolved", False) for i in issues]
    bb_resolved = [bb_by_id[i].get("resolved", False) for i in issues]
    hy_resolved = [hy_by_id[i].get("resolved", False) for i in issues]

    mp_tokens = [mp_by_id[i].get("total_input_tokens", 0) + mp_by_id[i].get("total_output_tokens", 0) for i in issues]
    bb_tokens = [bb_by_id[i].get("total_input_tokens", 0) + bb_by_id[i].get("total_output_tokens", 0) for i in issues]
    hy_tokens = [hy_by_id[i].get("total_input_tokens", 0) + hy_by_id[i].get("total_output_tokens", 0) for i in issues]

    mp_latency = [mp_by_id[i].get("total_latency_ms", 0) for i in issues]
    bb_latency = [bb_by_id[i].get("total_latency_ms", 0) for i in issues]
    hy_latency = [hy_by_id[i].get("total_latency_ms", 0) for i in issues]

    n = len(issues)
    n_mp = sum(mp_resolved)
    n_bb = sum(bb_resolved)
    n_hy = sum(hy_resolved)

    output = {"n_issues": n, "resolved": {"MP": n_mp, "BB": n_bb, "Hybrid": n_hy}}

    # ── a) McNemar's Test ────────────────────────────────────────────
    print("=" * 70)
    print("McNemar's Test Results (Exact Binomial)")
    print("=" * 70)

    pairs = [("MP vs BB", mp_resolved, bb_resolved),
             ("MP vs Hybrid", mp_resolved, hy_resolved),
             ("BB vs Hybrid", bb_resolved, hy_resolved)]

    mcnemar_results = {}
    for name, a, b in pairs:
        res = mcnemar_exact(a, b)
        mcnemar_results[name] = res
        sig = "Yes" if res["significant"] else "No"
        print(f"  {name:15s}  a={res['a']} b={res['b']} c={res['c']} d={res['d']}  "
              f"p={res['p_value']:.4f}  Significant(a=0.05)? {sig}")

    output["mcnemar"] = mcnemar_results

    # ── b) Cohen's h ─────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("Effect Size — Cohen's h")
    print("=" * 70)

    p_mp, p_bb, p_hy = n_mp / n, n_bb / n, n_hy / n
    h_mp_bb = cohens_h(p_bb, p_mp)
    h_mp_hy = cohens_h(p_hy, p_mp)
    h_bb_hy = cohens_h(p_bb, p_hy)

    def h_label(h):
        ah = abs(h)
        if ah < 0.2:
            return "negligible"
        if ah < 0.5:
            return "small"
        if ah < 0.8:
            return "medium"
        return "large"

    cohens_results = {
        "MP_vs_BB": {"h": round(h_mp_bb, 4), "interpretation": h_label(h_mp_bb)},
        "MP_vs_Hybrid": {"h": round(h_mp_hy, 4), "interpretation": h_label(h_mp_hy)},
        "BB_vs_Hybrid": {"h": round(h_bb_hy, 4), "interpretation": h_label(h_bb_hy)},
    }
    output["cohens_h"] = cohens_results

    for name, data in cohens_results.items():
        print(f"  {name:15s}  h={data['h']:.4f}  ({data['interpretation']})")

    # ── c) Wilcoxon Signed-Rank — Token & Latency ────────────────────
    print()
    print("=" * 70)
    print("Wilcoxon Signed-Rank Test (Token Cost & Latency)")
    print("=" * 70)

    wilcoxon_results = {}
    wilcoxon_pairs = [
        ("MP_vs_BB_tokens", mp_tokens, bb_tokens),
        ("MP_vs_Hybrid_tokens", mp_tokens, hy_tokens),
        ("BB_vs_Hybrid_tokens", bb_tokens, hy_tokens),
        ("MP_vs_BB_latency", mp_latency, bb_latency),
        ("MP_vs_Hybrid_latency", mp_latency, hy_latency),
        ("BB_vs_Hybrid_latency", bb_latency, hy_latency),
    ]

    for name, a_vals, b_vals in wilcoxon_pairs:
        diffs = [b - a for a, b in zip(a_vals, b_vals)]
        if all(d == 0 for d in diffs):
            wilcoxon_results[name] = {"statistic": None, "p_value": 1.0, "significant": False}
            print(f"  {name:30s}  (all diffs=0, skipped)")
            continue
        stat, p = wilcoxon(a_vals, b_vals)
        sig = p < 0.05
        wilcoxon_results[name] = {"statistic": float(stat), "p_value": float(p), "significant": sig}
        mean_a = np.mean(a_vals)
        mean_b = np.mean(b_vals)
        print(f"  {name:30s}  W={stat:.0f}  p={p:.6f}  "
              f"{'***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.'}  "
              f"(mean: {mean_a:.0f} vs {mean_b:.0f})")

    output["wilcoxon"] = wilcoxon_results

    # ── d) IFS Comparison ────────────────────────────────────────────
    print()
    print("=" * 70)
    print("IFS Comparison (Paired t-test & Wilcoxon)")
    print("=" * 70)

    ifs_data = json.loads((data_root / "ifs" / "ifs_results.json").read_text(encoding="utf-8"))

    ifs_results = {}
    config_map = {
        "MP": "sequential_message_passing",
        "BB": "sequential_blackboard",
        "Hybrid": "sequential_hybrid",
    }

    # Extract per-issue Coder IFS for each config
    coder_ifs = {}
    for label, config_key in config_map.items():
        config_data = ifs_data.get(config_key, {})
        per_issue = {}
        for iid, issue_data in config_data.items():
            if isinstance(issue_data, dict) and "stage_ifs" in issue_data:
                val = issue_data["stage_ifs"].get("Coder")
                if val is not None and isinstance(val, (int, float)):
                    per_issue[iid] = val
        coder_ifs[label] = per_issue

    # Paired comparison for Coder IFS
    common_issues_ifs = sorted(
        set(coder_ifs["MP"]) & set(coder_ifs["BB"]) & set(coder_ifs["Hybrid"])
    )
    n_ifs = len(common_issues_ifs)

    mp_cifs = [coder_ifs["MP"][i] for i in common_issues_ifs]
    bb_cifs = [coder_ifs["BB"][i] for i in common_issues_ifs]
    hy_cifs = [coder_ifs["Hybrid"][i] for i in common_issues_ifs]

    ifs_pairs = [
        ("MP_vs_BB_coder_ifs", mp_cifs, bb_cifs),
        ("MP_vs_Hybrid_coder_ifs", mp_cifs, hy_cifs),
        ("BB_vs_Hybrid_coder_ifs", bb_cifs, hy_cifs),
    ]

    for name, a_vals, b_vals in ifs_pairs:
        diffs = [b - a for a, b in zip(a_vals, b_vals)]
        nonzero = [d for d in diffs if d != 0]
        if len(nonzero) < 2:
            ifs_results[name] = {"t_stat": None, "t_p": None, "w_stat": None, "w_p": None,
                                 "n": n_ifs, "mean_a": float(np.mean(a_vals)),
                                 "mean_b": float(np.mean(b_vals))}
            print(f"  {name:30s}  Too few non-zero diffs ({len(nonzero)})")
            continue

        t_stat, t_p = ttest_rel(a_vals, b_vals)
        w_stat, w_p = wilcoxon(a_vals, b_vals)

        ifs_results[name] = {
            "t_stat": float(t_stat), "t_p": float(t_p),
            "w_stat": float(w_stat), "w_p": float(w_p),
            "n": n_ifs,
            "mean_a": round(float(np.mean(a_vals)), 4),
            "mean_b": round(float(np.mean(b_vals)), 4),
            "significant_ttest": t_p < 0.05,
            "significant_wilcoxon": w_p < 0.05,
        }
        print(f"  {name:30s}  n={n_ifs}  "
              f"means: {np.mean(a_vals):.4f} vs {np.mean(b_vals):.4f}  "
              f"t={t_stat:.3f} p={t_p:.4f}{'*' if t_p < 0.05 else ''}  "
              f"W={w_stat:.0f} p={w_p:.4f}{'*' if w_p < 0.05 else ''}")

    output["ifs_comparison"] = ifs_results

    # ── e) Odds Ratio ────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("Odds Ratio (BB vs MP)")
    print("=" * 70)

    or_bb_mp = odds_ratio_ci(n_bb, n, n_mp, n)
    or_hy_mp = odds_ratio_ci(n_hy, n, n_mp, n)
    or_bb_hy = odds_ratio_ci(n_bb, n, n_hy, n)

    odds_results = {
        "BB_vs_MP": or_bb_mp,
        "Hybrid_vs_MP": or_hy_mp,
        "BB_vs_Hybrid": or_bb_hy,
    }
    output["odds_ratio"] = odds_results

    for name, data in odds_results.items():
        print(f"  {name:15s}  OR={data['odds_ratio']:.4f}  "
              f"95%CI=[{data['ci_95_lower']:.4f}, {data['ci_95_upper']:.4f}]")

    # ── Summary ──────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  N issues: {n}")
    print(f"  Resolved: MP={n_mp}/{n} ({100*p_mp:.1f}%), "
          f"BB={n_bb}/{n} ({100*p_bb:.1f}%), "
          f"Hybrid={n_hy}/{n} ({100*p_hy:.1f}%)")
    print()
    print("  McNemar MP vs BB:  p={:.4f} ({})".format(
        mcnemar_results["MP vs BB"]["p_value"],
        "significant" if mcnemar_results["MP vs BB"]["significant"] else "NOT significant"))
    print("  Cohen's h (BB vs MP): {:.4f} ({})".format(
        cohens_results["MP_vs_BB"]["h"], cohens_results["MP_vs_BB"]["interpretation"]))
    print("  Odds Ratio (BB vs MP): {:.4f} [95%CI: {:.4f}-{:.4f}]".format(
        or_bb_mp["odds_ratio"], or_bb_mp["ci_95_lower"], or_bb_mp["ci_95_upper"]))
    print()
    ifs_mp_bb = ifs_results.get("MP_vs_BB_coder_ifs", {})
    mean_a = ifs_mp_bb.get("mean_a") or 0
    mean_b = ifs_mp_bb.get("mean_b") or 0
    w_p = ifs_mp_bb.get("w_p") or 1.0
    print(f"  IFS Coder (MP vs BB): means {mean_a:.4f} vs {mean_b:.4f}, Wilcoxon p={w_p:.4f}")
    print()
    print("  Token cost (Wilcoxon MP vs BB): p={:.6f}".format(
        wilcoxon_results["MP_vs_BB_tokens"]["p_value"]))
    print("  Latency (Wilcoxon MP vs BB): p={:.6f}".format(
        wilcoxon_results["MP_vs_BB_latency"]["p_value"]))

    # ── Save ─────────────────────────────────────────────────────────
    out_path = data_root / "analysis" / "statistical_tests.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\n  Saved to {out_path}")


if __name__ == "__main__":
    main()
