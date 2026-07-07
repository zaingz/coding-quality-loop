"""Hero banner v2 generator — dark and light variants.

Renders 1680x720 PNGs showing the PLAN -> EXECUTE -> REVIEW loop with
tagline. Uses matplotlib only (already a repo-agnostic Python stdlib
adjacent). Re-run with `python3 docs/images/src/banner_v2.py`.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parents[1]

PHASES = [
    (
        "PLAN",
        "Contract · Context map\nRight-size gate · Plan",
    ),
    (
        "EXECUTE",
        "Small slice · Verify\nRecord evidence",
    ),
    (
        "REVIEW",
        "Fresh-context review\nCompletion record",
    ),
]


def draw(dark: bool, path: Path) -> None:
    if dark:
        bg = "#0b0e13"
        fg = "#f2f4f8"
        card_bg = "#141922"
        card_edge = "#252c37"
        accent = "#7cc4ff"
        muted = "#8b93a3"
        chip_bg = "#1c2331"
    else:
        bg = "#ffffff"
        fg = "#0b0e13"
        card_bg = "#f4f6fa"
        card_edge = "#dfe4ed"
        accent = "#1f6feb"
        muted = "#5a6474"
        chip_bg = "#eef2f8"

    fig = plt.figure(figsize=(16.8, 7.2), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_facecolor(bg)
    fig.patch.set_facecolor(bg)

    # Chip / eyebrow
    ax.add_patch(
        FancyBboxPatch(
            (5, 82), 24, 6,
            boxstyle="round,pad=0.4,rounding_size=1.5",
            linewidth=0, facecolor=chip_bg,
        )
    )
    ax.text(
        17, 85, "Coding Quality Loop  ·  v3.1",
        ha="center", va="center",
        fontsize=13, color=accent, fontweight="bold", family="DejaVu Sans",
    )

    # Headline
    ax.text(
        5, 72,
        "Make your AI coding agent ship changes",
        ha="left", va="center",
        fontsize=34, color=fg, fontweight="bold", family="DejaVu Sans",
    )
    ax.text(
        5, 63,
        "you can trust.",
        ha="left", va="center",
        fontsize=34, color=accent, fontweight="bold", family="DejaVu Sans",
    )

    # Subhead
    ax.text(
        5, 54,
        "Executable gates · independent review · radical candor.\n"
        "One dependency-free skill. 121 offline gate cases. Zero lock-in.",
        ha="left", va="top",
        fontsize=15, color=muted, family="DejaVu Sans",
    )

    # Three phase cards
    card_y = 12
    card_h = 26
    card_w = 26
    gap = 3
    left0 = 6
    for i, (title, sub) in enumerate(PHASES):
        x = left0 + i * (card_w + gap + 4)
        ax.add_patch(
            FancyBboxPatch(
                (x, card_y), card_w, card_h,
                boxstyle="round,pad=0.5,rounding_size=1.5",
                linewidth=1.2, edgecolor=card_edge, facecolor=card_bg,
            )
        )
        ax.text(
            x + card_w / 2, card_y + card_h - 6,
            title,
            ha="center", va="center",
            fontsize=18, color=accent, fontweight="bold", family="DejaVu Sans",
        )
        ax.text(
            x + card_w / 2, card_y + card_h - 15,
            sub,
            ha="center", va="center",
            fontsize=12, color=fg, family="DejaVu Sans",
        )

        # Arrow to next
        if i < len(PHASES) - 1:
            ax_arrow = FancyArrowPatch(
                (x + card_w + 0.5, card_y + card_h / 2),
                (x + card_w + gap + 3.5, card_y + card_h / 2),
                arrowstyle="-|>", mutation_scale=18,
                linewidth=2.0, color=accent,
            )
            ax.add_patch(ax_arrow)

    # Feedback caption
    ax.text(
        50, 6,
        "durable lessons feed back into the next PLAN",
        ha="center", va="center",
        fontsize=11, color=muted, style="italic", family="DejaVu Sans",
    )

    fig.savefig(path, facecolor=bg, dpi=100)
    plt.close(fig)


def main() -> None:
    draw(dark=True, path=OUT / "banner-v2-dark.png")
    draw(dark=False, path=OUT / "banner-v2-light.png")
    print(f"wrote {OUT/'banner-v2-dark.png'}")
    print(f"wrote {OUT/'banner-v2-light.png'}")


if __name__ == "__main__":
    main()
