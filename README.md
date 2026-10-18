# texformules

[![CI](https://github.com/antnardo/texformules/actions/workflows/ci.yml/badge.svg)](https://github.com/antnardo/texformules/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/texformules.svg)](https://pypi.org/project/texformules/)
[![Python](https://img.shields.io/pypi/pyversions/texformules.svg)](https://pypi.org/project/texformules/)
[![License MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/antnardo/texformules/blob/main/LICENSE)

Real LaTeX formulas for documents built in Python. texformules cuts a line of text
into prose and LaTeX fragments, typesets all the missing fragments in **one LaTeX
compilation**, and keeps each one in a cache as a PNG and as a **one-page PDF**,
together with its **baseline**, so that it sits on the line of the surrounding text.
An optional extra, `texformules.figures`, styles matplotlib figures to match the same
LaTeX documents.

```bash
pip install texformules             # formulas
pip install "texformules[figures]"  # and the matplotlib figures
```

```python
from texformules import FormulaBook, default_cache, split

book = FormulaBook(default_cache())
fragments = split(r"Kinetic energy theorem: $\Delta E_c = W(\vec F)$, 2 marks")
formulas = book.render(f.text for f in fragments if f.latex)

for fragment in fragments:
    if fragment.latex and formulas[fragment.text].ok:
        formula = formulas[fragment.text]
        print(book.pdf(formula.key), formula.pdf_box)  # page, and its box in PDF points
    else:
        print(fragment.text)
```

Full reference: [docs/DOC.md](https://github.com/antnardo/texformules/blob/main/docs/DOC.md).

## Why

Formulas written for a LaTeX document use the macros of its preamble: `\SI` from
siunitx, `\vect`, `\dd`, whatever the author defined. Nothing short of LaTeX knows
them: not a conversion to Unicode, not matplotlib's mathtext, not KaTeX. So when a
Python program has to show those formulas — in a PDF report built with reportlab, on
a web page, in a desktop application — the only faithful renderer is LaTeX itself,
with the same preamble.

Calling LaTeX once per formula is slow: loading a large preamble alone takes seconds.
texformules sends all the formulas still missing from the cache to a single
compilation, then keeps each of them:

- **a PNG**, grey and transparent, at the resolution you ask for (288 dpi by default,
  600 for print);
- **a one-page PDF**, the very page LaTeX produced, cut out of the batch: vector, sharp
  at any zoom and on any printer;
- **its box**: width, height and depth in TeX points, and in PDF points through
  `Formula.pdf_box`. The depth puts the baseline of the formula on the baseline of
  the text.

The next request for the same formula, with the same preamble, is served from the
cache without LaTeX.

## Requirements

- Python 3.13 or later (latexdetok, which reads the LaTeX, requires it).
- A TeX distribution on the `PATH` for anything to be typeset: TeX Live, MacTeX or
  MiKTeX, with `lualatex` (preferred) or `pdflatex`, `kpsewhich`, and the `preview`
  package. The default preamble also needs `amsmath`, `amssymb` and `siunitx`. On
  Debian or Ubuntu:

  ```bash
  sudo apt-get install texlive-luatex texlive-latex-extra texlive-science preview-latex-style
  ```

- Without TeX, the package still imports and splits text; `FormulaBook.available` is
  false and every formula comes back rejected, with the reason, so that you can show
  the source instead.

The Python dependencies are latexdetok, pypdfium2 (renders and cuts the PDF pages,
no dvipng nor ImageMagick) and Pillow. The `figures` extra adds matplotlib.

## Splitting text

`split(text)` reads the line as TeX would (with latexdetok) and returns a list of
`Fragment`s: `text`, `latex` (true for a fragment to typeset) and `problems`.

```python
>>> [(f.text, f.latex) for f in split(r"so ($x=1$), then \SI{5e-8}N % note to self")]
[('so ', False), ('($x=1$),', True), (' then ', False), ('\\SI{5e-8}N', True)]
```

- A LaTeX fragment covers the whole word around the formula, punctuation included,
  so that a line break never leaves "(" or "," alone; and a command keeps its
  arguments, even without braces (`\SI{5e-8}N`).
- `%` comments are removed: they are notes for the author, not for the reader
  (`comments(text)` returns them).
- What TeX would print as plain text is translated without LaTeX: `~`, `--`, `---`,
  `\og`/`\fg`, `\%`, group braces…
- The whole line is checked by latexdetok. A word with an error or a warning (a `$`
  never closed, `_` outside math, `\input` or `\def` inside a formula) is **not** sent
  to LaTeX, where it would break the batch: it stays as typed, and its `problems`
  say where (`start`, `end`), how bad (`severity`) and why (`message`,
  `suggestion`).

`french_spacing(text)` sets the no-break spaces of French typography, for the text
fragments of French documents.

## Rendering

```python
from texformules import FormulaBook, default_cache

book = FormulaBook(default_cache(), dpi=600, size=10)
formulas = book.render([r"$\frac{a}{b}$", r"\SI{9.81}{m/s^2}", r"$\oops$"])

ok = formulas[r"$\frac{a}{b}$"]
ok.width, ok.height, ok.depth   # TeX points, half-point border included
ok.pdf_box                      # PdfBox(width, height, depth) in PDF points
book.image(ok.key)              # Path to the PNG
book.pdf(ok.key)                # Path to the one-page PDF

bad = formulas[r"$\oops$"]
bad.ok, bad.error, bad.marks    # False, 'Undefined control sequence.', ((1, 6),)
```

`render` returns a dict keyed by source. A formula LaTeX rejects keeps its error
message and, for an undefined command, the places of that command in its source
(`marks`), so you can highlight them. `Formula.to_json()` gives a JSON-ready summary
(size in em for web pages, or the error).

`render` holds a lock: one `FormulaBook` can be shared by the threads of a web server.
pdfium itself is not thread-safe: if other code in your process uses pypdfium2, hold
your own lock around `render` as well.

## With reportlab-layout

[reportlab-layout](https://pypi.org/project/reportlab_layout/) sets a PDF page inline,
on the baseline, with `inline_pdf` (version 1.10 with the `pdf` extra), and an image
with `inline_image`. Both take the box of `Formula.pdf_box`:

```python
from xml.sax.saxutils import escape

from reportlab_layout import inline_pdf
from texformules import FormulaBook, default_cache, split

book = FormulaBook(default_cache())

def markup(text: str) -> str:
    fragments = split(text)
    formulas = book.render(f.text for f in fragments if f.latex)
    parts = []
    for fragment in fragments:
        formula = formulas.get(fragment.text) if fragment.latex else None
        if formula is not None and formula.ok:
            box = formula.pdf_box
            parts.append(inline_pdf(book.pdf(formula.key), width=box.width,
                                    height=box.height, depth=box.depth))
        else:
            parts.append(escape(fragment.text))  # french_spacing(...) first, for French
    return "".join(parts)
```

Pass the markup to reportlab-layout's `InlineParagraph` (a plain `Paragraph` cannot
draw PDF pages); the paragraph style needs `autoLeading="max"`. A rejected formula
falls back to its source here; set it in a monospaced font if you prefer. reportlab-layout writes each font
stream once, however many formulas share it, so a page of vector formulas weighs less
than the same page with 600 dpi PNGs.

## Elsewhere

- **Web pages**: serve `book.image(key)` and use `formula.to_json()`: `width`,
  `height` and `depth` are in em of the type size, so `height: {height}em;
  vertical-align: -{depth}em` sets the image on the baseline at any font size.
- **Other PDF libraries**: the one-page PDF can be laid down as a form XObject; its
  MediaBox is the box, and the baseline lies `pdf_box.depth` above its bottom.

## Your own preamble

By default the preamble loads amsmath, amssymb and siunitx. Pass any preamble, without
`\documentclass` (the batch uses `book` at 10 pt):

```python
book = FormulaBook(
    default_cache(),
    preamble=r"""
\usepackage{amsmath,amssymb}
\usepackage{siunitx}
\usepackage{fontspec}\setmainfont{TeX Gyre Pagella}
\newcommand\vect[1]{\vec{#1}}
\input{mymacros}
""",
    engine="lualatex",
)
```

- `engine` is a name or a path; by default `lualatex`, else `pdflatex`. fontspec needs
  lualatex (or xelatex).
- `size` is the type size in TeX points, `dpi` the PNG resolution; both enter the
  cache key.
- A preamble may `\input` files of yours: they are followed (see below).
- `default_preamble()` uses `\input{ampackages}` instead when `kpsewhich` finds that
  file: it is the author's own macro suite, absent anywhere else.

## The cache

`default_cache()` is `~/Library/Caches/texformules` on macOS,
`%LOCALAPPDATA%\texformules\Cache` on Windows and `$XDG_CACHE_HOME/texformules`
(`~/.cache/texformules` by default) elsewhere; any folder will do. Each formula is stored under a
24-character key as `<key>.json`, `<key>.png` and `<key>.pdf`, written atomically, so
several programs can share the folder.

The key is a hash of the source, the engine, the preamble, the size, the resolution,
and **the content of every file the preamble reads outside the TeX distribution**.
Each compilation runs with `-recorder`; the files listed in its `.fls` that do not
belong to the distribution (your `.tex`, `.sty`, `.lua`… including `TEXMFHOME`) are
recorded in a manifest, `preamble-<hash>.json`. Edit a macro in one of them and the
next batch typesets the formulas again. Data files (`.py`, `.csv`…) are not followed:
they change often, and never a formula.

To clear the cache, delete the folder. Rejections that are the formula's own fault
are cached too; those due to the preamble, an interrupted compilation or a missing
TeX are not, and are retried.

## Figures

`texformules.figures` (extra `figures`) styles matplotlib for figures inserted in a
LaTeX document: sizes in centimetres, LaTeX fonts and preamble, a decimal comma that
does not touch the locale, insets, and cropping to the ink.

```python
import matplotlib.pyplot as plt
import numpy as np
from texformules.figures import apply_style, save_figure, style_axes

apply_style(8, 6)                 # 8 cm by 6 cm, before creating the figure
x = np.linspace(-4, 4, 500)
fig, ax = plt.subplots()
ax.plot(x, np.sinc(x) ** 2)
ax.set_xlabel(r"$\theta$ (\unit{\radian})")   # siunitx is in the preamble
style_axes(ax)                    # grey spines, outward ticks, 0,5 and ×10⁵
save_figure(fig, "slit.pdf")      # saved, then cropped by pdfcrop
```

`apply_style` changes `rcParams` for every figure to come, `restore_style()` undoes it,
and `style_params(...)` returns the same settings for `plt.rc_context`. The figures
came from the `latex_figures` package; its names (`latexify`, `format_axes`,
`save_fig`, `restaurer`, `ScalarFormatterVirgule`…) still work, as deprecated aliases
listed in DOC.md.

## Limits

- One formula is one line of the batch document: display environments that need
  several paragraphs (`align` outside math…) are not supported; `$$…$$` and `\[…\]`
  are set inline in `\displaystyle`.
- Commands that would affect the other formulas of the batch — definitions, file
  input and output, catcode changes, the `document` environment — are refused inside
  a formula. Define your macros in the preamble.
- Only an undefined command is located inside a rejected formula; for other errors,
  the message is all TeX gives.
- Each one-page PDF embeds the fonts subset for its whole batch: on its own it is
  heavier than its PNG (about 15 kB against 6 kB); it pays off when the document
  embeds each font stream once.
- latexdetok's messages are in English; for French, call
  `latexdetok.set_language("fr")` or set `LATEXDETOK_LANG=fr`.

## Development

```bash
uv sync --group dev
uv run ruff format src tests examples
uv run ruff check src tests examples
uv run mypy
uv run pytest -q              # the `latex` tests are skipped without TeX
uv run pytest -q -m latex     # only those that compile
uv build
```

The version is `texformules.__version__`; a GitHub release tagged `v<version>`
publishes to PyPI through trusted publishing.

## License

MIT, see [LICENSE](https://github.com/antnardo/texformules/blob/main/LICENSE).
