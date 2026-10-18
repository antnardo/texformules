import re
from pathlib import Path

import texformules

# The public API: these names are what users import.
PUBLIC = {
    "BP_PER_PT",
    "Formula",
    "FormulaBook",
    "PdfBox",
    "default_cache",
    "default_preamble",
    "french_spacing",
    "split",
}


def test_version_read_by_pyproject():
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert 'path = "src/texformules/__init__.py"' in pyproject
    assert re.fullmatch(r"\d+\.\d+\.\d+", texformules.__version__)


def test_public_api_is_exported():
    assert set(texformules.__all__) >= PUBLIC
    assert all(hasattr(texformules, name) for name in texformules.__all__)
