"""Formulas typeset by LaTeX once and for all, and kept as PNG and as PDF.

Formulas written for a real LaTeX document use the macros of its preamble
(``\\vect``, ``\\dd``, ``\\SI`` from siunitx…). No renderer that does without LaTeX
knows them — not a conversion to Unicode, not matplotlib's mathtext, not KaTeX. So
each formula is typeset by LaTeX with that preamble. The missing formulas go together
into **a single compilation** — about five seconds, the time it takes to load a large
preamble — and each is then kept in a cache, as PNG and as a one-page PDF.

The ``preview`` package makes each formula a page of its own size. TeX writes its
dimensions (width, height, depth) to a separate file: the depth gives the baseline, to
set the image on the line of the text. A half-point border keeps the antialiasing from
being clipped; the dimensions include it. pypdfium2 renders the pages, without dvipng
or ImageMagick: 288 dots per inch are enough on screen, 600 for print.

**A one-page PDF per formula** is kept beside the PNG, under the same key: the very
page ``preview`` made in the batch's PDF, extracted by pypdfium2 (``import_pages``),
with no other dependency. It is therefore the PNG's box, border included: its MediaBox
has the width and total height TeX reports, to the rounding of its three decimals, and
the baseline runs at the depth above the bottom (:class:`PdfBox`, in PDF points). Laid
down as a form XObject, the formula prints as vectors: sharp at any printer resolution
and any zoom, where a PNG, even at 600 dots per inch, remains a raster that the printer
resamples and that zooming shows.

What this PDF weighs comes down to its fonts. It embeds those it uses, but subset for
**the whole batch** and not for its own glyphs alone: pdfium copies the page's objects
as they are and cannot tighten a subset. Measured on 2026-10-09 on a hundred typical
formulas with a large preamble (lualatex, Erewhon and Gentium): the batch's PDF weighs
89 kB; each one-page PDF from 10 to 53 kB, 15 kB median, 1.8 MB for the hundred, 70 %
of it fonts; the PNGs at 600 dots per inch 6.4 kB median, 0.66 MB for the hundred. In a
batch of seven, a PDF weighs 4 to 8 kB. On its own, the PDF is thus heavier than its
PNG. But the hundred carry only five distinct font streams, 46 kB in all, identical to
the byte from one PDF to another of the same batch. For a vector document to weigh
less than with PNGs, it must embed each stream only once, recognised by its digest —
which is the job of the layout library (reportlab-layout's ``inline_pdf`` does it).

An entry kept before the PDFs existed has none: like an entry whose PNG is missing, it
is typeset again under the same key, by the first batch that asks for it — one
compilation per batch, once. Bumping ``_VERSION`` would have cost as many compilations,
but changed every key and left the old PNGs in the cache, which nothing cleans up; and
the rendering had not changed. A kept rejection has neither PNG nor PDF and stays
valid. The extraction happens inside ``render``, with the batch's PDF open: the calls
to pdfium stay under whatever lock a caller takes around ``render`` (pdfium is not
thread-safe).

**The fingerprint of the preamble** goes into the key of every formula. Hashing the
text of the preamble is not enough: ``\\input{mymacros}`` is one line, and the macros
live in ``mymacros.tex``, in the packages it loads… So every compilation runs with
``-recorder``, whose ``.fls`` lists the files read; those that do not come from the
distribution (the user's own TeX and Lua sources, ``TEXMFHOME`` included) are kept in a
manifest, and their content goes into the fingerprint. Changing ``\\vect`` therefore
typesets the formulas again, at the next batch. The distribution itself only changes
with its release year, which is in the engine's path. Data files the preamble reads
(a ``.py`` read through Lua, say) do not enter it: they change often, and never a
formula.

A formula TeX rejects is located by the line of the error in the log
(``-file-line-error``): it stays as raw LaTeX, flagged, and the rejection is kept. A
rejection that is not the formula's own doing (broken preamble, interrupted
compilation, no LaTeX) is not kept: the formula will be tried again. If the PDF does
not have one page per formula, the batch is run once more without the faulty formulas.

Without a LaTeX distribution, nothing is typeset: callers show the sources as they are.
"""

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pypdfium2
from latexdetok import TexFile, TexGroup

__all__ = [
    "BP_PER_PT",
    "Formula",
    "FormulaBook",
    "PdfBox",
    "Runner",
    "default_cache",
    "default_preamble",
]

#: PDF points (1/72 inch) per TeX point (1/72.27 inch).
BP_PER_PT = 72 / 72.27

