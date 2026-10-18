"""Saving a figure, cropped as tight as can be by an external tool.

``bbox_inches="tight"`` leaves a margin around the text boxes; pdfcrop (PDF),
ImageMagick (PNG) or epstool (EPS) crop to the ink. The figure goes through a temporary
file, deleted afterwards, and the tools run without a shell: a path with spaces breaks
nothing. Without the tool, the figure is saved uncropped, with a warning.
"""

import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Any

from matplotlib.figure import Figure

__all__ = ["FORMATS", "save_figure"]

#: Format → possible cropping commands, the first one found is used ({e}: input, {s}: output).
FORMATS: dict[str, list[list[str]]] = {
    "pdf": [["pdfcrop", "{e}", "{s}"]],
    "png": [["magick", "{e}", "-trim", "{s}"], ["convert", "{e}", "-trim", "{s}"]],
    "eps": [["epstool", "--bbox", "--copy", "{e}", "{s}"]],
}


def _command(fmt: str) -> list[str] | None:
    for command in FORMATS[fmt]:
        if shutil.which(command[0]):
            return command
    return None


def save_figure(
    fig: Figure,
    path: str | Path,
    fmt: str | None = None,
    dpi: int = 300,
    tight: bool = True,
    crop: bool = True,
) -> Path:
    """Saves ``fig`` as PDF, PNG or EPS (from the extension, or ``fmt``), cropped.

    The extension is added to the name if it is missing. Returns the path written.

    :raises ValueError: for a format outside :data:`FORMATS`.
    :raises subprocess.CalledProcessError: when the cropping tool fails.
    """
    target = Path(path).expanduser().resolve()
    fmt = fmt or target.suffix.lstrip(".").lower()
    if fmt not in FORMATS:
        raise ValueError(f"Unsupported format: {fmt!r} ({', '.join(FORMATS)}).")
    if target.suffix.lower() != f".{fmt}":
        target = target.with_name(target.name + f".{fmt}")
    options: dict[str, Any] = {"dpi": dpi, "format": fmt, "bbox_inches": "tight" if tight else None}

    command = _command(fmt) if crop else None
    if crop and command is None:
        tools = ", ".join(c[0] for c in FORMATS[fmt])
        warnings.warn(f"{tools} not found: figure not cropped.", stacklevel=2)
    if command is None:
        fig.savefig(target, **options)
        return target
    with tempfile.TemporaryDirectory() as folder:
        raw = Path(folder) / f"figure.{fmt}"
        fig.savefig(raw, **options)
        arguments = [a.format(e=raw, s=target) for a in command]
        subprocess.run(arguments, check=True, capture_output=True)
    return target
