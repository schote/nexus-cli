"""Show matplotlib figures in a detached viewer process, so the CLI can exit while windows stay open."""
import pickle
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import matplotlib.pyplot as plt


def show() -> None:
    """Drop-in replacement for `plt.show()`: hand all open figures to a detached viewer and return immediately."""
    figs = [plt.figure(n) for n in plt.get_fignums()]
    if not figs:
        return
    # Hand over via file rather than a pipe: unpickling creates the GUI windows, which can take seconds over a
    # forwarded X display, and the CLI must not wait for that.
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        pickle.dump(figs, f)  # figures created via pyplot re-register with pyplot on unpickle
    detach = (
        {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    # The viewer intentionally outlives this process, so silence Popen's "still running" ResourceWarning on cleanup.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        subprocess.Popen(
            [sys.executable, "-m", __name__, f.name],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **detach,
        )
    plt.close("all")


if __name__ == "__main__":
    path = Path(sys.argv[1])
    try:
        with path.open("rb") as f:
            pickle.load(f)
    finally:
        path.unlink()
    plt.show()
