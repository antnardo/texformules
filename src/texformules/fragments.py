"""A line of text cut into plain text and LaTeX fragments, on latexdetok's tree.

The lines this was written for are grading-scheme criteria, comments and labels: prose
with a formula here and there, typed by hand. latexdetok reads the line as TeX would
read it: math, groups, comments, commands with the arguments their signature gives
them, including without braces (``\\SI{5e-8}N``, ``\\SI1{\\micro m}``) or after a space
(``\\SI{5e-8} N``). A split written by hand, character by character, cut those
arguments off their command; real lines are full of them.

A LaTeX fragment covers the whole **word**: the run without blanks that holds the
formula, brackets and punctuation included (``(\\SI{100}{cm^3}),``), plus the arguments
bound to its commands. reportlab breaks a line on either side of each image, space or
not; a formula on its own would leave "(" at the end of a line and "," at the start of
the next. Typeset with the word, the punctuation stays in place, in the same font,
since LaTeX sets it with the same preamble.

The rest is text, translated as TeX would print it: ``%`` comments removed (notes the
author keeps for themself, which the reader must not see), ``\\og``/``\\fg``, ``~``, the
``--`` and ``---`` ligatures, group braces, the space a command word swallows.

**The whole line goes through latexdetok** (``check``): structure and meaning, as TeX
would read them — a ``$`` never closed, a brace left open, ``_`` or ``\\alpha`` outside
math, ``\\left`` without ``\\right``. A word touched by an error or a warning is not
sent to LaTeX, where it would break the batch: it stays as typed, with its
:class:`Problem` objects — where, and why — for the caller to show. An information
("``\\dfarc`` unknown: ``\\dfrac``?") stops nothing: LaTeX will say whether the command
exists, since the preamble is not read here.

The messages are latexdetok's, in the language it is set to: English by default,
French with ``latexdetok.set_language("fr")`` or ``LATEXDETOK_LANG=fr``.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass

from latexdetok import Severity, TexComment, TexFile, TexGroup, check
from latexdetok.definitions import DEFINING_COMMANDS, INCLUDING_COMMANDS

__all__ = ["Fragment", "Problem", "comments", "french_spacing", "split"]

# The commands the text renders without LaTeX: most lines carry nothing else.
_TEXT_COMMANDS = {
    "og": "« ",
    "fg": " »",
    "%": "%",
    "&": "&",
    "_": "_",
    "#": "#",
    "$": "$",
    "{": "{",
    "}": "}",
    ",": " ",
    ";": " ",
    " ": " ",
    "-": "",  # discretionary hyphen
    "/": "",  # italic correction
    "ldots": "…",
    "dots": "…",
    "textellipsis": "…",
    "oe": "œ",
    "OE": "Œ",
    "ae": "æ",
    "AE": "Æ",
    "textendash": "–",
    "textemdash": "—",
}
# What a formula may not carry: they all go into a single document (formulas.py), which
# a definition, a file read or written, a catcode change or the ``document``
# environment would affect as a whole; and the two macros that document defines for
# itself. latexdetok recognises them as commands, where a hand-written pattern only saw
# letters: "cd[a-z]+", meant for those two macros, rejected ``\\cdot``.
_FORBIDDEN = (
    DEFINING_COMMANDS
    | frozenset(INCLUDING_COMMANDS)
    | {"write", "openout", "openin", "immediate", "catcode", "makeatletter", "makeatother"}
    | {"cdformula", "cdsizes"}
)
_LIGATURES = (("---", "—"), ("--", "–"), ("``", "“"), ("''", "”"))
_BLANKS = " \t\r\n"


@dataclass(frozen=True, slots=True)
class Problem:
    """What latexdetok finds wrong with a fragment: the place in its text (end
    excluded), the severity (``error``, ``warning`` or ``info``), the message, and the
    fix when it knows one."""

    start: int
    end: int
    severity: str
    message: str
    suggestion: str | None = None


@dataclass(frozen=True, slots=True)
class Fragment:
    """A piece of a line: text, or a LaTeX fragment to typeset. ``problems`` says what
    latexdetok finds in it: a fragment carrying an error or a warning stays text, as it
    was typed."""

    text: str
    latex: bool = False
    problems: tuple[Problem, ...] = ()


def split(text: str) -> list[Fragment]:
    """Cuts a line into text and LaTeX fragments, comments removed.

    Text fragments keep their spaces; two text fragments never follow each other.
    """
    source = _Source(text)
    fragments: list[Fragment] = []
    pending: list[str] = []
    for word, blank in source.words():
        if word.latex is not None or word.problems:
            if pending:
                fragments.append(Fragment("".join(pending)))
                pending.clear()
            fragments.append(Fragment(word.latex or word.text, word.latex is not None, word.problems))
        else:
            if word.text.startswith(" »"):  # like babel, \fg removes the space before it
                while pending and pending[-1][-1:] in _BLANKS:
                    pending[-1] = pending[-1].rstrip(_BLANKS)
                    if not pending[-1]:
                        pending.pop()
            pending.append(word.text)
        if blank:
            pending.append(" ")
    if pending:
        fragments.append(Fragment("".join(pending).rstrip(" ")))
    return [fragment for fragment in fragments if fragment.text]


def comments(text: str) -> list[str]:
    """The ``%`` comments of the line, without the ``%``: the notes its author kept."""
    tex = TexFile(_lines(text))
    tex.analyse()
    return [str(node)[1:].strip() for node in _walk(tex.container) if isinstance(node, TexComment)]


def french_spacing(text: str) -> str:
    """The spaces of French typography, as polyglossia sets them.

    A no-break space before ":" and inside guillemets, a narrow no-break space before
    "; ! ?", whether the author typed a space or not. Like polyglossia, even after a
    digit ("12 :30"); only "://" is spared.
    """
    text = re.sub(r"«[   ]*", "« ", text)
    text = re.sub(r"[   ]*»", " »", text)
    text = re.sub(r"(?<=\S)[   ]*:(?!//)", " :", text)
    return re.sub(r"(?<=\S)[   ]*([;!?])", " \\1", text)


@dataclass(frozen=True, slots=True)
class _Word:
    """A word of the line: its rendered text, or its LaTeX source if it must be
    typeset, and what latexdetok finds in it."""

    text: str
    latex: str | None
    problems: tuple[Problem, ...] = ()


class _Source:
    """The line as latexdetok reads it, and its words, in character positions."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.tex = TexFile(_lines(text))
        self.nodes = list(self.tex.analyse().content)
        starts = [0]
        for line in self.tex.lines:
            starts.append(starts[-1] + len(line))
        self._starts = starts
        self.hidden = self._hidden()
        self.bound = self._bound()
        # The whole line, structure and meaning (see the module docstring); a line with
        # no diagnostic lets all its words through.
        self.diagnostics = [
            (self.offset(diagnostic.start), self.offset(diagnostic.end), diagnostic)
            for diagnostic in check(TexFile(_lines(text)), follow_inputs=False)
        ]

    def offset(self, position: tuple[int, int]) -> int:
        line, column = position
        return self._starts[line - 1] + column

    def span(self, node: object) -> tuple[int, int]:
        return self.offset(node.start_position), self.offset(node.end_position)  # type: ignore[attr-defined]

    def _hidden(self) -> list[bool]:
        """What TeX does not read: a comment, its end of line and the blanks after it."""
        hidden = [False] * len(self.text)
        for node in self.nodes:
            if isinstance(node, TexComment):
                start, end = self.span(node)
                while end < len(self.text) and self.text[end] in "\r\n":
                    end += 1
                while end < len(self.text) and self.text[end] in " \t":
                    end += 1
                for index in range(start, end):
                    hidden[index] = True
        return hidden

    def _bound(self) -> list[bool]:
        """What must not be cut: the inside of groups, and a command with its arguments."""
        bound = [False] * len(self.text)
        for node in self.nodes:
            start, end = self.span(node)
            if node.is_command():
                arguments = [argument for argument in node.arguments or () if argument is not None]
                if arguments:
                    end = max(self.span(argument)[1] for argument in arguments)
            elif not isinstance(node, TexGroup):
                continue
            for index in range(start, end):
                bound[index] = True
        return bound

    def words(self) -> list[tuple[_Word, bool]]:
        """The words, each with a flag: is it followed by a space?"""
        runs: list[list[int]] = []
        current: list[int] = []
        blank_after: list[bool] = []
        for index, char in enumerate(self.text):
            if self.hidden[index]:
                continue
            if char in _BLANKS and not self.bound[index]:
                if current:
                    runs.append(current)
                    blank_after.append(True)
                    current = []
                continue
            current.append(index)
        if current:
            runs.append(current)
            blank_after.append(False)
        words = []
        for run, blank in zip(runs, blank_after, strict=True):
            word = self._word(run)
            # \og swallows the space after it and sets its own, a no-break one. The other
            # commands keep it: \fg and preamble macros typically end with \xspace.
            ends_with_og = "".join(self.text[i] for i in run).endswith("\\og")
            words.append((word, blank and not ends_with_og))
        return words

    def _word(self, run: list[int]) -> _Word:
        start, end = run[0], run[-1] + 1
        nodes = [node for node in self.nodes if _overlaps(self.span(node), (start, end))]
        nodes = [node for node in nodes if not isinstance(node, TexComment)]
        raw = "".join(self.text[index] for index in run)
        problems = self._problems(run)
        suspect = any(problem.severity != Severity.INFO.value for problem in problems)
        inside = set(run)
        if not suspect and all(self._plain(node, inside) for node in nodes):
            return _Word(self._render(run, nodes), None)
        # One formula per line of the batch's document (formulas.py); TeX reads an end
        # of line as a space.
        latex = " ".join(self._latex(run, nodes).splitlines())
        forbidden = self._forbidden(run, nodes)
        if suspect or forbidden:
            # as typed: the faulty places fall within it
            return _Word(raw, None, problems + forbidden)
        # Informations only hold for the source itself: \( \) and $$ get rewritten.
        return _Word(raw, latex, problems if latex == raw else ())

    def _forbidden(self, run: list[int], nodes: list[object]) -> tuple[Problem, ...]:
        """The commands a formula may not carry (``_FORBIDDEN``), and the ``document``
        environment, as positions in the word's text."""
        rank = {index: position for position, index in enumerate(run)}
        found = []
        for node in (child for top in nodes for child in _walk(top)):
            if node.is_env("document"):  # type: ignore[attr-defined]
                name = 'the "document" environment'
            elif node.is_command() and node.content in _FORBIDDEN:  # type: ignore[attr-defined]
                name = f'"\\{node.content}"'  # type: ignore[attr-defined]
            else:
                continue
            start, end = self.span(node)
            inside = [rank[index] for index in range(start, end) if index in rank]
            if inside:
                found.append(
                    Problem(
                        min(inside),
                        max(inside) + 1,
                        Severity.ERROR.value,
                        f"{name} is not allowed in a formula: it would affect the other formulas, "
                        "typeset together",
                    )
                )
        return tuple(found)

    def _problems(self, run: list[int]) -> tuple[Problem, ...]:
        """What latexdetok finds wrong with the word, as positions in its text."""
        rank = {index: position for position, index in enumerate(run)}
        problems = []
        for start, end, diagnostic in self.diagnostics:
            inside = [rank[index] for index in range(start, max(end, start + 1)) if index in rank]
            if inside:
                problems.append(
                    Problem(
                        min(inside),
                        max(inside) + 1,
                        diagnostic.severity.value,
                        diagnostic.message,
                        diagnostic.suggestion,
                    )
                )
        return tuple(problems)

    def _plain(self, node: object, inside: set[int]) -> bool:
        """True if the node is written without LaTeX: text, a text command, a group.

        ``^``, ``_``, ``&`` and ``#`` mean nothing in text: TeX would reject them, and
        LaTeX will say why.
        """
        if isinstance(node, TexGroup):
            return node.is_bracket_group() and all(self._plain(child, inside) for child in node.content)
        if node.is_command():  # type: ignore[attr-defined]
            return node.content in _TEXT_COMMANDS and not node.arguments  # type: ignore[attr-defined]
        start, end = self.span(node)
        return not any(self.text[index] in "^_&#" for index in range(start, end) if index in inside)

    def _render(self, run: list[int], nodes: list[object]) -> str:
        """The text of a word without LaTeX, as TeX prints it."""
        inside = set(run)
        return "".join(self._render_node(node, inside) for node in nodes)

    def _render_node(self, node: object, inside: set[int]) -> str:
        if isinstance(node, TexGroup):
            return "".join(self._render_node(child, inside) for child in node.content)
        if node.is_command():  # type: ignore[attr-defined]
            return _TEXT_COMMANDS[node.content]  # type: ignore[attr-defined]
        start, end = self.span(node)
        text = "".join(self.text[index] for index in range(start, end) if index in inside)
        return _ligatures(text.replace("~", " "))

    def _latex(self, run: list[int], nodes: list[object]) -> str:
        """The source of a word to typeset, as inline math: ``$$…$$`` and ``\\[…\\]`` in
        ``\\displaystyle``, ``\\(…\\)`` as ``$…$``."""
        replaced = {}
        for node in nodes:
            if isinstance(node, TexGroup) and node.is_math() and node.delimiter != "$":
                body = node.arg()
                display = node.delimiter in ("$$", "\\[")
                replaced[self.span(node)[0]] = (
                    self.span(node)[1],
                    f"$\\displaystyle {body}$" if display else f"${body}$",
                )
        pieces: list[str] = []
        skip_until = -1
        for index in run:
            if index < skip_until:
                continue
            if index in replaced:
                skip_until, text = replaced[index]
                pieces.append(text)
                continue
            pieces.append(self.text[index])
        return "".join(pieces)


def _lines(text: str) -> list[str]:
    return text.splitlines(keepends=True) or [""]


def _walk(node: object) -> Iterator[object]:
    yield node
    if isinstance(node, TexGroup):
        for child in node.content:
            yield from _walk(child)


def _overlaps(first: tuple[int, int], second: tuple[int, int]) -> bool:
    return first[0] < second[1] and second[0] < first[1]


def _ligatures(text: str) -> str:
    for ligature, char in _LIGATURES:
        text = text.replace(ligature, char)
    return text