# Changing the rendering (border, template) changes this version, hence the fingerprints.
_VERSION = "2"
_BORDER_PT = 0.5  # around each formula, so as not to clip the antialiasing
_KEY = re.compile(r"[0-9a-f]{24}")
_JOB = "formules"
# What a rejection owes to the formula itself: only that kind is kept in the cache.
_OWN_ERROR = "own"
# The sources recorded in the manifest, data files excluded (see the module docstring).
_SOURCES = frozenset({".tex", ".sty", ".cls", ".cfg", ".def", ".fd", ".clo", ".ldf", ".ltx", ".lua"})
_FALLBACK_PREAMBLE = "\\usepackage{amsmath,amssymb}\n\\usepackage{siunitx}"

#: What runs the engine: ``subprocess.run``'s signature; tests pass a fake.
Runner = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class PdfBox:
    """A formula's box in PDF points, border included: the box of its PDF page.

    ``width`` and ``height`` are the **total** width and height of the page (its
    MediaBox, to TeX's rounding, three decimals); ``depth`` is the distance from the
    bottom of the page to the baseline. They are the ``width``, ``height`` and
    ``depth`` of reportlab-layout's ``inline_image`` and ``inline_pdf``, for the PNG as
    for the PDF.
    """

    width: float
    height: float
    depth: float


@dataclass(frozen=True, slots=True)
class Formula:
    """A typeset formula, or one TeX rejected.

    The dimensions are in TeX points, border included: ``height`` above the baseline,
    ``depth`` below it. ``size`` is the type size it was set in. :attr:`pdf_box` gives
    them in PDF points, to lay down the image or the PDF page.
    """

    source: str
    key: str
    ok: bool
    width: float = 0.0
    height: float = 0.0
    depth: float = 0.0
    error: str | None = None
    size: float = 10.0
    # Where LaTeX stumbled in the rejected source, when its log says so (_faulty).
    marks: tuple[tuple[int, int], ...] = ()

    @property
    def pdf_box(self) -> PdfBox:
        """The box in PDF points; zero for a rejected formula."""
        return PdfBox(
            width=self.width * BP_PER_PT,
            height=(self.height + self.depth) * BP_PER_PT,
            depth=self.depth * BP_PER_PT,
        )

    def to_json(self) -> dict[str, object]:
        """For web pages: the size in em and the baseline, or the reason for the rejection."""
        if not self.ok:
            return {
                "source": self.source,
                "error": self.error or "rejected by LaTeX",
                "marks": [list(mark) for mark in self.marks],
            }
        return {
            "source": self.source,
            "key": self.key,
            "width": round(self.width / self.size, 3),
            "height": round((self.height + self.depth) / self.size, 3),
            "depth": round(self.depth / self.size, 3),
        }


