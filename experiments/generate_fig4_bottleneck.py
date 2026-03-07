"""Generate Fig 4 — Information Flow Bottleneck Model.

Horizontal flow: Issue → IFS → File Targeting → Patch Generation → Resolve
Green boxes = BB advantage, pink dashed box = bottleneck.
Reference: fig4 patch_generation_black_text.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = PROJECT_ROOT / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

# Style
matplotlib.rcParams["font.family"] = "serif"
matplotlib.rcParams["font.size"] = 11
matplotlib.rcParams["figure.dpi"] = 300

GREEN = "#2ECC71"
GREEN_BG = "#D5F5E3"
RED_BORDER = "#E74C3C"
RED_BG = "#FADBD8"
GRAY_BG = "#F0F0F0"
BLACK = "#222222"


def generate():
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title("Information Flow Bottleneck Model",
                 fontsize=15, fontweight="bold", pad=18)

    # Stage definitions
    # (label, bb_val, mp_val, diff_text, is_bottleneck)
    stages = [
        ("Issue",                    None,    None,    None,    None),
        ("Information\nRetention (IFS)", "BB: 0.586", "MP: 0.362", "+62%",  False),
        ("File\nTargeting",         "BB: 82.6%",  "MP: 55.1%",  "+27.5pp", False),
        ("Patch\nGeneration",       "BB: ~22%", "MP: ~22%", None,    True),
        ("Resolve",                 "BB: 16%",  "MP: 12%",  "+4pp",  False),
    ]

    n = len(stages)
    box_w = 2.0
    box_h = 2.8
    gap = 0.7
    total_w = n * box_w + (n - 1) * gap
    x_start = (14 - total_w) / 2
    y_center = 3.2

    box_positions = []  # store (x, y) for arrows

    for i, (label, bb_val, mp_val, diff_text, is_bottleneck) in enumerate(stages):
        x = x_start + i * (box_w + gap)
        y_bot = y_center - box_h / 2
        box_positions.append((x, y_center))

        # Box style
        if is_bottleneck is None:
            # "Issue" box — neutral gray
            fc, ec, ls, lw = GRAY_BG, "#AAAAAA", "solid", 1.5
        elif is_bottleneck:
            # Bottleneck — pink, dashed red border
            fc, ec, ls, lw = RED_BG, RED_BORDER, "dashed", 2.0
        else:
            # BB advantage — green
            fc, ec, ls, lw = GREEN_BG, GREEN, "solid", 2.0

        rect = mpatches.FancyBboxPatch(
            (x, y_bot), box_w, box_h,
            boxstyle="round,pad=0.15", facecolor=fc,
            edgecolor=ec, linewidth=lw, linestyle=ls,
        )
        ax.add_patch(rect)

        # Stage label (top of box)
        if is_bottleneck is None:
            # "Issue" — centered single label
            ax.text(x + box_w / 2, y_center, label,
                    ha="center", va="center", fontsize=12, fontweight="bold",
                    color=BLACK)
        else:
            ax.text(x + box_w / 2, y_center + box_h / 2 - 0.45, label,
                    ha="center", va="top", fontsize=11, fontweight="bold",
                    color=BLACK, linespacing=1.1)

        # BB / MP values
        if bb_val and mp_val:
            bb_color = BLACK
            ax.text(x + box_w / 2, y_center - 0.15, bb_val,
                    ha="center", va="center", fontsize=11,
                    color=bb_color, fontweight="bold")
            ax.text(x + box_w / 2, y_center - 0.65, mp_val,
                    ha="center", va="center", fontsize=11,
                    color=BLACK, fontweight="bold")

            if is_bottleneck:
                ax.text(x + box_w / 2, y_center - 1.15, "(no difference)",
                        ha="center", va="center", fontsize=9,
                        color=BLACK, fontstyle="italic")

        # Difference annotation (bottom of green boxes)
        if diff_text and not is_bottleneck:
            # Small green badge at bottom
            badge_y = y_bot + 0.35
            badge = mpatches.FancyBboxPatch(
                (x + box_w / 2 - 0.45, badge_y - 0.18), 0.9, 0.36,
                boxstyle="round,pad=0.05", facecolor=GREEN, alpha=0.25,
                edgecolor="none",
            )
            ax.add_patch(badge)
            ax.text(x + box_w / 2, badge_y, diff_text,
                    ha="center", va="center", fontsize=9,
                    color=BLACK, fontweight="bold")

        # Arrow to next stage
        if i < n - 1:
            arrow_x_start = x + box_w + 0.05
            arrow_x_end = x + box_w + gap - 0.05
            # Dashed red arrow into bottleneck
            if stages[i + 1][4]:  # next is bottleneck
                ax.annotate("", xy=(arrow_x_end, y_center),
                            xytext=(arrow_x_start, y_center),
                            arrowprops=dict(arrowstyle="->, head_width=0.3",
                                            color=RED_BORDER, lw=2,
                                            linestyle="dashed"))
            else:
                ax.annotate("", xy=(arrow_x_end, y_center),
                            xytext=(arrow_x_start, y_center),
                            arrowprops=dict(arrowstyle="->, head_width=0.3",
                                            color="#666666", lw=1.8))

    # BOTTLENECK label under the patch generation box
    bottleneck_x = x_start + 3 * (box_w + gap) + box_w / 2
    bottleneck_y = y_center - box_h / 2 - 0.35
    bbox_props = dict(boxstyle="round,pad=0.15", facecolor=RED_BG,
                      edgecolor=RED_BORDER, linewidth=1.5)
    ax.text(bottleneck_x, bottleneck_y, "BOTTLENECK",
            ha="center", va="center", fontsize=10, fontweight="bold",
            color=RED_BORDER, bbox=bbox_props)

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor=GREEN_BG, edgecolor=GREEN,
                       linewidth=1.5, label="BB > MP (upstream advantage)"),
        mpatches.Patch(facecolor=RED_BG, edgecolor=RED_BORDER,
                       linewidth=1.5, linestyle="dashed",
                       label="No difference (bottleneck)"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=9,
              framealpha=0.9, edgecolor="#CCCCCC")

    # Save
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig4_bottleneck_model.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig4_bottleneck_model.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("Fig 4 (Bottleneck Model) saved to:", FIGURES_DIR)


if __name__ == "__main__":
    generate()
