import re
import subprocess
import sys
from pathlib import Path

import texformules

# Every name downstream code imports today: they must not move.
DEPENDENTS_USE = {
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


def test_public_api_keeps_the_names_dependents_use():
    assert set(texformules.__all__) >= DEPENDENTS_USE
    assert all(hasattr(texformules, name) for name in texformules.__all__)


def test_core_import_does_not_load_matplotlib():
    code = "import sys, texformules; print('matplotlib' in sys.modules, 'texformules.figures' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.split() == ["False", "False"]
