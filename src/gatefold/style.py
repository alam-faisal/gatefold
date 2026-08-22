from __future__ import annotations

from dataclasses import dataclass, field

from matplotlib import cm, rcParams
from matplotlib.colors import to_rgb, to_hex

# --------------------------------------------------------------------------
# Public data model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StyleSpec:
    fill: str
    text: str = "white"
    edge: str = "none"


@dataclass(frozen=True)
class Palette:
    styles: dict[str, StyleSpec] = field(default_factory=dict)
    wire: str = "#C7CCD1"
    barrier: str = "#9AA1A9"

    def get(self, key: str) -> StyleSpec:
        return self.styles.get(key, self.styles["default"])


def _readable_text(fill: str) -> str:
    """Black or white, whichever contrasts better against `fill`."""
    r, g, b = to_rgb(fill)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "black" if luminance > 0.6 else "white"


# Fills sampled from the plasma colormap; text color picked per-swatch since
# plasma spans dark purple to bright yellow. Swap in your own for house
# style / brand colors.
_PLASMA_FRACTIONS = {"default": 0.15, "single": 0.5, "multi": 0.8}
DEFAULT_PALETTE = Palette(
    styles={
        name: StyleSpec(fill=(fill := to_hex(cm.plasma(frac))), text=_readable_text(fill))
        for name, frac in _PLASMA_FRACTIONS.items()
    }
)


def set_clean_rcparams() -> None:
    """Call once (e.g. at import time in your notebook) for LaTeX-like typography."""
    rcParams["mathtext.fontset"] = "cm"
    rcParams["font.family"] = "sans-serif"
    rcParams["font.sans-serif"] = ["Helvetica", "Arial", "DejaVu Sans"]
    rcParams["axes.linewidth"] = 0.0
