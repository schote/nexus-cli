"""Entry point of the Nexus CLI with system, sequence and protocol commands."""
from pathlib import Path
from time import sleep

import console
import matplotlib.pyplot as plt
from console.interfaces.acquisition_data import AcquisitionData
from nexus_service.acquisition_manager import AcquisitionControlManager
from pypulseq import Sequence
from rich.console import Console
from typer import Option, Typer

from nexus_cli import calibrations, parameter, system_tests
from nexus_cli.utilities.acquisition import run_acquisition
from nexus_cli.utilities.io import ensure_valid_header_file, ensure_valid_seq_file, load_mrd_header
from nexus_cli.utilities.protocol import PauseStep, Protocol, SequenceStep

app = Typer(help="Nexus Console CLI")

app.add_typer(calibrations.app, name="calibrate")
app.add_typer(parameter.app, name="parameter")
app.add_typer(system_tests.app, name="tests")

@app.command(name="device-config")
def get_device_config():
    """Print the device configuration loaded by the running Nexus service."""
    with AcquisitionControlManager() as m:
        print(m.acquisition.get_device_configuration())

@app.command(name="sequence-system")
def get_sequence_system():
    """Print the PyPulseq system limits derived from the device configuration."""
    with AcquisitionControlManager() as m:
        print(m.acquisition.get_sequence_system())

@app.command(name="run-sequence")
def run_sequence(
    path: Path = Option(help="Path to pypulseq sequence file."),
    mrd_header_path: Path | None = Option(None, help="Path to the ISMRMRD header file, if available."),
    export_dir: Path = Option(envvar="NEXUS_EXPORT_DIR", help="Directory for exported acquisition data."),
):
    """Run a pypulseq sequence file on the scanner.

    Loads the `.seq` file, configures the sequence system from the running Nexus
    service, and executes the acquisition using the current `console.parameter`.
    When `--mrd-header-path` points to an ISMRMRD XML header the acquisition data is
    saved as an ISMRMRD file in `--export-dir` (or `NEXUS_EXPORT_DIR`).
    """
    seq_path = Path(path)
    ensure_valid_seq_file(seq_path)
    with AcquisitionControlManager() as m:
        seq = Sequence(system=m.acquisition.get_sequence_system())
        seq.read(seq_path)
        dur = round(seq.duration()[0], 4)
        print(f"Running sequence {seq_path.name} with duration: {dur} s")
        m.acquisition.set_sequence(sequence=seq, parameter=console.parameter)
        acq_data: AcquisitionData = run_acquisition(m.acquisition)

        if mrd_header_path is not None:
            header_path = Path(mrd_header_path)
            ensure_valid_header_file(header_path)
            data_path = acq_data.save_ismrmrd(header=load_mrd_header(header_path), user_path=str(export_dir))
            print(f"Stored acquisition data >> {data_path}")

@app.command(name="plot-sequence")
def plot_sequence(
    path: str = Option(help="Path to pypulseq sequence file."),
    time_range: tuple[float, float] = Option((0, 0.1), help = "Time range of the sequence plot in ms"),
    plot_unrolled: bool = Option(False, help="True -> unrolled sequence, False -> pulseq sequence"),
):
    """Plot a pypulseq sequence file.

    Parameters
    ----------
    path
        Path to the pypulseq sequence file (`.seq`).
    plot_unrolled
        When `True`, plot the waveforms unrolled by the Nexus service, otherwise plot
        the pulseq sequence, by default `False`.

    """
    seq_path = Path(path)
    ensure_valid_seq_file(seq_path)
    with AcquisitionControlManager() as m:
        seq = Sequence(system=m.acquisition.get_sequence_system())
        seq.read(seq_path)
        dur = round(seq.duration()[0], 4)
        print(f"Running sequence {seq_path.name} with duration: {dur} s")

        if plot_unrolled:
            m.acquisition.set_sequence(sequence=seq, parameter=console.parameter)
            m.acquisition.plot_waveforms(time_range)
        else:
            seq.plot(time_range=time_range, show_blocks=False)
        plt.show()

@app.command(name="run-protocol")
def run_protocol(
    path: str = Option(help="Path to protocol json file."),
    export_dir: Path = Option(envvar="NEXUS_EXPORT_DIR", help="Directory for exported acquisition data."),
):
    """Run a protocol which consists of multiple sequences.

    The protocol is defined in json format.

    Parameters
    ----------
    path
        Path to the protocol json file.
    export_dir
        Directory for the exported acquisition data, defaults to `NEXUS_EXPORT_DIR`.

    """
    protocol = Protocol.load(path)
    Console().print(protocol)
    for step in protocol.steps:
        match step:
            case SequenceStep():
                run_sequence(path=step.sequence, mrd_header_path=step.header, export_dir=export_dir)
            case PauseStep():
                with Console().status(f"{step.message}..."):
                    if step.duration is None:
                        sleep(3)
                    else:
                        sleep(step.duration)
