"""Cut a few lines into text and formulas, typeset the formulas, print what came out.

Run it twice: the second run is served by the cache, without calling LaTeX. It needs a
TeX distribution (lualatex or pdflatex) on the PATH; without one, every formula comes
back rejected, with the reason.

    python examples/render_formulas.py
"""

from texformules import FormulaBook, default_cache, split

LINES = [
    r"Kinetic energy theorem: $\Delta E_c=W(\vec F)$, 2 marks",
    r"Numerical value \SI{3.0e8}{m/s} with its unit % the unit is mandatory",
    r"Unknown macro $\speed = 3$ and a $ never closed",
]


def main() -> None:
    book = FormulaBook(default_cache(), dpi=300)
    print(f"LaTeX available: {book.available}")
    fragments = [fragment for line in LINES for fragment in split(line)]
    formulas = book.render(fragment.text for fragment in fragments if fragment.latex)
    for fragment in fragments:
        if not fragment.latex:
            for problem in fragment.problems:
                piece = fragment.text[problem.start : problem.end]
                print(f"  kept as text {fragment.text!r}: {problem.severity} at {piece!r}: {problem.message}")
            continue
        formula = formulas[fragment.text]
        if formula.ok:
            box = formula.pdf_box
            print(f"{formula.source!r}: {box.width:.1f} x {box.height:.1f} pt, depth {box.depth:.1f} pt")
            print(f"    PNG {book.image(formula.key)}")
            print(f"    PDF {book.pdf(formula.key)}")
        else:
            print(f"{formula.source!r} rejected: {formula.error} at {list(formula.marks)}")


if __name__ == "__main__":
    main()
