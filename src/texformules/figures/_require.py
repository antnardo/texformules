"""Fails early, and says which extra to install, when matplotlib is missing.

``texformules.figures`` is the only part of the package that needs matplotlib, a heavy
dependency the formulas do without: it comes with the ``figures`` extra. Without this
check, the error would name matplotlib alone, and not how to get it.
"""

__all__: list[str] = []

try:
    import matplotlib  # noqa: F401
except ModuleNotFoundError as error:  # pragma: no cover - depends on the environment
    raise ModuleNotFoundError(
        "texformules.figures needs matplotlib: pip install 'texformules[figures]'",
        name=error.name,
    ) from error
