"""Gradient system test with a periodic train of trapezoidal gradients."""
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
    """Build a trapezoidal gradient which fills one period of the gradient test.

    The gradient area corresponds to `duty_cycle` times the area of a rectangular gradient
    with maximum amplitude over the whole period. The trapezoid is delayed to the end of the period.

    Parameters
    ----------
    channel
        Gradient channel, one of `x`, `y` or `z`.
    system
        PyPulseq system limits of the scanner.
    max_amplitude
        Gradient amplitude relative to the maximum gradient of `system`, by default 1.
    period
        Duration of one period in s, by default 0.1 s.
    duty_cycle
        Fraction of the period with gradient at maximum amplitude, by default 0.2.
    rise_time
        Rise time of the trapezoid in s. If None, the fastest rise time of `system` is used.

    Returns
    -------
        PyPulseq trapezoidal gradient event.
    """
    total_area = system.max_grad * period * max_amplitude
    grad = pp.make_trapezoid(
        channel=channel,
        area=duty_cycle*total_area,
        max_grad=system.max_grad*max_amplitude,
        rise_time=rise_time,
    )
    grad.delay = period - pp.calc_duration(grad)
    return grad


@app.command(name="gradient")
def gradient_test(
    channels: str = "xyz",
    max_amplitude: float = 1.,
    period: float = 0.1,
    duty_cycle: float = 0.2,
    total_duration: float = 300.,
    rise_time: float | None = None,
    show_plot: bool = False,
):
    """Run a gradient test with a periodic train of trapezoidal gradients.

    Prints the expected gradient strength, GPA output current and console output voltage per channel,
    builds the sequence and runs it after confirmation with Enter. The sequence does not contain
    ADC events, no data is acquired.

    Parameters
    ----------
    channels
        Gradient channels to play out, any combination of `x`, `y` and `z`, by default `xyz`.
    max_amplitude
        Gradient amplitude relative to the maximum gradient of the sequence system, by default 1.
    period
        Duration of one period in s, by default 0.1 s.
    duty_cycle
        Fraction of the period with gradient at maximum amplitude, by default 0.2.
    total_duration
        Total duration of the test in s, by default 300 s.
    rise_time
        Rise time of the trapezoids in s. If None, the fastest rise time of the sequence system is used.
    show_plot
        When `True`, plot the sequence before execution, by default `False`.
    """
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
