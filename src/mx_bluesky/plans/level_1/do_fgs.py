from typing import Callable

import bluesky.plan_stubs as bps
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScanCommon as GridScanDevice
from dodal.devices.synchrotron import Synchrotron
from dodal.log import LOGGER
from dodal.plans.check_topup import check_topup_and_wait_if_necessary

"""
do fgs should:
Accept a gridscan device, a detector device, a synchrotron device, a group of optional parameters, metadata
"""

#When other detectors are available in dodal, move the detector to a more general type
def do_fgs(grid_scan_device: GridScanDevice, detector: EigerDetector, synchrotron: Synchrotron,
           pre_plans: None | Callable, post_plans: None | Callable
           ):
    """Triggers a grid scan motion program and waits for completion. Optionally run other plans before and after completion.

    The core logic for this lowest-level plan is to wait for synchrotron top-up, then kickoff and wait for FGS completion.

    Args:
        grid_scan_device (GridScanDevice): Device which can trigger a fast grid scan and wait for completion
        detector (StandardDetector): Need to convert Eiger to standard detector / something more generic
        synchrotron (Synchrotron): Synchrotron device
        pre_plans (Optional, Callable): Generic plan called just before kickoff, eg zocalo setup. Parameters specified in higher-level plans.
        post_plans (Optional, Callable): Generic plan called just before complete, eg waiting on zocalo.


    Returns:
    Status
    """
    expected_images = yield from bps.rd(grid_scan_device.expected_images)
    exposure_sec_per_image = yield from bps.rd(detector.cam.acquire_time)
    LOGGER.info("waiting for topup if necessary...")
    yield from check_topup_and_wait_if_necessary(
        synchrotron,
        expected_images * exposure_sec_per_image,
        30.0,
    )
    if pre_plans:
        yield from pre_plans()
    LOGGER.info("Wait for all moves with no assigned group")
    yield from bps.wait()
    LOGGER.info("kicking off FGS")
    yield from bps.kickoff(grid_scan_device, wait=True)
    if post_plans:
        yield from post_plans()
    LOGGER.info("completing FGS")
    yield from bps.complete(grid_scan_device, wait=True)