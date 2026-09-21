"""B0 shimming via iterative gradient offset optimisation."""
# %%
from copy import deepcopy
from os import name

import console
import matplotlib.pyplot as plt
import numpy as np
from console.interfaces.acquisition_data import AcquisitionData
from console.interfaces.device_configuration import NexusConfiguration
from console.interfaces.dimensions import Dimensions
from console.utilities.sequences.spectrometry import fid
from console.utilities.snr import signal_to_noise_ratio
from nexus_service.acquisition_manager import AcquisitionControlManager
from nexus_cli.calibrations import app
from nexus_cli.utilities import plotting

def run_fid(f0: float, shims: Dimensions, seq) -> AcquisitionData:
    """Acquire a single FID with the given Larmor frequency and gradient offsets.

    Temporarily overrides `console.parameter.larmor_frequency` and
    `console.parameter.gradient_offset` for the duration of the acquisition,
    then restores the original values regardless of success or failure.

    Args:
        config: Nexus system configuration (connection and service settings).
        f0: Larmor frequency in Hz to use for this acquisition.
        shims: Gradient offset values (x, y, z) in mV to apply.
        seq: A pre-constructed pypulseq sequence object.

    Returns:
        The `ReceiveData` object from the first receive channel.

    Raises:
        ValueError: If `console.parameter` is `None`.

    """
    if console.parameter is None:
        raise ValueError("Acquisition parameter not set.")
    # Store and update the acquisition parameters
    initial_f0 = console.parameter.larmor_frequency
    initial_shim = console.parameter.gradient_offset
    console.parameter.larmor_frequency = f0
    console.parameter.gradient_offset = shims

    with AcquisitionControlManager() as m:
        m.acquisition.set_sequence(sequence=seq, parameter=console.parameter)
        acq_data: AcquisitionData = m.acquisition.run()

    # Restore the acquisition parameters
    console.parameter.larmor_frequency = initial_f0
    console.parameter.gradient_offset = initial_shim

    return acq_data.receive_data[0]

