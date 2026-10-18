import numpy as np
import pytest

from texformules.figures.axes import DecimalCommaFormatter, add_inset, style_axes


@pytest.fixture
def axes(figures):
    import matplotlib.pyplot as plt

    _, ax = plt.subplots()
    ax.plot(np.linspace(0, 3e5, 10), np.linspace(0, 2e-3, 10))
    return ax


def test_each_axis_gets_its_own_formatter(axes):
    style_axes(axes)
    assert axes.xaxis.get_major_formatter() is not axes.yaxis.get_major_formatter()


def test_common_factors_stay_independent(axes):
    # With a shared formatter, the last axis drawn imposed its factor on the other.
    style_axes(axes)
    axes.figure.canvas.draw()
    assert "10^{5}" in axes.xaxis.get_major_formatter().get_offset()
    assert "10^{\N{MINUS SIGN}3}" in axes.yaxis.get_major_formatter().get_offset()


def test_decimal_comma_without_locale(figures):
    import matplotlib.pyplot as plt

    formatter = DecimalCommaFormatter()
    fig, ax = plt.subplots()
    ax.set_xlim(0, 2)
    ax.xaxis.set_major_formatter(formatter)
    fig.canvas.draw()
    assert formatter(1.5) == r"$\mathdefault{1{,}50}$"  # ticks 0, 0.25…


def test_decimal_point_on_request(axes):
    style_axes(axes, decimal_comma=False)
    axes.set_xlim(0, 2)
    axes.figure.canvas.draw()
    formatter = axes.xaxis.get_major_formatter()
    assert not isinstance(formatter, DecimalCommaFormatter)
    assert "{,}" not in formatter(1.5)


def test_log_axis_keeps_its_formatter(figures):
    import matplotlib.pyplot as plt

    _, ax = plt.subplots()
    ax.set_yscale("log")
    style_axes(ax)
    assert not isinstance(ax.yaxis.get_major_formatter(), DecimalCommaFormatter)


def test_format_ticks_false_keeps_the_formatters(axes):
    before = axes.xaxis.get_major_formatter()
    style_axes(axes, format_ticks=False)
    assert axes.xaxis.get_major_formatter() is before


def test_spines_visible_and_grey(axes):
    style_axes(axes)
    assert all(spine.get_visible() for spine in axes.spines.values())


def test_inset_placed_inside_the_axes(axes):
    inset = add_inset(axes, [0.6, 0.1, 0.3, 0.3])
    axes.figure.canvas.draw()
    parent = axes.get_position()
    position = inset.get_position()
    assert position.x0 == pytest.approx(parent.x0 + 0.6 * parent.width)
    assert position.width == pytest.approx(0.3 * parent.width)
