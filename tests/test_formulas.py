import json
import shutil
from pathlib import Path

import pypdfium2
import pytest
from PIL import Image

from texformules import BP_PER_PT, Formula, FormulaBook, PdfBox, default_cache, default_preamble
from texformules import formulas as formulas_module
from texformules.formulas import _distribution_trees, _faulty

# TeX writes the MediaBox to three decimals; pdfium reads it back as single floats.
TOLERANCE_BP = 2e-3


def test_formulas_typeset_in_a_single_compilation(book, fake_latex):
    result = book.render(["$x^2$", "$y$"])
    assert fake_latex.calls == 1
    assert all(formula.ok for formula in result.values())
    assert book.image(result["$x^2$"].key) is not None


def test_duplicate_sources_typeset_once(book, fake_latex):
    result = book.render(["$x$", "$x$"])
    assert list(result) == ["$x$"]
    assert fake_latex.calls == 1


def test_to_json_gives_dimensions_in_em_with_the_border(book):
    data = book.render(["$x^2$"])["$x^2$"].to_json()
    assert (data["width"], data["height"], data["depth"]) == (3.1, 1.15, 0.3)
    assert set(data) == {"source", "key", "width", "height", "depth"}


def test_second_request_served_by_the_cache(book, fake_latex):
    book.render(["$x^2$"])
    book.render(["$x^2$"])
    assert fake_latex.calls == 1


def test_rejected_formula_located_at_its_line_and_kept(book, fake_latex):
    result = book.render(["$x^2$", "$\\bad y$", "$z$"])
    assert [formula.ok for formula in result.values()] == [True, False, True]
    assert result["$\\bad y$"].error == "Undefined control sequence."
    book.render(["$\\bad y$"])
    assert fake_latex.calls == 1


def test_rejected_formula_to_json_gives_error_and_marks():
    formula = Formula("$\\foo$", "0" * 24, ok=False, error="Undefined control sequence.", marks=((1, 5),))
    assert formula.to_json() == {
        "source": "$\\foo$",
        "error": "Undefined control sequence.",
        "marks": [[1, 5]],
    }


def test_rejected_formula_without_error_says_rejected_by_latex():
    assert Formula("$x$", "0" * 24, ok=False).to_json()["error"] == "rejected by LaTeX"


def test_preamble_error_rejects_everything_and_keeps_nothing(book, fake_latex):
    result = book.render(["$x^2$", "$\\badpreamble$"])
    assert not any(formula.ok for formula in result.values())
    assert result["$x^2$"].error.startswith("preamble: ")
    book.render(["$x^2$"])
    assert fake_latex.calls == 2


def test_shifted_pages_rerun_the_batch_without_the_faulty_formula(book, fake_latex):
    result = book.render(["$a$", "$\\bad\\twopages$", "$c$"])
    assert fake_latex.calls == 2
    assert [formula.ok for formula in result.values()] == [True, False, True]


def test_size_and_resolution_change_the_key(tmp_path, fake_latex):
    common = {"preamble": "", "engine": "lualatex", "runner": fake_latex}
    screen = FormulaBook(tmp_path / "cache", **common)
    printer = FormulaBook(tmp_path / "cache", dpi=600, **common)
    large = FormulaBook(tmp_path / "cache", size=12, **common)
    keys = {book.render(["$x$"])["$x$"].key for book in (screen, printer, large)}
    assert len(keys) == 3
    small_png = screen.image(screen.render(["$x$"])["$x$"].key)
    fine_png = printer.image(printer.render(["$x$"])["$x$"].key)
    with Image.open(small_png) as small, Image.open(fine_png) as fine:
        assert fine.width > 2 * small.width
        assert fine.mode == "LA"
    assert large.render(["$x$"])["$x$"].to_json()["width"] == pytest.approx(31 / 12, abs=1e-3)


def test_modified_preamble_file_typesets_again(tmp_path, fake_latex):
    macros = tmp_path / "macros.tex"
    macros.write_text("\\newcommand\\vect[1]{\\vec{#1}}\n", encoding="utf-8")
    fake_latex.inputs = [macros]

    def book():
        return FormulaBook(
            tmp_path / "cache", preamble="\\input{macros}", engine="lualatex", runner=fake_latex
        )

    first = book().render(["$\\vect u$"])["$\\vect u$"]
    assert book().render(["$\\vect u$"])["$\\vect u$"].key == first.key
    assert fake_latex.calls == 1
    macros.write_text("\\newcommand\\vect[1]{\\mathbf{#1}}\n", encoding="utf-8")
    assert book().render(["$\\vect u$"])["$\\vect u$"].key != first.key
    assert fake_latex.calls == 2


