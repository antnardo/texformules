# Reference

## Contents

- [Overview](#overview)
- [Splitting text](#splitting-text)
  - [`split`](#split)
  - [`Fragment`](#fragment)
  - [`Problem`](#problem)
  - [`comments`](#comments)
  - [`french_spacing`](#french_spacing)
  - [The splitting rules](#the-splitting-rules)
- [Typesetting formulas](#typesetting-formulas)
  - [`FormulaBook`](#formulabook)
  - [`Formula`](#formula)
  - [`PdfBox`](#pdfbox)
  - [`BP_PER_PT`](#bp_per_pt)
  - [`default_cache`](#default_cache)
  - [`default_preamble`](#default_preamble)
  - [`Runner`](#runner)
  - [The batch document](#the-batch-document)
  - [How errors are located](#how-errors-are-located)
  - [The cache](#the-cache)
  - [The JSON of `Formula.to_json()`](#the-json-of-formulato_json)
- [Figures](#figures)
  - [`apply_style`](#apply_style)
  - [`style_params`](#style_params)
  - [`restore_style`](#restore_style)
  - [`figure_size`](#figure_size)
  - [`style_axes`](#style_axes)
  - [`DecimalCommaFormatter`](#decimalcommaformatter)
  - [`add_inset`](#add_inset)
  - [`save_figure`](#save_figure)
  - [Constants](#constants)
  - [Names from `latex_figures`](#names-from-latex_figures)
- [Troubleshooting](#troubleshooting)
- [Every name the package exports](#every-name-the-package-exports)

## Overview

Two steps, two modules, and an optional third:

| Module | Does | Needs |
| --- | --- | --- |
| `texformules.fragments` | cuts a line into text and LaTeX fragments | latexdetok |
| `texformules.formulas` | typesets fragments in one batch, caches PNG and PDF | pypdfium2, Pillow, a TeX distribution at run time |
| `texformules.figures` | styles matplotlib figures for LaTeX documents | the `figures` extra (matplotlib) |

Everything in the first two is re-exported by `texformules`. `import texformules`
does not import matplotlib; `import texformules.figures` without matplotlib raises
`ModuleNotFoundError` with the extra to install.

## Splitting text

### `split`

```python
split(text: str) -> list[Fragment]
```

Cuts `text` into text fragments and LaTeX fragments, `%` comments removed. Text
fragments keep their spaces; two text fragments never follow each other; empty
fragments are dropped, so `split("")` is `[]`. A LaTeX fragment's `text` is the
source to pass to `FormulaBook.render`. Never raises on malformed LaTeX: what is wrong
ends up in `Fragment.problems`.

### `Fragment`

A frozen dataclass.

| Field | Type | Meaning |
| --- | --- | --- |
| `text` | `str` | rendered text, or the LaTeX source to typeset |
| `latex` | `bool` | true for a fragment to typeset (default `False`) |
| `problems` | `tuple[Problem, ...]` | what latexdetok finds in it (default `()`) |

A fragment with an error or a warning is never a LaTeX fragment: `latex` is false and
`text` is the word exactly as typed, so that the positions of its problems fall
within it. A LaTeX fragment may carry `info` problems (a likely typo in a command
name), positioned in its `text`.

### `Problem`

A frozen dataclass.

| Field | Type | Meaning |
| --- | --- | --- |
| `start`, `end` | `int` | the faulty place in the fragment's `text`, end excluded |
| `severity` | `str` | `"error"`, `"warning"` or `"info"` |
| `message` | `str` | why, in latexdetok's language |
| `suggestion` | `str \| None` | the fix, when latexdetok knows one |

latexdetok writes its messages in English unless `latexdetok.set_language("fr")` was
called or `LATEXDETOK_LANG=fr` is set. The messages texformules adds itself (for a
forbidden command) are in English.

### `comments`

```python
comments(text: str) -> list[str]
```

The `%` comments of `text`, without the `%` and stripped: the notes `split` removes.

### `french_spacing`

```python
french_spacing(text: str) -> str
```

The spaces of French typography, as polyglossia sets them: a no-break space (U+00A0)
before `:` and inside `« »`, a narrow no-break space (U+202F) before `; ! ?`, whether
the author typed a space or not. Like polyglossia, even after a digit; only `://` is
spared. Idempotent. Apply it to text fragments only.

### The splitting rules

latexdetok parses the whole line as TeX would: math, groups, comments, and commands
with the arguments their signature gives them.

1. **Comments.** A `%` comment, its end of line and the blanks that follow are
   dropped, as TeX drops them: `"a%c\nb"` gives `"ab"`.
2. **Words.** The line is cut at blanks, except inside a group or between a command
   and its arguments (`\SI{5e-8} N` is one word: the unit is an argument).
3. **Text or formula.** A word is text if all it holds is plain characters, text
   commands and brace groups. The text commands are rendered without LaTeX: `\og`
   `\fg` (French quotes with no-break spaces), `\%` `\&` `\_` `\#` `\$` `\{` `\}`,
   `\,` `\;`, a backslash before a space, `\-` and `\/` (dropped), `\ldots` `\dots` `\textellipsis`,
   `\oe` `\OE` `\ae` `\AE`, `\textendash` `\textemdash`; `~` becomes a no-break
   space; `--`, `---`, two backquotes and `''` become typographic dashes and quotes. Any
   other command, any math, or `^ _ & #` makes the word a formula.
4. **A formula is the whole word**, punctuation included: `($x=1$),` is typeset as
   one, so the line never breaks between the formula and its brackets.
5. **Math is set inline.** `\(…\)` becomes `$…$`; `$$…$$` and `\[…\]` become
   `$\displaystyle …$`. A formula spanning several lines is joined into one.
6. **Checks.** latexdetok's diagnostics for the whole line are attached to the words
   they touch. A word with an `error` or a `warning` stays text, as typed. So does a
   word holding a command that would affect the other formulas of the batch:
   definitions (`\def`, `\newcommand`…), file input (`\input`, `\include`…),
   `\write`, `\openout`, `\openin`, `\immediate`, `\catcode`, `\makeatletter`,
   `\makeatother`, the `document` environment, and the batch's own macros
   `\cdformula` and `\cdsizes`.
7. **Spaces.** `\og` swallows the space after it (it sets its own); `\fg` removes the
   blanks before it, like babel.

## Typesetting formulas

### `FormulaBook`

```python
FormulaBook(
    cache: Path,
    *,
    preamble: str | None = None,   # None: default_preamble()
    engine: str | None = None,     # None: lualatex, else pdflatex
    runner: Runner = subprocess.run,
    timeout: int = 120,            # seconds per compilation
    size: float = 10.0,            # type size, TeX points
    dpi: float = 288.0,            # PNG resolution
)
```

Nothing happens at construction: the preamble and the engine are looked up at the
first formula requested (or at `available`), so an application starts without
waiting for `kpsewhich`. The cache folder is created at the first write.

| Member | Returns | Meaning |
| --- | --- | --- |
| `render(sources: Iterable[str])` | `dict[str, Formula]` | the formulas, keyed by source, in order, duplicates merged; the missing ones typeset in one compilation |
| `available` | `bool` | an engine was given or found |
| `image(key: str)` | `Path \| None` | the PNG; None for an unknown or malformed key |
| `pdf(key: str)` | `Path \| None` | the one-page PDF; None likewise |

`render` never raises for a LaTeX problem: a formula that could not be typeset comes
back with `ok=False` and an `error`. It holds a lock, so a `FormulaBook` can be shared
between threads; pdfium is called under that lock. If other code in the process uses
pypdfium2, take a common lock around `render`.

A malformed key (anything but 24 lowercase hexadecimal digits) never opens a file:
keys may come from a URL.

The `error` strings texformules writes itself:

| `error` | Cause | Cached |
| --- | --- | --- |
| TeX's message, e.g. `Undefined control sequence.` | the formula's own error | yes |
| `preamble: <TeX's message>` | the preamble does not compile | no |
| `compilation interrupted` | fewer pages or dimensions than formulas | no |
| `unreadable dimensions` | a line of the `.sizes` file could not be parsed | no |
| `LaTeX did not finish: <reason>` | the engine could not run, or timed out | no |
| `no LaTeX distribution on this machine` | no engine found | no |

When some formulas fail on their own and others are interrupted (a faulty formula can
shift the pages of the next ones), the interrupted ones are compiled once more
without the faulty ones.

### `Formula`

A frozen dataclass.

| Field | Type | Meaning |
| --- | --- | --- |
| `source` | `str` | the LaTeX source |
| `key` | `str` | 24 hexadecimal digits, the cache key |
| `ok` | `bool` | typeset |
| `width` | `float` | TeX points, border included |
| `height` | `float` | above the baseline, TeX points, border included |
| `depth` | `float` | below the baseline, TeX points, border included |
| `error` | `str \| None` | why it was rejected |
| `size` | `float` | the type size, TeX points |
| `marks` | `tuple[tuple[int, int], ...]` | where LaTeX stumbled in `source`, `(start, end)` pairs |

| Member | Returns |
| --- | --- |
| `pdf_box` | `PdfBox`: the box in PDF points; zeros for a rejected formula |
| `to_json()` | `dict[str, object]`, see [below](#the-json-of-formulato_json) |

The border is half a point on every side: `width` is the ink's width plus 1 pt,
`height` and `depth` each have half a point more than the ink.

### `PdfBox`

A frozen dataclass: `width`, `height`, `depth`, in PDF points (1/72 inch). `width` and
`height` are the size of the one-page PDF (its MediaBox, to TeX's three decimals);
`depth` is the distance from the bottom of the page up to the baseline. They are the
`width`, `height` and `depth` arguments of reportlab-layout's `inline_pdf` and
`inline_image`.

### `BP_PER_PT`

`72 / 72.27`: PDF points per TeX point. `Formula` dimensions times `BP_PER_PT` give
`PdfBox`.

### `default_cache`

```python
default_cache() -> Path
```

`~/Library/Caches/texformules` on macOS, `%LOCALAPPDATA%\texformules\Cache` on
Windows, `$XDG_CACHE_HOME/texformules` (`~/.cache/texformules` by default) elsewhere. Formulas
depend on the preamble, not on the document, so one cache per user serves every
program.

### `default_preamble`

```python
default_preamble() -> str
```

`\usepackage{amsmath,amssymb}` and `\usepackage{siunitx}`, or `\input{ampackages}`
when `kpsewhich ampackages.tex` finds that file (its author's own suite; on other
machines it is absent and the fallback applies). Pass `preamble=` to use your own.

### `Runner`

The type of `FormulaBook(runner=…)`: a callable with `subprocess.run`'s signature. It
is called as `runner(command, cwd=folder, capture_output=True, timeout=…,
check=False)`; its return value is ignored, the files it leaves in `cwd` are read.
Tests pass a fake that writes those files.

### The batch document

The missing formulas are written, one per line, into a document of class `book` at
10 pt (the body is set at `size`), compiled with
`-interaction=nonstopmode -file-line-error -recorder`:

```latex
\documentclass[10pt]{book}
<preamble>
\usepackage[active,tightpage]{preview}
\setlength\PreviewBorder{0.5pt}
% \cdformula{…} boxes its argument, writes its width, height and depth
% to \jobname.sizes, and puts it on a preview page of its own
\begin{document}
\fontsize{10}{12}\selectfont
\cdformula{$\frac{a}{b}$}
\cdformula{\SI{9.81}{m/s^2}}
\end{document}
```

Each formula is set in text mode: write `$…$` for math. pypdfium2 renders each page to
a grey, transparent PNG and copies it, alone, into a one-page PDF.

### How errors are located

With `-file-line-error`, TeX prefixes each error with `file:line:`. Since each formula
is on a line of its own, the line gives the formula; an error above the first formula
is the preamble's.

For `Undefined control sequence`, TeX prints on the next line what it was reading,
ending with the command it does not know, rewritten its own way (a space after each
name, `...` before a long line). texformules takes that name and finds every use of
it in the source with latexdetok, so that `\dd` is not mistaken for the start of
`\ddot`. Those positions are `Formula.marks`. For any other error, TeX does not say
where, and `marks` is empty.

### The cache

For each formula, in the cache folder:

| File | Content |
| --- | --- |
| `<key>.json` | `{"ok", "width", "height", "depth", "error", "marks"}` |
| `<key>.png` | grey and transparent (mode `LA`), at `dpi` |
| `<key>.pdf` | the formula's page, alone |
| `preamble-<hash>.json` | the manifest: the user files the preamble read, one per preamble and engine |

Each file is written to `<name>.part`, then renamed; the PNG and the PDF before the
JSON, so that whoever finds the JSON finds both.

The key is the first 24 hexadecimal digits of the SHA-256 of: a format version, the
engine path, the preamble, the size, the resolution, the path and SHA-256 of each file
in the manifest, and the source. So:

- changing the preamble, the engine, `size` or `dpi` gives new keys;
- **editing a file the preamble reads** gives new keys at the next batch. The manifest
  lists the `INPUT` lines of the `.fls` with a TeX or Lua suffix (`.tex`, `.sty`,
  `.cls`, `.cfg`, `.def`, `.fd`, `.clo`, `.ldf`, `.ltx`, `.lua`) that lie neither in
  the compilation folder nor under the distribution (`SELFAUTOPARENT`, `TEXMFVAR`):
  files under `TEXMFHOME` are followed;
- upgrading the distribution changes the engine's path when its year is in it (TeX
  Live, MacTeX), hence the keys.

A cached rejection is kept only when it is the formula's own fault. A successful entry
whose PNG or PDF is missing is typeset again under the same key. Nothing is ever
deleted: to reclaim the space, delete the folder.

### The JSON of `Formula.to_json()`

For a typeset formula, sizes in em of the type size, rounded to three decimals, so a
web page can scale them with its font:

```json
{"source": "$\\frac{a}{b}$", "key": "b07fb1e59ac4ca2aa8f0f090",
 "width": 0.797, "height": 1.608, "depth": 0.643}
```

`height` is the **total** height (above and below the baseline); `depth` the part
below. In CSS: `height: 1.608em; vertical-align: -0.643em`.

For a rejected formula:

```json
{"source": "$\\oops$", "error": "Undefined control sequence.", "marks": [[1, 6]]}
```

`error` is `"rejected by LaTeX"` when no message was kept.

## Figures

`from texformules.figures import …`, with the `figures` extra. Sizes are in
centimetres.

### `apply_style`

```python
apply_style(width=None, height=None, ratio=None, usetex=True,
            family="sans-serif", preamble=None) -> dict[str, Any]
```

Updates `matplotlib.rcParams` with `style_params(...)` and returns them. Call it
before creating the figures; figures already created keep their settings. The first
call saves the settings it changes, for `restore_style`. No locale is changed.

### `style_params`

```python
style_params(width=None, height=None, ratio=None, usetex=True,
             family="sans-serif", preamble=None) -> dict[str, Any]
```

The settings without applying them, for `plt.rc_context(style_params(8, 6))`.

| Parameter | Meaning |
| --- | --- |
| `width` | cm, 16 by default |
| `height` | cm; by default `ratio` × `width` |
| `ratio` | the golden ratio (0.618) by default |
| `usetex` | render text with LaTeX (`latex`, dvipng or ghostscript needed) |
| `family` | `"sans-serif"` or `"serif"` |
| `preamble` | `text.latex.preamble`: a string, or a list of lines; `PREAMBLE` by default, `""` for none; used only with `usetex` |

The settings: 11 pt labels and titles, 10 pt ticks, 8 pt legend, mathtext tick
formatting, Arial/Helvetica or Times, subplot margins suited to a small figure,
`pgf.texsystem = "pdflatex"`.

### `restore_style`

```python
restore_style() -> None
```

Gives back the settings from before the first `apply_style`; does nothing if it was
not called, or a second time.

### `figure_size`

```python
figure_size(width=16.0, height=None, ratio=None) -> tuple[float, float]
```

The size in inches of a figure given in cm. Without `height`, it is `ratio` × `width`
(golden ratio by default). A height over `MAX_HEIGHT` (22 cm) is brought down to it,
with a `UserWarning`.

### `style_axes`

```python
style_axes(ax=None, format_ticks=True, decimal_comma=True) -> Axes
```

Grey 0.5 pt spines, ticks outward at the bottom and left, and with `format_ticks` a
formatter of its own on each linear axis: `DecimalCommaFormatter`, or with
`decimal_comma=False` a mathtext `ScalarFormatter` with the same power limits.
Logarithmic axes keep theirs. Calls `tight_layout` on the figure. `ax` defaults to
`plt.gca()`; returns it.

### `DecimalCommaFormatter`

A `matplotlib.ticker.ScalarFormatter` in math notation, with powers of ten outside
[10⁻², 10⁴], writing `1{,}5` for 1.5 (`{,}` keeps math mode from adding a space after
the comma). The comma does not come from `locale`, which acts on the whole program and
fails without a French locale.

### `add_inset`

```python
add_inset(ax, rect) -> Axes
```

Inset axes inside `ax`, `rect = [x0, y0, width, height]` in fractions of `ax`. Tick
labels shrink as the square root of the relative size. Built on `Axes.inset_axes`, so
the inset follows `ax` when the layout changes.

### `save_figure`

```python
save_figure(fig, path, fmt=None, dpi=300, tight=True, crop=True) -> Path
```

Saves `fig` as PDF, PNG or EPS, from the extension of `path` or from `fmt`, adding the
extension when missing, then crops it to the ink with the first tool found in
`FORMATS`: pdfcrop, ImageMagick (`magick` or `convert`), epstool. No shell is used,
and the temporary file is deleted. Returns the absolute path written.

- `ValueError` for another format;
- a `UserWarning`, and an uncropped figure, when no tool is found;
- `subprocess.CalledProcessError` when the tool fails.

### Constants

| Name | Value |
| --- | --- |
| `PREAMBLE` | `\usepackage{amsmath}` and `\usepackage{siunitx}` |
| `INCH` | 2.54 (cm) |
| `MAX_HEIGHT` | 22.0 (cm), the usable height of an A4 page |
| `FORMATS` | format → list of cropping commands, `{e}` the input, `{s}` the output |

### Names from `latex_figures`

The figures were the `latex_figures` package. Its names are kept, **deprecated**, so
that scripts only change their import (`from latex_figures import …` becomes
`from texformules.figures import …`). They will be removed in a future major
release.

| Old name | New name | Note |
| --- | --- | --- |
| `latexify(fig_width, fig_height, ratio, usetex, famille, preamble)` | `apply_style(width, height, ratio, usetex, family, preamble)` | the old one keeps `PREAMBULE` as its default |
| `parametres_latex(...)` | `style_params(...)` | same |
| `restaurer()` | `restore_style()` | the same function |
| `fig_size(fig_width, fig_height, ratio)` | `figure_size(width, height, ratio)` | |
| `format_axes(ax, format_ticks)` | `style_axes(ax, format_ticks, decimal_comma)` | the same function |
| `ScalarFormatterVirgule` | `DecimalCommaFormatter` | the same class |
| `add_subplot_axes(ax, rect)` | `add_inset(ax, rect)` | the same function |
| `save_fig(fig, file_name, fmt, dpi, tight, crop)` | `save_figure(fig, path, fmt, dpi, tight, crop)` | |
| `PREAMBULE` | `PREAMBLE` | the old one loads `\usepackage[french]{babel}` and siunitx; the new one amsmath and siunitx |
| `INCH`, `MAX_HEIGHT`, `FORMATS` | unchanged | |

They live in `texformules.figures.legacy` and are re-exported by
`texformules.figures`.

## Troubleshooting

**Every formula fails with `no LaTeX distribution on this machine`.** Neither
`lualatex` nor `pdflatex` is on the `PATH` of the process. A GUI or a service may not
see the shell's `PATH`: pass `engine="/full/path/to/lualatex"`.

**Every formula fails with `preamble: …`.** The preamble does not compile; the message
is TeX's first error. Compile a minimal document with that preamble by hand. A
missing `preview.sty` shows up here too (Debian: `preview-latex-style`).

**`LaTeX did not finish: … timed out`.** The first compilation with a large preamble,
or a fresh LuaTeX font cache, can take long: raise `timeout`.

**A macro was changed but the old rendering stays.** The file defining it is not in
the manifest: it lies under the distribution's tree, or has a suffix that is not
followed. Move it under `TEXMFHOME` or next to your project, or delete the cache.

**Formulas look right on screen but blurry on paper.** Use the PDF (`book.pdf`) with
reportlab-layout's `inline_pdf`, or raise `dpi` to 600.

**`ModuleNotFoundError: texformules.figures needs matplotlib`.** Install the extra:
`pip install "texformules[figures]"`.

**Figures fail with `usetex`.** matplotlib needs `latex`, and dvipng or ghostscript,
plus the packages of the preamble (siunitx). Pass `usetex=False` to use mathtext.

**latexdetok's messages are in the wrong language.** Call
`latexdetok.set_language("en")` or `("fr")`, or set `LATEXDETOK_LANG`.

**latexdetok's warnings fill the log.** `split` reports them as problems already;
`logging.getLogger("latexdetok").setLevel(logging.ERROR)` keeps them out of the log.

## Every name the package exports

`texformules`:

| Name | Kind |
| --- | --- |
| `BP_PER_PT` | constant |
| `Formula` | dataclass |
| `FormulaBook` | class |
| `Fragment` | dataclass |
| `PdfBox` | dataclass |
| `Problem` | dataclass |
| `Runner` | type alias |
| `__version__` | string |
| `comments` | function |
| `default_cache` | function |
| `default_preamble` | function |
| `french_spacing` | function |
| `split` | function |

`texformules.figures`: `FORMATS`, `INCH`, `MAX_HEIGHT`, `PREAMBLE`,
`DecimalCommaFormatter`, `add_inset`, `apply_style`, `figure_size`, `restore_style`,
`save_figure`, `style_axes`, `style_params`; deprecated: `PREAMBULE`,
`ScalarFormatterVirgule`, `add_subplot_axes`, `fig_size`, `format_axes`, `latexify`,
`parametres_latex`, `restaurer`, `save_fig`.
