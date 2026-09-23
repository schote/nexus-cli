"""Calibration commands for Larmor frequency, flip angle and shims."""
from typer import Typer

app = Typer(help="Calibration methods.")

# Imported after `app` is defined, the submodules register their commands on it.
from . import flip_angle, frequency, shimming  # noqa: E402

__all__ = [
    "flip_angle",
    "frequency",
    "shimming",
]