def test_manifest_lists_the_user_files_read(tmp_path, book, fake_latex):
    macros = tmp_path / "macros.tex"
    macros.write_text("\n", encoding="utf-8")
    data = tmp_path / "data.py"
    data.write_text("\n", encoding="utf-8")
    fake_latex.inputs = [macros, data]
    book.render(["$x$"])
    [manifest] = (tmp_path / "cache").glob("preamble-*.json")
    assert json.loads(manifest.read_text(encoding="utf-8")) == [str(macros.resolve())]


def test_without_latex_nothing_is_typeset(tmp_path, monkeypatch):
    monkeypatch.setattr(formulas_module.shutil, "which", lambda name: None)
    book = FormulaBook(tmp_path / "cache", preamble="")
    [formula] = book.render(["$x$"]).values()
    assert (book.available, formula.ok) == (False, False)
    assert formula.error == "no LaTeX distribution on this machine"
    assert not (tmp_path / "cache").exists()


def test_engine_failure_is_not_kept(tmp_path):
    def failing(command, **kwargs):
        raise OSError("engine crashed")

    book = FormulaBook(tmp_path / "cache", preamble="", engine="lualatex", runner=failing)
    [formula] = book.render(["$x$"]).values()
    assert formula.error == "LaTeX did not finish: engine crashed"
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize("key", ["../../etc/passwd", "ABCDEF0123456789abcdef01", ""])
def test_malformed_key_opens_nothing(book, key):
    assert book.image(key) is None
    assert book.pdf(key) is None


def test_one_page_pdf_beside_the_image(book, single_page):
    formula = book.render(["$x^2$"])["$x^2$"]
    path = book.pdf(formula.key)
    assert path is not None and path.with_suffix(".png") == book.image(formula.key)
    (width, height), _ = single_page(path)
    box = formula.pdf_box
    assert (width, height) == pytest.approx((box.width, box.height), abs=TOLERANCE_BP)


def test_pdf_box_in_pdf_points_border_included(book):
    box = book.render(["$x^2$"])["$x^2$"].pdf_box
    expected = (31 * BP_PER_PT, 11.5 * BP_PER_PT, 3 * BP_PER_PT)
    assert (box.width, box.height, box.depth) == pytest.approx(expected)


def test_rejected_formula_has_no_pdf_and_a_zero_box(book):
    formula = book.render(["$\\bad y$"])["$\\bad y$"]
    assert book.pdf(formula.key) is None
    assert formula.pdf_box == PdfBox(0.0, 0.0, 0.0)


def test_entry_without_pdf_typeset_again_under_the_same_key(book, fake_latex):
    first = book.render(["$x^2$"])["$x^2$"]
    book.pdf(first.key).unlink()
    second = book.render(["$x^2$"])["$x^2$"]
    assert (fake_latex.calls, second.key) == (2, first.key)
    assert book.pdf(second.key) is not None


@pytest.mark.parametrize(
    ("platform", "parts"),
    [("darwin", ("Library", "Caches", "texformules")), ("linux", (".cache", "texformules"))],
)
def test_default_cache_per_platform(monkeypatch, platform, parts):
    monkeypatch.setattr(formulas_module.sys, "platform", platform)
    assert default_cache().parts[-len(parts) :] == parts


class TestDefaultPreamble:
    def test_fallback_loads_amsmath_and_siunitx(self, monkeypatch):
        monkeypatch.setattr(formulas_module, "_kpsewhich", lambda *arguments: None)
        preamble = default_preamble()
        assert "{amsmath,amssymb}" in preamble
        assert "{siunitx}" in preamble

    def test_ampackages_used_when_kpsewhich_finds_it(self, monkeypatch, tmp_path):
        monkeypatch.setattr(formulas_module, "_kpsewhich", lambda *arguments: tmp_path / "ampackages.tex")
        assert default_preamble() == "\\input{ampackages}"


class TestFaulty:
    """Where LaTeX stumbled in a rejected formula, so that callers can highlight it."""

    def test_unknown_command_located_at_each_use(self):
        source = r"$\dd x+\ddot y\cdot\dd z$"
        context = r"<argument> $\dd "  # as TeX writes it: a space after the name
        marks = _faulty(source, "Undefined control sequence.", context)
        assert [source[start:end] for start, end in marks] == [r"\dd", r"\dd"]

    def test_line_truncated_by_tex_still_located(self):
        source = r"$\vect\xi\cdot\unknown x$"
        context = r"<argument> ... \xi \cdot \unknown "
        assert _faulty(source, "Undefined control sequence.", context) == ((14, 22),)

    def test_other_error_not_located(self):
        assert _faulty(r"$a^{b$}", "Missing } inserted.", "<inserted text> ") == ()


