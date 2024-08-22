from time import time
from typing import Callable, Optional

import bluesky.plan_stubs as bps
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScanCommon
from dodal.devices.synchrotron import Synchrotron
from dodal.log import LOGGER
from dodal.plans.check_topup import check_topup_and_wait_if_necessary

from mx_bluesky.device_setup_plans.read_hardware_for_setup import (
    read_hardware_for_zocalo,
)


def do_fgs(
    grid_scan_device: FastGridScanCommon,
    detector: EigerDetector,  # Once Eiger inherits from StandardDetector, use that type instead
    synchrotron: Synchrotron,
    during_collection_plans: Optional[Callable] = None,
):
    """Triggers a grid scan motion program and waits for completion, accounting for synchrotron topup.
        Optionally run other plans kickoff and between kickoff and completion. A bluesky run MUST be open before this plan is
        called

    Args:
        grid_scan_device (GridScanDevice): Device which can trigger a fast grid scan and wait for completion
        detector (EigerDetector)
        synchrotron (Synchrotron): Synchrotron device
        pre_plans (Optional, Callable): Generic plan called just before kickoff, eg zocalo setup. Parameters specified in higher-level plans.
        during_collection_plans (Optional, Callable): Generic plan called in between kickoff but and completion, eg waiting on zocalo.
    """

    expected_images = yield from bps.rd(grid_scan_device.expected_images)
    exposure_sec_per_image = yield from bps.rd(detector.cam.acquire_time)
    LOGGER.info("waiting for topup if necessary...")
    yield from check_topup_and_wait_if_necessary(
        synchrotron,
        expected_images * exposure_sec_per_image,
        30.0,
    )
    read_hardware_for_zocalo(detector)
    LOGGER.info("Wait for all moves with no assigned group")
    yield from bps.wait()
    LOGGER.info("kicking off FGS")
    yield from bps.kickoff(grid_scan_device, wait=True)
    gridscan_start_time = time()
    if during_collection_plans:
        yield from during_collection_plans()
    LOGGER.info("completing FGS")
    yield from bps.complete(grid_scan_device, wait=True)
    # Remove this logging statement once metrics have been added
    LOGGER.info(
        f"Gridscan motion program took {round(time()-gridscan_start_time,2)} to complete"
    )
