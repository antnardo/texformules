"""The names of latex_figures, the package ``texformules.figures`` replaces. Deprecated.

latex_figures had French names (``restaurer``, ``ScalarFormatterVirgule``) and
keyword arguments (``famille``, ``fig_width``); the package is English now. The old
names stay so that existing scripts keep working unchanged after
``from latex_figures import …`` becomes ``from texformules.figures import …``; new code
uses the new names. They will go in a future major release.

Where only the name changed, the alias is the new object itself. Where the arguments
changed too, a thin wrapper keeps the old signature, and the old defaults: the old
``latexify`` and ``parametres_latex`` keep :data:`PREAMBULE`, which loads French babel,
where the new ones load nothing language-specific.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from matplotlib.figure import Figure

from texformules.figures.axes import DecimalCommaFormatter, add_inset, style_axes
from texformules.figures.export import save_figure
from texformules.figures.style import apply_style, figure_size, restore_style, style_params

__all__ = [
    "PREAMBULE",
    "ScalarFormatterVirgule",
    "add_subplot_axes",
    "fig_size",
    "format_axes",
    "latexify",
    "parametres_latex",
    "restaurer",
    "save_fig",
]

#: latex_figures's default preamble: French babel and siunitx.
PREAMBULE = "\\usepackage[french]{babel}\n\\usepackage{siunitx}"

ScalarFormatterVirgule = DecimalCommaFormatter
add_subplot_axes = add_inset
format_axes = style_axes
restaurer = restore_style


def fig_size(
    fig_width: float = 16.0, fig_height: float | None = None, ratio: float | None = None
) -> tuple[float, float]:
    """Deprecated: :func:`~texformules.figures.figure_size`."""
    return figure_size(fig_width, fig_height, ratio)


def parametres_latex(
    fig_width: float | None = None,
    fig_height: float | None = None,
    ratio: float | None = None,
    usetex: bool = True,
    famille: str = "sans-serif",
    preamble: str | Sequence[str] | None = None,
) -> dict[str, Any]:
    """Deprecated: :func:`~texformules.figures.style_params`, French babel by default."""
    return style_params(fig_width, fig_height, ratio, usetex, famille, _old_default(preamble))


def latexify(
    fig_width: float | None = None,
    fig_height: float | None = None,
    ratio: float | None = None,
    usetex: bool = True,
    famille: str = "sans-serif",
    preamble: str | Sequence[str] | None = None,
) -> dict[str, Any]:
    """Deprecated: :func:`~texformules.figures.apply_style`, French babel by default."""
    return apply_style(fig_width, fig_height, ratio, usetex, famille, _old_default(preamble))


def save_fig(
    fig: Figure,
    file_name: str | Path,
    fmt: str | None = None,
    dpi: int = 300,
    tight: bool = True,
    crop: bool = True,
) -> Path:
    """Deprecated: :func:`~texformules.figures.save_figure`."""
    return save_figure(fig, file_name, fmt, dpi, tight, crop)


def _old_default(preamble: str | Sequence[str] | None) -> str | Sequence[str]:
    return PREAMBULE if preamble is None else preamble
