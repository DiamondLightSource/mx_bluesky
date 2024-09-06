from __future__ import annotations

import json

from blueapi.core import BlueskyContext, MsgGenerator
from dodal.devices.eiger import EigerDetector
from dodal.devices.oav.oav_parameters import OAV_CONFIG_JSON, OAVParameters

from mx_bluesky.hyperion.device_setup_plans.utils import (
    start_preparing_data_collection_then_do_plan,
)
from mx_bluesky.hyperion.experiment_plans.grid_detect_then_xray_centre_plan import (
    GridDetectThenXRayCentreComposite,
    detect_grid_and_do_gridscan,
)
from mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan import (
    PinTipCentringComposite,
    pin_tip_centre_plan,
)
from mx_bluesky.hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    ispyb_activation_wrapper,
)
from mx_bluesky.hyperion.log import LOGGER
from mx_bluesky.hyperion.parameters.constants import CONST
from mx_bluesky.hyperion.parameters.gridscan import (
    GridScanWithEdgeDetect,
    PinTipCentreThenXrayCentre,
)
from mx_bluesky.hyperion.utils.context import device_composite_from_context


def create_devices(context: BlueskyContext) -> GridDetectThenXRayCentreComposite:
    """
    GridDetectThenXRayCentreComposite contains all the devices we need, reuse that.
    """
    return device_composite_from_context(context, GridDetectThenXRayCentreComposite)


def create_parameters_for_grid_detection(
    pin_centre_parameters: PinTipCentreThenXrayCentre,
) -> GridScanWithEdgeDetect:
    params_json = json.loads(pin_centre_parameters.model_dump_json())
    del params_json["tip_offset_um"]
    grid_detect_and_xray_centre = GridScanWithEdgeDetect(**params_json)
    LOGGER.info(
        f"Parameters for grid detect and xray centre: {grid_detect_and_xray_centre.model_dump_json(indent=2)}"
    )
    return grid_detect_and_xray_centre


def pin_centre_then_xray_centre_plan(
    composite: GridDetectThenXRayCentreComposite,
    parameters: PinTipCentreThenXrayCentre,
    oav_config_file: str = OAV_CONFIG_JSON,
):
    """Plan that perfoms a pin tip centre followed by an xray centre to completely
    centre the sample"""
    oav_config_file = parameters.oav_centring_file

    pin_tip_centring_composite = PinTipCentringComposite(
        oav=composite.oav,
        smargon=composite.smargon,
        backlight=composite.backlight,
        pin_tip_detection=composite.pin_tip_detection,
    )

    def _pin_centre_then_xray_centre_plan():
        yield from pin_tip_centre_plan(
            pin_tip_centring_composite,
            parameters.tip_offset_um,
            oav_config_file,
        )

        grid_detect_params = create_parameters_for_grid_detection(parameters)

        oav_params = OAVParameters("xrayCentring", oav_config_file)

        yield from detect_grid_and_do_gridscan(
            composite,
            grid_detect_params,
            oav_params,
        )

    yield from ispyb_activation_wrapper(_pin_centre_then_xray_centre_plan(), parameters)


def pin_tip_centre_then_xray_centre(
    composite: GridDetectThenXRayCentreComposite,
    parameters: PinTipCentreThenXrayCentre,
    oav_config_file: str = OAV_CONFIG_JSON,
) -> MsgGenerator:
    """Starts preparing for collection then performs the pin tip centre and xray centre"""

    eiger: EigerDetector = composite.eiger

    eiger.set_detector_parameters(parameters.detector_params)

    return start_preparing_data_collection_then_do_plan(
        eiger,
        composite.detector_motion,
        parameters.detector_params.detector_distance,
        pin_centre_then_xray_centre_plan(composite, parameters, oav_config_file),
        group=CONST.WAIT.GRID_READY_FOR_DC,
    )
