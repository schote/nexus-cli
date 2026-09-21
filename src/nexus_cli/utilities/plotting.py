"""Show matplotlib figures in a detached viewer process, so the CLI can exit while windows stay open."""
import pickle
import subprocess
import sys

import matplotlib.pyplot as plt


def show() -> None:
    """Drop-in replacement for `plt.show()`: hand all open figures to a detached viewer and return immediately."""
    figs = [plt.figure(n) for n in plt.get_fignums()]
    if not figs:
        return
    detach = (
        {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    viewer = subprocess.Popen(
        [sys.executable, "-m", __name__],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **detach,
    )
    pickle.dump(figs, viewer.stdin)  # figures created via pyplot re-register with pyplot on unpickle
    viewer.stdin.close()
    plt.close("all")


if __name__ == "__main__":
    pickle.load(sys.stdin.buffer)
    plt.show()
