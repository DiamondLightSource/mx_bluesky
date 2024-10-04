import os
from enum import Enum
from pathlib import Path

from bluesky.plan_stubs import abs_set, rd, sleep

from mx_bluesky.beamlines.i24.jungfrau_commissioning.plans.jungfrau_plans import (
    check_and_clear_errors,
    do_manual_acquisition,
    set_software_trigger,
    wait_for_writing,
    setup_detector
)
from mx_bluesky.beamlines.i24.jungfrau_commissioning.utils import run_number
from mx_bluesky.beamlines.i24.jungfrau_commissioning.utils.jf_commissioning_devices import (
    JungfrauM1,
)
from mx_bluesky.beamlines.i24.jungfrau_commissioning.utils.log import LOGGER
from mx_bluesky.beamlines.i24.jungfrau_commissioning.utils import i24


class GainMode(str, Enum):
    dynamic = "dynamic"
    forceswitchg1 = "forceswitchg1"
    forceswitchg2 = "forceswitchg2"


def set_gain_mode(
    jungfrau: JungfrauM1,
    gain_mode: GainMode,
    wait=True,
    check_for_errors=True,
    timeout_s=3,
):
    LOGGER.info(f"Setting gain mode {gain_mode.value}")
    yield from abs_set(jungfrau.gain_mode, gain_mode.value, wait=wait)
    time = 0.0
    current_gain_mode = ""
    while current_gain_mode != gain_mode.value and time < timeout_s:
        yield from sleep(0.1)
        current_gain_mode = yield from rd(jungfrau.gain_mode)
        time += 0.1
    if time > timeout_s:
        raise TimeoutError(f"Gain mode change unsuccessful in {timeout_s} seconds")
    if check_for_errors:
        yield from check_and_clear_errors(jungfrau)


def do_darks(
    jungfrau: JungfrauM1,
    directory: str = "/dls/i24/data/2024/cm37275-4/jungfrau_commissioning/",
    check_for_errors=True,
    exp_time_s=0.001,
    acq_time_s=0.001,
    focred_gain_ratio=10,
    num_images=1000,
    timeout_factor=6,
):
    """Do a set of 1000 images at dynamic gain, forced gain 1, forced gain 2.
    For the collections at forced gain modes, the acquisition time will be
    multiplied by the forced gain ratio."""

    directory_prefix = (
        Path(directory)
        / f"{run_number(Path(directory)):05d}_darks_{acq_time_s}s_per_frame"
    )
    os.makedirs(directory_prefix, exist_ok=True)

    LOGGER.info(f"Writing data to {directory_prefix}")

    timeout_factor = max(10, timeout_factor * 0.001 / acq_time_s)

    # TODO CHECK IF FILES EXIST
    fg_acq_time = acq_time_s * focred_gain_ratio

    yield from set_software_trigger(jungfrau)

    # Gain 0
    yield from set_gain_mode(
        jungfrau, GainMode.dynamic, check_for_errors=check_for_errors
    )
    yield from abs_set(jungfrau.file_directory, directory_prefix.as_posix(), wait=True)
    yield from abs_set(jungfrau.file_name, "G0", wait=True)
    yield from do_manual_acquisition(
        jungfrau, exp_time_s, acq_time_s, num_images, timeout_factor
    )
    yield from sleep(0.3)

    # Gain 1
    yield from set_gain_mode(
        jungfrau, GainMode.forceswitchg1, check_for_errors=check_for_errors
    )
    yield from abs_set(jungfrau.file_name, "G1", wait=True)
    yield from do_manual_acquisition(
        jungfrau, exp_time_s, fg_acq_time, num_images, timeout_factor
    )
    yield from sleep(0.3)

    # Gain 2
    yield from set_gain_mode(
        jungfrau, GainMode.forceswitchg2, check_for_errors=check_for_errors
    )
    yield from abs_set(jungfrau.file_name, "G2", wait=True)
    yield from do_manual_acquisition(
        jungfrau, exp_time_s, fg_acq_time, num_images, timeout_factor
    )
    yield from sleep(0.3)

    # Leave on dynamic after finishing
    yield from set_gain_mode(
        jungfrau, GainMode.dynamic, check_for_errors=check_for_errors
    )


def do_pedestal_darks(    
    jungfrau: JungfrauM1,
    directory: str = "/dls/i24/data/2024/cm37275-4/jungfrau_commissioning/",
    check_for_errors=True,
    exp_time_s=0.001,
    acq_time_s=0.001,
    focred_gain_ratio=10,
    num_images=1000,
    timeout_factor=6,
    pedestal_frames=20,
    pedestal_loops=200):

    directory_prefix = (
        Path(directory)
        / f"{run_number(Path(directory)):05d}_darks_{acq_time_s}s_per_frame_pedestal"
    )
    os.makedirs(directory_prefix, exist_ok=True)

    LOGGER.info(f"Writing data to {directory_prefix}")

    yield from set_software_trigger(jungfrau)

    yield from setup_detector(jungfrau, exp_time_s, acq_time_s, pedestal_frames*pedestal_loops*2)

    yield from set_gain_mode(
        jungfrau, GainMode.dynamic, check_for_errors=check_for_errors
    )
    yield from abs_set(jungfrau.file_directory, directory_prefix.as_posix(), wait=True)
    yield from abs_set(jungfrau.file_name, "Pedestal", wait=True)

    yield from abs_set(jungfrau.pedestal_frames, pedestal_frames, wait=True)
    yield from abs_set(jungfrau.pedestal_loops, pedestal_loops, wait=True)

    yield from abs_set(jungfrau.pedestal_mode, 1, wait=True)

    yield from abs_set(jungfrau.acquire_start, 1, wait=True)
    yield from wait_for_writing(jungfrau, 1000)

    yield from sleep(0.3)

    yield from abs_set(jungfrau.pedestal_mode, 0, wait=True)


def take_darks():
    """"Take darks in pedestal and old style, at 1kHz and 2kHz"""
    jf = i24.jungfrau()
    for time in [0.001, 0.0005]:
        LOGGER.info(f"Taking data at exposure time = {time}")
        yield from do_pedestal_darks(jf, exp_time_s=time, acq_time_s=time)
        yield from do_darks(jf, exp_time_s=time, acq_time_s=time, focred_gain_ratio=10)
