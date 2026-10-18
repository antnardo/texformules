import pytest
from latexdetok import set_language

from texformules import Fragment, Problem, comments, french_spacing, split

NBSP = "\N{NO-BREAK SPACE}"
THIN = "\N{NARROW NO-BREAK SPACE}"


@pytest.fixture(autouse=True)
def english_messages():
    """latexdetok's messages in English, whatever LATEXDETOK_LANG says."""
    set_language("en")


def pieces(text):
    return [(fragment.text, fragment.latex) for fragment in split(text)]


def problems(text):
    """The fragments carrying problems: (text, [(faulty piece, severity)])."""
    return [
        (f.text, [(f.text[p.start : p.end], p.severity) for p in f.problems])
        for f in split(text)
        if f.problems
    ]


class TestSplit:
    def test_text_without_latex_stays_whole(self):
        assert split("Newton's second law applied") == [Fragment("Newton's second law applied")]

    def test_formula_between_dollars(self):
        assert pieces("method: $r=const$ hence uniform") == [
            ("method: ", False),
            ("$r=const$", True),
            (" hence uniform", False),
        ]

    def test_macro_outside_math_with_its_arguments(self):
        assert pieces("Value \\SI{30}{km.s^{-1}} 2 marks") == [
            ("Value ", False),
            ("\\SI{30}{km.s^{-1}}", True),
            (" 2 marks", False),
        ]

    @pytest.mark.parametrize(
        ("text", "latex"),
        [
            pytest.param("\\SI{5e-8}N 1-2 marks", "\\SI{5e-8}N", id="unit-without-braces"),
            pytest.param("less than \\SI1{\\micro m})", "\\SI1{\\micro m})", id="number-without-braces"),
            pytest.param("\\SI{5e-8} N next", "\\SI{5e-8} N", id="argument-after-a-space"),
            pytest.param("\\SI{3}\\meter end", "\\SI{3}\\meter", id="command-argument"),
        ],
    )
    def test_argument_without_braces_stays_with_its_command(self, text, latex):
        assert [fragment.text for fragment in split(text) if fragment.latex] == [latex]

    def test_attached_punctuation_typeset_with_the_formula(self):
        assert pieces("so ($x=1$), then") == [("so ", False), ("($x=1$),", True), (" then", False)]

    def test_adjacent_formulas_form_a_single_fragment(self):
        assert pieces("\\num{9.83}$\\pm$\\SI{0.03}{m/s^2}") == [("\\num{9.83}$\\pm$\\SI{0.03}{m/s^2}", True)]

    def test_quotes_and_symbols_translated_without_latex(self):
        assert pieces("\\og speed \\fg{} and 100\\%") == [(f"«{NBSP}speed{NBSP}» and 100%", False)]

    def test_og_swallows_the_space_and_fg_keeps_it(self):
        assert pieces("\\og length\\fg (in metres)") == [(f"«{NBSP}length{NBSP}» (in metres)", False)]

    def test_display_math_and_parenthesised_math_become_inline(self):
        assert pieces("$$\\int f$$ then \\(a+b\\)") == [
            ("$\\displaystyle \\int f$", True),
            (" then ", False),
            ("$a+b$", True),
        ]

    def test_ligatures_tilde_and_text_braces_rendered(self):
        assert pieces("a -- b --- c~d {x}") == [(f"a – b — c{NBSP}d x", False)]

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("Comment % note to self", "Comment", id="end-of-line"),
            pytest.param("a % c1\n  b % c2\nc", "a b c", id="several-lines"),
            pytest.param("a%c\nb", "ab", id="joins-two-words"),
        ],
    )
    def test_comment_removed_like_tex(self, text, expected):
        assert pieces(text) == [(expected, False)]

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("price: 5\\$ and $x", id="unmatched-dollar"),
            pytest.param("$\\input{x}$ dangerous", id="dangerous-macro"),
            pytest.param("$\\cdformula{x}$", id="batch-macro"),
            pytest.param("\\frac{a}{b", id="open-brace"),
        ],
    )
    def test_doubtful_fragment_stays_text(self, text):
        assert all(not fragment.latex for fragment in split(text))

    def test_empty_text_gives_no_fragment(self):
        assert split("") == []

    @pytest.mark.parametrize("source", ["$a\\cdot b$", "$1+\\cdots+n$"])
    def test_cdot_is_not_a_batch_macro(self, source):
        """A pattern "cd[a-z]+", written for \\cdformula, used to reject \\cdot."""
        assert pieces(source) == [(source, True)]

    def test_formula_over_two_lines_joined_into_one(self):
        assert pieces("$a\nb$") == [("$a b$", True)]


class TestProblems:
    """The whole line goes through latexdetok, and what it finds wrong is located."""

    def test_valid_line_has_no_problem(self):
        line = "Field--potential relation: $V_1-V_3=\\int_{(1)}^{(3)}\\vec E\\cdot\\mathrm{d}\\vec\\ell$"
        assert problems(line) == []
        assert [f.latex for f in split(line)] == [False, True]

    def test_dollar_never_closed_stays_as_typed(self):
        [fragment] = [f for f in split("price: $x and nothing") if f.problems]
        assert (fragment.text, fragment.latex) == ("$x", False)
        [problem] = fragment.problems
        assert (problem.start, problem.end, problem.severity) == (0, 1, "warning")  # blocks too

    def test_subscript_outside_math_is_an_error(self):
        assert problems("subscript V_1 outside math") == [("V_1", [("_", "error")])]

    @pytest.mark.parametrize(
        ("text", "faulty"),
        [
            pytest.param("$\\input{x}$", "\\input", id="file"),
            pytest.param("$\\frac{\\def\\a{b}}{2}$", "\\def", id="inside-an-argument"),
            pytest.param("$\\cdformula{x}$", "\\cdformula", id="batch-macro"),
        ],
    )
    def test_forbidden_command_located(self, text, faulty):
        [(source, found)] = problems(text)
        assert source == text and found == [(faulty, "error")]

    def test_forbidden_command_message_says_why(self):
        [fragment] = split("$\\input{x}$")
        [problem] = fragment.problems
        assert problem.message.startswith('"\\input" is not allowed in a formula')

    def test_information_does_not_block_the_formula(self):
        [fragment] = split("$\\dfarc{1}{2}$")
        assert fragment.latex
        [problem] = fragment.problems
        assert (problem.start, problem.end, problem.severity) == (1, 7, "info")
        assert isinstance(problem, Problem)
        assert "\\dfrac" in problem.message


def test_comments_readable_apart():
    assert comments("Sign % to be made explicit\nnext % and this") == ["to be made explicit", "and this"]


class TestFrenchSpacing:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("Bas: entre", f"Bas{NBSP}: entre", id="colon-attached"),
            pytest.param("Bas : entre", f"Bas{NBSP}: entre", id="colon-spaced"),
            pytest.param("oui; non! vrai?", f"oui{THIN}; non{THIN}! vrai{THIN}?", id="high-punctuation"),
            pytest.param("«texte»", f"«{NBSP}texte{NBSP}»", id="guillemets"),
            pytest.param("http://example.org", "http://example.org", id="url"),
        ],
    )
    def test_spaces_set_like_polyglossia(self, text, expected):
        assert french_spacing(text) == expected

    def test_already_spaced_text_unchanged(self):
        text = f"«{NBSP}a{NBSP}» : b ; c"
        assert french_spacing(french_spacing(text)) == french_spacing(text)
