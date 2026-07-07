"""Anatomy of a shipped change — infographic.

Maps the seven checkpoints onto a real artifact set from the walkthrough
in `examples/walkthrough/` (invoice-rounding fix). Every label pulls a
verbatim excerpt from `examples/walkthrough/agent-record.json`.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parents[1] / "anatomy-of-a-change.png"

BG = "#0b0e13"
FG = "#f2f4f8"
CARD_BG = "#141922"
CARD_EDGE = "#252c37"
ACCENT = "#7cc4ff"
MUTED = "#8b93a3"
GOOD = "#4ade80"

STEPS = [
    ("1  Task contract",
     "Fix invoice totals\nthat round per line\ninstead of once."),
    ("2  Context map",
     "billing/invoice.py\nbilling/tests/*\n(2 files, not tree)"),
    ("3  Right-size gate",
     "One localized fix.\nNo retry framework.\nNo new dependency."),
    ("4  Small slice",
     "invoice.py + one\nregression test.\nNo cleanup."),
    ("5  Red\u2192green",
     "test_multiline_\ntotal_rounds_once:\nred, then green."),
    ("6  Fresh review",
     "fresh_context=true\npatched=false\nverdict=approve"),
    ("7  Completion",
     "Evidence, rollback,\nrisks. The shipping\ngate signs off."),
]


def draw():
    fig = plt.figure(figsize=(16.8, 8.4), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_facecolor(BG)
    fig.patch.set_facecolor(BG)

    ax.text(5, 92, "Anatomy of a shipped change",
            ha="left", va="center", fontsize=24, color=FG, fontweight="bold",
            family="DejaVu Sans")
    ax.text(5, 86, "Traced on the real walkthrough in examples/walkthrough/ — invoice rounding fix",
            ha="left", va="center", fontsize=12, color=MUTED,
            family="DejaVu Sans")

    def draw_card(x, y, w, h, title, body, tint=None):
        edge = tint or CARD_EDGE
        ax.add_patch(
            FancyBboxPatch(
                (x, y), w, h,
                boxstyle="round,pad=0.4,rounding_size=1.5",
                linewidth=1.4 if tint else 1.2, edgecolor=edge, facecolor=CARD_BG,
            )
        )
        ax.text(x + 1.2, y + h - 2.5, title,
                ha="left", va="top", fontsize=11.5, color=ACCENT,
                fontweight="bold", family="DejaVu Sans")
        ax.text(x + 1.2, y + h - 7.5, body,
                ha="left", va="top", fontsize=9.5, color=FG,
                family="DejaVu Sans")

    # Single row of 7 cards
    card_w = 12.2
    card_h = 26
    gap = 1.1
    left = 3.5
    row_y = 35

    positions = []
    for i in range(7):
        x = left + i * (card_w + gap)
        positions.append((x, row_y))

    for i, ((title, body), (x, y)) in enumerate(zip(STEPS, positions)):
        tint = GOOD if i == 4 else None  # highlight red\u2192green evidence
        draw_card(x, y, card_w, card_h, title, body, tint=tint)

    # Arrows between cards
    for i in range(6):
        x1, y1 = positions[i]
        x2, y2 = positions[i + 1]
        arrow = FancyArrowPatch(
            (x1 + card_w + 0.05, y1 + card_h / 2),
            (x2 - 0.05, y2 + card_h / 2),
            arrowstyle="-|>", mutation_scale=12, color=ACCENT, linewidth=1.6,
        )
        ax.add_patch(arrow)

    # Footer note
    ax.text(
        50, 6,
        "Every artifact above is committed at examples/walkthrough/agent-record.json — the same file "
        "`verify-gates` checks in eval fixtures.",
        ha="center", va="center", fontsize=10, color=MUTED, style="italic",
        family="DejaVu Sans",
    )

    fig.savefig(OUT, facecolor=BG, dpi=100)
    plt.close(fig)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    draw()
