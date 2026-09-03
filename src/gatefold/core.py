from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.axes import Axes
from matplotlib.backend_bases import RendererBase

from .style import Palette, DEFAULT_PALETTE

# --------------------------------------------------------------------------
# Public data model
# --------------------------------------------------------------------------

Qubit = str


@dataclass(frozen=True)
class Item:
    """One drawable thing: a gate, a term, whatever. `style` keys into a Palette."""

    qubits: tuple[Qubit, ...]
    label: str
    style: str = "default"


@dataclass(frozen=True)
class Layer:
    """A set of Items packed ASAP; a barrier is drawn after unless it's the last layer.

    Items may conflict: several touching the same qubit are packed into consecutive columns,
    with no barrier between them, in the order given. That order is a precondition -- items
    sharing a qubit must appear here in the order they need to run.
    """

    items: list[Item]


# --------------------------------------------------------------------------
# Layout: greedy list scheduling + ASAP packing
# --------------------------------------------------------------------------


def _assign_columns(spans: list[tuple[Qubit, ...]]) -> list[int]:
    """Column for each span: one past the latest column any qubit it covers was last placed
    in (0 if never placed).

    `spans` must already be in a valid execution order -- two items sharing a qubit appear in
    the order they need to run. See ARCHITECTURE.md for why availability is tracked per qubit
    rather than per column.
    """
    next_free: dict[Qubit, int] = {}
    assigned = []
    for span in spans:
        col = max((next_free.get(q, 0) for q in span), default=0)
        assigned.append(col)
        for q in span:
            next_free[q] = col + 1
    return assigned


def _span(qubits: tuple[Qubit, ...], row_of: dict[Qubit, int], qubit_labels: list[Qubit]) -> tuple[Qubit, ...]:
    """Rows an item visually crosses (inclusive), for collision purposes —
    a line between two non-adjacent rows blocks every row in between."""
    if not qubits:
        return ()
    rows = [row_of[q] for q in qubits]
    return tuple(qubit_labels[r] for r in range(min(rows), max(rows) + 1))


def _pack_layers(
    layers: list[Layer], qubit_labels: list[Qubit], row_of: dict[Qubit, int]
) -> tuple[list[tuple[float, Item]], list[float], float]:
    """Lay layers out left to right with one unit of barrier gap between consecutive layers.

    Returns (items with their absolute x, barrier x positions, total width).
    """
    placed: list[tuple[float, Item]] = []
    barrier_xs: list[float] = []
    x = 0.0
    for i, layer in enumerate(layers):
        cols = _assign_columns([_span(it.qubits, row_of, qubit_labels) for it in layer.items])
        for it, col in zip(layer.items, cols):
            placed.append((x + col, it))
        width = max((c + 1 for c in cols), default=0)
        x += max(width, 1)
        if i != len(layers) - 1:
            barrier_xs.append(x)
            x += 1.0
    return placed, barrier_xs, x


def _default_qubit_order(qubits: Iterable[Qubit]) -> list[Qubit]:
    """Sort qubit labels numerically when every one parses as an int (true for essentially
    every real backend's qubit indices), lexicographically otherwise."""
    try:
        return sorted(qubits, key=int)
    except ValueError:
        return sorted(qubits, key=str)


# --------------------------------------------------------------------------
# Text fitting: shrink-to-fit, then wrap-to-fit
# --------------------------------------------------------------------------

# A `$...$` mathtext span is atomic (never split mid-formula); anything else
# wraps at whitespace like ordinary text.
_WRAP_TOKEN = re.compile(r"\$[^$]*\$|\S+")

# For width *estimation* only (see _fit_text): a LaTeX command (\dagger, \uparrow, ...) is one
# rendered glyph, not one glyph per letter of its name; structural markup ($, ^, _, {, }) takes
# no width of its own -- its operand's width is what matters, and that operand is counted
# separately by this same pass.
_LATEX_COMMAND = re.compile(r"\\[a-zA-Z]+")
_LATEX_STRUCTURAL = re.compile(r"[$^_{}]")

# Fraction of the box the text is allowed to occupy (the remainder is inner padding), the
# spacing between wrapped lines, and the step the fontsize search shrinks by.
_TEXT_WIDTH_FRAC = 0.92
_TEXT_HEIGHT_FRAC = 0.85
_LINE_SPACING = 1.2
_FONTSIZE_STEP = 0.5


