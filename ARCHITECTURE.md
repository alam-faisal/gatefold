# gatefold architecture

How the package is laid out, what each piece does, and why the layout and
text-fitting code is shaped the way it is. Read this before changing
anything in `_fit_text` or `plot_circuit`'s draw loop — most of the
non-obvious code there exists to keep a large diagram fast.

## Module layout

```
src/gatefold/
├── __init__.py   public API re-exports only, plus __version__
├── style.py      colors and typography: StyleSpec, Palette, etc.
└── core.py       data model (Item, Layer), layout, text fitting, plot_circuit.
```

Consumer adapters (datacraft, Qaravan, …) import from
`gatefold` only, never from `gatefold.core` / `gatefold.style`.

`__version__` comes from installed package metadata
(`importlib.metadata.version`), so the version lives in `pyproject.toml`.

## Data model

```python
Item(qubits: tuple[str, ...], label: str, style: str = "default")
Layer(items: list[Item])
```

An `Item` is one drawable thing on one or more qubit rows. `style` is an
opaque key into a `Palette`. A `Layer` is a
group of items drawn together, with a dashed barrier after it (except the
last).

`Layer.items` need **not** be mutually non-conflicting. Items touching the
same qubit are packed into consecutive columns inside the layer, with no
barrier between them, **in the order given**.

## Layout pipeline

`plot_circuit` runs three stages before drawing anything:

1. **Qubit ordering** (`_default_qubit_order`) — when every label parses as
   an `int`, sort numerically; otherwise lexicographically. Integer-indexed
   qubits are the common case, and a string sort puts `"10"`
   between `"1"` and `"2"`.

2. **Span computation** (`_span`) — the rows an item *visually* crosses,
   inclusive. A connector between rows 0 and 2 occupies row 1 as well, even
   though qubit 1 is not one of its qubits, because the line is drawn
   through it. Collision detection operates on this visual span, not on
   `item.qubits`.

3. **Column assignment** (`_assign_columns`, per layer) — each item goes in
   the earliest column consistent with every qubit in its span: one past
   the latest column any of those qubits was last placed in.

   ```
   next_free: dict[qubit, int]
   col = max(next_free.get(q, 0) for q in span)
   next_free[q] = col + 1  for every q in span
   ```

   This is **exactly the ASAP schedule** on the conflict DAG (`u → v` when
   `u` precedes `v` in the layer and their spans intersect). For a fixed
   qubit `q`, the items whose span covers `q` get strictly increasing
   columns, so `q`'s most recent user is also its highest-column user, and
   `max_{q ∈ span(v)} next_free[q] = max_{u ∈ pred(v)} (col(u) + 1)` — the
   ASAP recurrence. It is exact rather than a heuristic: columns are
   unbounded and the order is given, so nothing is arbitrated.

   ASAP scheduling is done within each layer. An item never slides left past a barrier even
   when its qubits are free on the other side.

   The mechanism is a per-resource next-free-slot scheduler, not
   interval-graph coloring by lowest available index. Scanning columns in
   index order reuses an early column whenever that column's own reservation
   set misses the item's span, even if a qubit the item needs was used more
   recently elsewhere, placing the item left of where it can run. Tracking
   next-free per qubit avoids this: a qubit's most recent use determines when
   it is next available, whichever column that use landed in.
   `test_assign_columns_tracks_most_recent_conflict_not_just_column_history`
   covers the five-item case where the two differ.

   It is also cheaper: O(n · |span|) rather than the O(n²) set-intersection
   scan.

`_pack_layers` then walks the layers, laying each one out at `x` and
advancing `x` by `max(layer_width, 1)`, plus one unit of gap with a barrier
line in it between consecutive layers. It returns `(placed, barrier_xs,
total_width)` where `placed` is `[(x, Item), …]` in absolute data
coordinates.

**Coordinate convention**: row `r` is drawn at `y = -r`, so qubit 0 is at
the top and rows descend. `x` is in units of one column. Nothing is
rescaled afterwards — data coordinates *are* the layout grid, which is what
lets `_fit_text` reason about box sizes in data units and convert to pixels
with a single `transData` call.

## Text fitting

The goal: every label ends up inside its box, at the largest readable font
size, wrapping onto more lines rather than shrinking too much.

