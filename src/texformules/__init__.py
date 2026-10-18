"""LaTeX formulas typeset in batches, cached as PNG and one-page PDF with their baseline.

Two steps, two modules:

- ``fragments`` cuts a line into text and LaTeX fragments, on latexdetok's tree
  (:func:`split`), removes the comments and can set French spacing; the whole line
  goes through latexdetok, and what it finds wrong follows each fragment
  (:class:`Problem`);
- ``formulas`` typesets the fragments in a single compilation per batch, with the
  document's preamble, and keeps them as PNG and as one-page PDF, with their baseline
  (:class:`FormulaBook`, :class:`PdfBox`).

Only latexdetok and pypdfium2 are needed to import it; LaTeX is called at the first
missing formula.

    book = FormulaBook(default_cache(), dpi=600)
    fragments = split(r"Result: $T_0=\\SI{2.0}{s}$, 2 marks")
    formulas = book.render(f.text for f in fragments if f.latex)
    for formula in formulas.values():
        pdf, box = book.pdf(formula.key), formula.pdf_box  # box in PDF points
"""

from texformules.formulas import (
    BP_PER_PT,
    Formula,
    FormulaBook,
    PdfBox,
    Runner,
    default_cache,
    default_preamble,
)
from texformules.fragments import Fragment, Problem, comments, french_spacing, split

__version__ = "0.2.0"

__all__ = [
    "BP_PER_PT",
    "Formula",
    "FormulaBook",
    "Fragment",
    "PdfBox",
    "Problem",
    "Runner",
    "__version__",
    "comments",
    "default_cache",
    "default_preamble",
    "french_spacing",
    "split",
]
