"""Smoke tests: plot_circuit runs and returns an Axes. Doesn't check pixel output."""

import matplotlib

matplotlib.use("Agg")

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
