"""Evidence dashboard — one graphic summarizing the proof.

Sections:
  - 144 offline gate cases (broken down across 6 gate suites; the 10-case trigger
    smoke fixture is excluded because its default grader cannot fail)
  - Zero runtime deps
  - Per-agent code-quality lift (honest split incl. Codex -1.11)
  - Five published eval runs in examples/ (only webapp 07-07 is real-CLI)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "evidence-dashboard.png"

BG = "#0b0e13"
FG = "#f2f4f8"
CARD_BG = "#141922"
CARD_EDGE = "#252c37"
ACCENT = "#7cc4ff"
GOOD = "#4ade80"
BAD = "#f87171"
MUTED = "#8b93a3"

SUITES = [
    ("Static", 11),
    ("Behavioral", 44),
    ("Memory", 26),
    ("Reality", 23),
    ("Routing", 24),
    ("Hook", 16),
]

# Honest per-agent code-quality lift (excluding process artifacts)
# Sudoku 07-01: Codex +1.0, Claude Code +4.5, Droid/GLM-5.2 +8.0
# Webapp 07-07: Claude Code +6.67, Codex -1.11
AGENTS = [
    ("Droid / GLM-5.2\nSudoku 07-01", 8.0),
    ("Claude Code\nWebapp 07-07", 6.67),
    ("Claude Code\nSudoku 07-01", 4.5),
    ("Codex\nSudoku 07-01", 1.0),
    ("Codex\nWebapp 07-07", -1.11),
]


def card(ax, x, y, w, h, title, subtitle=None):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.5,rounding_size=1.5",
            linewidth=1.2, edgecolor=CARD_EDGE, facecolor=CARD_BG,
        )
    )
    ax.text(
        x + 2, y + h - 2.5, title,
        ha="left", va="top", fontsize=13, color=MUTED, fontweight="bold",
        family="DejaVu Sans",
    )
    if subtitle:
        ax.text(
            x + 2, y + h - 5.5, subtitle,
            ha="left", va="top", fontsize=10, color=MUTED,
            family="DejaVu Sans",
        )


def main():
    fig = plt.figure(figsize=(16.8, 9.4), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_facecolor(BG)
    fig.patch.set_facecolor(BG)

    # Title
    ax.text(
        5, 94, "Evidence dashboard",
        ha="left", va="center", fontsize=24, color=FG, fontweight="bold",
        family="DejaVu Sans",
    )
    ax.text(
        5, 89, "Every number below is re-runnable on a clean checkout · zero runtime deps · candor-first",
        ha="left", va="center", fontsize=12, color=MUTED, family="DejaVu Sans",
    )

    # Big number: 144
    card(ax, 5, 62, 38, 22, "OFFLINE GATE CASES")
    ax.text(
        24, 74, "144", ha="center", va="center",
        fontsize=64, color=ACCENT, fontweight="bold", family="DejaVu Sans",
    )
    ax.text(
        24, 66, "across 6 gate suites, re-run on every push",
        ha="center", va="center", fontsize=11, color=MUTED, family="DejaVu Sans",
    )

    # Suite breakdown (horizontal bars)
    card(ax, 45, 62, 50, 22, "SUITE BREAKDOWN")
    max_val = max(v for _, v in SUITES)
    bar_area_x = 62
    bar_area_w = 26
    row_h = 2.1
    top = 76
    for i, (name, val) in enumerate(SUITES):
        y = top - i * row_h
        ax.text(
            60, y, name,
            ha="right", va="center", fontsize=10.5, color=FG,
            family="DejaVu Sans",
        )
        w = bar_area_w * (val / max_val)
        ax.add_patch(
            FancyBboxPatch(
                (bar_area_x, y - 0.7), w, 1.4,
                boxstyle="round,pad=0,rounding_size=0.3",
                linewidth=0, facecolor=ACCENT,
            )
        )
        ax.text(
            bar_area_x + w + 0.6, y, f"{val}",
            ha="left", va="center", fontsize=10.5, color=FG,
            family="DejaVu Sans",
        )

    # Per-agent code-quality lift chart
    card(ax, 5, 25, 90, 32, "CODE-QUALITY LIFT (excludes process artifacts)",
         subtitle="Honest bars: we ship our negative results next to the positive ones.")

    n = len(AGENTS)
    plot_left = 12
    plot_right = 92
    plot_w = plot_right - plot_left
    bar_slot = plot_w / n
    axis_y = 33
    max_abs = 9.0  # y-axis span
    scale = 12 / max_abs  # 12 units of y per max_abs, so +8.0 tops at ~44
    for i, (label, val) in enumerate(AGENTS):
        cx = plot_left + bar_slot * (i + 0.5)
        bw = bar_slot * 0.42
        color = GOOD if val >= 0 else BAD
        top_y = axis_y + val * scale
        y0 = min(axis_y, top_y)
        h = abs(val * scale)
        ax.add_patch(
            FancyBboxPatch(
                (cx - bw / 2, y0), bw, h,
                boxstyle="round,pad=0,rounding_size=0.3",
                linewidth=0, facecolor=color,
            )
        )
        # Value label (above for positive, below for negative)
        if val >= 0:
            ax.text(cx, top_y + 1.5, f"+{val}", ha="center", va="bottom",
                    fontsize=13, color=color, fontweight="bold",
                    family="DejaVu Sans")
        else:
            # Place negative label further below to clear the axis-line label
            ax.text(cx, top_y - 2.4, f"{val}", ha="center", va="top",
                    fontsize=13, color=color, fontweight="bold",
                    family="DejaVu Sans")
        # Agent label — sit below the value label for negative bars
        agent_label_y = axis_y - 5.5 if val < 0 else axis_y - 2.8
        ax.text(cx, agent_label_y, label, ha="center", va="top",
                fontsize=9.5, color=FG, family="DejaVu Sans")

    # Zero baseline
    ax.plot([plot_left, plot_right], [axis_y, axis_y],
            color=MUTED, linewidth=1.0, linestyle="--")
    ax.text(plot_left - 0.5, axis_y, "0",
            ha="right", va="center", fontsize=10, color=MUTED,
            family="DejaVu Sans")

    # Bottom row: zero deps + three live evals
    def stat_card(x, w, title, big, sub):
        card(ax, x, 4, w, 18, title)
        ax.text(x + w / 2, 12, big, ha="center", va="center",
                fontsize=46, color=ACCENT, fontweight="bold",
                family="DejaVu Sans")
        ax.text(x + w / 2, 6.5, sub, ha="center", va="center",
                fontsize=10, color=MUTED, family="DejaVu Sans")

    stat_card(5, 28, "RUNTIME DEPS", "0", "stdlib-only Python helper")
    stat_card(36, 28, "HOSTS SUPPORTED", "5",
              "Claude · Codex · Cursor · Pi · Droid")
    stat_card(67, 28, "PUBLISHED EVAL RUNS", "5",
              "only webapp 07-07 is real-CLI")

    fig.savefig(OUT, facecolor=BG, dpi=100)
    plt.close(fig)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
