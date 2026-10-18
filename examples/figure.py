"""A figure ready for LaTeX: 8 cm by 6 cm, decimal comma, cropped PDF.

``apply_style`` sets sizes and fonts before the figure is created; ``style_axes`` formats
the axes; ``save_figure`` saves the figure cropped to the ink (pdfcrop). Save before
``plt.show()``, which empties the figure when its window closes. Needs the ``figures``
extra, and LaTeX with siunitx since ``usetex`` is on.

    python examples/figure.py
"""

import matplotlib.pyplot as plt
import numpy as np

from texformules.figures import apply_style, save_figure, style_axes


def main() -> None:
    apply_style(8, 6)  # width, height in cm
    x = np.linspace(-4, 4, 500)
    fig, ax = plt.subplots()
    ax.plot(x, np.sinc(x) ** 2)
    ax.set_title("Diffraction by a slit")
    ax.set_xlabel(r"$x=\frac{a\sin\theta}{\lambda}$")
    ax.set_ylabel(r"$I/I_0$")
    style_axes(ax)
    print(save_figure(fig, "slit.pdf"))


if __name__ == "__main__":
    main()
