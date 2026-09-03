"""Smoke tests: plot_circuit runs and returns an Axes. Doesn't check pixel output."""

import matplotlib.pyplot as plt

from gatefold import Item, Layer, plot_circuit


def test_single_qubit_only():
    layers = [Layer(items=[Item(("q0",), "X")]), Layer(items=[Item(("q0",), "H")])]
    ax = plot_circuit(layers)
    assert isinstance(ax, plt.Axes)


def test_multi_qubit_connector():
    layers = [Layer(items=[Item(("q0", "q1"), "CNOT")])]
    ax = plot_circuit(layers)
    assert isinstance(ax, plt.Axes)


def test_empty_layer_list_returns_empty_axes():
    # no layers -> qubit_labels infers to [], nothing is drawn, but
    # plot_circuit should still hand back a usable (empty) Axes rather
    # than raising.
    ax = plot_circuit([])
    assert isinstance(ax, plt.Axes)
    assert len(ax.patches) == 0
    assert len(ax.lines) == 0


def test_qubit_labels_default_to_numeric_order_not_lexicographic():
    layers = [Layer(items=[Item((q,), "X") for q in ("0", "1", "2", "9", "10", "11")])]
    ax = plot_circuit(layers)
    # row 0 is qubit "0", drawn topmost (y=0) down to row 5 = qubit "11" (y=-5)
    wire_labels = [t.get_text() for t in ax.texts if t.get_text() in {"0", "1", "2", "9", "10", "11"}]
    assert wire_labels == ["0", "1", "2", "9", "10", "11"]


def test_long_label_wraps_across_multiple_lines_instead_of_only_shrinking():
    long_label = "a very long label that will not fit on one line no matter how small the font gets"
    layers = [Layer(items=[Item(("q0",), long_label)])]
    ax = plot_circuit(layers, box_size=(0.8, 0.7))
    rendered = [t.get_text() for t in ax.texts if t.get_text() and "\n" in t.get_text()]
    assert rendered, "expected the long label to be wrapped onto multiple lines"
