"""Read and modify the global acquisition parameter `console.parameter`."""
import json

import console
from console.interfaces.dimensions import Dimensions
from console.interfaces.enums import DDCMethod
from typer import BadParameter, Option, Typer

app = Typer(help="Show and modify the global acquisition parameter.")


def _parse_ddc_method(value: str | None) -> DDCMethod | None:
    """Accept the DDC method by name (FIR, AVG, CIC) or by its enum value, case-insensitive."""
    if value is None:
        return None
    for method in DDCMethod:
        if value.upper() == method.name or value.lower() == method.value:
            return method
    choices = ", ".join(m.name for m in DDCMethod)
    raise BadParameter(f"Unknown DDC method '{value}', choose one of: {choices}")


@app.command(name="show")
def show_parameter(
    as_json: bool = Option(False, "--json", help="Print the parameter as JSON."),
):
    """Print the current acquisition parameter and the state file it is bound to."""
    if as_json:
        print(json.dumps(console.parameter.to_dict(), indent=2))
    else:
        print(console.parameter)


@app.command(name="set")
def set_parameter(
    larmor_frequency: float | None = Option(None, help="Larmor frequency in Hz."),
    b1_scaling: float | None = Option(None, help="Scaling of the B1 field (RF transmit power)."),
    gradient_offset: tuple[float, float, float] | None = Option(
        None, help="Gradient offset x y z in mV.", metavar="X Y Z"
    ),
    fov_scaling: tuple[float, float, float] | None = Option(
        None, help="Field of view scaling for Gx Gy Gz.", metavar="X Y Z"
    ),
    channel_assignment: tuple[int, int, int] | None = Option(
        None, help="Console output channels assigned to gradient x y z.", metavar="X Y Z"
    ),
    ddc_method: str | None = Option(
        None, help="Decimation filter method: FIR, AVG or CIC.", callback=_parse_ddc_method
    ),
    num_averages: int | None = Option(None, min=1, help="Number of acquisition averages."),
    averaging_delay: float | None = Option(None, min=0., help="Delay in seconds between averages."),
):
    """Set one or more acquisition parameter values.

    Only the given options are changed, every change is written to the state file
    immediately. Run `parameter show` afterwards to verify the result.
    """
    param = console.parameter

    if larmor_frequency is not None:
        param.larmor_frequency = larmor_frequency
    if b1_scaling is not None:
        param.b1_scaling = b1_scaling
    if gradient_offset is not None:
        param.gradient_offset = Dimensions(*gradient_offset)
    if fov_scaling is not None:
        param.fov_scaling = Dimensions(*fov_scaling)
    if channel_assignment is not None:
        param.channel_assignment = Dimensions(*channel_assignment)
    if ddc_method is not None:
        param.ddc_method = ddc_method
    if num_averages is not None:
        param.num_averages = num_averages
    if averaging_delay is not None:
        param.averaging_delay = averaging_delay

    print(param)
