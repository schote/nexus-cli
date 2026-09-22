from typer import Typer, Option

from nexus_cli import calibrations, parameter
from nexus_cli.utilities.io import load_mrd_header
from nexus_cli.utilities.protocol import Protocol, SequenceStep, PauseStep
from pathlib import Path
from time import sleep

import console

from nexus_service.acquisition_manager import AcquisitionControlManager
from console.interfaces.acquisition_data import AcquisitionData
from pypulseq import Sequence
from nexus_cli.utilities.io import ensure_valid_seq_file, ensure_valid_header_file
from rich.progress import Progress
from rich.console import Console

app = Typer(help="Nexus Console CLI")

app.add_typer(calibrations.app, name="calibrate")
app.add_typer(parameter.app, name="parameter")

@app.command(name="device-config")
def get_device_config():
    with AcquisitionControlManager() as m:
        print(m.acquisition.get_device_configuration())

@app.command(name="sequence-system")
def get_sequence_system():
    with AcquisitionControlManager() as m:
        print(m.acquisition.get_sequence_system())

@app.command(name="run-sequence")
def run_sequence(
    path: str | Path = Option(help="Path to pypulseq sequence file."),
    mrd_header_path: str | Path | None = Option(None, help="Path to the ISMRMRD header file, if available."),
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
    with Progress() as progress:
        with AcquisitionControlManager() as m:
            seq = Sequence(system=m.acquisition.get_sequence_system())
            seq.read(seq_path)
            dur = round(seq.duration()[0], 4)
            print(f"Running sequence {seq_path.name} with duration: {dur} s")
            m.acquisition.set_sequence(sequence=seq, parameter=console.parameter)

            task = progress.add_task("Acquisition", total=100)
            def on_progress(value: float) -> None:
                progress.update(task, completed=value)
            acq_data: AcquisitionData = m.acquisition.run(progress_callback=on_progress)

            if mrd_header_path is not None:
                header_path = Path(mrd_header_path)
                ensure_valid_header_file(header_path)
                acq_data.save_ismrmrd(header=load_mrd_header(header_path), user_path=str(export_dir))

@app.command(name="plot-sequence")
def plot_sequence(
    path: str = Option(help="Path to pypulseq sequence file."),
    plot_unrolled: bool = Option(False, help="True -> unrolled sequence, False -> pulseq sequence"),
):
    """Plot sequence.

    Parameters
    ----------
    path, optional
        Sequence path, by default Option(help="Path to pypulseq sequence file.")
    plot_unrolled, optional
        Plot unrolled or pulseq sequence, by default Option(False, help="True -> unrolled sequence, False -> pulseq sequence")

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
            m.acquisition.plot_waveforms()
        else:
            seq.plot()

@app.command(name="run-protocol")
def run_protocol(path: str = Option(help="Path to protocol json file.")):
    """Run a protocol which consists of multiple sequences.

    The protocol is defined in json format.

    Parameters
    ----------
    path, optional
        Path to procotol json file, by default Option(help="Path to protocol json file.")

    """
    protocol = Protocol.load(path)
    for step in protocol.steps:
        match step:
            case SequenceStep():
                run_sequence(step.sequence, step.header)
            case PauseStep():
                if step.duration is not None:
                    with Console().status(f"{step.message}..."):
                        sleep(step.duration)
