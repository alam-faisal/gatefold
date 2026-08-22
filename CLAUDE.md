# gatefold

A lightweight, framework-agnostic Python package for drawing clean quantum
circuit diagrams with matplotlib. No qiskit/cirq dependency — the only
input vocabulary is `Item` (something drawn on one or more qubit rows)
grouped into `Layer`s. Projects with their own circuit representation
(datacraft, Qaravan, whatever) write a small adapter that converts their
objects into `list[Layer]` and hand it to `plot_circuit`.

The core layout/drawing logic already exists in `gatefold.py` in this
directory (packing algorithm, box/connector drawing, text auto-fit,
mathtext labels, a considered default palette). The job here is to turn
that single file into a proper installable, PyPI-published package called
`gatefold`, with no change to its actual behavior.

## Conventions (follow these throughout)

- **Python style**: type hints everywhere; minimal docstrings (one line +
  non-obvious args only, no boilerplate); functional by default, classes
  only when state genuinely warrants it (dataclasses for data are fine);
  short functions.
- **Package manager**: `uv`. Use `uv add`, `uv build`, `uv publish` —
  never raw `pip`/`twine` unless uv can't do it.
- **Build backend**: `hatchling`, via `pyproject.toml`. Src layout:
  `src/gatefold/`.
- **Testing**: every new function that touches geometry/layout (packing,
  span calculation, text fitting) needs a test. State plainly in a comment
  or commit message what each test catches and what it doesn't — e.g. "this
  checks column assignment for overlapping spans, not visual correctness."
- **No behavior changes** during the packaging refactor. This is a
  mechanical split of one file into a package; if you spot an actual bug
  or improvement, note it in TODO.md rather than fixing it inline, so the
  refactor commit stays reviewable as a pure move.

## Target structure

```
gatefold/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
├── src/
│   └── gatefold/
│       ├── __init__.py      # public API re-exports only
│       ├── core.py          # Item, Layer, layout (_pack_layers, _greedy_color, _span), plot_circuit, _fit_fontsize
│       └── style.py         # StyleSpec, Palette, DEFAULT_PALETTE, set_clean_rcparams
└── tests/
    ├── test_layout.py       # _greedy_color, _span, _pack_layers
    └── test_plot_circuit.py # smoke test: plot_circuit runs and returns an Axes for a few representative layer configs
```

Split `gatefold.py`'s contents along the `core.py` / `style.py` line drawn
above — `style.py` has zero matplotlib-plotting logic, only data +
rcParams; `core.py` imports from `style.py`.

`__init__.py` should expose exactly: `Item`, `Layer`, `Palette`,
`StyleSpec`, `DEFAULT_PALETTE`, `plot_circuit`, `set_clean_rcparams`. This
is the whole public surface — adapters in consumer repos (datacraft,
Qaravan) import only from here, never from `core`/`style` directly.

## Dependencies

Runtime: `matplotlib` only. Dev: `pytest`, `hatchling` (build-time, not a
runtime dep).

## Out of scope for this pass

- No CLI.
- No adapters for datacraft or Qaravan — those live in their own repos and
  depend on `gatefold` once it's published, they don't live inside it.
- No docs site; README.md carries the usage example.
