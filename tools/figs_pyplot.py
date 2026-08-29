"""PDF figures for the wave-consensus paper, matplotlib (pyplot) edition.

Charted's column charts mis-scale capped axes (see charted bug ticket filed
2026-08-29: y_range=(0,0.25) renders against a (0,1) domain because
calculate_axis_dimensions ceil()s max<=1, and column gridlines land at
bar-slot centres instead of value positions). Pyplot gives exact control.

Regenerates all three paper/figures/*.png at the exact previous pixel
sizes (fig1 1520x880, fig2/fig3 1400x880) so paper_pdf.py is untouched.

Usage (any python with matplotlib):
  .venv/bin/python tools/figs_pyplot.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "paper/figures"

BLUE = "#3b6fb5"
GRID = "#e3e3e3"
TITLE = "#222222"
SUBT = "#555555"
TXT = "#333333"


def style_ax(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.tick_params(colors=TXT, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.margins(x=0.04)


def head(fig: plt.Figure, title: str, subtitle: str) -> None:
    fig.text(0.08, 0.945, title, ha="left", va="top",
             fontsize=13, fontweight="bold", color=TITLE)
    fig.text(0.08, 0.895, subtitle, ha="left", va="top",
             fontsize=9.5, color=SUBT)


def fig1() -> None:
    vals = [0.20289, 0.17534, 0.18140, 0.15385, 0.18571, 0.15816]
    labs = ["RI\ncontent", "RI\nfull", "VO\ncontent", "VO\nfull",
            "base\ncontent", "base\nfull"]
    fig, ax = plt.subplots(figsize=(7.6, 4.4), dpi=200)
    fig.subplots_adjust(left=0.09, right=0.98, top=0.84, bottom=0.16)
    head(fig, "Calibrated delta over the frozen bar, all six pre-registered cells",
         "delta (nats); dashed line = pre-registered GO threshold 0.02")
    bars = ax.bar(range(6), vals, width=0.62, color=BLUE, alpha=0.9, zorder=3)
    ax.set_xticks(range(6), labs)
    ax.set_ylim(0, 0.25)
    ax.set_yticks([0, 0.05, 0.10, 0.15, 0.20, 0.25])
    style_ax(ax)
    ax.axhline(0.02, color="#b3402a", linestyle="--", linewidth=1.2, zorder=4)
    ax.text(5.42, 0.024, "GO threshold 0.02", fontsize=8, color="#b3402a",
            ha="right", va="bottom")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.004, f"{v:.3f}",
                ha="center", va="bottom", fontsize=8.5, color=TXT)
    fig.savefig(OUT / "fig1-cells.png")
    plt.close(fig)


def fig2() -> None:
    vals = [0.9561, 2.8714, 1.0]
    labs = ["Jury RI panel\n(4 x 4B)", "Jury full\n12-config", "27B\nself-review"]
    fig, ax = plt.subplots(figsize=(7.0, 4.4), dpi=200)
    fig.subplots_adjust(left=0.09, right=0.98, top=0.84, bottom=0.16)
    head(fig, "Verification route cost relative to the 27B self-review route",
         "USD per 8,000-proposition run; 27B self-review = 1.00x")
    bars = ax.bar(range(3), vals, width=0.5, color=BLUE, alpha=0.9, zorder=3)
    ax.set_xticks(range(3), labs)
    ax.set_ylim(0, 3.15)
    style_ax(ax)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.05, f"{v:.2f}x",
                ha="center", va="bottom", fontsize=9, color=TXT)
    fig.savefig(OUT / "fig2-cost.png")
    plt.close(fig)


def fig3() -> None:
    vals = [0.3396, 0.3419]
    labs = ["Jury-gated\n(WCT-EM ri)", "27B self-review\ngated"]
    fig, ax = plt.subplots(figsize=(7.0, 4.4), dpi=200)
    fig.subplots_adjust(left=0.09, right=0.98, top=0.84, bottom=0.16)
    head(fig, "False-claim rate by verification route",
         "both routes co-fail the same two claims; CI of the route difference spans zero")
    bars = ax.bar(range(2), vals, width=0.42, color=BLUE, alpha=0.9, zorder=3)
    ax.set_xticks(range(2), labs)
    ax.set_ylim(0, 0.4)
    ax.set_yticks([0, 0.1, 0.2, 0.3, 0.4])
    style_ax(ax)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.008, f"{v:.4f}%",
                ha="center", va="bottom", fontsize=9, color=TXT)
    fig.savefig(OUT / "fig3-fcr.png")
    plt.close(fig)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    for f in sorted(OUT.iterdir()):
        print(f.name, f.stat().st_size)
