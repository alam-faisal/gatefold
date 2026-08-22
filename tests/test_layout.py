"""Layout unit tests: column assignment, span calculation, qubit ordering, and text
wrapping -- not visual correctness."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from gatefold.core import (
    Item,
    Layer,
    _default_qubit_order,
    _fit_text,
    _greedy_color,
    _pack_layers,
    _span,
    _tokenize_for_wrap,
    _wrap_tokens,
)


def test_greedy_color_overlapping_spans_get_different_columns():
    # both items touch qubit "b" -> can't share a column
    items = ["a-b", "b-c"]
    spans = {"a-b": {"a", "b"}, "b-c": {"b", "c"}}
    cols = _greedy_color(items, lambda it: spans[it])
    assert cols == [0, 1]


def test_greedy_color_disjoint_spans_share_a_column():
    # disjoint qubit sets -> both fit in column 0
    items = ["a", "c"]
    spans = {"a": {"a"}, "c": {"c"}}
    cols = _greedy_color(items, lambda it: spans[it])
    assert cols == [0, 0]


def test_span_single_qubit():
    row_of = {"q0": 0, "q1": 1, "q2": 2}
    labels = ["q0", "q1", "q2"]
    assert _span(("q1",), row_of, labels) == ("q1",)


def test_span_adjacent_rows():
    row_of = {"q0": 0, "q1": 1, "q2": 2}
    labels = ["q0", "q1", "q2"]
    assert _span(("q0", "q1"), row_of, labels) == ("q0", "q1")


def test_span_non_adjacent_rows_includes_rows_in_between():
    # a connector between q0 and q2 visually crosses q1 too, so it must
    # block q1's column even though q1 isn't one of the item's qubits
    row_of = {"q0": 0, "q1": 1, "q2": 2}
    labels = ["q0", "q1", "q2"]
    assert _span(("q0", "q2"), row_of, labels) == ("q0", "q1", "q2")


def test_span_empty_qubits():
    row_of = {"q0": 0}
    labels = ["q0"]
    assert _span((), row_of, labels) == ()


def test_pack_layers_overlapping_items_advance_x_by_layer_width():
    # two overlapping single-qubit items in one layer land in separate
    # columns of that layer, so the layer's width is 2, not 1
    labels = ["q0"]
    row_of = {"q0": 0}
    layers = [Layer(items=[Item(("q0",), "A"), Item(("q0",), "B")])]
    placed, barrier_xs, total_width = _pack_layers(layers, labels, row_of)
    xs = sorted(x for x, _ in placed)
    assert xs == [0.0, 1.0]
    assert barrier_xs == []  # no barrier after the last layer
    assert total_width == 2.0


def test_pack_layers_inserts_barrier_between_non_final_layers():
    labels = ["q0"]
    row_of = {"q0": 0}
    layers = [
        Layer(items=[Item(("q0",), "A")]),
        Layer(items=[Item(("q0",), "B")]),
    ]
    placed, barrier_xs, total_width = _pack_layers(layers, labels, row_of)
    assert barrier_xs == [1.0]
    assert total_width == 3.0  # 1 (layer A) + 1 (barrier gap) + 1 (layer B)


def test_default_qubit_order_sorts_numeric_labels_by_value():
    # catches the "10" < "2" bug a plain lexicographic sort produces
    assert _default_qubit_order({"0", "1", "2", "9", "10", "11"}) == ["0", "1", "2", "9", "10", "11"]


def test_default_qubit_order_falls_back_to_lexicographic_for_non_numeric_labels():
    assert _default_qubit_order({"qb", "qa"}) == ["qa", "qb"]


def test_tokenize_for_wrap_splits_plain_words():
    assert _tokenize_for_wrap("hello world") == ["hello", "world"]


def test_tokenize_for_wrap_keeps_mathtext_span_atomic():
    # a $...$ span must never be split mid-formula, even though it contains a space
    assert _tokenize_for_wrap(r"$a + b$ world") == [r"$a + b$", "world"]


def test_wrap_tokens_splits_when_a_line_would_exceed_max_width():
    _, ax = plt.subplots()
    probe = ax.text(0, 0, "", fontsize=10, alpha=0)
    ax.figure.canvas.draw()
    # first measure the width of all four tokens on one line, then force a wrap
    # by giving _wrap_tokens a budget narrower than that
    renderer = ax.figure.canvas.get_renderer()
    probe.set_text("aaaa bbbb cccc dddd")
    full_width = probe.get_window_extent(renderer=renderer).width
    lines = _wrap_tokens(probe, ["aaaa", "bbbb", "cccc", "dddd"], full_width * 0.6)
    assert len(lines) > 1
    plt.close(ax.figure)


def test_wrap_tokens_keeps_a_single_line_when_it_already_fits():
    _, ax = plt.subplots()
    probe = ax.text(0, 0, "", fontsize=10, alpha=0)
    ax.figure.canvas.draw()
    lines = _wrap_tokens(probe, ["short"], max_width_px=10_000)
    assert lines == ["short"]
    plt.close(ax.figure)


def test_fit_text_wraps_long_text_instead_of_shrinking_past_the_floor():
    # a label far too long for a small box, at a high floor, must come back
    # wrapped onto multiple lines rather than shrunk to a single tiny line
    _, ax = plt.subplots()
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 5)
    long_label = "a very long label that will not fit on one line at any reasonable size"
    wrapped, fs = _fit_text(ax, long_label, box_w_data=1.0, box_h_data=2.0, base_fs=12.0, min_fs=8.0)
    assert "\n" in wrapped
    assert fs >= 8.0
    plt.close(ax.figure)


def test_fit_text_keeps_short_text_on_one_line_at_base_fontsize():
    _, ax = plt.subplots()
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 5)
    wrapped, fs = _fit_text(ax, "H", box_w_data=0.8, box_h_data=0.7, base_fs=10.0, min_fs=5.0)
    assert wrapped == "H"
    assert fs == 10.0
    plt.close(ax.figure)
