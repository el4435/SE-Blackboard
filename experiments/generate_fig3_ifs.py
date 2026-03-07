"""Generate Fig 3 — IFS Analysis (dual panel, style-refined).

(a) Coder Stage IFS bar chart with p-value bracket
(b) IFS Decay Across Pipeline with dashed Hybrid, +50% annotation, gray band
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
FIGURES_DIR = PROJECT_ROOT / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

# Style
matplotlib.rcParams["font.family"] = "serif"
matplotlib.rcParams["font.size"] = 11
matplotlib.rcParams["axes.labelsize"] = 12
matplotlib.rcParams["axes.titlesize"] = 13
matplotlib.rcParams["figure.dpi"] = 300
sns.set_style("whitegrid")

COLORS = {"mp": "#E74C3C", "bb": "#2ECC71", "hybrid": "#3498DB"}
LABELS = {"mp": "MP", "bb": "BB", "hybrid": "Hybrid"}

# Data
data_root = PROJECT_ROOT / "data"
ifs_summary = json.loads(
    (data_root / "ifs" / "ifs_summary_real.json").read_text(encoding="utf-8")
)
stage_ifs = ifs_summary["stage_average_ifs"]


def generate():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5),
                                    gridspec_kw={"width_ratios": [1, 1.3]})

    configs = ["mp", "bb", "hybrid"]
    labels_map = {"mp": "Seq-MP", "bb": "Seq-BB", "hybrid": "Seq-Hybrid"}

    # Panel (a): Coder Stage IFS
    coder_vals = [stage_ifs[labels_map[c]]["Coder"] for c in configs]

    bars = ax1.bar(range(3), coder_vals,
                   color=[COLORS[c] for c in configs],
                   width=0.6, edgecolor="white", linewidth=1.5)

    for i, (bar, val) in enumerate(zip(bars, coder_vals)):
        ax1.text(bar.get_x() + bar.get_width() / 2, val + 0.015,
                 f"{val:.3f}", ha="center", fontsize=11, fontweight="bold")

    ax1.set_xticks(range(3))
    ax1.set_xticklabels([LABELS[c] for c in configs])
    ax1.set_ylabel("IFS (Coder Stage)")
    ax1.set_title("(a)  Coder Stage IFS", fontweight="bold")
    ax1.set_ylim(0, 0.75)

    # Panel (b): IFS Decay Across Pipeline
    stages = ["Planner", "Coder", "Reviewer", "Tester"]
    x_stages = np.arange(len(stages))

    # Gray band at bottom (near-zero region)
    ax2.axhspan(0, 0.10, color="#F0F0F0", zorder=0)

    # BB line (solid, circles)
    bb_vals = [stage_ifs["Seq-BB"].get(s) for s in stages]
    bb_valid_idx = [i for i, v in enumerate(bb_vals) if isinstance(v, (int, float))]
    bb_valid_vals = [bb_vals[i] for i in bb_valid_idx]
    ax2.plot(bb_valid_idx, bb_valid_vals, marker="o", color=COLORS["bb"],
             linewidth=2.2, markersize=8, label="Blackboard", zorder=3)

    # Hybrid line (dashed, squares)
    hy_vals = [stage_ifs["Seq-Hybrid"].get(s) for s in stages]
    hy_valid_idx = [i for i, v in enumerate(hy_vals) if isinstance(v, (int, float))]
    hy_valid_vals = [hy_vals[i] for i in hy_valid_idx]
    ax2.plot(hy_valid_idx, hy_valid_vals, marker="s", color=COLORS["hybrid"],
             linewidth=2.2, markersize=8, linestyle="--", label="Hybrid", zorder=3)

    # MP single point (diamond) at Coder
    mp_coder = stage_ifs["Seq-MP"]["Coder"]
    ax2.scatter([1], [mp_coder], color=COLORS["mp"], s=120, zorder=5,
                marker="D", edgecolors="black", linewidth=0.8, label="MP (Coder only)")

    # +50% annotation arrow from MP to BB at Coder stage
    bb_coder = stage_ifs["Seq-BB"]["Coder"]
    mid_y = (mp_coder + bb_coder) / 2
    ax2.annotate("", xy=(1, bb_coder - 0.01), xytext=(1, mp_coder + 0.01),
                 arrowprops=dict(arrowstyle="<->", color=COLORS["bb"],
                                 lw=1.8, shrinkA=0, shrinkB=0))
    pct_diff = (bb_coder - mp_coder) / mp_coder * 100
    ax2.text(1.12, mid_y, f"+{pct_diff:.0f}%",
             fontsize=10, color=COLORS["bb"], fontweight="bold", va="center")

    ax2.set_xticks(x_stages)
    ax2.set_xticklabels(stages)
    ax2.set_ylabel("Information Fidelity Score")
    ax2.set_title("(b)  IFS Decay Across Pipeline", fontweight="bold")
    ax2.set_ylim(0, 0.90)
    ax2.legend(loc="upper right", fontsize=9, framealpha=0.9)

    # Save
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig3_ifs_analysis.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig3_ifs_analysis.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("Fig 3 (IFS Analysis) saved to:", FIGURES_DIR)


if __name__ == "__main__":
    generate()