def default_cache() -> Path:
    """The cache of the formulas, per user: they depend on the preamble, not on the document."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "texformules"
    if sys.platform == "win32":
        return (
            Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
            / "texformules"
            / "Cache"
        )
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "texformules"


def default_preamble() -> str:
    """amsmath, amssymb and siunitx; ``\\input{ampackages}`` when kpsewhich finds it.

    ``ampackages`` is its author's own macro suite: on any other machine kpsewhich does
    not find it, and the fallback applies. Pass ``preamble=`` to :class:`FormulaBook`
    to use your own.
    """
    if _kpsewhich("ampackages.tex") is not None:
        return "\\input{ampackages}"
    return _FALLBACK_PREAMBLE


def _kpsewhich(*arguments: str) -> Path | None:
    program = shutil.which("kpsewhich")
    if program is None:
        return None
    try:
        found = subprocess.run(
            [program, *arguments], capture_output=True, text=True, timeout=10, check=False
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(found) if found else None


@dataclass(frozen=True, slots=True)
class _Result:
    """What a compilation says about a formula, before it enters the cache."""

    source: str
    ok: bool
    width: float = 0.0
    height: float = 0.0
    depth: float = 0.0
    image: bytes = b""
    pdf: bytes = b""
    error: str | None = None
    cause: str | None = None  # _OWN_ERROR when the rejection is the formula's own doing
    marks: tuple[tuple[int, int], ...] = ()


class FormulaBook:
    """Typesets the missing formulas and keeps them: one compilation per batch.

    :param cache: the cache folder, safely shared between programs: each file is
        written aside, then renamed.
    :param preamble: the preamble, without ``\\documentclass``; by default
        :func:`default_preamble`.
    :param engine: the engine, a name or a path; by default lualatex, else pdflatex.
    :param runner: what runs the engine, with ``subprocess.run``'s signature.
    :param timeout: how long a compilation may take, in seconds.
    :param size: the type size, in TeX points.
    :param dpi: the resolution of the images, in pixels per inch.

    The preamble and the engine are only looked up at the first formula asked for: an
    application starts without waiting for kpsewhich.
    """

    def __init__(
        self,
        cache: Path,
        *,
        preamble: str | None = None,
        engine: str | None = None,
        runner: Runner = subprocess.run,
        timeout: int = 120,
        size: float = 10.0,
        dpi: float = 288.0,
    ) -> None:
        self._cache = cache
        self._wanted = (preamble, engine)
        self._runner = runner
        self._timeout = timeout
        self._size = size
        self._dpi = dpi
        self._lock = threading.Lock()
        self._settled: tuple[str, str | None, str] | None = None

    @property
    def available(self) -> bool:
        """True when a TeX engine was found (or given): formulas can be typeset."""
        return self._settle()[1] is not None

    def image(self, key: str) -> Path | None:
        """The PNG of a typeset formula, or None if the key is unknown or malformed."""
        return self._file(key, ".png")

    def pdf(self, key: str) -> Path | None:
        """The one-page PDF of a typeset formula, or None like :meth:`image`.

        The page is the box of :attr:`Formula.pdf_box`, baseline at ``depth`` from the bottom.
        """
        return self._file(key, ".pdf")

    def _file(self, key: str, suffix: str) -> Path | None:
        # The key comes from web pages too: only a well-formed one may name a file.
        if not _KEY.fullmatch(key):
            return None
        path = self._cache / f"{key}{suffix}"
        return path if path.is_file() else None

    def render(self, sources: Iterable[str]) -> dict[str, Formula]:
        """The formulas asked for, typeset if need be; a single compilation for all of them."""
        wanted = list(dict.fromkeys(sources))
        with self._lock:
            known = {source: self._cached(source) for source in wanted}
            missing = [source for source, formula in known.items() if formula is None]
            if missing:
                results = self._compile(missing)
                self._settled = None  # the manifest may have changed the fingerprint
                for result in results:
                    known[result.source] = self._store(result)
        return {source: formula for source, formula in known.items() if formula is not None}

    # ------------------------------------------------------------------
    # Fingerprint and cache
    # ------------------------------------------------------------------
    def _settle(self) -> tuple[str, str | None, str]:
        """Preamble, engine, and the fingerprint that goes into every key."""
        if self._settled is None:
            preamble, engine = self._wanted
            preamble = default_preamble() if preamble is None else preamble
            engine = engine if engine is not None else _engine()
            parts = [_VERSION, str(engine), preamble, f"{self._size:g}pt", f"{self._dpi:g}dpi"]
            for path in self._manifest(preamble, engine):
                try:
                    parts.append(f"{path}:{hashlib.sha256(path.read_bytes()).hexdigest()}")
                except OSError:
                    parts.append(f"{path}:absent")
            self._settled = (preamble, engine, "\n".join(parts))
        return self._settled

    def _manifest_path(self, preamble: str, engine: str | None) -> Path:
        digest = hashlib.sha256(f"{_VERSION}\n{engine}\n{preamble}".encode()).hexdigest()[:24]
        return self._cache / f"preamble-{digest}.json"

    def _manifest(self, preamble: str, engine: str | None) -> list[Path]:
        """The user's files the preamble reads, as recorded by the last batch."""
        record = self._manifest_path(preamble, engine)
        try:
            return [Path(path) for path in json.loads(record.read_text(encoding="utf-8"))]
        except (OSError, ValueError, TypeError):
            return []

    def _key(self, source: str) -> str:
        salt = self._settle()[2]
        return hashlib.sha256(f"{salt}\n{source}".encode()).hexdigest()[:24]

    def _cached(self, source: str) -> Formula | None:
        key = self._key(source)
        record = self._cache / f"{key}.json"
        if not record.is_file():
            return None
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
            if not data.get("ok") and "marks" not in data:
                return None  # rejected before errors were located: typeset once more
            data["marks"] = tuple(tuple(mark) for mark in data.get("marks", ()))
            formula = Formula(source=source, key=key, size=self._size, **data)
        except (ValueError, TypeError):
            return None
        if formula.ok and (self.image(key) is None or self.pdf(key) is None):
            return None  # an entry from before the PDFs, or a maimed one: typeset under the same key
        return formula

    def _store(self, result: _Result) -> Formula:
        key = self._key(result.source)
        formula = Formula(
            source=result.source,
            key=key,
            ok=result.ok,
            width=result.width,
            height=result.height,
            depth=result.depth,
            error=result.error,
            size=self._size,
            marks=result.marks,
        )
        if result.ok or result.cause == _OWN_ERROR:
            self._cache.mkdir(parents=True, exist_ok=True)
            if result.ok:
                # Image and PDF before the JSON: whoever reads the JSON finds both.
                _write_atomically(self._cache / f"{key}.png", result.image)
                _write_atomically(self._cache / f"{key}.pdf", result.pdf)
            data = {
                "ok": formula.ok,
                "width": formula.width,
                "height": formula.height,
                "depth": formula.depth,
                "error": formula.error,
                "marks": [list(mark) for mark in formula.marks],
            }
            _write_atomically(self._cache / f"{key}.json", json.dumps(data).encode())
        return formula

    # ------------------------------------------------------------------
    # Compilation
    # ------------------------------------------------------------------
    def _compile(self, sources: Sequence[str]) -> list[_Result]:
        preamble, engine, _ = self._settle()
        if engine is None:
            return [
                _Result(source, False, error="no LaTeX distribution on this machine") for source in sources
            ]
        results = self._run(preamble, engine, sources)
        faulty = {result.source for result in results if result.cause == _OWN_ERROR}
        interrupted = [result for result in results if not result.ok and result.cause is None]
        if faulty and interrupted:
            # A faulty formula may have shifted the pages of the next ones: typeset them without it.
            retried = {
                result.source: result
                for result in self._run(preamble, engine, [r.source for r in interrupted])
            }
            results = [retried.get(result.source, result) for result in results]
        return results

    def _run(self, preamble: str, engine: str, sources: Sequence[str]) -> list[_Result]:
        with tempfile.TemporaryDirectory(prefix="texformules-") as folder:
            work = Path(folder)
            first_line = _write_document(work / f"{_JOB}.tex", preamble, sources, self._size)
            command = [engine, "-interaction=nonstopmode", "-file-line-error", "-recorder", f"{_JOB}.tex"]
            try:
                self._runner(command, cwd=work, capture_output=True, timeout=self._timeout, check=False)
            except (OSError, subprocess.SubprocessError) as error:
                return [_Result(source, False, error=f"LaTeX did not finish: {error}") for source in sources]
            self._record_manifest(work, preamble, engine)
            return self._collect(work, sources, first_line)

    def _collect(self, work: Path, sources: Sequence[str], first_line: int) -> list[_Result]:
        errors = _errors(work / f"{_JOB}.log")
        preamble = [message for line, (message, _) in errors.items() if line < first_line]
        if preamble:
            return [_Result(source, False, error=f"preamble: {preamble[0]}") for source in sources]
        sizes_path = work / f"{_JOB}.sizes"
        sizes = sizes_path.read_text(encoding="utf-8").splitlines() if sizes_path.is_file() else []
        pdf = work / f"{_JOB}.pdf"
        document = pypdfium2.PdfDocument(pdf) if pdf.is_file() else None
        results: list[_Result] = []
        try:
            aligned = document is not None and len(document) == len(sources) == len(sizes)
            for rank, source in enumerate(sources):
                if (first_line + rank) in errors:
                    message, context = errors[first_line + rank]
                    marks = _faulty(source, message, context)
                    results.append(_Result(source, False, error=message, cause=_OWN_ERROR, marks=marks))
                elif not aligned or document is None:
                    results.append(_Result(source, False, error="compilation interrupted"))
                else:
                    results.append(self._keep(source, document, rank, sizes[rank]))
        finally:
            if document is not None:
                document.close()
        return results

    def _keep(self, source: str, document: pypdfium2.PdfDocument, rank: int, size_line: str) -> _Result:
        values = [float(value) for value in re.findall(r"(-?[\d.]+)pt", size_line)]
        if len(values) != 3:
            return _Result(source, False, error="unreadable dimensions")
        width, height, depth = values
        bitmap = document[rank].render(scale=self._dpi / 72, fill_color=(255, 255, 255, 0))
        return _Result(
            source,
            True,
            width=width + 2 * _BORDER_PT,
            height=height + _BORDER_PT,
            depth=depth + _BORDER_PT,
            image=_png(bitmap.to_pil()),
            pdf=_single_page(document, rank),
        )

    def _record_manifest(self, work: Path, preamble: str, engine: str) -> None:
        """Records from the ``.fls`` the files read outside the distribution."""
        recorder = work / f"{_JOB}.fls"
        if not recorder.is_file():
            return
        distribution = [
            path
            for path in (_kpsewhich("-var-value=SELFAUTOPARENT"), _kpsewhich("-var-value=TEXMFVAR"))
            if path
        ]
        inputs: dict[str, None] = {}
        base = work
        for line in recorder.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("PWD "):
                base = Path(line[4:])
            elif line.startswith("INPUT "):
                path = Path(line[6:])
                path = path if path.is_absolute() else base / path
                path = path.resolve()
                if (
                    path.suffix not in _SOURCES
                    or path.is_relative_to(work.resolve())
                    or any(path.is_relative_to(root.resolve()) for root in distribution)
                ):
                    continue
                inputs[str(path)] = None
        self._cache.mkdir(parents=True, exist_ok=True)
        record = self._manifest_path(preamble, engine)
        _write_atomically(record, json.dumps(sorted(inputs), indent=0).encode())


