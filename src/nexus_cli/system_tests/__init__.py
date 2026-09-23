"""System test commands."""
from typer import Typer

app = Typer(help="System tests.")

# Imported after `app` is defined, the submodules register their commands on it.
from . import gradient_test  # noqa: E402

__all__ = [
    "gradient_test",
]
