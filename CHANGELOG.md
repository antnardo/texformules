# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-10-18

First release on PyPI. The formulas were a module shared by two private projects; the
figures were the `latex_figures` package, never published.

### Added

- **`split(text)`** cuts a line into text and LaTeX `Fragment`s on latexdetok's tree:
  a formula takes its whole word, punctuation included, and a command keeps its
  arguments even without braces; `%` comments are removed (`comments` returns them);
  text commands, `~` and ligatures are rendered without LaTeX. The whole line is
  checked by latexdetok, and a word with an error or a warning, or with a command
  that would affect the other formulas of the batch, stays text, with its `Problem`s
  located.
- **`FormulaBook(cache, preamble=…, engine=…)`** typesets the missing formulas in a
  single compilation (`render`), and keeps each one as a grey transparent PNG and as
  a one-page vector PDF, with its width, height and depth (`Formula`, and `PdfBox` in
  PDF points). The cache key follows the content of every file the preamble reads
  outside the distribution, recorded with `-recorder`. Rejected formulas keep TeX's
  message, and the places of an undefined command (`Formula.marks`).
  `Formula.to_json()` gives sizes in em for web pages.
- `default_cache()`, `default_preamble()` (amsmath, amssymb and siunitx),
  `french_spacing()`, `BP_PER_PT`.
- **`texformules.figures`**, with the `figures` extra (matplotlib ≥ 3.8):
  `apply_style`, `style_params`, `restore_style`, `figure_size`, `style_axes` (with
  `decimal_comma`), `DecimalCommaFormatter`, `add_inset`, `save_figure` (cropped by
  pdfcrop, ImageMagick or epstool), from `latex_figures` 0.1.0.
- The names of `latex_figures` (`latexify`, `parametres_latex`, `restaurer`,
  `fig_size`, `format_axes`, `ScalarFormatterVirgule`, `add_subplot_axes`, `save_fig`,
  `PREAMBULE`) as deprecated aliases, with their old keywords and defaults.
- `py.typed`, documentation in `docs/DOC.md`, examples, CI on Linux and macOS with
  Python 3.13 and 3.14 and a job compiling with TeX Live, publication through PyPI
  trusted publishing.

### Changed, for those who used the unpublished code

- Comments, docstrings and error messages are in English: `rejected by LaTeX`,
  `preamble: …`, `compilation interrupted`, `no LaTeX distribution on this machine`.
- Importing `texformules` no longer sets latexdetok's language to French nor lowers
  its logger's level: call `latexdetok.set_language("fr")` and set the `latexdetok`
  logger's level yourself.
- The preamble manifest is now `preamble-<hash>.json` (was `preambule-…`): formulas
  cached before are typeset once more, under new keys.
- The figures' new default preamble loads amsmath and siunitx instead of French babel
  and siunitx; the deprecated `latexify` and `parametres_latex` keep the old one.

[0.1.0]: https://github.com/antnardo/texformules/releases/tag/v0.1.0
