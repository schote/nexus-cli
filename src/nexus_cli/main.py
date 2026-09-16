from typer import Typer

from nexus_cli import calibrations

from nexus_service.acquisition_manager import AcquisitionControlManager

app = Typer(help="Nexus Console CLI")

app.add_typer(calibrations.app, name="calibration")

@app.command(name="device-config")
def get_device_config():
    with AcquisitionControlManager() as m:
        print(m.get_device_configuration())

@app.command(name="sequence-system")
def get_sequence_system():
    with AcquisitionControlManager() as m:
        print(m.get_sequence_system())
