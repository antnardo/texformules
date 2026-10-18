import shutil

import matplotlib as mpl
import pytest

from texformules.figures import style
from texformules.figures.style import (
    INCH,
    PREAMBLE,
    apply_style,
    figure_size,
    restore_style,
    style_params,
)


@pytest.fixture(autouse=True)
def fresh_style(figures):
    """No apply_style from an earlier test, and the rcParams given back afterwards."""
    style._SAVED = None
    with mpl.rc_context():
        yield
    style._SAVED = None


def test_size_in_centimetres_converted_to_inches():
    assert figure_size(8, 6) == pytest.approx((8 / INCH, 6 / INCH))


def test_default_height_at_the_golden_ratio():
    width, height = figure_size(16)
    assert height / width == pytest.approx(0.618, abs=1e-3)


def test_height_beyond_22_cm_brought_down_with_a_warning():
    with pytest.warns(UserWarning, match="22"):
        assert figure_size(16, 30)[1] == pytest.approx(22 / INCH)


def test_apply_style_applies_and_returns_the_params():
    params = apply_style(8, 6, usetex=False)
    assert mpl.rcParams["figure.figsize"] == pytest.approx([8 / INCH, 6 / INCH])
    assert params["text.usetex"] is False


def test_restore_style_gives_back_the_settings_before_the_first_apply():
    before = dict(mpl.rcParams)
    apply_style(8, 6, usetex=False)
    apply_style(10, usetex=False, family="serif")
    assert mpl.rcParams["font.family"] == ["serif"]
    restore_style()
    assert dict(mpl.rcParams) == before
    restore_style()  # no effect a second time
    assert dict(mpl.rcParams) == before


def test_params_usable_in_rc_context():
    with mpl.rc_context(style_params(10, ratio=0.5, usetex=False, family="serif")):
        assert mpl.rcParams["font.family"] == ["serif"]
        assert mpl.rcParams["figure.figsize"][1] == pytest.approx(5 / INCH)


class TestPreamble:
    def test_amsmath_and_siunitx_by_default(self):
        preamble = style_params()["text.latex.preamble"]
        assert preamble == PREAMBLE
        assert "{amsmath}" in preamble and "{siunitx}" in preamble
        assert "babel" not in preamble

    def test_preamble_given_as_lines_or_string(self):
        lines = [r"\usepackage{amsmath}", r"\usepackage{physics}"]
        assert style_params(preamble=lines)["text.latex.preamble"] == "\n".join(lines)
        assert style_params(preamble="")["text.latex.preamble"] == ""

    @pytest.mark.latex
    def test_preamble_compiles_with_latex(self, tmp_path):
        if shutil.which("latex") is None:
            pytest.skip("no LaTeX distribution")
        import matplotlib.pyplot as plt

        with mpl.rc_context(style_params(8, 6)):
            fig, ax = plt.subplots()
            ax.plot([0, 1], [0, 1])
            ax.set_xlabel(r"$v$ (\qty{1}{\m\per\s})")
            fig.savefig(tmp_path / "preamble.pdf")
        assert (tmp_path / "preamble.pdf").stat().st_size > 0
