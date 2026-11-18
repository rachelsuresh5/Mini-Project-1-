"""One consistent chart style for every static figure (matplotlib)."""
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from config import PALETTE as P

BLUE = P["series"][0]


def apply_style() -> None:
    mpl.rcParams.update({
        "figure.facecolor": P["surface"],
        "axes.facecolor": P["surface"],
        "savefig.facecolor": P["surface"],
        "figure.dpi": 110,
        "savefig.dpi": 160,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.edgecolor": P["axis"],
        "axes.linewidth": 0.8,
        "axes.labelcolor": P["ink2"],
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": P["ink"],
        "axes.titlelocation": "left",
        "axes.titlepad": 24,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": P["grid"],
        "grid.linewidth": 0.6,
        "grid.linestyle": "-",
        "xtick.color": P["muted"],
        "ytick.color": P["muted"],
        "xtick.labelcolor": P["ink2"],
        "ytick.labelcolor": P["ink2"],
        "legend.frameon": False,
        "legend.labelcolor": P["ink2"],
        "axes.prop_cycle": mpl.cycler(color=P["series"]),
        "lines.linewidth": 2,
    })


def subtitle(ax, text: str) -> None:
    """Grey one-line takeaway under the title."""
    ax.text(0, 1.02, text, transform=ax.transAxes, fontsize=9.5,
            color=P["ink2"], va="bottom")


def money_fmt(unit: str = "M"):
    div = {"M": 1e6, "B": 1e9}[unit]
    return FuncFormatter(lambda v, _: f"${v / div:,.0f}{unit}" if abs(v) >= div or v == 0
                         else f"${v / div:,.1f}{unit}")


def save(fig, name: str, folder) -> None:
    fig.tight_layout()
    fig.savefig(folder / f"{name}.png", bbox_inches="tight")
    plt.close(fig)
