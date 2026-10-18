"""matplotlib figures ready for a LaTeX document: size in cm, fonts, decimal comma,
insets, tight cropping. Needs the ``figures`` extra (matplotlib).

Usage::

    import matplotlib.pyplot as plt
    from texformules.figures import apply_style, save_figure, style_axes

    apply_style(8, 6)  # width, height in cm, before creating the figures
    fig, ax = plt.subplots()
    ax.plot(x, y)
    style_axes(ax)  # spines, ticks, decimal comma
    save_figure(fig, "figure.pdf")  # cropped by pdfcrop

Formerly the separate ``latex_figures`` package; its names are kept as deprecated
aliases (:mod:`texformules.figures.legacy`).
"""

# First: a clear error, naming the extra, when matplotlib is missing.
import texformules.figures._require  # noqa: F401  # isort: skip
from texformules.figures.axes import DecimalCommaFormatter, add_inset, style_axes
from texformules.figures.export import FORMATS, save_figure
from texformules.figures.legacy import (
    PREAMBULE,
    ScalarFormatterVirgule,
    add_subplot_axes,
    fig_size,
    format_axes,
    latexify,
    parametres_latex,
    restaurer,
    save_fig,
)
from texformules.figures.style import (
    INCH,
    MAX_HEIGHT,
    PREAMBLE,
    apply_style,
    figure_size,
    restore_style,
    style_params,
)

__all__ = [
    "FORMATS",
    "INCH",
    "MAX_HEIGHT",
    "PREAMBLE",
    "PREAMBULE",
    "DecimalCommaFormatter",
    "ScalarFormatterVirgule",
    "add_inset",
    "add_subplot_axes",
    "apply_style",
    "fig_size",
    "figure_size",
    "format_axes",
    "latexify",
    "parametres_latex",
    "restaurer",
    "restore_style",
    "save_fig",
    "save_figure",
    "style_axes",
    "style_params",
]
