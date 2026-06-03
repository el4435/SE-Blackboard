"""Generate Fig 5 — Case Study: django-13028 (MP vs BB pipeline comparison).

Left panel: Message-Passing (failed), Right panel: Blackboard (resolved).
Each panel shows 4 pipeline stages with status, description, result badge, stats.
Reference: fig5 information_flow_regenerated.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.transforms as mtransforms

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = PROJECT_ROOT / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

matplotlib.rcParams["font.family"] = "serif"
matplotlib.rcParams["font.size"] = 10
matplotlib.rcParams["figure.dpi"] = 300

# Colors
RED_BG = "#FDF2F2"
RED_LIGHT = "#FADBD8"
GREEN_BG = "#F2FDF5"
GREEN_LIGHT = "#D5F5E3"
OK_GREEN = "#27AE60"
FAIL_RED = "#E74C3C"
WARN_ORANGE = "#E67E22"
BLACK = "#222222"
GRAY = "#888888"


def _draw_panel(ax, title, bg_color, row_alt_color, stages, result, result_color,
                stats_text):
    """Draw one pipeline panel.

    stages: list of (stage_name, status_text, status_color, description)
    """
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.axis("off")

    # Panel background
    panel_bg = mpatches.FancyBboxPatch(
        (0, 0.6), 10, 7.0,
        boxstyle="round,pad=0.15", facecolor=bg_color,
        edgecolor="#DDDDDD", linewidth=1.0,
    )
    ax.add_patch(panel_bg)

    # Title
    ax.text(5, 7.15, title, ha="center", va="center",
            fontsize=13, fontweight="bold", color=BLACK)

    # Stage rows
    n_stages = len(stages)
    row_h = 1.25
    row_top = 6.4

    for i, (stage_name, status_text, status_color, desc) in enumerate(stages):
        y_top = row_top - i * row_h
        y_center = y_top - row_h / 2

        # Alternating row background
        if i % 2 == 0:
            row_bg = mpatches.FancyBboxPatch(
                (0.3, y_top - row_h), 9.4, row_h,
                boxstyle="round,pad=0.02", facecolor=row_alt_color,
                edgecolor="none", alpha=0.5,
            )
            ax.add_patch(row_bg)

        # Stage name (left column)
        ax.text(0.6, y_center, stage_name, ha="left", va="center",
                fontsize=11, fontweight="bold", color=BLACK)

        # Status badge (middle column)
        badge_bbox = dict(boxstyle="round,pad=0.2", facecolor="white",
                          edgecolor=status_color, linewidth=1.2)
        ax.text(2.8, y_center, status_text, ha="left", va="center",
                fontsize=9.5, fontweight="bold", color=status_color,
                bbox=badge_bbox)

        # Description (right column)
        ax.text(9.6, y_center, desc, ha="right", va="center",
                fontsize=8.5, color="#444444", linespacing=1.3,
                style="italic")

    # Result badge at bottom
    badge_w, badge_h = 2.4, 0.5
    badge_x = 5 - badge_w / 2
    badge_y = 1.15
    result_rect = mpatches.FancyBboxPatch(
        (badge_x, badge_y), badge_w, badge_h,
        boxstyle="round,pad=0.12", facecolor=result_color,
        edgecolor="none", alpha=0.15,
    )
    ax.add_patch(result_rect)
    result_border = mpatches.FancyBboxPatch(
        (badge_x, badge_y), badge_w, badge_h,
        boxstyle="round,pad=0.12", facecolor="none",
        edgecolor=result_color, linewidth=2.0,
    )
    ax.add_patch(result_border)
    ax.text(5, badge_y + badge_h / 2, result, ha="center", va="center",
            fontsize=12, fontweight="bold", color=result_color)

    # Stats line
    ax.text(5, 0.75, stats_text, ha="center", va="center",
            fontsize=8.5, color=GRAY)


def generate():
    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(16, 5.5))

    # ── Left panel: Message-Passing (FAILED) ─────────────────────────
    mp_stages = [
        ("Planner",  "[OK] Correct diagnosis", OK_GREEN,
         "Identifies check_filterable\nas root cause"),
        ("Coder",    "[X] Wrong location", FAIL_RED,
         "Patches QueryClone() line 355\n(cache management, not filtering)"),
        ("Reviewer", "[>] 3 iterations", WARN_ORANGE,
         "Rejects patch each time\nbut Coder cannot find correct location"),
        ("Tester",   "[X] FAIL", FAIL_RED,
         "Patch does not fix\nthe actual bug"),
    ]
    _draw_panel(ax_l, "Message-Passing: django-13028",
                RED_BG, RED_LIGHT, mp_stages,
                "FAILED", FAIL_RED,
                "34,042 tokens \u00b7 3 iter \u00b7 131s")

    # ── Right panel: Blackboard (RESOLVED) ───────────────────────────
    bb_stages = [
        ("Planner",  "[OK] Correct diagnosis", OK_GREEN,
         "Writes structured analysis\nto shared state"),
        ("Coder",    "[OK] Correct location", OK_GREEN,
         "Reads original traceback:\nline 1131, check_filterable\n\u2192 precise patch"),
        ("Reviewer", "[OK] Accept", OK_GREEN,
         "Patch targets correct\nmethod, accepts immediately"),
        ("Tester",   "[OK] PASS", OK_GREEN,
         "All tests pass\nin 1 iteration"),
    ]
    _draw_panel(ax_r, "Blackboard: django-13028",
                GREEN_BG, GREEN_LIGHT, bb_stages,
                "RESOLVED", OK_GREEN,
                "30,732 tokens \u00b7 1 iter \u00b7 67s")

    # ── Bottom caption ───────────────────────────────────────────────
    fig.text(0.5, 0.02,
             "Key: BB preserves exact traceback (line 1131, check_filterable) "
             "\u2013 Coder targets correct method",
             ha="center", fontsize=9, color=GRAY, fontstyle="italic")

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(FIGURES_DIR / "fig5_case_study.pdf", bbox_inches="tight")
    fig.savefig(FIGURES_DIR / "fig5_case_study.png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("Fig 5 (Case Study) saved to:", FIGURES_DIR)


if __name__ == "__main__":
    generate()
