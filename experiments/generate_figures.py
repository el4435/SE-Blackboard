"""Day 6 — Generate paper figures for SE-Blackboard.

Generates Figures 1-7 as PDF and PNG.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
FIGURES_DIR = PROJECT_ROOT / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

# ── Style ────────────────────────────────────────────────────────────
matplotlib.rcParams["font.family"] = "serif"
matplotlib.rcParams["font.size"] = 11
matplotlib.rcParams["axes.labelsize"] = 12
matplotlib.rcParams["axes.titlesize"] = 13
matplotlib.rcParams["figure.dpi"] = 300
sns.set_style("whitegrid")

COLORS = {
    "mp": "#E74C3C",
    "bb": "#2ECC71",
    "hybrid": "#3498DB",
}
LABELS = {
    "mp": "Message\nPassing",
    "bb": "Blackboard",
    "hybrid": "Hybrid",
}
LEGEND_LABELS = {
    "mp": "Message Passing",
    "bb": "Blackboard",
    "hybrid": "Hybrid",
}


# ── Data Loading ─────────────────────────────────────────────────────

def load_results(config_dir: str) -> list[dict]:
    results = []
    for f in sorted(os.listdir(config_dir)):
        if f.endswith(".json") and "_summary" not in f:
            data = json.loads(Path(config_dir, f).read_text(encoding="utf-8"))
            results.append(data)
    return results


def wilson_ci(p: float, n: int, z: float = 1.96):
    """Wilson score interval for binomial proportion."""
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return max(0, center - margin), min(1, center + margin)


data_root = PROJECT_ROOT / "data"
results_root = data_root / "results"

mp_results = load_results(str(results_root / "sequential_message_passing"))
bb_results = load_results(str(results_root / "sequential_blackboard"))
hy_results = load_results(str(results_root / "sequential_hybrid"))

mp_by_id = {r["issue_id"]: r for r in mp_results}
bb_by_id = {r["issue_id"]: r for r in bb_results}
hy_by_id = {r["issue_id"]: r for r in hy_results}
all_issues = sorted(set(mp_by_id) & set(bb_by_id) & set(hy_by_id))

N = len(all_issues)
n_mp = sum(1 for i in all_issues if mp_by_id[i].get("resolved", False))
n_bb = sum(1 for i in all_issues if bb_by_id[i].get("resolved", False))
n_hy = sum(1 for i in all_issues if hy_by_id[i].get("resolved", False))


# ── Figure 1: Resolve Rate Bar Chart ────────────────────────────────

def fig1_resolve_rate():
    fig, ax = plt.subplots(figsize=(6, 4))

    configs = ["mp", "bb", "hybrid"]
    counts = [n_mp, n_bb, n_hy]
    rates = [c / N for c in counts]

    bars = ax.bar(range(3), [r * 100 for r in rates],
                  color=[COLORS[c] for c in configs],
                  width=0.6, edgecolor="white", linewidth=1.5)

    # Error bars (Wilson CI)
    for i, (c, rate) in enumerate(zip(configs, rates)):
        lo, hi = wilson_ci(rate, N)
        ax.errorbar(i, rate * 100, yerr=[[rate * 100 - lo * 100], [hi * 100 - rate * 100]],
                     fmt="none", color="black", capsize=5, linewidth=1.5)
        ax.text(i, rate * 100 + (hi - rate) * 100 + 1.5,
                f"{counts[i]}/{N}", ha="center", fontsize=11, fontweight="bold")

    ax.set_xticks(range(3))
    ax.set_xticklabels([LABELS[c] for c in configs])
    ax.set_ylabel("Resolve Rate (%)")
    ax.set_title("Resolve Rate by Communication Architecture\n(Sequential Pipeline, N=50)")
    ax.set_ylim(0, 30)
    ax.yaxis.set_major_locator(plt.MultipleLocator(5))

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig1_resolve_rate.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig1_resolve_rate.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("  Fig 1: Resolve Rate - DONE")


# ── Figure 2: Difficulty Breakdown ───────────────────────────────────

def fig2_difficulty_breakdown():
    """Group issues by repository as proxy for difficulty."""
    # Assign difficulty based on repo (from our data)
    difficulty_map = {}
    for iid in all_issues:
        repo = iid.split("__")[0]
        if repo in ("django", ):
            difficulty_map[iid] = "Easy"
        elif repo in ("pytest-dev", "pallets", "pydata"):
            difficulty_map[iid] = "Medium"
        else:  # sympy, sphinx, astropy, pylint
            difficulty_map[iid] = "Hard"

    fig, ax = plt.subplots(figsize=(7, 4))

    levels = ["Easy", "Medium", "Hard"]
    configs_list = ["mp", "bb", "hybrid"]
    by_id_map = {"mp": mp_by_id, "bb": bb_by_id, "hybrid": hy_by_id}

    x = np.arange(len(levels))
    width = 0.25

    for j, cfg in enumerate(configs_list):
        rates = []
        annotations = []
        for level in levels:
            issues_in_level = [i for i in all_issues if difficulty_map[i] == level]
            n_level = len(issues_in_level)
            n_resolved = sum(1 for i in issues_in_level if by_id_map[cfg][i].get("resolved", False))
            rate = n_resolved / n_level if n_level > 0 else 0
            rates.append(rate * 100)
            annotations.append(f"{n_resolved}/{n_level}")

        bars = ax.bar(x + j * width - width, rates, width,
                      label=LEGEND_LABELS[cfg], color=COLORS[cfg],
                      edgecolor="white", linewidth=1)
        for i, (bar, ann) in enumerate(zip(bars, annotations)):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    ann, ha="center", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(levels)
    ax.set_ylabel("Resolve Rate (%)")
    ax.set_xlabel("Difficulty Level (by Repository)")
    ax.set_title("Resolve Rate by Difficulty Level")
    ax.legend(loc="upper right")
    ax.set_ylim(0, 45)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig2_difficulty_breakdown.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig2_difficulty_breakdown.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("  Fig 2: Difficulty Breakdown - DONE")


# ── Figure 3: IFS Analysis (dual subplot) ───────────────────────────

def fig3_ifs_analysis():
    ifs_summary = json.loads((data_root / "ifs" / "ifs_summary_real.json").read_text(encoding="utf-8"))
    stage_ifs = ifs_summary["stage_average_ifs"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw={"width_ratios": [1, 1.3]})

    # Left panel: Coder stage comparison
    configs = ["mp", "bb", "hybrid"]
    labels_map = {"mp": "Seq-MP", "bb": "Seq-BB", "hybrid": "Seq-Hybrid"}
    coder_vals = [stage_ifs[labels_map[c]]["Coder"] for c in configs]

    bars = ax1.bar(range(3), coder_vals, color=[COLORS[c] for c in configs],
                   width=0.6, edgecolor="white", linewidth=1.5)
    for i, (bar, val) in enumerate(zip(bars, coder_vals)):
        ax1.text(bar.get_x() + bar.get_width() / 2, val + 0.02,
                 f"{val:.3f}", ha="center", fontsize=10)

    ax1.set_xticks(range(3))
    ax1.set_xticklabels([LABELS[c] for c in configs])
    ax1.set_ylabel("IFS (Coder Stage)")
    ax1.set_title("(a) Coder Stage IFS Comparison")
    ax1.set_ylim(0, 0.85)

    # Right panel: Full pipeline stages for BB and Hybrid
    stages = ["Planner", "Coder", "Reviewer", "Tester"]
    for cfg_label, color, marker in [("Seq-BB", COLORS["bb"], "o"),
                                      ("Seq-Hybrid", COLORS["hybrid"], "s")]:
        vals = []
        for stage in stages:
            v = stage_ifs[cfg_label].get(stage)
            vals.append(v if isinstance(v, (int, float)) else None)

        valid_stages = [i for i, v in enumerate(vals) if v is not None]
        valid_vals = [vals[i] for i in valid_stages]

        display_label = cfg_label.replace("Seq-", "")
        ax2.plot(valid_stages, valid_vals, marker=marker, color=color,
                 linewidth=2, markersize=8, label=display_label)

    # Add MP Coder point
    mp_coder = stage_ifs["Seq-MP"]["Coder"]
    ax2.scatter([1], [mp_coder], color=COLORS["mp"], s=100, zorder=5,
                marker="D", label="MP (Coder only)")

    ax2.set_xticks(range(4))
    ax2.set_xticklabels(stages)
    ax2.set_ylabel("Information Fidelity Score")
    ax2.set_title("(b) IFS Across Pipeline Stages")
    ax2.set_ylim(0, 1.0)
    ax2.legend(loc="upper right", fontsize=9)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig3_ifs_analysis.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig3_ifs_analysis.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("  Fig 3: IFS Analysis - DONE")


# ── Figure 4: Failure Mode Distribution ──────────────────────────────

def fig4_failure_analysis():
    failure_data = json.loads(
        (data_root / "analysis" / "failure_analysis.json").read_text(encoding="utf-8")
    )
    summaries = failure_data["summaries"]

    fig, ax = plt.subplots(figsize=(7, 4))

    configs = ["A-Seq(MP)", "B-Seq(BB)", "C-Seq(Hy)"]
    config_colors_map = ["mp", "bb", "hybrid"]
    categories = ["empty_patch", "patch_apply_error", "other"]
    cat_labels = ["Empty Patch", "Patch Apply Error", "Other"]
    cat_colors = ["#F39C12", "#E74C3C", "#95A5A6"]

    x = np.arange(len(configs))
    width = 0.6
    bottom = np.zeros(len(configs))

    for cat, cat_label, color in zip(categories, cat_labels, cat_colors):
        values = [summaries[c].get(cat, 0) for c in configs]
        ax.bar(x, values, width, bottom=bottom, label=cat_label, color=color,
               edgecolor="white", linewidth=1)
        # Annotate non-zero segments
        for i, v in enumerate(values):
            if v > 0:
                ax.text(i, bottom[i] + v / 2, str(v), ha="center", va="center",
                        fontsize=9, fontweight="bold", color="white")
        bottom += values

    # Add resolved count on top
    for i, cfg in enumerate(configs):
        res = summaries[cfg]["resolved"]
        total_fail = sum(summaries[cfg].get(cat, 0) for cat in categories)
        ax.text(i, total_fail + 1, f"Resolved: {res}", ha="center", fontsize=9,
                color="green", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(["Message\nPassing", "Blackboard", "Hybrid"])
    ax.set_ylabel("Number of Failed Issues")
    ax.set_title("Failure Mode Distribution by Communication Architecture")
    ax.legend(loc="upper right")
    ax.set_ylim(0, 55)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig4_failure_analysis.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig4_failure_analysis.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("  Fig 4: Failure Analysis - DONE")


# ── Figure 5: Cost-Efficiency ────────────────────────────────────────

def fig5_cost_efficiency():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    configs = ["mp", "bb", "hybrid"]
    avg_tokens = [25316, 54849, 43278]
    resolve_rates = [12.0, 16.0, 12.0]
    tokens_per_resolve = [
        25316 * 50 / max(n_mp, 1),
        54849 * 50 / max(n_bb, 1),
        43278 * 50 / max(n_hy, 1),
    ]

    # Left: scatter (avg tokens vs resolve rate)
    for cfg, tok, rate in zip(configs, avg_tokens, resolve_rates):
        ax1.scatter(tok / 1000, rate, s=200, color=COLORS[cfg], zorder=5,
                    edgecolors="black", linewidth=1)
        ax1.annotate(LEGEND_LABELS[cfg], (tok / 1000, rate),
                     textcoords="offset points", xytext=(10, 5), fontsize=9)

    ax1.set_xlabel("Avg Tokens per Issue (K)")
    ax1.set_ylabel("Resolve Rate (%)")
    ax1.set_title("(a) Tokens vs Resolve Rate")
    ax1.set_xlim(15, 65)
    ax1.set_ylim(8, 20)

    # Right: tokens per resolved issue
    bars = ax2.bar(range(3), [t / 1000 for t in tokens_per_resolve],
                   color=[COLORS[c] for c in configs],
                   width=0.6, edgecolor="white", linewidth=1.5)
    for i, (bar, val) in enumerate(zip(bars, tokens_per_resolve)):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                 f"{val / 1000:.0f}K", ha="center", fontsize=10, fontweight="bold")

    ax2.set_xticks(range(3))
    ax2.set_xticklabels([LABELS[c] for c in configs])
    ax2.set_ylabel("Tokens per Resolved Issue (K)")
    ax2.set_title("(b) Cost per Resolution")

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig5_cost_efficiency.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig5_cost_efficiency.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("  Fig 5: Cost Efficiency - DONE")


# ── Figure 6: Overlap Diagram ────────────────────────────────────────

def fig6_overlap():
    mp_set = {i for i in all_issues if mp_by_id[i].get("resolved", False)}
    bb_set = {i for i in all_issues if bb_by_id[i].get("resolved", False)}
    hy_set = {i for i in all_issues if hy_by_id[i].get("resolved", False)}

    try:
        from matplotlib_venn import venn3
        fig, ax = plt.subplots(figsize=(6, 5))
        v = venn3([mp_set, bb_set, hy_set],
                  set_labels=("Message Passing", "Blackboard", "Hybrid"),
                  set_colors=(COLORS["mp"], COLORS["bb"], COLORS["hybrid"]),
                  alpha=0.6, ax=ax)
        ax.set_title("Issue Resolution Overlap Across Communication Modes\n(N=50 issues)")
        plt.tight_layout()
        fig.savefig(FIGURES_DIR / "fig6_overlap.pdf", bbox_inches="tight")
        fig.savefig(FIGURES_DIR / "fig6_overlap.png", bbox_inches="tight", dpi=300)
        plt.close(fig)
    except ImportError:
        # Fallback: manual overlap table
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.axis("off")

        # Compute intersections
        all3 = mp_set & bb_set & hy_set
        mp_only = mp_set - bb_set - hy_set
        bb_only = bb_set - mp_set - hy_set
        hy_only = hy_set - mp_set - bb_set
        mp_bb = (mp_set & bb_set) - hy_set
        mp_hy = (mp_set & hy_set) - bb_set
        bb_hy = (bb_set & hy_set) - mp_set

        text = (
            f"All 3 configs: {len(all3)} issues\n"
            f"MP only: {len(mp_only)}\n"
            f"BB only: {len(bb_only)}\n"
            f"Hybrid only: {len(hy_only)}\n"
            f"MP+BB only: {len(mp_bb)}\n"
            f"MP+Hybrid only: {len(mp_hy)}\n"
            f"BB+Hybrid only: {len(bb_hy)}\n"
            f"\nTotal unique resolved: {len(mp_set | bb_set | hy_set)}/{N}"
        )
        ax.text(0.5, 0.5, text, transform=ax.transAxes, fontsize=12,
                ha="center", va="center", family="monospace")
        ax.set_title("Issue Resolution Overlap")
        plt.tight_layout()
        fig.savefig(FIGURES_DIR / "fig6_overlap.pdf", bbox_inches="tight")
        fig.savefig(FIGURES_DIR / "fig6_overlap.png", bbox_inches="tight", dpi=300)
        plt.close(fig)

    print("  Fig 6: Overlap - DONE")


# ── Figure 7: Case Study (django-13028) ─────────────────────────────

def fig7_case_study():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    def draw_pipeline(ax, title, stages, color, success):
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 6)
        ax.axis("off")
        ax.set_title(title, fontsize=13, fontweight="bold")

        y = 3.0
        box_w, box_h = 1.8, 0.8

        for i, (label, ifs_val, annotation) in enumerate(stages):
            x = 0.5 + i * 2.5
            fc = color if ifs_val else "#DDDDDD"
            alpha = 0.3 + 0.7 * (ifs_val or 0) if ifs_val else 0.3
            rect = mpatches.FancyBboxPatch(
                (x, y - box_h / 2), box_w, box_h,
                boxstyle="round,pad=0.1", facecolor=fc, alpha=alpha,
                edgecolor="black", linewidth=1.5
            )
            ax.add_patch(rect)
            ax.text(x + box_w / 2, y, label, ha="center", va="center",
                    fontsize=10, fontweight="bold")
            if ifs_val is not None:
                ax.text(x + box_w / 2, y - box_h / 2 - 0.3,
                        f"IFS={ifs_val:.2f}", ha="center", fontsize=8, color="gray")
            if annotation:
                ax.text(x + box_w / 2, y + box_h / 2 + 0.3,
                        annotation, ha="center", fontsize=8,
                        color="red" if "lost" in annotation.lower() else "green")

            if i < len(stages) - 1:
                ax.annotate("", xy=(x + box_w + 0.4, y), xytext=(x + box_w + 0.1, y),
                            arrowprops=dict(arrowstyle="->", color="black", lw=1.5))

        # Result marker
        marker_x = 0.5 + (len(stages) - 1) * 2.5 + box_w + 0.6
        if success:
            ax.text(marker_x, y, "RESOLVED", fontsize=12, color="green",
                    fontweight="bold", ha="left", va="center")
        else:
            ax.text(marker_x, y, "FAILED", fontsize=12, color="red",
                    fontweight="bold", ha="left", va="center")

    # MP failed on django-13028
    draw_pipeline(ax1, "Message Passing: django-13028",
                  [("Planner", None, ""),
                   ("Coder", 0.25, "Info lost"),
                   ("Reviewer", None, ""),
                   ("Tester", None, "")],
                  COLORS["mp"], False)

    # BB succeeded on django-13028
    draw_pipeline(ax2, "Blackboard: django-13028",
                  [("Planner", 0.75, ""),
                   ("Coder", 0.75, "Info preserved"),
                   ("Reviewer", 0.50, ""),
                   ("Tester", 0.25, "")],
                  COLORS["bb"], True)

    # Add blackboard annotation
    ax2.text(5, 0.8, "Blackboard: Coder reads issue directly",
             ha="center", fontsize=9, style="italic", color=COLORS["bb"])

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig7_case_study.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig7_case_study.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("  Fig 7: Case Study - DONE")


# ── Fig 8: Information Flow Bottleneck Model ────────────────────────

def fig8_bottleneck_model():
    """Horizontal flow diagram showing BB vs MP performance at each pipeline stage."""
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title("Information Flow Bottleneck Model", fontsize=14, fontweight="bold", pad=15)

    stages = [
        ("Issue", None, None, None),
        ("IFS\n(Info Retention)", "BB: 0.58", "MP: 0.39", True),
        ("File\nTargeting", "BB: 83%", "MP: 55%", True),
        ("Patch\nGeneration", "~22%", "~22%", False),
        ("Resolve", "BB: 16%", "MP: 12%", True),
    ]

    y_center = 2.5
    box_w, box_h = 2.0, 1.6
    gap = 0.8

    for i, (label, bb_val, mp_val, bb_better) in enumerate(stages):
        x = 0.5 + i * (box_w + gap)

        # Box color
        if bb_better is None:
            fc = "#F0F0F0"
            ec = "black"
        elif bb_better:
            fc = "#D5F5E3"
            ec = COLORS["bb"]
        else:
            fc = "#FADBD8"
            ec = "#E74C3C"

        rect = mpatches.FancyBboxPatch(
            (x, y_center - box_h / 2), box_w, box_h,
            boxstyle="round,pad=0.15", facecolor=fc,
            edgecolor=ec, linewidth=2.0
        )
        ax.add_patch(rect)

        # Stage label
        ax.text(x + box_w / 2, y_center + 0.3, label,
                ha="center", va="center", fontsize=10, fontweight="bold")

        # BB and MP values
        if bb_val and mp_val:
            ax.text(x + box_w / 2, y_center - 0.3, bb_val,
                    ha="center", va="center", fontsize=9, color=COLORS["bb"],
                    fontweight="bold")
            ax.text(x + box_w / 2, y_center - 0.6, mp_val,
                    ha="center", va="center", fontsize=9, color=COLORS["mp"])

        # Arrow to next stage
        if i < len(stages) - 1:
            arrow_x = x + box_w + 0.05
            arrow_end = arrow_x + gap - 0.1
            # Dashed red arrow for bottleneck stage
            if i == 2:  # After Patch Generation = bottleneck
                ax.annotate("", xy=(arrow_end, y_center), xytext=(arrow_x, y_center),
                            arrowprops=dict(arrowstyle="->", color="#E74C3C",
                                            lw=2, linestyle="dashed"))
            else:
                ax.annotate("", xy=(arrow_end, y_center), xytext=(arrow_x, y_center),
                            arrowprops=dict(arrowstyle="->", color="black", lw=1.5))

    # Bottleneck label
    bottleneck_x = 0.5 + 3 * (box_w + gap) + box_w / 2
    ax.text(bottleneck_x, y_center - box_h / 2 - 0.4,
            "BOTTLENECK", ha="center", fontsize=10,
            color="#E74C3C", fontweight="bold")

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor="#D5F5E3", edgecolor=COLORS["bb"],
                       linewidth=1.5, label="BB > MP"),
        mpatches.Patch(facecolor="#FADBD8", edgecolor="#E74C3C",
                       linewidth=1.5, label="No difference (bottleneck)"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=9,
              framealpha=0.9)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig8_bottleneck_model.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig8_bottleneck_model.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("  Fig 8: Bottleneck Model - DONE")


# ── Fig 9: File Targeting Rate ──────────────────────────────────────

def fig9_file_targeting():
    """Bar chart comparing correct file targeting rates across modes."""
    modes = ["MP", "BB", "Hybrid"]
    colors_list = [COLORS["mp"], COLORS["bb"], COLORS["hybrid"]]

    # Data from filtered_analysis.json
    targeting_rates = [55.1, 82.6, 78.1]

    fig, ax = plt.subplots(figsize=(6, 4.5))

    bars = ax.bar(modes, targeting_rates, color=colors_list, edgecolor="black",
                  linewidth=1.2, width=0.6)

    # Value labels on bars
    for bar, val in zip(bars, targeting_rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=12,
                fontweight="bold")

    ax.set_ylabel("Correct File Targeting Rate (%)", fontsize=12)
    ax.set_title("Correct File Targeting Rate\n(Among Non-Empty Patches)",
                 fontsize=13, fontweight="bold")
    ax.set_ylim(0, 100)
    ax.axhline(y=50, color="gray", linestyle="--", alpha=0.5, linewidth=0.8)

    # Add annotation for BB advantage
    ax.annotate("+27.5pp", xy=(1, 82.6), xytext=(1.6, 90),
                fontsize=10, color=COLORS["bb"], fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=COLORS["bb"], lw=1.5))

    sns.despine()
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig9_file_targeting.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig9_file_targeting.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("  Fig 9: File Targeting - DONE")


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating figures...")
    fig1_resolve_rate()
    fig2_difficulty_breakdown()
    fig3_ifs_analysis()
    fig4_failure_analysis()
    fig5_cost_efficiency()
    fig6_overlap()
    fig7_case_study()
    fig8_bottleneck_model()
    fig9_file_targeting()
    print()
    print("All figures saved to:", FIGURES_DIR)
    for f in sorted(FIGURES_DIR.glob("*")):
        print(f"  {f.name}")