def _png(image: Any) -> bytes:
    """The image as a grey, transparent PNG: the formula prints in black, on any background."""
    buffer = io.BytesIO()
    image.convert("LA").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _single_page(document: pypdfium2.PdfDocument, rank: int) -> bytes:
    """Page ``rank`` of the batch, alone in a PDF: same MediaBox, same resources."""
    single = pypdfium2.PdfDocument.new()
    try:
        single.import_pages(document, [rank])
        buffer = io.BytesIO()
        single.save(buffer)
    finally:
        single.close()
    return buffer.getvalue()


def _write_atomically(path: Path, data: bytes) -> None:
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(data)
    partial.replace(path)


def _write_document(path: Path, preamble: str, sources: Sequence[str], size: float) -> int:
    """The batch's document; returns the line of the first formula, for reading the log."""
    head = [
        "\\documentclass[10pt]{book}",
        *preamble.splitlines(),
        "\\usepackage[active,tightpage]{preview}",
        f"\\setlength\\PreviewBorder{{{_BORDER_PT}pt}}",
        "\\newwrite\\cdsizes",
        "\\immediate\\openout\\cdsizes=\\jobname.sizes",
        "\\newcommand\\cdformula[1]{\\sbox0{#1}"
        "\\immediate\\write\\cdsizes{\\the\\wd0,\\the\\ht0,\\the\\dp0}"
        "\\begin{preview}\\usebox0\\end{preview}}",
        "\\begin{document}",
        f"\\fontsize{{{size:g}}}{{{1.2 * size:g}}}\\selectfont",
    ]
    lines = [*head, *(f"\\cdformula{{{source}}}" for source in sources), "\\end{document}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(head) + 1


def _errors(log: Path) -> dict[int, tuple[str, str]]:
    """The errors of the log, by line of the source (``-file-line-error``): the message,
    and the line after it, where TeX shows what it was reading when it stumbled."""
    errors: dict[int, tuple[str, str]] = {}
    if not log.is_file():
        return errors
    pattern = re.compile(rf"^(?:\./)?{_JOB}\.tex:(\d+): (.*)$")
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    for rank, line in enumerate(lines):
        found = pattern.match(line)
        if found:
            context = lines[rank + 1] if rank + 1 < len(lines) else ""
            errors.setdefault(int(found.group(1)), (found.group(2).strip(), context))
    return errors


def _faulty(source: str, message: str, context: str) -> tuple[tuple[int, int], ...]:
    """Where LaTeX stumbled in a formula, as positions in its source: every use of the
    command it does not know. TeX puts it at the end of the line after the message
    ("The control sequence at the end of the top line of your error message was never
    \\def'ed"), with the tokens rewritten its own way — a space after each name, "..."
    before a line too long —: only the name is kept, and latexdetok finds it in the
    source, where a pattern would mistake it for the start of another one (``\\dd`` and
    ``\\ddot``). For other errors, the log does not say where: nothing is located."""
    if not message.startswith("Undefined control sequence"):
        return ()
    found = re.search(r"\\([A-Za-z@]+|.)\s*$", context)
    if found is None:
        return ()
    name = found.group(1)
    tex = TexFile([source])
    stack = list(tex.analyse().content)
    marks = []
    while stack:
        node = stack.pop()
        if isinstance(node, TexGroup):
            stack.extend(node.content)
        elif node.is_command(name) and node.start_position and node.end_position:
            marks.append((node.start_position[1], node.end_position[1]))
    return tuple(sorted(marks))


def _engine() -> str | None:
    """lualatex, which fontspec-based preambles need, else pdflatex."""
    for name in ("lualatex", "pdflatex"):
        found = shutil.which(name)
        if found is not None:
            return found
    return None