The constraint: doing this the direct way is way too slow.

### Costs

**1. `fig.canvas.draw()` is not O(1).**

Text measurement needs a renderer, and the obvious way to get one is
`fig.canvas.draw()` followed by `get_renderer()`. But a fresh `draw()`
re-renders *every artist already on the axes*. Calling it once per item
inside the draw loop makes item `k` cost O(k), so the loop as a whole
becomes O(n²) in the number of items. Measured on a 240-item diagram: 0.22 s
as it stands, 5.5 s with a draw per item.

The fix: `plot_circuit` calls `ax.figure.canvas.draw()` **exactly once**,
before the draw loop, grabs the renderer, and threads it into every
`_fit_text` call. `_fit_text` takes `renderer` as a parameter and never
draws the canvas itself.

**2. Measuring a mathtext string is far more expensive than rendering it.**

Profiling the auto-fit search found the *search* costing several times more
than the actual text rendering. Each distinct mathtext string handed to the
renderer sends matplotlib's `font_manager` off to score every installed
system font — slow on a machine with many fonts, and evidently not fully
amortized by matplotlib's own cache across distinct short strings within a
process. A shrink loop that re-measures candidate strings at 10.0, 9.5,
9.0, … is therefore dominated by font lookup.

The fix: **measure once per item, estimate everything else.**

```
probe = ax.text(..., text, fontsize=base_fs, alpha=0)   # invisible probe
ref_bbox = probe.get_window_extent(renderer=renderer)   # the only measurement
px_per_char_ref = ref_bbox.width / total_estimated_chars
line_height_ref = ref_bbox.height
```

Every candidate font size thereafter uses `scale = fs / base_fs` and
linearly scaled widths — no further renderer calls at all. The probe is
`remove()`d when the search finishes.

Text width is treated as proportional to a **visible-glyph count**
(`_estimate_char_count`), calibrated against that single real measurement:

- `_LATEX_COMMAND` (`\dagger`, `\uparrow`, …) → collapsed to one glyph.
  `\dagger` renders as one symbol, not seven letters.
- `_LATEX_STRUCTURAL` (`$ ^ _ { }`) → zero width. The markup itself draws
  nothing; its operand is counted separately by the same pass.

This is deliberately approximate.

### The search itself

`_fit_text` combines shrinking and wrapping in one loop rather than
shrinking a single line all the way to the floor and only then wrapping:

```
for fs in base_fs, base_fs - 0.5, …:
    widths ← token glyph counts × px_per_char_ref × (fs / base_fs)
    lines, widest ← _pack_by_width(tokens, widths, budget = 0.92 · box_w_px)
    height ← line_height_ref · (fs / base_fs) · 1.2 · len(lines)
    accept if widest ≤ 0.92 · box_w_px and height ≤ 0.85 · box_h_px
    accept unconditionally at fs ≤ min_fs
```

The `0.92` / `0.85` factors are inner padding: text that exactly touches
the box edge looks wrong even though it technically fits. The `1.2` is
line spacing.

Because the same `0.92 · box_w_px` is both the packing budget and the
width acceptance test, the width check can only fail when a *single token*
is wider than the budget — i.e. an unsplittable long word or one atomic
`$…$` span. Everything else is resolved by the packer adding a line, and
the loop then only has to decide whether the resulting stack of lines is
too tall. That is the mechanism by which long labels grow lines instead of
shrinking to 5pt.

Tokenization (`_WRAP_TOKEN = r"\$[^$]*\$|\S+"`) makes a `$…$` span
**atomic**: it is never split mid-formula even though it may contain
spaces. Everything else wraps at whitespace like ordinary text.

`_pack_by_width` returns the widest line's width alongside the lines. The
caller already holds per-token widths, so this comes for free and avoids a
measurement of the joined string.

Multi-qubit items get the same treatment with `connector_label_width`
(default 1.6 data units) as the width budget, since their label sits beside
the connector rather than inside a box.

## Drawing and visual detail

`plot_circuit`'s draw loop, in order: wires and row labels, then each
placed item, then barriers. Visual stacking is controlled by explicit
`zorder`, not by draw order:

