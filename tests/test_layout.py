"""Layout unit tests: column assignment and span calculation, not visual correctness."""

from gatefold.core import Item, Layer, _greedy_color, _pack_layers, _span


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
