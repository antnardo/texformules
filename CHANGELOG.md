# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [0.2.1] — 2026-10-20

### Fixed

- `FormulaBook.render` no longer loses the whole batch to one source left open. A
  brace, a bracket, a `$` or an environment never closed (or closed without being
  opened) swallowed the next formulas and `\end{document}`, and every formula came back
  `compilation interrupted`. latexdetok now reads each source before the batch is
  written: such a source is refused (`not sent to LaTeX: …`, its places in `marks`),
  and the others are typeset.
- `FormulaBook.render` refuses as well the commands `split` keeps as text, which would
  affect the other formulas of the batch: definitions, `\global`, file input and
  output, `\catcode`, `\makeatletter`, the `document` environment, `\cdformula` and
  `\cdsizes`. A caller that did not go through `split` sent them to LaTeX.

## [0.2.0] — 2026-10-18

texformules does one thing: the formulas.

### Removed

- `texformules.figures` and the `figures` extra: styling matplotlib figures is another
  job, for another package.

### Changed

- `default_preamble()` is always amsmath, amssymb and siunitx.

## [0.1.0] — 2026-10-18

First release.

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
- `default_cache()`, `default_preamble()`, `french_spacing()`, `BP_PER_PT`.

[0.2.1]: https://github.com/antnardo/texformules/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/antnardo/texformules/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/antnardo/texformules/releases/tag/v0.1.0
