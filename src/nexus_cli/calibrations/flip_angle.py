"""Transmit power calibration (flip angle / B1 scaling)."""
# %%
import time

import console
import matplotlib.pyplot as plt
import numpy as np

from nexus_service.acquisition_manager import AcquisitionControlManager
from console.utilities.sequences.spectrometry import fid
from scipy.signal import find_peaks

from nexus_cli.calibrations import app
from nexus_cli.utilities import plotting


def fa_model(samples: np.ndarray, amp: float, efficiency: float, damping: float, noise: float) -> np.ndarray:
    """Sinusoidal model for the flip-angle calibration curve.

    Models the measured FID signal integral as a damped sinusoid of the fli
    angle, used for fitting the 90° operating point.

    Args:
        samples: Array of flip-angle values (in degrees or radians, consistent
            with `efficiency`).
        amp: Peak amplitude of the sinusoid.
        efficiency: Angular efficiency factor (scales the argument of `sin`).
        damping: Linear damping coefficient applied across the sample range.
        noise: Constant noise floor offset.

    Returns:
        Model signal values with the same shape as `samples`.

    """
    return amp *(1-damping*samples)* np.abs(np.sin(efficiency * samples)) + noise


@app.command(name="b1")
def calibrate_flip_angle(
    start: int = 45,
    stop: int = 225,
    steps: int = 10,
    delay: int = 2000,
    center_window: int = 100,
    show_plot: bool = True,
) -> None:
    """Calibrate the B1 transmit gain by sweeping the flip angle.

    Acquires an FID at each of `steps` linearly spaced flip angles between
    `start` and `stop` degrees. For each acquisition the magnitude FFT spectrum
    is computed and the peak integral inside a central window is recorded.
    The 90° operating point is identified from the peak of the integral curve
    and used to compute a correction factor for `console.parameter.b1_scaling`.

    Args:
        config: Nexus system configuration (connection and service settings).
        start: First flip angle in the sweep (degrees). Defaults to 45.
        stop: Last flip angle in the sweep (degrees). Defaults to 225.
        steps: Number of equally spaced flip angles to measure. Defaults to 10.
        delay: Delay between consecutive FID acquisitions (ms). Defaults to 2000.
        center_window: Width of the spectral integration window around the
            centre bin (samples). Defaults to 100.
        show_plot: When `True`, display a stem plot of the signal integral vs.
            flip angle. Defaults to `True`.

    Raises:
        ValueError: If any acquisition returns no processed receive data.

    """
    acq_data = []
    flip_angles = np.round(np.linspace(start, stop, steps))
    num_samples = 1000
    # Data acquisition
    for k, flip in enumerate(flip_angles):

        print(f"Acquiring acquisition data... flip angle: {flip}°, {k+1}/{steps}", end="\r")

        # Use managed instance
        with AcquisitionControlManager() as m:
            seq = fid.constructor(
                rf_duration=150e-6,
                flip_angle=np.deg2rad(flip),
                acq_bandwidth=20e3,
                num_samples=num_samples,
                system=m.acquisition.get_sequence_system(),
            )
            m.acquisition.set_sequence(sequence=seq, parameter=console.parameter)
            acq_data.append(m.acquisition.run())

        time.sleep(delay/1000)

    print("\nProcessing...")

    window_start = int(num_samples/2-center_window/2)
    peak_window = slice(window_start, window_start+center_window)
    integrals = []

    for k, acq in enumerate(acq_data):
        rx_data = acq.receive_data[0].processed_data
        if rx_data is None:
            msg = f"No receive data available for acquisition {k}/{steps}"
            raise ValueError(msg)
        data_fft = np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(rx_data), axis=-1)))
        integrals.append(np.sum(data_fft[0, peak_window], axis=-1))

    integrals_array = np.stack(integrals, axis=0)

    # Calculate b1 factor based on measured data
    arg_max_measured, _ = find_peaks(integrals_array, height=np.amax(integrals_array)/2)
    if len(arg_max_measured) > 0:
        b1_factor_measured = flip_angles[arg_max_measured[0]] / 90
    else:
        arg_max_measured = np.argmax(integrals_array)
        b1_factor_measured = flip_angles[arg_max_measured] / 90

    # TODO: Check flip angle model

    b1_factor = b1_factor_measured

    new_b1_scaling = console.parameter.b1_scaling*b1_factor
    print(f"Old b1 scaling: {console.parameter.b1_scaling}, new b1 scaling: {new_b1_scaling}")
    console.parameter.b1_scaling = new_b1_scaling

    # TODO: Save calibration data

    if show_plot:
        _, ax = plt.subplots(1, 1)
        ax.scatter(flip_angles, integrals_array, label="measurement")
        ax.legend()
        ax.set_ylabel("Signal integral")
        ax.set_xlabel("Flip angle / °")
        plotting.show()
