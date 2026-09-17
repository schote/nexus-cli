from typer import Typer, Option

from nexus_cli import calibrations, parameter
from nexus_cli.utilities.io import load_mrd_header
from pathlib import Path

import console

from nexus_service.acquisition_manager import AcquisitionControlManager
from console.interfaces.acquisition_data import AcquisitionData
from pypulseq import Sequence

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
    path: str = Option(help="Path to pypulseq sequence file."),
    mrd_header_path: str | None = Option(None, help="Path to the ISMRMRD header file, if available."),
    export_dir: Path = Option(envvar="NEXUS_EXPORT_DIR", help="Directory for exported acquisition data."),
):
    """Run a pypulseq sequence file on the scanner.

    Loads the `.seq` file, configures the sequence system from the running Nexus
    service, and executes the acquisition using the current `console.parameter`.
    When `--mrd-header-path` points to an ISMRMRD XML header the acquisition data is
    saved as an ISMRMRD file in `--export-dir` (or `NEXUS_EXPORT_DIR`).
    """
    if (_seq_path := Path(path)).suffix != ".seq":
        raise ValueError("Invalid sequence file, `.seq` file required.")

    with AcquisitionControlManager() as m:
        seq = Sequence(system=m.acquisition.get_sequence_system())
        seq.read(_seq_path)
        dur = round(seq.duration()[0], 4)
        print(f"Loaded sequence with duration: {dur} s")
        m.acquisition.set_sequence(sequence=seq, parameter=console.parameter)
        acq_data: AcquisitionData = m.acquisition.run()

        if mrd_header_path is not None:
            if (_header_path := Path(mrd_header_path)).suffix != ".xml":
                raise ValueError("Invalid header file, `.h5` file expected.")
            acq_data.save_ismrmrd(
                header=load_mrd_header(_header_path),
                user_path=str(export_dir),
            )
