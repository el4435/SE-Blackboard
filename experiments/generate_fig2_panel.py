"""Generate Fig 2 — Main Results Panel (3 subplots).

Combines resolve rate, difficulty breakdown, and file targeting into one figure.
Reference: fig2 panel_c_black_dashed_line.png
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
LABELS = {"mp": "MP", "bb": "BB", "hybrid": "Hybrid"}


# ── Data Loading ─────────────────────────────────────────────────────

def load_results(config_dir: str) -> list[dict]:
    results = []
    for f in sorted(os.listdir(config_dir)):
        if f.endswith(".json") and "_summary" not in f:
            data = json.loads(Path(config_dir, f).read_text(encoding="utf-8"))
            results.append(data)
    return results


def wilson_ci(p: float, n: int, z: float = 1.96):
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

# Difficulty mapping (same as original)
difficulty_map = {}
for iid in all_issues:
    repo = iid.split("__")[0]
    if repo in ("django",):
        difficulty_map[iid] = "Easy"
    elif repo in ("pytest-dev", "pallets", "pydata"):
        difficulty_map[iid] = "Medium"
    else:
        difficulty_map[iid] = "Hard"

by_id_map = {"mp": mp_by_id, "bb": bb_by_id, "hybrid": hy_by_id}


# ── Figure Generation ────────────────────────────────────────────────

def generate():
    fig, (ax_a, ax_b, ax_c) = plt.subplots(1, 3, figsize=(14, 4.5))

    configs = ["mp", "bb", "hybrid"]

    # ── Panel (a): Resolve Rate ──────────────────────────────────────
    counts = [n_mp, n_bb, n_hy]
    rates = [c / N for c in counts]

    bars_a = ax_a.bar(range(3), [r * 100 for r in rates],
                      color=[COLORS[c] for c in configs],
                      width=0.6, edgecolor="white", linewidth=1.5)

    for i, (c, rate) in enumerate(zip(configs, rates)):
        lo, hi = wilson_ci(rate, N)
        ax_a.errorbar(i, rate * 100,
                      yerr=[[rate * 100 - lo * 100], [hi * 100 - rate * 100]],
                      fmt="none", color="black", capsize=5, linewidth=1.5)
        ax_a.text(i, hi * 100 + 1.5,
                  f"{rate * 100:.0f}%", ha="center", fontsize=11, fontweight="bold")

    ax_a.set_xticks(range(3))
    ax_a.set_xticklabels([LABELS[c] for c in configs])
    ax_a.set_ylabel("Resolve Rate (%)")
    ax_a.set_title("(a)  Resolve Rate", fontweight="bold")
    ax_a.set_ylim(0, 35)
    ax_a.yaxis.set_major_locator(plt.MultipleLocator(5))

    # ── Panel (b): By Difficulty ─────────────────────────────────────
    levels = ["Easy", "Medium", "Hard"]
    hatches = ["", "//", ".."]
    level_counts = {lv: sum(1 for i in all_issues if difficulty_map[i] == lv)
                    for lv in levels}

    width_b = 0.25
    x_b = np.arange(len(configs))

    for j, (level, hatch) in enumerate(zip(levels, hatches)):
        level_rates = []
        for cfg in configs:
            issues_in_level = [i for i in all_issues if difficulty_map[i] == level]
            n_level = len(issues_in_level)
            n_resolved = sum(1 for i in issues_in_level
                             if by_id_map[cfg][i].get("resolved", False))
            level_rates.append(n_resolved / n_level * 100 if n_level > 0 else 0)

        bars_b = ax_b.bar(x_b + (j - 1) * width_b, level_rates, width_b,
                          color=[COLORS[c] for c in configs],
                          hatch=hatch, edgecolor="white", linewidth=0.8)

    # Build hatching legend
    legend_patches = []
    for level, hatch in zip(levels, hatches):
        n_lv = level_counts[level]
        legend_patches.append(
            mpatches.Patch(facecolor="#AAAAAA", hatch=hatch,
                           edgecolor="black", linewidth=0.5,
                           label=f"{level} (n={n_lv})")
        )
    ax_b.legend(handles=legend_patches, loc="upper right", fontsize=8,
                framealpha=0.9)

    ax_b.set_xticks(x_b)
    ax_b.set_xticklabels([LABELS[c] for c in configs])
    ax_b.set_ylabel("Resolve Rate (%)")
    ax_b.set_title("(b)  By Difficulty", fontweight="bold")
    ax_b.set_ylim(0, 40)

    # ── Panel (c): File Targeting ────────────────────────────────────
    targeting_rates = [55.1, 82.6, 78.1]

    bars_c = ax_c.bar(range(3), targeting_rates,
                      color=[COLORS[c] for c in configs],
                      width=0.6, edgecolor="white", linewidth=1.5)

    for i, (bar, val) in enumerate(zip(bars_c, targeting_rates)):
        ax_c.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                  f"{val:.1f}%", ha="center", fontsize=11, fontweight="bold")

    # Black dashed 50% reference line
    ax_c.axhline(y=50, color="black", linestyle="--", linewidth=1.2, alpha=0.7)

    # +27.5pp annotation
    ax_c.annotate("+27.5pp", xy=(1, 82.6), xytext=(1.55, 90),
                  fontsize=10, color=COLORS["bb"], fontweight="bold",
                  arrowprops=dict(arrowstyle="->", color=COLORS["bb"], lw=1.5))

    ax_c.set_xticks(range(3))
    ax_c.set_xticklabels([LABELS[c] for c in configs])
    ax_c.set_ylabel("Correct File Targeting Rate (%)")
    ax_c.set_title("(c)  File Targeting", fontweight="bold")
    ax_c.set_ylim(0, 100)

    # ── Save ─────────────────────────────────────────────────────────
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig2_main_results_panel.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig2_main_results_panel.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("Fig 2 (Main Results Panel) saved to:", FIGURES_DIR)


if __name__ == "__main__":
    generate()