| zorder | artists |
|---|---|
| 0 | qubit wires, barrier lines |
| 1 | box drop shadow, multi-qubit connector line |
| 2 | gate box, connector row markers |
| 3 | all label text |

Visual details:

- **Drop shadow** — a second `FancyBboxPatch`, identical geometry, offset
  by `(+0.025, -0.025)` data units, `facecolor="black"`, `alpha=0.08`,
  `linewidth=0`. Enough to lift the box off the wire, not enough to read as
  a shadow.
- **Corner radius scales with the box** — `rounding_size = 0.22 · box_h`,
  so changing `box_size` keeps the corner proportion rather than making
  small boxes look over-rounded.
- **Connector markers punch out of the line** — each row marker is a circle
  filled with the style color and stroked in `white`, drawn at zorder 2
  over the zorder 1 connector line. The white ring separates marker from
  line without a second color in the palette.
- **Round caps** — wires and connectors use `solid_capstyle="round"` so
  line ends do not read as blunt rectangles at the diagram's scale.
- **Barriers** — dashed `(0, (4, 3))`, 1.1pt, in `#9AA1A9`. That grey is
  darker than the wire's `#C7CCD1`; the dash pattern, not the colour, is what
  keeps a barrier from competing with the gates.
- **Axes are invisible** — `ax.axis("off")`, with `xlim` starting at `-1.3`
  to leave a gutter for row labels and `ylim` padded 0.8 on each side.
- **Default figsize** scales with content: `(max(6, total_width · 1.1),
  max(2.5, n_qubits · 0.65 + 1))`.

### Palette

`DEFAULT_PALETTE` samples the `plasma` colormap at fractions 0.15 / 0.5 /
0.8 for the `default` / `single` / `multi` style keys. plasma spans dark
purple to bright yellow, so label color cannot be a constant: `_readable_text`
picks black or white per swatch by relative luminance
(`0.299 R + 0.587 G + 0.114 B > 0.6`). Swapping in house colors means
replacing the `Palette`, and the same helper keeps labels readable.

`Palette.get` falls back to the `"default"` entry for unknown style keys —
so an adapter emitting a style gatefold has never seen renders rather than
raising.

### Typography

`set_clean_rcparams()` sets four global matplotlib rcParams. Nothing in
gatefold calls it; the consumer calls it, and it then applies to every plot
made in that process, not only gatefold's.

| rcParam | matplotlib default | set to | effect |
|---|---|---|---|
| `mathtext.fontset` | `dejavusans` | `cm` | `$…$` expressions render in Computer Modern |
| `font.family` | `sans-serif` | `sans-serif` | no change from stock matplotlib; matters only if the consumer set something else first |
| `font.sans-serif` | 11-name list | `Helvetica`, `Arial`, `DejaVu Sans` | candidates for non-math text, first installed name wins; DejaVu Sans ships with matplotlib, so the list always resolves |
| `axes.linewidth` | `0.8` | `0.0` | no effect on gatefold output, which calls `ax.axis("off")`; applies to other axes in the session |

For a gatefold diagram the visible change is therefore: text inside `$…$` in
Computer Modern, text outside it in Helvetica or Arial when either is
installed.

## Tests

`tests/test_layout.py` covers column assignment, span calculation, qubit
ordering, token packing, and the shrink/wrap search. **These test layout
arithmetic, not visual correctness**.

`tests/test_plot_circuit.py` is a smoke suite: `plot_circuit` returns an
`Axes` for single-qubit circuits, multi-qubit connectors, and the empty
layer list, and the qubit-ordering and label-wrapping behavior survives end
to end. **It does not compare pixels**, so a regression that changes
rendering without changing artist counts or text content will pass.

`tests/conftest.py` selects the `Agg` backend, which renders into an
in-memory buffer, so the suite needs no display.

## Try not to change

If you change this code, these are the things that will cost you
either speed or correctness:

1. `fig.canvas.draw()` is called **once** per `plot_circuit`, outside the
   item loop. Never inside `_fit_text`.
2. `_fit_text` makes **one** `get_window_extent` call per item. Every other
   width in the search is derived arithmetically.
3. Column assignment tracks next-free-slot **per qubit**, never per column.
4. `$…$` spans stay atomic through tokenization.
5. `Layer.items` is never reordered.
