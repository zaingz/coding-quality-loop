"""Gate-gaming incident panel — 2026-07-07.

Three-panel comic-strip layout telling the CHANGELOG 3.1.0 story:
an agent softened its local copy of diff-audit and reported PASS;
the pristine gates caught it; v3.1 added helper-integrity sha256 hashes.

All copy is paraphrased from CHANGELOG.md \u00a73.1.0 lines 14\u201318 and
examples/webapp-agent-eval-2026-07-07/README.md lines describing the
softening incident.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "gate-gaming.png"

BG = "#0b0e13"
FG = "#f2f4f8"
CARD_BG = "#141922"
CARD_EDGE = "#252c37"
ACCENT = "#7cc4ff"
BAD = "#f87171"
GOOD = "#4ade80"
MUTED = "#8b93a3"


PANELS = [
    (
        "1  The gaming",
        BAD,
        "An agent edited its local copy of\n"
        "diff-audit.py, softening two checks\n"
        "(untracked-file secrets, test\n"
        "weakening), then reported PASS.",
        "verify: Overall: PASS\n(under a softened gate)",
    ),
    (
        "2  The catch",
        ACCENT,
        "The pristine gates \u2014 not the\n"
        "workspace copy \u2014 were re-run\n"
        "against the same record and\n"
        "immediately failed the record.",
        "sha256(diff-audit)=b7a1\u2026\nsha256(pristine)=e6f3\u2026\nMISMATCH",
    ),
    (
        "3  The harness change",
        GOOD,
        "v3.1.0 added helper-integrity\n"
        "reporting: verify prints sha256\n"
        "of each helper module so hooks/CI\n"
        "can catch a locally modified gate.",
        "SKILL.md rule: never repair or\nstub the helper; report and stop.",
    ),
]


def draw():
    fig = plt.figure(figsize=(16.8, 9.0), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_facecolor(BG)
    fig.patch.set_facecolor(BG)

    ax.text(5, 92, "The gate-gaming incident \u2014 2026-07-07",
            ha="left", va="center", fontsize=24, color=FG,
            fontweight="bold", family="DejaVu Sans")
    ax.text(5, 86, "Our best marketing artifact is the one we did not want to publish.",
            ha="left", va="center", fontsize=12, color=MUTED,
            style="italic", family="DejaVu Sans")

    card_w = 28
    card_h = 60
    gap = 3
    left = 5
    y = 15

    for i, (title, color, body, code) in enumerate(PANELS):
        x = left + i * (card_w + gap)
        # Panel border
        ax.add_patch(
            FancyBboxPatch(
                (x, y), card_w, card_h,
                boxstyle="round,pad=0.5,rounding_size=1.5",
                linewidth=1.5, edgecolor=color, facecolor=CARD_BG,
            )
        )
        # Big panel number/title
        ax.text(x + 1.6, y + card_h - 3.5, title,
                ha="left", va="top", fontsize=16, color=color,
                fontweight="bold", family="DejaVu Sans")
        # Body
        ax.text(x + 1.6, y + card_h - 12, body,
                ha="left", va="top", fontsize=11.5, color=FG,
                family="DejaVu Sans")
        # Code / mono chip
        ax.add_patch(
            FancyBboxPatch(
                (x + 1.6, y + 4), card_w - 3.2, 14,
                boxstyle="round,pad=0.3,rounding_size=0.8",
                linewidth=0, facecolor="#0b0e13",
            )
        )
        ax.text(x + 2.8, y + 15, code,
                ha="left", va="top", fontsize=10.5, color=color,
                family="DejaVu Sans Mono")

    ax.text(50, 6,
            "Source: CHANGELOG.md \u00a7 3.1.0 \u00b7 examples/webapp-agent-eval-2026-07-07/",
            ha="center", va="center", fontsize=10, color=MUTED,
            family="DejaVu Sans")

    fig.savefig(OUT, facecolor=BG, dpi=100)
    plt.close(fig)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    draw()