@app.command(name="shims")
def calibrate_shimming(
    start_range: float = 0.1,
    end_range: float = 0.01,
    num_dummies: int = 3,
    show_plot: bool = False,
) -> None:
    """Calibrate first-order active shims using iterative coordinate descent.

    Acquires dummy FIDs to stabilise the system, then iteratively adjusts the
    X, Y, and Z gradient offset channels one at a time, keeping the change that
    maximises the spectral peak amplitude. The shim step size starts at
    `start_range` and is multiplied by 0.75 after each full X/Y/Z cycle until
    it falls below `end_range`.

    On convergence `console.parameter.gradient_offset` is set to the best found
    shim values (in mV) and `console.parameter.larmor_frequency` is updated to
    correct for the residual frequency offset observed in the shimmed FID.

    Args:
        start_range: Initial gradient-offset step size in normalised mT/m units.
            Defaults to 0.1.
        end_range: Stopping threshold; the optimisation exits when the step size
            falls below this value. Defaults to 0.01.
        num_dummies: Number of dummy FID acquisitions before the optimisation
            starts. Defaults to 3.
        show_plot: When `True`, display a three-panel figure showing the initial
            vs. shimmed FID, the frequency spectrum, and the convergence curve.
            Defaults to `False`.

    Raises:
        ValueError: If `console.parameter` is `None`.

    """
    if console.parameter is None:
        raise ValueError("Acquisition parameter not set.")
    # Reset gradient offsets
    shims_current_mv = Dimensions(x=0., y=0., z=0.)

    f_0 = console.parameter.larmor_frequency

    with AcquisitionControlManager() as m:
        device_config: NexusConfiguration = m.acquisition.get_device_configuration()
        system = m.acquisition.get_sequence_system()

    # Construct FID sequence
    seq = fid.constructor(
        rf_duration=150e-6,
        num_samples=1000,
        acq_bandwidth=20e3,
        dead_time=3e-3,
        flip_angle=np.pi/4, # running with 45 degree to avoid overtipping.
        system=system,
    )

    gpa_gain = Dimensions.from_list(list(device_config.tx.gpa_gain)) # V/A
    grad_eff = Dimensions.from_list(list(device_config.tx.gradient_efficiency))  #T/m/A
    print(f"GPA gain: {gpa_gain} V/A\nGradient efficiency: {grad_eff} T/m/A")
    gain_eff_prod = gpa_gain * grad_eff

    # Run shimming process
    # Convert gradient offsets from mV to mT/m
    shims_best = shims_current_mv * gain_eff_prod
    shim_step = start_range

    # Run dummy scans
    for _ in range(num_dummies):
        _ = run_fid(f_0, shims_current_mv, seq)

    data = run_fid(f_0, shims_current_mv, seq)
    initial_data = data.processed_data.squeeze()
    initial_data_fft = np.fft.fftshift(np.fft.fft(np.fft.fftshift(initial_data)))
    amp_best = np.max(np.abs(initial_data_fft))
    amp_data = [amp_best]

    while(shim_step > end_range):
        # X gradient positive step
        _shims = deepcopy(shims_best)
        _shims.x += (shim_step / 2)
        acq_data = run_fid(f_0, _shims / gain_eff_prod, seq).processed_data.squeeze()
        amp_1 = np.max(np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))))
        # X gradient negative step
        _shims.x -= shim_step
        acq_data = run_fid(f_0, _shims / gain_eff_prod, seq).processed_data.squeeze()
        amp_2 = np.max(np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))))

        if amp_1 > amp_2 and amp_1 > amp_best:
            amp_best = amp_1
            shims_best.x += (shim_step / 2)
        elif amp_2 > amp_1 and amp_2 > amp_best:
            amp_best = amp_2
            shims_best.x -= (shim_step / 2)

        # Y gradient positive step
        _shims = deepcopy(shims_best)
        _shims.y += (shim_step / 2)
        acq_data = run_fid(f_0, _shims / gain_eff_prod, seq).processed_data.squeeze()
        amp_1 = np.max(np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))))
        # Y gradient negative step
        _shims.y -= shim_step
        acq_data = run_fid(f_0, _shims / gain_eff_prod, seq).processed_data.squeeze()
        amp_2 = np.max(np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))))

        if amp_1 > amp_2 and amp_1 > amp_best:
            amp_best = amp_1
            shims_best.y += (shim_step / 2)
        elif amp_2 > amp_1 and amp_2 > amp_best:
            amp_best = amp_2
            shims_best.y -= (shim_step / 2)

        # Z gradient positive step
        _shims = deepcopy(shims_best)
        _shims.z += (shim_step / 2)
        acq_data = run_fid(f_0, _shims / gain_eff_prod, seq).processed_data.squeeze()
        amp_1 = np.max(np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))))
        # Z gradient negative step
        _shims.z -= shim_step
        acq_data = run_fid(f_0, _shims / gain_eff_prod, seq).processed_data.squeeze()
        amp_2 = np.max(np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(acq_data)))))

        if amp_1 > amp_2 and amp_1 > amp_best:
            amp_best = amp_1
            shims_best.z += (shim_step / 2)
        elif amp_2 > amp_1 and amp_2 > amp_best:
            amp_best = amp_2
            shims_best.z -= (shim_step / 2)

        print(f"Step: +/-{shim_step:.4f} mT/m; \
            Optimized shims: {shims_best:.4f} mT/m | {(shims_best/gain_eff_prod):.4f} mV")
        amp_data.append(amp_best)
        shim_step *= 0.75  # Decrease step size of shim range

    # FID with best shim setting
    shimmed_data = run_fid(f_0, shims_best / gain_eff_prod, seq).processed_data.squeeze()
    shimmed_data_fft = np.fft.fftshift(np.fft.fft(np.fft.fftshift(shimmed_data)))
    time_scale = np.arange(np.size(shimmed_data))*data.dwell_time
    fft_freq = np.fft.fftshift(np.fft.fftfreq(np.size(shimmed_data), data.dwell_time))

    # Determine f0 offset after shimming
    f_0_offset = fft_freq[np.argmax(np.abs(shimmed_data_fft))]

    # Update console parameter
    console.parameter.larmor_frequency = f_0 - f_0_offset
    console.parameter.gradient_offset = shims_best / gain_eff_prod

    print(f"\nOptimized shims: {shims_best} mT/m ({shims_best / gain_eff_prod} mV)")
    print(f"Frequency offset [Hz]: {f_0_offset}\nNew frequency f0 [Hz]: {f_0 - f_0_offset}")

    # TODO: Save data

    if show_plot:
        _, ax = plt.subplots(1, 3, figsize=(15, 3))
        ax[0].plot(time_scale*1e3, np.abs(initial_data), label="Initial")
        ax[0].plot(time_scale*1e3, np.abs(shimmed_data), label="Shimmed")
        ax[0].set_xlabel("Time / ms")
        ax[0].set_ylabel("Amplitude / mV")
        ax[0].legend()
        ax[1].plot(fft_freq*1e-3, np.abs(initial_data_fft), label="Initial")
        ax[1].plot(fft_freq*1e-3, np.abs(shimmed_data_fft), label="Initial")
        ax[1].set_xlabel("Frequency / kHz")
        ax[1].set_ylabel("Amplitude / a.u")
        ax[1].legend()
        ax[2].plot(amp_data)
        ax[2].set_xlabel("Iteration")
        ax[2].set_ylabel("Peak amplitude / mV")
        plotting.show()
