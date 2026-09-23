"""Helpers for running acquisitions on the Nexus service."""
import time
from concurrent.futures import ThreadPoolExecutor

from console.interfaces.acquisition_data import AcquisitionData
from console.spcm_control.acquisition_control import AcquisitionControl
from rich.progress import Progress


def run_acquisition(acquisition: AcquisitionControl, description: str = "Running sequence") -> AcquisitionData:
    """Run an acquisition and display its progress.

    The `run()` call of the acquisition control proxy blocks until the acquisition is finished.
    It is executed in a thread, while the main thread polls the progress from the Nexus service.

    Parameters
    ----------
    acquisition
        Acquisition control proxy with a sequence already set.
    description
        Label of the progress bar, by default "Acquisition".

    Returns
    -------
        Acquisition data returned by the service.
    """
    with Progress() as progress, ThreadPoolExecutor(max_workers=1) as executor:
        task = progress.add_task(description, total=100)
        future = executor.submit(acquisition.run)
        while not future.done():
            progress.update(task, completed=acquisition.get_progress())
            time.sleep(0.1)
        acq_data = future.result()
        progress.update(task, completed=100)
    return acq_data