def _tokenize_for_wrap(text: str) -> list[str]:
    return _WRAP_TOKEN.findall(text)


def _estimate_char_count(text: str) -> int:
    """Rough visible-glyph count for a mathtext-ish string, for width *estimation* -- not
    a substitute for measuring when the actual rendered width matters."""
    return len(_LATEX_STRUCTURAL.sub("", _LATEX_COMMAND.sub("#", text)))


def _pack_by_width(
    tokens: list[str], widths: list[float], space_width: float, max_width_px: float
) -> tuple[list[str], float]:
    """Greedily pack tokens (with precomputed widths) into lines <= max_width_px.

    Returns (lines, widest line's width) -- the widest width comes for free from the
    per-token widths the caller already holds, so no measurement of the joined text is needed.
    """
    lines: list[str] = []
    line_widths: list[float] = []
    current: list[str] = []
    current_width = 0.0
    for tok, w in zip(tokens, widths):
        candidate_width = w if not current else current_width + space_width + w
        if current and candidate_width > max_width_px:
            lines.append(" ".join(current))
            line_widths.append(current_width)
            current, current_width = [tok], w
        else:
            current.append(tok)
            current_width = candidate_width
    if current:
        lines.append(" ".join(current))
        line_widths.append(current_width)
    return lines, (max(line_widths) if line_widths else 0.0)


def _fit_text(
    ax: Axes,
    renderer: RendererBase,
    text: str,
    box_w_data: float,
    box_h_data: float,
    base_fs: float,
    min_fs: float = 5.0,
) -> tuple[str, float]:
    """Largest fontsize in [min_fs, base_fs] at which `text`, wrapped to fit box_w_data, also
    fits box_h_data -- shrinking the font and adding lines together. Always returns something
    (the min_fs attempt is used even if it still overflows vertically).

    Two things here are load-bearing for speed, both explained in ARCHITECTURE.md: `renderer`
    is supplied by the caller rather than obtained from a canvas draw, and `text` is measured
    exactly once (at base_fs) with every candidate size's widths scaled arithmetically from
    that one measurement. Sizing is therefore deliberately approximate, not pixel-exact.
    """
    p0 = ax.transData.transform((0, 0))
    p1 = ax.transData.transform((box_w_data, box_h_data))
    box_w_px, box_h_px = abs(p1[0] - p0[0]), abs(p1[1] - p0[1])

    tokens = _tokenize_for_wrap(text)
    probe = ax.text(0, 0, text, fontsize=base_fs, ha="center", va="center", alpha=0)

    ref_bbox = probe.get_window_extent(renderer=renderer)
    token_char_counts = [_estimate_char_count(tok) for tok in tokens]
    total_chars = sum(token_char_counts) or 1
    px_per_char_ref = ref_bbox.width / total_chars
    line_height_ref = ref_bbox.height

    max_width_px = box_w_px * _TEXT_WIDTH_FRAC
    max_height_px = box_h_px * _TEXT_HEIGHT_FRAC

    fs = base_fs
    while True:
        scale = fs / base_fs
        px_per_char = px_per_char_ref * scale
        widths = [c * px_per_char for c in token_char_counts]
        lines, max_line_width = _pack_by_width(tokens, widths, px_per_char, max_width_px)
        total_height = line_height_ref * scale * _LINE_SPACING * max(len(lines), 1)
        if (max_line_width <= max_width_px and total_height <= max_height_px) or fs <= min_fs:
            wrapped = "\n".join(lines)
            break
        fs -= _FONTSIZE_STEP
    probe.remove()
    return wrapped, fs


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------

_ROW_LABEL_FONTSIZE = 9.5
_BOX_PAD = 0.02
_BOX_ROUNDING_FRAC = 0.22  # corner radius as a fraction of box height, so it scales with the box
_SHADOW_OFFSET = 0.025  # data units, down and to the right
_SHADOW_ALPHA = 0.08
_MARKER_RADIUS = 0.15  # connector's per-row marker
_CONNECTOR_LABEL_GAP = 0.28  # gap between a connector line and its label


