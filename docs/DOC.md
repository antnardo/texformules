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
- [Troubleshooting](#troubleshooting)
- [Every name the package exports](#every-name-the-package-exports)

## Overview

Two steps, two modules:

| Module | Does | Needs |
| --- | --- | --- |
| `texformules.fragments` | cuts a line into text and LaTeX fragments | latexdetok |
| `texformules.formulas` | typesets fragments in one batch, caches PNG and PDF | pypdfium2, Pillow, a TeX distribution at run time |

Everything is re-exported by `texformules`.

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
   definitions (`\def`, `\newcommand`…), `\global`, file input (`\input`, `\include`…),
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
| `not sent to LaTeX: <latexdetok's message>` | a brace, a bracket, a `$` or an environment never closed, or closed without being opened | no |
| `not sent to LaTeX: "\gdef" is not allowed in a formula: …` | a command that would affect the other formulas, the ones `split` refuses (step 6 above) | no |
| TeX's message, e.g. `Undefined control sequence.` | the formula's own error | yes |
| `preamble: <TeX's message>` | the preamble does not compile | no |
| `compilation interrupted` | fewer pages or dimensions than formulas | no |
| `unreadable dimensions` | a line of the `.sizes` file could not be parsed | no |
| `LaTeX did not finish: <reason>` | the engine could not run, or timed out | no |
| `no LaTeX distribution on this machine` | no engine found | no |

Before the compilation, latexdetok reads each source alone. One that would not stay in
its place in the batch — `$\frac{1}{2$`, `a}`, `\begin{align}x` — would swallow the
next formulas and `\end{document}`, and TeX would attribute the error to no line: it is
refused, with `marks` on the faulty places, and the others are typeset. So is a source
holding a command that would affect the other formulas, the ones `split` keeps as text
(step 6 above):

```python
formulas = book.render(["$a$", r"$\frac{1}{2$"])
formulas["$a$"].ok                            # True
bad = formulas[r"$\frac{1}{2$"]
bad.error                                     # 'not sent to LaTeX: “$” never closed'
[bad.source[s:e] for s, e in bad.marks]       # ['$', '{', '$']
```

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

`\usepackage{amsmath,amssymb}` and `\usepackage{siunitx}`. Pass `preamble=` to use your
own.

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
  the compilation folder nor in a tree of the distribution (`TEXMFDIST`, `TEXMFMAIN`,
  `TEXMFSYSVAR`, `TEXMFSYSCONFIG`, `TEXMFVAR`, `TEXMFCONFIG`, as `kpsewhich` names
  them): files under `TEXMFHOME` and `TEXMFLOCAL` are followed;
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
