import subprocess
from pathlib import Path

import pytest

from texformules.figures import export
from texformules.figures.export import save_figure


@pytest.fixture
def figure(figures):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    return fig


def test_extension_added_and_file_written_without_cropping(figure, tmp_path):
    path = save_figure(figure, tmp_path / "figure", fmt="png", crop=False)
    assert path.name == "figure.png"
    assert path.exists()


def test_unknown_format_rejected(figure, tmp_path):
    with pytest.raises(ValueError, match="Unsupported format"):
        save_figure(figure, tmp_path / "figure.jpg")


def test_missing_tool_saves_uncropped_with_a_warning(figure, tmp_path, monkeypatch):
    monkeypatch.setattr(export.shutil, "which", lambda name: None)
    with pytest.warns(UserWarning, match="not found"):
        path = save_figure(figure, tmp_path / "figure.pdf")
    assert path.exists()


def test_cropping_without_shell_and_without_temporary_file_left(figure, tmp_path, monkeypatch):
    calls = []

    def fake_run(arguments, **options):
        calls.append((arguments, options))
        source, target = arguments[1], arguments[2]
        assert " " in target  # a path with spaces passed as it is
        Path(target).write_bytes(Path(source).read_bytes())
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(export.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(export.subprocess, "run", fake_run)
    path = save_figure(figure, tmp_path / "my figure.pdf")
    ((arguments, options),) = calls
    assert arguments[0] == "pdfcrop"
    assert "shell" not in options
    assert path.exists()
    assert not Path(arguments[1]).exists()  # temporary folder deleted


@pytest.mark.latex
def test_real_cropping_with_pdfcrop(figure, tmp_path):
    if export.shutil.which("pdfcrop") is None:
        pytest.skip("pdfcrop missing")
    assert save_figure(figure, tmp_path / "cropped.pdf").stat().st_size > 0
