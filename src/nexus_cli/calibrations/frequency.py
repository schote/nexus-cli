"""Larmor-frequency calibration using a spin-echo spectrum."""
# %%
import warnings

import console
import matplotlib.pyplot as plt
import numpy as np
from console.interfaces.acquisition_data import AcquisitionData
from console.utilities.sequences.spectrometry import se_spectrum
from console.utilities.snr import signal_to_noise_ratio

from nexus_service.acquisition_manager import AcquisitionControlManager

from nexus_cli.calibrations import app


@app.command(name="f0")
def calibrate_larmor_frequency(show_plot: bool = True, min_snr: float = 20.) -> None:
    """Calibrate the Larmor frequency using a spin-echo spectrum.

    Acquires a single spin-echo spectrum, computes the FFT, and determines the
    frequency offset between the spectral peak and the current Larmor frequency.
    If the measured SNR meets or exceeds `min_snr` the offset is applied to
    `console.parameter.larmor_frequency`. Otherwise a `UserWarning` is raised and
    the frequency is left unchanged.

    Args:
        show_plot: When `True`, display a two-panel figure with the time-domain
            signal and the magnitude frequency spectrum.
        min_snr: Minimum SNR in dB required to apply the frequency correction.
            Defaults to 20 dB.

    Raises:
        ValueError: If the acquisition returns no receive data.
        UserWarning: If the measured SNR is below `min_snr`.

    """
    current_f0 = console.parameter.larmor_frequency

    with AcquisitionControlManager() as m:
        seq = se_spectrum.constructor(
            echo_time=10e-3,
            rf_duration=150e-6,
            num_samples=1000,
            acq_bandwidth=20e3,
            system=m.acquisition.get_sequence_system(),
        )
        m.acquisition.set_sequence(sequence=seq, parameter=console.parameter)
        acq_data: AcquisitionData = m.acquisition.run()

    if not acq_data.receive_data or acq_data.receive_data[0].processed_data is None:
        raise ValueError("No acquisition data.")
    data = acq_data.receive_data[0].processed_data.squeeze()
    data_fft = np.fft.fftshift(np.fft.fft(np.fft.fftshift(data)))
    fft_freq = np.fft.fftshift(np.fft.fftfreq(data.size, acq_data.receive_data[0].dwell_time))

    max_spec = np.max(np.abs(data_fft))
    f_0_offset = fft_freq[np.argmax(np.abs(data_fft))]

    snr = signal_to_noise_ratio(data_fft, dwell_time=acq_data.receive_data[0].dwell_time)

    print(f"Frequency offset [Hz]: {f_0_offset}\nNew frequency f0 [Hz]: {current_f0 + f_0_offset}")
    print(f"Frequency spectrum max.: {max_spec}")
    print(f"Number of samples: {acq_data.receive_data[0].num_samples} ({acq_data.receive_data[0].num_samples_raw} raw samples)")
    print("SNR [dB]: ", snr)

    if snr >= min_snr:
        console.parameter.larmor_frequency = current_f0 + f_0_offset
    else:
        msg = f"SNR of {snr} dB too low to adjust frequency. Please adjust manually."
        warnings.warn(msg, UserWarning)

    # TODO: Save calibration data

    if show_plot:
        time_axis = np.arange(data.size)*acq_data.receive_data[0].dwell_time*1e3
        _, ax = plt.subplots(1, 2, figsize=(12, 5))
        ax[0].plot(time_axis, np.abs(data), label="Abs")
        ax[0].plot(time_axis, np.real(data), label="Re")
        ax[0].plot(time_axis, np.imag(data), label="Im")
        ax[0].set_xlabel("Time [ms]")
        ax[0].set_ylabel("RX signal [mV]")
        ax[0].legend(loc="upper right")
        ax[1].plot(fft_freq, np.abs(data_fft))
        ax[1].set_ylim([0, max_spec * 1.05])
        ax[1].set_ylabel("Abs. FFT Spectrum [a.u.]")
        ax[1].set_xlabel("Frequency [Hz]")
        plt.show()
