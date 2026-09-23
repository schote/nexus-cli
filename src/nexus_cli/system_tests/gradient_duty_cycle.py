import console

import pypulseq as pp
import typer

from nexus_service.acquisition_manager import AcquisitionControlManager
from nexus_cli.system_tests import app
from nexus_cli.utilities.acquisition import run_acquisition


def build_gradient_block(
    channel: str,
    system: pp.Opts,
    max_amplitude: float = 1.,
    period: float = 0.1,
    duty_cycle: float = 0.2,
    rise_time: float | None = None,
):
    total_area = system.max_grad * period * max_amplitude
    grad = pp.make_trapezoid(
        channel=channel,
        area=duty_cycle*total_area,
        max_grad=system.max_grad*max_amplitude,
    )
    grad.delay = period - pp.calc_duration(grad)
    return grad


@app.command(name="gradient-pwm")
def gradient_pwm(
    channels: str = "xyz",
    max_amplitude: float = 1.,
    period: float = 0.1,
    duty_cycle: float = 0.2,
    total_duration: float = 300.,
    rise_time: float | None = None,
    show_plot: bool = False,
):
    with AcquisitionControlManager() as m:
        seq_sys = m.acquisition.get_sequence_system()
        dev_cfg = m.acquisition.get_device_configuration()

    print("\nGradient Test\n-----\n")
    print(f"Duty cycle: {100*duty_cycle} %\nPeriod: {period} s")
    if rise_time is not None:
        print(f"Using specified rise time: {rise_time*1e6} us")
    max_grad_pp = seq_sys.max_grad * max_amplitude / seq_sys.gamma
    print(f"Max. gradient ({round(100*max_amplitude)} % of sequence system): {1e3*max_grad_pp} mT/m")
    gpa_gain = dev_cfg.tx.gpa_gain
    grad_eff = dev_cfg.tx.gradient_efficiency
    max_current_amps = [round(max_grad_pp / eff, 2) for eff in grad_eff]
    print(f"GPA output: {max_current_amps} A (Ch1, Ch2, Ch3)")
    max_console_volts = [round(current / g, 2) for current, g in zip(max_current_amps, gpa_gain, strict=True)]
    print(f"Console output: {max_console_volts} V (Ch1, Ch2, Ch3)")

    gradients = []
    if "x" in channels:
        gx = build_gradient_block("x", seq_sys, max_amplitude, period, duty_cycle, rise_time)
        gradients.append(gx)
    if "y" in channels:
        gy = build_gradient_block("y", seq_sys, max_amplitude, period, duty_cycle, rise_time)
        gradients.append(gy)
    if "z" in channels:
        gz = build_gradient_block("z", seq_sys, max_amplitude, period, duty_cycle, rise_time)
        gradients.append(gz)

    seq = pp.Sequence(system=seq_sys)
    seq.set_definition("Name", "gradient-test")
    seq.set_definition("Channels", channels)
    seq.set_definition("Period", period)
    seq.set_definition("Duty cycle", duty_cycle)
    seq.set_definition("Maximum Relative Amplitude", max_amplitude)

    num_cycles = round(total_duration/period)
    print("Building sequence...")
    for _ in range(num_cycles):
        seq.add_block(*gradients)
    print(f"Done. Total sequence duration: {round(seq.duration()[0], 5)} s")

    if show_plot:
        print("Preparing plot...")
        seq.plot()

    # Request user to confirm execution
    typer.echo("\nPress Enter to confirm execution, any other key to abort...", nl=False)
    key = typer.getchar()
    typer.echo()
    if key not in ("\r", "\n"):
        raise typer.Abort()

    with AcquisitionControlManager() as m:
        m.acquisition.set_sequence(sequence=seq, parameter=console.parameter)
        _ = run_acquisition(m.acquisition)
    print("Done.")