@pytest.mark.latex
def test_real_compilation_with_amsmath(tmp_path, pdflatex):
    book = FormulaBook(tmp_path / "cache", preamble="\\usepackage{amsmath}", engine=pdflatex)
    result = book.render(["$\\frac{a}{b}$", "$\\unknown$"])
    assert result["$\\frac{a}{b}$"].ok
    assert result["$\\frac{a}{b}$"].depth > 0
    rejected = result["$\\unknown$"]
    assert not rejected.ok
    assert rejected.error.startswith("Undefined control sequence")
    assert [rejected.source[start:end] for start, end in rejected.marks] == ["\\unknown"]


@pytest.mark.latex
def test_real_pdf_page_has_the_announced_box_baseline_included(tmp_path, pdflatex, single_page):
    # A rule 10 pt wide and 8 pt high, 3 pt of which below the baseline.
    rule = "\\raisebox{-3pt}{\\rule{10pt}{8pt}}"
    book = FormulaBook(tmp_path / "cache", preamble="\\usepackage{amsmath}", engine=pdflatex)
    result = book.render([rule, "$\\frac{a}{b}$"])
    for formula in result.values():
        (width, height), _ = single_page(book.pdf(formula.key))
        box = formula.pdf_box
        assert (width, height) == pytest.approx((box.width, box.height), abs=TOLERANCE_BP)
    box = result[rule].pdf_box
    _, [(_, (left, bottom, right, top))] = single_page(book.pdf(result[rule].key))
    border = 0.5 * BP_PER_PT
    assert (left, right, top) == pytest.approx(
        (border, box.width - border, box.height - border), abs=TOLERANCE_BP
    )
    assert bottom == pytest.approx(box.depth - 3 * BP_PER_PT, abs=TOLERANCE_BP)


@pytest.mark.latex
def test_real_preamble_file_recorded_and_fingerprinted(tmp_path, pdflatex):
    macros = tmp_path / "macros.tex"
    macros.write_text("\\newcommand\\vect[1]{\\vec{#1}}\n", encoding="utf-8")
    preamble = f"\\input{{{macros.as_posix()}}}"

    def book():
        return FormulaBook(tmp_path / "cache", preamble=preamble, engine=pdflatex)

    first = book().render(["$\\vect u$"])["$\\vect u$"]
    assert first.ok, first.error
    [manifest] = (tmp_path / "cache").glob("preamble-*.json")
    assert str(macros.resolve()) in json.loads(manifest.read_text(encoding="utf-8"))
    settled = book().render(["$\\vect u$"])["$\\vect u$"]
    macros.write_text("\\newcommand\\vect[1]{\\mathbf{#1}}\n", encoding="utf-8")
    assert book().render(["$\\vect u$"])["$\\vect u$"].key != settled.key


@pytest.mark.latex
@pytest.mark.parametrize("engine", ["pdflatex", "lualatex"])
def test_text_mode_dingbats_typeset_as_glyphs(tmp_path, engine, single_page):
    found = shutil.which(engine)
    if found is None:
        pytest.skip(f"{engine} missing")
    book = FormulaBook(tmp_path / "cache", preamble="\\usepackage{pifont}", engine=found)
    result = book.render(["\\ding{43}", "\\ding{52}", "\\ding{74}"])
    assert all(formula.ok for formula in result.values()), [f.error for f in result.values()]
    for formula in result.values():
        assert formula.width > 1
        # A glyph of an embedded font, hence vectors, and no bitmap image.
        _, objects = single_page(book.pdf(formula.key))
        kinds = {kind for kind, _ in objects}
        assert pypdfium2.raw.FPDF_PAGEOBJ_TEXT in kinds
        assert pypdfium2.raw.FPDF_PAGEOBJ_IMAGE not in kinds


def test_distribution_trees_never_include_the_root(monkeypatch, tmp_path):
    """A TeX Live packaged by Debian lives in /usr/share: a tree named « / » would leave
    the user's own macros out of the manifest."""
    dist = tmp_path / "texlive" / "texmf-dist"
    trees = {"-var-value=TEXMFDIST": dist, "-var-value=TEXMFVAR": Path(tmp_path.anchor)}
    monkeypatch.setattr(formulas_module, "_kpsewhich", lambda argument: trees.get(argument))
    assert _distribution_trees() == [dist]
