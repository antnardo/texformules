import pytest

from texformules.figures import axes, export, legacy, style


@pytest.fixture(autouse=True)
def fresh_style(figures):
    import matplotlib as mpl

    style._SAVED = None
    with mpl.rc_context():
        yield
    style._SAVED = None


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (legacy.ScalarFormatterVirgule, axes.DecimalCommaFormatter),
        (legacy.add_subplot_axes, axes.add_inset),
        (legacy.format_axes, axes.style_axes),
        (legacy.restaurer, style.restore_style),
    ],
)
def test_renamed_names_are_the_new_objects(old, new):
    assert old is new


def test_latexify_keeps_its_old_keywords_and_french_preamble():
    import matplotlib as mpl

    params = legacy.latexify(fig_width=16, fig_height=6, usetex=False, famille="serif")
    assert params["text.latex.preamble"] == legacy.PREAMBULE
    assert "[french]{babel}" in legacy.PREAMBULE
    assert mpl.rcParams["font.family"] == ["serif"]


def test_restaurer_undoes_latexify():
    import matplotlib as mpl

    before = dict(mpl.rcParams)
    legacy.latexify(8, 6, usetex=False)
    legacy.restaurer()
    assert dict(mpl.rcParams) == before


def test_parametres_latex_takes_a_preamble_of_its_own():
    assert legacy.parametres_latex(preamble="")["text.latex.preamble"] == ""


def test_fig_size_keeps_its_old_keywords():
    assert legacy.fig_size(fig_width=8, fig_height=6) == style.figure_size(8, 6)


def test_save_fig_keeps_its_old_keywords(figures, tmp_path):
    import matplotlib.pyplot as plt

    fig, _ = plt.subplots()
    path = legacy.save_fig(fig, file_name=tmp_path / "old", fmt="png", crop=False)
    assert path.name == "old.png"
    assert export.FORMATS is figures.FORMATS


def test_every_old_name_importable_from_the_package(figures):
    old = {
        "PREAMBULE",
        "ScalarFormatterVirgule",
        "add_subplot_axes",
        "fig_size",
        "format_axes",
        "latexify",
        "parametres_latex",
        "restaurer",
        "save_fig",
    }
    assert old <= set(figures.__all__)
    assert all(hasattr(figures, name) for name in old)
