from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import numpy as np
from blueapi.core import MsgGenerator
from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from dodal.beamlines import i03
from dodal.devices.aperturescatterguard import AperturePositions, ApertureScatterguard
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.oav.oav_parameters import OAV_CONFIG_FILE_DEFAULTS, OAVParameters

from hyperion.device_setup_plans.utils import (
    start_preparing_data_collection_then_do_plan,
)
from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    create_devices as fgs_create_devices,
)
from hyperion.experiment_plans.flyscan_xray_centre_plan import flyscan_xray_centre
from hyperion.experiment_plans.oav_grid_detection_plan import (
    create_devices as oav_create_devices,
)
from hyperion.experiment_plans.oav_grid_detection_plan import grid_detection_plan
from hyperion.external_interaction.callbacks.oav_snapshot_callback import (
    OavSnapshotCallback,
)
from hyperion.log import LOGGER
from hyperion.parameters.beamline_parameters import get_beamline_parameters
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
    GridScanParams,
)

if TYPE_CHECKING:
    from hyperion.parameters.plan_specific.grid_scan_with_edge_detect_params import (
        GridScanWithEdgeDetectInternalParameters,
        GridScanWithEdgeDetectParams,
    )


def create_devices():
    fgs_create_devices()
    oav_create_devices()

    aperture_positions = AperturePositions.from_gda_beamline_params(
        get_beamline_parameters()
    )

    i03.detector_motion()

    i03.backlight()
    i03.aperture_scatterguard(aperture_positions=aperture_positions)


def wait_for_det_to_finish_moving(detector: DetectorMotion, timeout=120.0):
    LOGGER.info("Waiting for detector to finish moving")
    SLEEP_PER_CHECK = 0.1
    times_to_check = int(timeout / SLEEP_PER_CHECK)
    for _ in range(times_to_check):
        detector_state = yield from bps.rd(detector.shutter)
        detector_z_dmov = yield from bps.rd(detector.z.motor_done_move)
        LOGGER.info(f"Shutter state is {'open' if detector_state==1 else 'closed'}")
        LOGGER.info(f"Detector z DMOV is {detector_z_dmov}")
        if detector_state == 1 and detector_z_dmov == 1:
            return
        yield from bps.sleep(SLEEP_PER_CHECK)
    raise TimeoutError("Detector not finished moving")


def create_parameters_for_flyscan_xray_centre(
    grid_scan_with_edge_params: GridScanWithEdgeDetectInternalParameters,
    grid_parameters: GridScanParams,
) -> GridscanInternalParameters:
    params_json = json.loads(grid_scan_with_edge_params.json())
    params_json["experiment_params"] = json.loads(grid_parameters.json())
    flyscan_xray_centre_parameters = GridscanInternalParameters(**params_json)
    LOGGER.info(f"Parameters for FGS: {flyscan_xray_centre_parameters}")
    return flyscan_xray_centre_parameters


def detect_grid_and_do_gridscan(
    parameters: GridScanWithEdgeDetectInternalParameters,
    backlight: Backlight,
    aperture_scatterguard: ApertureScatterguard,
    detector_motion: DetectorMotion,
    oav_params: OAVParameters,
):
    assert aperture_scatterguard.aperture_positions is not None
    experiment_params: GridScanWithEdgeDetectParams = parameters.experiment_params
    grid_params = GridScanParams(dwell_time=experiment_params.exposure_time * 1000)

    detector_params = parameters.hyperion_params.detector_params
    snapshot_template = (
        f"{detector_params.prefix}_{detector_params.run_number}_{{angle}}"
    )

    oav_callback = OavSnapshotCallback()

    @bpp.subs_decorator([oav_callback])
    def run_grid_detection_plan(
        oav_params,
        fgs_params,
        snapshot_template,
        snapshot_dir,
    ):
        yield from grid_detection_plan(
            oav_params,
            fgs_params,
            snapshot_template,
            snapshot_dir,
            grid_width_microns=experiment_params.grid_width_microns,
        )

    yield from run_grid_detection_plan(
        oav_params,
        grid_params,
        snapshot_template,
        experiment_params.snapshot_dir,
    )

    # Hack because GDA only passes 3 values to ispyb
    out_upper_left = np.array(
        oav_callback.out_upper_left[0] + [oav_callback.out_upper_left[1][1]]
    )

    # Hack because the callback returns the list in inverted order
    parameters.hyperion_params.ispyb_params.xtal_snapshots_omega_start = (
        oav_callback.snapshot_filenames[0][::-1]
    )
    parameters.hyperion_params.ispyb_params.xtal_snapshots_omega_end = (
        oav_callback.snapshot_filenames[1][::-1]
    )
    parameters.hyperion_params.ispyb_params.upper_left = out_upper_left

    flyscan_xray_centre_parameters = create_parameters_for_flyscan_xray_centre(
        parameters, grid_params
    )

    yield from bps.abs_set(backlight.pos, Backlight.OUT)
    LOGGER.info(
        f"Setting aperture position to {aperture_scatterguard.aperture_positions.SMALL}"
    )
    yield from bps.abs_set(
        aperture_scatterguard, aperture_scatterguard.aperture_positions.SMALL
    )
    yield from wait_for_det_to_finish_moving(detector_motion)

    yield from flyscan_xray_centre(flyscan_xray_centre_parameters)


def grid_detect_then_xray_centre(
    parameters: Any,
    oav_param_files: dict = OAV_CONFIG_FILE_DEFAULTS,
) -> MsgGenerator:
    """
    A plan which combines the collection of snapshots from the OAV and the determination
    of the grid dimensions to use for the following grid scan.
    """
    backlight: Backlight = i03.backlight()
    eiger: EigerDetector = i03.eiger()
    aperture_scatterguard: ApertureScatterguard = i03.aperture_scatterguard()
    detector_motion: DetectorMotion = i03.detector_motion()
    attenuator: Attenuator = i03.attenuator()

    eiger.set_detector_parameters(parameters.hyperion_params.detector_params)

    oav_params = OAVParameters("xrayCentring", **oav_param_files)

    plan_to_perform = detect_grid_and_do_gridscan(
        parameters, backlight, aperture_scatterguard, detector_motion, oav_params
    )

    return start_preparing_data_collection_then_do_plan(
        eiger,
        attenuator,
        parameters.hyperion_params.ispyb_params.transmission_fraction,
        plan_to_perform,
    )
