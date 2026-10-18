import shutil
from pathlib import Path

import matplotlib
import pypdfium2
import pytest

from texformules import BP_PER_PT, FormulaBook

# Figures drawn off screen, before any test imports pyplot.
matplotlib.use("Agg")

# 30 pt by 8 pt + 2.5 pt, plus the half-point border on each side.
FAKE_PAGE = (31 * BP_PER_PT, 11.5 * BP_PER_PT)


class FakeLatex:
    """A fake lualatex: one page and one line of dimensions per formula.

    A formula holding ``\\bad`` is rejected at its line; ``\\badpreamble`` breaks the
    preamble; ``\\twopages`` produces one page too many, which shifts the next ones.
    With ``-recorder``, the ``.fls`` claims to have read the files of ``inputs``. Each
    page has the size of the announced box, half-point border included, as with
    ``preview``.
    """

    def __init__(self):
        self.calls = 0
        self.inputs: list[Path] = []

    def __call__(self, command, cwd, **kwargs):
        self.calls += 1
        work = Path(cwd)
        source = (work / "formules.tex").read_text(encoding="utf-8").splitlines()
        formulas = [(n, line) for n, line in enumerate(source, 1) if line.startswith("\\cdformula")]
        first = formulas[0][0]
        log, sizes = [], []
        document = pypdfium2.PdfDocument.new()
        for number, line in formulas:
            if "\\badpreamble" in line:
                log.append(f"./formules.tex:{first - 2}: LaTeX Error: File `missing.sty' not found.")
            elif "\\bad" in line:
                log.append(f"./formules.tex:{number}: Undefined control sequence.")
            sizes.append("30.0pt,8.0pt,2.5pt")
            document.new_page(*FAKE_PAGE)
            if "\\twopages" in line:
                document.new_page(*FAKE_PAGE)
        document.save(work / "formules.pdf")
        document.close()
        (work / "formules.sizes").write_text("\n".join(sizes) + "\n", encoding="utf-8")
        (work / "formules.log").write_text("\n".join(log) + "\n", encoding="utf-8")
        if "-recorder" in command:
            lines = [f"PWD {work}", "INPUT formules.tex", *(f"INPUT {path}" for path in self.inputs)]
            (work / "formules.fls").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def fake_latex():
    return FakeLatex()


@pytest.fixture
def book(tmp_path, fake_latex):
    """A FormulaBook with a temporary cache, compiling with the fake LaTeX."""
    return FormulaBook(
        tmp_path / "cache", preamble="\\usepackage{amsmath}", engine="lualatex", runner=fake_latex
    )


@pytest.fixture
def pdflatex():
    """The path of pdflatex; skips the test without a TeX distribution."""
    found = shutil.which("pdflatex")
    if found is None:
        pytest.skip("no LaTeX distribution")
    return found


@pytest.fixture
def single_page():
    """Reads a one-page PDF: its MediaBox (width, height) and its objects (type, bounds)."""

    def read(path):
        document = pypdfium2.PdfDocument(path)
        try:
            assert len(document) == 1
            page = document[0]
            left, bottom, right, top = page.get_mediabox()
            objects = [(obj.type, obj.get_bounds()) for obj in page.get_objects()]
        finally:
            document.close()
        return (right - left, top - bottom), objects

    return read


@pytest.fixture
def figures():
    """texformules.figures; the figures are closed after the test."""
    import matplotlib.pyplot as plt

    import texformules.figures

    yield texformules.figures
    plt.close("all")
