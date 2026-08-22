from importlib.metadata import PackageNotFoundError, version

from .core import Item, Layer, plot_circuit
from .style import Palette, StyleSpec, DEFAULT_PALETTE, set_clean_rcparams

try:
    __version__ = version("gatefold")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = [
    "Item",
    "Layer",
    "Palette",
    "StyleSpec",
    "DEFAULT_PALETTE",
    "plot_circuit",
    "set_clean_rcparams",
    "__version__",
]
