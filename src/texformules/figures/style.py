"""matplotlib settings for figures inserted in a LaTeX document.

Dimensions are in centimetres, like in the document. The settings start from those of
the SciPy "Cookbook" (Matplotlib/LaTeX_Examples). With ``usetex``, the LaTeX preamble
loads amsmath and siunitx, so that labels are written as in the document
(``\\qty{3}{\\m\\per\\s}``).

The settings saved before the first :func:`apply_style` live in a module variable, not
in a class: ``rcParams`` is itself global to matplotlib, and :func:`restore_style`
must undo every :func:`apply_style` since, whoever made it.
"""

import copy
import math
import warnings
from collections.abc import Sequence
from typing import Any

import matplotlib as mpl

__all__ = [
    "INCH",
    "MAX_HEIGHT",
    "PREAMBLE",
    "apply_style",
    "figure_size",
    "restore_style",
    "style_params",
]

INCH = 2.54  # cm
MAX_HEIGHT = 22.0  # cm, the usable height of an A4 page
_GOLDEN_RATIO = (math.sqrt(5) - 1) / 2  # 0.618
#: Default LaTeX preamble (``text.latex.preamble``), used when ``usetex`` is true.
PREAMBLE = "\\usepackage{amsmath}\n\\usepackage{siunitx}"

# Settings from before the first ``apply_style``, given back by ``restore_style``.
_SAVED: dict[str, Any] | None = None


def figure_size(
    width: float = 16.0, height: float | None = None, ratio: float | None = None
) -> tuple[float, float]:
    """Size (width, height) in inches of a figure given in cm.

    Without a height, it is ``ratio`` × width (the golden ratio by default). Beyond
    22 cm, the height is brought down to 22 cm, with a warning.
    """
    if height is None:
        height = width * (_GOLDEN_RATIO if ratio is None else ratio)
    if height > MAX_HEIGHT:
        warnings.warn(
            f"Figure height {height} cm too tall: brought down to {MAX_HEIGHT} cm.",
            stacklevel=2,
        )
        height = MAX_HEIGHT
    return width / INCH, height / INCH


def style_params(
    width: float | None = None,
    height: float | None = None,
    ratio: float | None = None,
    usetex: bool = True,
    family: str = "sans-serif",
    preamble: str | Sequence[str] | None = None,
) -> dict[str, Any]:
    """The rc parameters of :func:`apply_style`, to pass to ``plt.rc_context`` as well.

    ``width`` in cm (16 by default), ``height`` in cm or ``ratio`` × width; ``family``:
    ``"sans-serif"`` or ``"serif"``; ``preamble``: the LaTeX preamble (a string, or one
    line per item), :data:`PREAMBLE` by default, ``""`` for none; it only matters with
    ``usetex``.
    """
    inches_wide, inches_high = figure_size(16.0 if width is None else width, height, ratio)
    if preamble is None:
        preamble = PREAMBLE
    elif not isinstance(preamble, str):
        preamble = "\n".join(preamble)
    return {
        "pgf.texsystem": "pdflatex",
        "axes.labelsize": 11,
        "axes.titlesize": 11,
        "axes.formatter.use_mathtext": True,
        "font.size": 11,
        "text.usetex": usetex,
        "text.latex.preamble": preamble,
        "font.family": family,
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "legend.fontsize": 8,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "lines.markersize": 3,
        "figure.figsize": [inches_wide, inches_high],
        "figure.subplot.left": 0.16,
        "figure.subplot.right": 0.94,
        "figure.subplot.bottom": 0.14,
        "figure.subplot.top": 0.96,
        "figure.subplot.wspace": 0.3,
        "figure.subplot.hspace": 0.2,
    }


def apply_style(
    width: float | None = None,
    height: float | None = None,
    ratio: float | None = None,
    usetex: bool = True,
    family: str = "sans-serif",
    preamble: str | Sequence[str] | None = None,
) -> dict[str, Any]:
    """Applies :func:`style_params` to matplotlib (before creating the figures) and returns them.

    Figures already created keep their settings; no need to restart the console. No
    locale is changed: the decimal comma comes from :func:`~texformules.figures.style_axes`.
    :func:`restore_style` gives back the settings from before.
    """
    global _SAVED
    params = style_params(width, height, ratio, usetex, family, preamble)
    if _SAVED is None:
        _SAVED = {key: copy.deepcopy(mpl.rcParams[key]) for key in params}  # type: ignore[index]
    # matplotlib ≥ 3.11's stubs only accept literal keys; matplotlib checks every key at
    # run time anyway.
    mpl.rcParams.update(params)  # type: ignore[arg-type]
    return params


def restore_style() -> None:
    """Gives matplotlib back the settings from before the first :func:`apply_style` (its
    inverse); does nothing if it was not called."""
    global _SAVED
    if _SAVED is not None:
        mpl.rcParams.update(_SAVED)  # type: ignore[arg-type]
        _SAVED = None
