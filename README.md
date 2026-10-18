# texformules

[![CI](https://github.com/antnardo/texformules/actions/workflows/ci.yml/badge.svg)](https://github.com/antnardo/texformules/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/texformules.svg)](https://pypi.org/project/texformules/)
[![Python](https://img.shields.io/pypi/pyversions/texformules.svg)](https://pypi.org/project/texformules/)
[![License MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/antnardo/texformules/blob/main/LICENSE)

Typeset the LaTeX formulas of a document made in Python — a PDF built with reportlab,
a web page, an application — with LaTeX itself and your own preamble, and get each
formula back as an image that sits on the baseline of the surrounding text.

## The goal

You have text with LaTeX in it, written for LaTeX documents: a marking scheme, a list
of exercises, comments on a student's work —
`Kinetic energy theorem: $\Delta E_c = W(\vec F)$, 2 marks`. Now a Python program has
to show it outside LaTeX.

- **It must look as it does in the LaTeX document.** The formulas use the macros of
  that document's preamble (`\SI`, `\vect`, whatever was defined), which only LaTeX
  knows: mathtext, KaTeX or a conversion to Unicode would get them wrong or fail.
- **It must sit in a line of text.** A formula has a depth below the baseline; an
  image dropped on the line without it floats up.
- **It must be fast.** Starting LaTeX costs a second or more per run, more with a large
  preamble; a document may hold hundreds of formulas, and show them again and again.

## The means

texformules does three things, and only these.

1. **Split.** `split(text)` cuts a line into plain text and LaTeX fragments, reading it
   as TeX would (with [latexdetok](https://pypi.org/project/latexdetok/)). A fragment
   that would break the compilation — a `$` never closed, `_` outside math — is not
   sent to LaTeX: it stays as typed, with the reason.
2. **Typeset in one batch.** `FormulaBook.render(fragments)` sends every fragment not
   yet in the cache to **one** LaTeX compilation, with your preamble, and measures each
   formula: width, height and depth.
3. **Keep.** Each formula is stored in a cache as a **PNG** and as a **one-page PDF**
   (vector, cut out of the batch), with its box. The next request for the same formula
   and the same preamble is answered without LaTeX. Editing a file your preamble
   reads (`\input{mymacros}`) changes the keys, and the formulas are typeset again.

What you do with the images is yours: the box tells where the baseline is.

## Installation

```bash
pip install texformules
```

- Python 3.13 or later.
- A TeX distribution on the `PATH` — TeX Live, MacTeX or MiKTeX — with `lualatex` (or
  `pdflatex`), `kpsewhich` and the `preview` package; the default preamble also needs
  `amsmath`, `amssymb` and `siunitx`. On Debian or Ubuntu:

  ```bash
  sudo apt-get install texlive-luatex texlive-latex-extra texlive-science preview-latex-style
  ```

- Without TeX, the package still imports and splits text: `FormulaBook.available` is
  false and every formula comes back rejected, so that you can show its source.

The Python dependencies are latexdetok, pypdfium2 (renders and cuts the PDF pages:
no dvipng, no ImageMagick) and Pillow.

## Quick start

```python
from texformules import FormulaBook, default_cache, split

book = FormulaBook(default_cache())
fragments = split(r"Kinetic energy theorem: $\Delta E_c = W(\vec F)$, 2 marks")
formulas = book.render(f.text for f in fragments if f.latex)

for fragment in fragments:
    formula = formulas.get(fragment.text) if fragment.latex else None
    if formula is not None and formula.ok:
        print("formula", book.pdf(formula.key), formula.pdf_box)  # one-page PDF, box in PDF points
    else:
        print("text   ", fragment.text)
```

The complete reference is [docs/DOC.md](https://github.com/antnardo/texformules/blob/main/docs/DOC.md).

## Splitting text

`split(text)` returns `Fragment`s: `text`, `latex` (true for what to typeset) and
`problems`.

```python
>>> [(f.text, f.latex) for f in split(r"so ($x=1$), then \SI{5e-8}N % note to self")]
[('so ', False), ('($x=1$),', True), (' then ', False), ('\\SI{5e-8}N', True)]
```

- A LaTeX fragment takes in the whole word around the formula, punctuation included,
  so that a line break never leaves a « ( » or a « , » alone; a command keeps its
  arguments, even unbraced (`\SI{5e-8}N`).
- `%` comments are dropped: notes for the author, not for the reader
  (`comments(text)` returns them).
- What TeX prints as plain text is translated without LaTeX: `~`, `--`, `---`, `\%`,
  `\og`/`\fg`, group braces…
- A fragment with an error is kept as typed, and its `problems` say where (`start`,
  `end`), how bad (`severity`) and why (`message`, `suggestion`).

`french_spacing(text)` adds the no-break spaces of French typography to text fragments.

## Rendering

```python
book = FormulaBook(default_cache(), dpi=600, size=10)
formulas = book.render([r"$\frac{a}{b}$", r"\SI{9.81}{m/s^2}", r"$\oops$"])

ok = formulas[r"$\frac{a}{b}$"]
ok.width, ok.height, ok.depth   # TeX points
ok.pdf_box                      # PdfBox(width, height, depth), PDF points
book.image(ok.key)              # the PNG
book.pdf(ok.key)                # the one-page PDF

bad = formulas[r"$\oops$"]
bad.ok, bad.error, bad.marks    # False, 'Undefined control sequence.', ((1, 6),)
```

- `render` returns a dict keyed by source. A rejected formula keeps LaTeX's message
  and, for an undefined command, where it is in the source (`marks`), to highlight it.
- `Formula.to_json()` is a JSON-ready summary, sizes in em for web pages.
- `size` is the type size in points, `dpi` the PNG resolution (288 by default, 600 for
  print); both enter the cache key.
- One `FormulaBook` can be shared by the threads of a web server: `render` holds a
  lock. pdfium is not thread-safe: if other code of yours uses pypdfium2, take your own
  lock around `render` too.

## Using the formulas

**In a PDF made with [reportlab-layout](https://pypi.org/project/reportlab_layout/).**
`inline_pdf` sets a PDF page on the baseline of a paragraph (version 1.10, `pdf`
extra), vector and light: each font is embedded once for the whole document.

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
            parts.append(inline_pdf(book.pdf(formula.key), width=box.width, height=box.height, depth=box.depth))
        else:
            parts.append(escape(fragment.text))
    return "".join(parts)
```

Give the markup to an `InlineParagraph`, whose style has `autoLeading="max"`.

**On a web page.** Serve `book.image(key)`; `formula.to_json()` gives `width`, `height`
and `depth` in em, so `height: {height}em; vertical-align: -{depth}em` sets the image on
the baseline at any font size.

**With another PDF library.** Lay the one-page PDF down as a form XObject: its
MediaBox is the box, and the baseline lies `pdf_box.depth` above its bottom.

## Your preamble

The default preamble loads amsmath, amssymb and siunitx. Pass the one of your
documents, without `\documentclass` (the batch uses `book` at 10 pt):

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

`engine` is a name or a path: `lualatex` by default, `pdflatex` if it is missing;
fontspec needs lualatex.

## The cache

`default_cache()` is `~/Library/Caches/texformules` on macOS,
`%LOCALAPPDATA%\texformules\Cache` on Windows, `$XDG_CACHE_HOME/texformules`
(`~/.cache/texformules`) elsewhere; any folder will do, and several programs can share
it. Each formula is `<key>.json`, `<key>.png` and `<key>.pdf`, written atomically.

The key is a hash of the source, the engine, the preamble, the size, the resolution,
and the content of every file the preamble reads outside the TeX distribution: each
compilation runs with `-recorder`, and the TeX and Lua files it read (yours, under
`TEXMFHOME` included) are listed in a manifest. Delete the folder to clear the cache.

## Limits

- A formula is one line of the batch: display environments spanning paragraphs are not
  supported; `$$…$$` and `\[…\]` are set inline, in `\displaystyle`.
- A formula may not define commands, read or write files, or change catcodes: it would
  affect the other formulas of the batch. Define your macros in the preamble.
- In a rejected formula, only an undefined command is located; for other errors, the
  message is all TeX gives.
- A one-page PDF carries the fonts of its whole batch: on its own it is heavier than
  its PNG; it pays off in a document that embeds each font once.
- latexdetok's messages are in English; `latexdetok.set_language("fr")` or
  `LATEXDETOK_LANG=fr` gives them in French.

## Development

```bash
uv sync --group dev
uv run ruff format src tests examples
uv run ruff check src tests examples
uv run mypy
uv run pytest -q              # the `latex` tests are skipped without TeX
uv run pytest -q -m latex     # only those that compile
```

## License

MIT, see [LICENSE](https://github.com/antnardo/texformules/blob/main/LICENSE).
