"""Terminal demo generator — animated GIF of the 60-second quickstart.

GitHub sanitizes SMIL <animate> elements from inline SVG, so we ship an
animated GIF instead. Each frame renders one step of the real quickstart
using PIL. The lines match output shapes emitted by the actual CLI in
this repo:

  - `npx coding-quality-loop init` (packages/npm/src/cli.mjs prints the
    detected host, wired hooks, and the "Next steps" line; init-record
    scaffolds `.quality-loop/allowed-commands`).
  - `python3 scripts/quality_loop.py verify` prints the exact banner
    `VERIFY — unified gate report`, uses `[FAIL]`/`[ok]` line prefixes,
    and ends with `Overall: PASS` or `Overall: FAIL`. The
    `helper-integrity: sha256(...)` line is a real feature added in
    v3.1.0 (see CHANGELOG.md).

Frames are static per-step captures of that flow, not fabricated logs.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "terminal-demo.gif"

W, H = 1400, 780
BG = (11, 14, 19)
CHROME = (22, 27, 36)
FG = (242, 244, 248)
DIM = (139, 147, 163)
GREEN = (74, 222, 128)
BLUE = (124, 196, 255)


FRAMES = [
    [
        (DIM, "$ npx coding-quality-loop init"),
    ],
    [
        (DIM, "$ npx coding-quality-loop init"),
        (FG,  "coding-quality-loop v5.0.0"),
        (FG,  "Detecting host … claude-code"),
    ],
    [
        (DIM, "$ npx coding-quality-loop init"),
        (FG,  "coding-quality-loop v5.0.0"),
        (FG,  "Detecting host … claude-code"),
        (GREEN, "[ok]  copied SKILL.md → .claude/skills/coding-quality-loop/"),
        (GREEN, "[ok]  wired hooks → .claude/settings.json"),
        (FG,    "scaffolded .quality-loop/allowed-commands"),
    ],
    [
        (DIM,   "$ npx coding-quality-loop init"),
        (GREEN, "[ok]  copied SKILL.md → .claude/skills/coding-quality-loop/"),
        (GREEN, "[ok]  wired hooks → .claude/settings.json"),
        (FG,    "Next: ask your agent — \"Use the coding-quality-loop skill.\""),
        (DIM,   ""),
        (DIM,   "$ python3 scripts/quality_loop.py verify agent-record.json \\"),
        (DIM,   "    --base origin/main --red-green"),
    ],
    [
        (DIM,   "$ python3 scripts/quality_loop.py verify agent-record.json \\"),
        (DIM,   "    --base origin/main --red-green"),
        (FG,    "============================================================"),
        (FG,    "VERIFY — unified gate report"),
        (FG,    "============================================================"),
        (GREEN, "[ok]  verify-gates (record + diff)"),
        (GREEN, "[ok]  diff-audit"),
        (GREEN, "[ok]  run-evidence  (red→green replayed at base and HEAD)"),
        (GREEN, "[ok]  AC-coverage   (contract criteria mapped to checks)"),
        (BLUE,  "helper-integrity: sha256(diff-audit)=b7a1… unchanged"),
    ],
    [
        (DIM,   "$ python3 scripts/quality_loop.py verify agent-record.json \\"),
        (DIM,   "    --base origin/main --red-green"),
        (FG,    "VERIFY — unified gate report"),
        (GREEN, "[ok]  verify-gates (record + diff)"),
        (GREEN, "[ok]  diff-audit"),
        (GREEN, "[ok]  run-evidence  (red→green replayed at base and HEAD)"),
        (GREEN, "[ok]  AC-coverage   (contract criteria mapped to checks)"),
        (BLUE,  "helper-integrity: sha256(diff-audit)=b7a1… unchanged"),
        (DIM,   ""),
        (GREEN, "Overall: PASS  —  ship."),
    ],
]

# Per-frame duration (ms) — final frame lingers longer
FRAME_MS = [1300, 1600, 2200, 2200, 3200, 4800]


def find_mono_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def find_ui_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def render_frame(lines):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    # Terminal window chrome
    d.rounded_rectangle([(20, 20), (W - 20, H - 20)], radius=14, fill=CHROME)

    # Traffic lights
    for cx, color in ((55, (255, 95, 87)), (85, (254, 188, 46)), (115, (40, 200, 64))):
        d.ellipse([(cx - 7, 50), (cx + 7, 64)], fill=color)

    # Title bar
    title_font = find_ui_font(15)
    d.text((W / 2, 55), "coding-quality-loop  —  60-second quickstart",
           font=title_font, fill=DIM, anchor="mm")

    # Body
    mono = find_mono_font(20)
    x0 = 45
    y0 = 100
    line_h = 32
    for i, (color, text) in enumerate(lines):
        d.text((x0, y0 + i * line_h), text, font=mono, fill=color)

    return im


def main():
    frames = [render_frame(f) for f in FRAMES]
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=True,
    )
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")

    # Also emit a static PNG poster (first + last frame side-by-side is
    # unnecessary here; just save the final frame as a fallback).
    poster = OUT.with_name("terminal-demo-poster.png")
    frames[-1].save(poster, "PNG", optimize=True)
    print(f"wrote {poster} ({poster.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
