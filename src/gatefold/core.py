from __future__ import annotations

from dataclasses import dataclass

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

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
    """A set of Items packed ASAP; a barrier is drawn after unless it's the last layer."""

    items: list[Item]


# --------------------------------------------------------------------------
# Layout: greedy interval coloring + ASAP packing
# --------------------------------------------------------------------------


def _greedy_color(items: list, span_of) -> list[int]:
    """Assign each item the smallest column index whose reservation doesn't
    overlap its span. O(n^2) but n per layer is always small for circuit diagrams.
    """
    cols: list[set[str]] = []
    assigned = []
    for item in items:
        span = set(span_of(item))
        for c, taken in enumerate(cols):
            if not (taken & span):
                taken |= span
                assigned.append(c)
                break
        else:
            cols.append(set(span))
            assigned.append(len(cols) - 1)
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
    placed: list[tuple[float, Item]] = []
    barrier_xs: list[float] = []
    x = 0.0
    for i, layer in enumerate(layers):
        spans = [_span(it.qubits, row_of, qubit_labels) for it in layer.items]
        cols = _greedy_color(list(zip(layer.items, spans)), lambda pair: pair[1])
        for it, col in zip(layer.items, cols):
            placed.append((x + col, it))
        width = max((c + 1 for c in cols), default=0)
        x += max(width, 1)
        if i != len(layers) - 1:
            barrier_xs.append(x)
            x += 1.0
    return placed, barrier_xs, x


# --------------------------------------------------------------------------
# Text fitting
# --------------------------------------------------------------------------


def _fit_fontsize(ax, text: str, box_w_data: float, box_h_data: float, base_fs: float, min_fs: float = 5.0) -> float:
    """Shrink fontsize until the rendered text fits inside the box (in data coords)."""
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    p0 = ax.transData.transform((0, 0))
    p1 = ax.transData.transform((box_w_data, box_h_data))
    box_w_px, box_h_px = abs(p1[0] - p0[0]), abs(p1[1] - p0[1])

    probe = ax.text(0, 0, text, fontsize=base_fs, ha="center", va="center", alpha=0)
    fs = base_fs
    while fs > min_fs:
        probe.set_fontsize(fs)
        bbox = probe.get_window_extent(renderer=renderer)
        if bbox.width <= box_w_px * 0.92 and bbox.height <= box_h_px * 0.85:
            break
        fs -= 0.5
    probe.remove()
    return fs


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------


def plot_circuit(
    layers: list[Layer],
    qubit_labels: list[Qubit] | None = None,
    qubit_display: dict[Qubit, str] | None = None,
    palette: Palette = DEFAULT_PALETTE,
    ax: plt.Axes | None = None,
    figsize: tuple[float, float] | None = None,
    box_size: tuple[float, float] = (0.8, 0.7),
    base_fontsize: float = 10.0,
) -> plt.Axes:
    """Plot a list of Layers. Single-qubit items draw as rounded boxes;
    multi-qubit items draw as a connector line with a marker per touched row.
    """
    if qubit_labels is None:
        qubit_labels = sorted({q for layer in layers for it in layer.items for q in it.qubits}, key=str)
    row_of = {q: i for i, q in enumerate(qubit_labels)}

    placed, barrier_xs, total_width = _pack_layers(layers, qubit_labels, row_of)

    if figsize is None:
        figsize = (max(6.0, total_width * 1.1), max(2.5, len(qubit_labels) * 0.65 + 1))
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    ax.set_xlim(-1.3, total_width - 0.3)
    ax.set_ylim(-(len(qubit_labels) - 1) - 0.8, 0.8)
    ax.axis("off")

    # wires
    for row, q in enumerate(qubit_labels):
        y = -row
        ax.plot([-0.5, total_width - 0.5], [y, y], color=palette.wire, lw=1.2, zorder=0, solid_capstyle="round")
        ax.text(-0.85, y, (qubit_display or {}).get(q, q), ha="right", va="center", fontsize=9.5)

    box_w, box_h = box_size

    for x, item in placed:
        style = palette.get(item.style)
        rows = sorted(row_of[q] for q in item.qubits)

        if len(rows) <= 1:
            y = -rows[0]
            fs = _fit_fontsize(ax, item.label, box_w, box_h, base_fontsize)
            # subtle drop shadow for depth, then the box itself
            ax.add_patch(
                mpatches.FancyBboxPatch(
                    (x - box_w / 2 + 0.025, y - box_h / 2 - 0.025),
                    box_w,
                    box_h,
                    boxstyle=f"round,pad=0.02,rounding_size={box_h * 0.22}",
                    facecolor="black",
                    alpha=0.08,
                    linewidth=0,
                    zorder=1,
                )
            )
            ax.add_patch(
                mpatches.FancyBboxPatch(
                    (x - box_w / 2, y - box_h / 2),
                    box_w,
                    box_h,
                    boxstyle=f"round,pad=0.02,rounding_size={box_h * 0.22}",
                    facecolor=style.fill,
                    edgecolor=style.edge,
                    linewidth=0,
                    zorder=2,
                )
            )
            ax.text(x, y, item.label, ha="center", va="center", fontsize=fs, color=style.text, zorder=3)
        else:
            y_top, y_bot = -rows[0], -rows[-1]
            ax.plot([x, x], [y_top, y_bot], color=style.fill, lw=1.6, zorder=1, solid_capstyle="round")
            for row in rows:
                ax.add_patch(plt.Circle((x, -row), 0.15, facecolor=style.fill, edgecolor="white", lw=1.0, zorder=2))
            fs = _fit_fontsize(ax, item.label, 1.6, box_h, base_fontsize)
            ax.text(x + 0.28, (y_top + y_bot) / 2, item.label, ha="left", va="center", fontsize=fs, zorder=3)

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