def plot_circuit(
    layers: list[Layer],
    qubit_labels: list[Qubit] | None = None,
    qubit_display: dict[Qubit, str] | None = None,
    palette: Palette = DEFAULT_PALETTE,
    ax: Axes | None = None,
    figsize: tuple[float, float] | None = None,
    box_size: tuple[float, float] = (0.8, 0.7),
    base_fontsize: float = 10.0,
    min_fontsize: float = 5.0,
    connector_label_width: float = 1.6,
) -> Axes:
    """Plot a list of Layers. Single-qubit items draw as rounded boxes;
    multi-qubit items draw as a connector line with a marker per touched row.

    Long labels wrap across multiple lines before shrinking below min_fontsize --
    a label that doesn't fit on one line at any fontsize down to min_fontsize gets
    more lines instead of unreadably tiny text. connector_label_width is the width
    (in data units) a multi-qubit item's label is wrapped to fit, next to its connector line.
    """
    if qubit_labels is None:
        qubit_labels = _default_qubit_order({q for layer in layers for it in layer.items for q in it.qubits})
    row_of = {q: i for i, q in enumerate(qubit_labels)}

    placed, barrier_xs, total_width = _pack_layers(layers, qubit_labels, row_of)

    if figsize is None:
        figsize = (max(6.0, total_width * 1.1), max(2.5, len(qubit_labels) * 0.65 + 1))
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    ax.set_xlim(-1.3, total_width - 0.3)
    ax.set_ylim(-(len(qubit_labels) - 1) - 0.8, 0.8)
    ax.axis("off")

    # One draw for the whole figure, whose renderer every _fit_text call below then reuses.
    # A draw() per item would re-render every artist already placed, making the loop
    # quadratic in item count -- see ARCHITECTURE.md.
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()

    # wires
    for row, q in enumerate(qubit_labels):
        y = -row
        ax.plot([-0.5, total_width - 0.5], [y, y], color=palette.wire, lw=1.2, zorder=0, solid_capstyle="round")
        ax.text(-0.85, y, (qubit_display or {}).get(q, q), ha="right", va="center", fontsize=_ROW_LABEL_FONTSIZE)

    box_w, box_h = box_size
    boxstyle = f"round,pad={_BOX_PAD},rounding_size={box_h * _BOX_ROUNDING_FRAC}"

    for x, item in placed:
        style = palette.get(item.style)
        rows = sorted(row_of[q] for q in item.qubits)

        if len(rows) <= 1:
            y = -rows[0]
            wrapped, fs = _fit_text(ax, renderer, item.label, box_w, box_h, base_fontsize, min_fontsize)
            # subtle drop shadow for depth, then the box itself
            ax.add_patch(
                mpatches.FancyBboxPatch(
                    (x - box_w / 2 + _SHADOW_OFFSET, y - box_h / 2 - _SHADOW_OFFSET),
                    box_w,
                    box_h,
                    boxstyle=boxstyle,
                    facecolor="black",
                    alpha=_SHADOW_ALPHA,
                    linewidth=0,
                    zorder=1,
                )
            )
            ax.add_patch(
                mpatches.FancyBboxPatch(
                    (x - box_w / 2, y - box_h / 2),
                    box_w,
                    box_h,
                    boxstyle=boxstyle,
                    facecolor=style.fill,
                    edgecolor=style.edge,
                    linewidth=0,
                    zorder=2,
                )
            )
            ax.text(x, y, wrapped, ha="center", va="center", fontsize=fs, color=style.text, zorder=3)
        else:
            y_top, y_bot = -rows[0], -rows[-1]
            ax.plot([x, x], [y_top, y_bot], color=style.fill, lw=1.6, zorder=1, solid_capstyle="round")
            for row in rows:
                ax.add_patch(
                    plt.Circle((x, -row), _MARKER_RADIUS, facecolor=style.fill, edgecolor="white", lw=1.0, zorder=2)
                )
            wrapped, fs = _fit_text(
                ax, renderer, item.label, connector_label_width, box_h, base_fontsize, min_fontsize
            )
            ax.text(
                x + _CONNECTOR_LABEL_GAP, (y_top + y_bot) / 2, wrapped, ha="left", va="center", fontsize=fs, zorder=3
            )

    for bx in barrier_xs:
        ax.plot(
            [bx, bx],
            [0.5, -(len(qubit_labels) - 1) - 0.5],
            color=palette.barrier,
            linestyle=(0, (4, 3)),
            linewidth=1.1,
            zorder=0,
        )

    return ax
