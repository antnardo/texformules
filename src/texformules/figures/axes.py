"""Axes formatting: discreet spines, outward ticks, decimal comma."""

from collections.abc import Sequence
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.ticker import ScalarFormatter

__all__ = ["DecimalCommaFormatter", "add_inset", "style_axes"]


def _comma(text: str) -> str:
    # In math mode (mathtext or LaTeX), "{,}" avoids the space that follows a
    # punctuation comma.
    return text.replace(".", "{,}")


class DecimalCommaFormatter(ScalarFormatter):
    """A ``ScalarFormatter`` in math notation, with a decimal comma, and powers of 10
    outside [10⁻², 10⁴].

    The comma does not go through ``locale.setlocale("fr_FR")``, which would act on
    the whole program and fails where no French locale is installed.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("useMathText", True)
        super().__init__(**kwargs)
        self.set_powerlimits((-2, 4))

    def __call__(self, x: float, pos: int | None = None) -> str:
        return _comma(super().__call__(x, pos))

    def get_offset(self) -> str:
        return _comma(super().get_offset())


def style_axes(ax: Axes | None = None, format_ticks: bool = True, decimal_comma: bool = True) -> Axes:
    """Thin grey spines, outward ticks, and (``format_ticks``) a formatter of its own on
    each linear axis: :class:`DecimalCommaFormatter`, or with ``decimal_comma=False`` a
    mathtext ``ScalarFormatter`` with the same power limits. Calls ``tight_layout`` on
    the figure of ``ax`` (the current axes by default).

    Each axis gets its own formatter: a single shared formatter kept only one common
    factor (the ×10⁵ of the x axis lost to the y axis's).
    """
    if ax is None:
        ax = plt.gca()
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("gray")
        spine.set_linewidth(0.5)
    ax.xaxis.set_ticks_position("bottom")
    ax.yaxis.set_ticks_position("left")
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_tick_params(direction="out", which="both", color="gray")
        if format_ticks and axis.get_scale() == "linear":
            axis.set_major_formatter(_formatter(decimal_comma))
    figure = ax.get_figure()
    if figure is not None:
        figure.tight_layout()  # type: ignore[union-attr]
    return ax


def _formatter(decimal_comma: bool) -> ScalarFormatter:
    if decimal_comma:
        return DecimalCommaFormatter()
    formatter = ScalarFormatter(useMathText=True)
    formatter.set_powerlimits((-2, 4))
    return formatter


def add_inset(ax: Axes, rect: Sequence[float]) -> Axes:
    """Inset axes inside ``ax``; ``rect = [x0, y0, width, height]`` as fractions of
    ``ax`` (for instance ``[0.6, 0.1, 0.3, 0.3]``).

    The tick labels shrink as the square root of the relative size. The inset follows
    ``ax`` if the layout changes (``Axes.inset_axes``).

    Example::

        inset = add_inset(ax, rect=[0.6, 0.1, 0.3, 0.3])
        inset.plot(wavelengths, sines, "o", ms=3)
        inset.set_xlim(0, 650)
    """
    x0, y0, width, height = rect
    inset = ax.inset_axes((x0, y0, width, height))
    for axis, factor in ((inset.xaxis, width), (inset.yaxis, height)):
        labels = axis.get_ticklabels()
        size = labels[0].get_fontsize() if labels else 10.0
        axis.set_tick_params(labelsize=size * factor**0.5)
    return inset
