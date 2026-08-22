# TODO

Work through in order. Check off as you go.

## 1. Scaffolding
- [ ] Create `src/gatefold/`, `tests/`, move nothing yet.
- [ ] `pyproject.toml`: name `gatefold`, `build-system` = hatchling,
      `dependencies = ["matplotlib>=3.7"]`, `requires-python = ">=3.10"`
      (needed for `X | Y` union syntax already used in the source).
      Include `[project.optional-dependencies] dev = ["pytest"]`.
- [ ] `.gitignore` for Python (`__pycache__`, `*.egg-info`, `dist/`,
      `.venv`, etc.)
- [ ] `LICENSE` — ask which license before picking one (MIT is the
      default assumption if no answer, but confirm).
- [ ] `git init`, first commit of scaffolding only.

## 2. Split gatefold.py into the package
- [ ] Create `src/gatefold/style.py`: move `StyleSpec`, `Palette`,
      `DEFAULT_PALETTE`, `set_clean_rcparams`.
- [ ] Create `src/gatefold/core.py`: move `Item`, `Layer`,
      `_greedy_color`, `_span`, `_pack_layers`, `_fit_fontsize`,
      `plot_circuit`. Import style objects from `.style`.
- [ ] Create `src/gatefold/__init__.py` re-exporting the public API
      listed in CLAUDE.md, plus `__version__`.
- [ ] Delete the old top-level `gatefold.py` once its contents are fully
      accounted for — diff the two to make sure nothing was dropped.
- [ ] `uv sync` and confirm `python -c "import gatefold"` works.

## 3. Tests
- [ ] `tests/test_layout.py`: unit tests for `_greedy_color` (overlapping
      vs. disjoint spans land in different/same columns) and `_span`
      (multi-row span calculation, including the non-adjacent-rows case).
- [ ] `tests/test_plot_circuit.py`: smoke tests that `plot_circuit` runs
      without error and returns a `matplotlib.axes.Axes` for: a
      single-qubit-only circuit, a circuit with a multi-qubit connector,
      and an empty layer list (edge case — decide what should happen here
      and assert it explicitly rather than just "doesn't crash").
- [ ] `uv run pytest` green.

## 4. README
- [ ] Short usage example building a couple of `Layer`/`Item` objects and
      calling `plot_circuit`, mirroring the demo already used to validate
      the design (see chat history / prior render if available).
- [ ] One line on the adapter pattern: "gatefold has no opinion on your
      circuit representation — write a ~20-line function converting your
      objects into `list[Layer]`."
- [ ] Install instructions: `pip install gatefold` / `uv add gatefold`.

## 5. Build and publish
- [ ] `uv build` — confirm `dist/` contains both a wheel and sdist.
- [ ] Create a PyPI account if one doesn't exist yet; generate an API
      token scoped to the whole account (first publish only).
- [ ] `uv publish` — if it prompts for credentials, use `__token__` as
      username and the API token as password, or set
      `UV_PUBLISH_TOKEN` in the environment.
- [ ] Confirm the listing renders correctly at
      `https://pypi.org/project/gatefold/` (README renders, metadata
      correct).
- [ ] Tag the release in git (`v0.1.0`) matching the version in
      `pyproject.toml`.

## 6. Nice-to-haves (only after 1–5 are done and working)
- [ ] GitHub Actions workflow to build + publish on tag push, using PyPI
      Trusted Publishing (OIDC) instead of a stored API token.
- [ ] `CHANGELOG.md`.
