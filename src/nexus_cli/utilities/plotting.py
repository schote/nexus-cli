"""Show matplotlib figures in a detached viewer process, so the CLI can exit while windows stay open."""
import os
import pickle
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
from rich.console import Console

_SHOWN = "shown"


def show() -> None:
    """Drop-in replacement for `plt.show()`: hand all open figures to a detached viewer and return once they are on screen.

    Raises:
        RuntimeError: If the viewer exits before the windows are shown (e.g. no display available).

    """
    figs = [plt.figure(n) for n in plt.get_fignums()]
    if not figs:
        return
    # Hand over via file rather than a pipe: unpickling creates the GUI windows, which can take seconds over a
    # forwarded X display, and the CLI must not block on that.
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
        viewer = subprocess.Popen(
            [sys.executable, "-m", __name__, f.name],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **detach,
        )
        # The viewer reports on its stdout until the windows are up (or it dies, closing the pipe).
        with Console().status("Preparing plot..."):
            output = []
            for line in viewer.stdout:
                if line.rstrip() == _SHOWN:
                    break
                output.append(line)
            else:
                raise RuntimeError("Plot viewer exited before showing the figures:\n" + "".join(output))
        viewer.stdout.close()
        del viewer
    plt.close("all")


if __name__ == "__main__":
    from matplotlib.backends import BackendFilter, backend_registry

    path = Path(sys.argv[1])
    try:
        with path.open("rb") as f:
            pickle.load(f)
    finally:
        path.unlink()
    if plt.get_backend().lower() in backend_registry.list_builtin(BackendFilter.NON_INTERACTIVE):
        sys.exit(f"No GUI backend available (matplotlib fell back to {plt.get_backend()}); is a display configured?")
    plt.show(block=False)
    plt.pause(0.1)  # process pending GUI events so the windows are mapped and drawn
    print(_SHOWN, flush=True)
    # The CLI closes the pipe now; route any later output to devnull instead of a broken pipe.
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())
    os.dup2(devnull, sys.stderr.fileno())
    plt.show()
