from unittest.mock import ANY, MagicMock, call, patch

import bluesky.plan_stubs as bps
import pytest
from dodal.devices.zebra import DISCONNECT, SOFT_IN3
from ophyd_async.core import get_mock_put

from mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2 import (
    TTL_EIGER,
    TTL_PILATUS,
    enter_hutch,
    initialise_extruder,
    laser_check,
    run_main_extruder_plan,
    tidy_up_at_collection_end_plan,
)
from mx_bluesky.I24.serial.parameters import ExtruderParameters
from mx_bluesky.I24.serial.setup_beamline import Eiger, Pilatus


@pytest.fixture
def dummy_params():
    params = {
        "visit": "foo",
        "directory": "bar",
        "filename": "protein",
        "exposure_time_s": 0.1,
        "detector_distance_mm": 100,
        "detector_name": "eiger",
        "num_images": 10,
        "pump_status": False,
    }
    return ExtruderParameters(**params)


@pytest.fixture
def dummy_params_pp():
    params_pp = {
        "visit": "foo",
        "directory": "bar",
        "filename": "protein",
        "exposure_time_s": 0.1,
        "detector_distance_mm": 100,
        "detector_name": "pilatus",
        "num_images": 10,
        "pump_status": True,
        "laser_dwell_s": 0.01,
        "laser_delay_s": 0.005,
    }
    return ExtruderParameters(**params_pp)


def fake_generator(value):
    yield from bps.null()
    return value


@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caget")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caput")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.get_detector_type")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.logger")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.setup_logging")
def test_initialise_extruder(
    fake_log_setup,
    fake_log,
    fake_det,
    fake_caput,
    fake_caget,
    detector_stage,
    RE,
):
    fake_caget.return_value = "/path/to/visit"
    fake_det.side_effect = [fake_generator(Eiger())]
    RE(initialise_extruder(detector_stage))
    assert fake_caput.call_count == 10
    assert fake_caget.call_count == 1


@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.setup_logging")
async def test_enterhutch(fake_log_setup, detector_stage, RE):
    RE(enter_hutch(detector_stage))
    assert await detector_stage.z.user_readback.get_value() == 1480


@pytest.mark.parametrize(
    "laser_mode, det_type, expected_in1, expected_out",
    [
        ("laseron", Eiger(), "Yes", SOFT_IN3),
        ("laseroff", Eiger(), "No", DISCONNECT),
        ("laseron", Pilatus(), "Yes", SOFT_IN3),
        ("laseroff", Pilatus(), "No", DISCONNECT),
    ],
)
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.get_detector_type")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.setup_logging")
async def test_laser_check(
    fake_log_setup,
    fake_det,
    laser_mode,
    expected_in1,
    expected_out,
    det_type,
    zebra,
    detector_stage,
    RE,
):
    fake_det.side_effect = [fake_generator(det_type)]
    RE(laser_check(laser_mode, zebra, detector_stage))

    TTL = TTL_EIGER if isinstance(det_type, Pilatus) else TTL_PILATUS
    assert await zebra.inputs.soft_in_1.get_value() == expected_in1
    assert await zebra.output.out_pvs[TTL].get_value() == expected_out


@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.sleep")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.DCID")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.call_nexgen")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caput")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caget")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.sup")
@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.setup_zebra_for_quickshot_plan"
)
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.setup_logging")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.bps.rd")
def test_run_extruder_quickshot_with_eiger(
    fake_read,
    fake_log_setup,
    mock_quickshot_plan,
    fake_sup,
    fake_caget,
    fake_caput,
    fake_nexgen,
    fake_dcid,
    fake_sleep,
    RE,
    zebra,
    shutter,
    aperture,
    backlight,
    beamstop,
    detector_stage,
    dummy_params,
):
    fake_start_time = MagicMock()
    # Mock end of data collection (zebra disarmed)
    fake_read.side_effect = [fake_generator(0)]
    RE(
        run_main_extruder_plan(
            zebra,
            aperture,
            backlight,
            beamstop,
            detector_stage,
            shutter,
            dummy_params,
            fake_dcid,
            fake_start_time,
        )
    )
    assert fake_nexgen.call_count == 1
    assert fake_dcid.notify_start.call_count == 1
    assert fake_sup.setup_beamline_for_collection_plan.call_count == 1
    # Check temporary piilatus hack is in there
    assert fake_sup.pilatus.call_count == 2
    mock_quickshot_plan.assert_called_once()


@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.sleep")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.DCID")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caput")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caget")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.sup")
@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.setup_zebra_for_extruder_with_pump_probe_plan"
)
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.setup_logging")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.bps.rd")
def test_run_extruder_pump_probe_with_pilatus(
    fake_read,
    fake_log_setup,
    mock_pp_plan,
    fake_sup,
    fake_caget,
    fake_caput,
    fake_dcid,
    fake_sleep,
    RE,
    zebra,
    shutter,
    aperture,
    backlight,
    beamstop,
    detector_stage,
    dummy_params_pp,
):
    fake_start_time = MagicMock()
    # Mock end of data collection (zebra disarmed)
    fake_read.side_effect = [fake_generator(0)]
    RE(
        run_main_extruder_plan(
            zebra,
            aperture,
            backlight,
            beamstop,
            detector_stage,
            shutter,
            dummy_params_pp,
            fake_dcid,
            fake_start_time,
        )
    )
    assert fake_dcid.notify_start.call_count == 1
    assert fake_sup.move_detector_stage_to_position_plan.call_count == 1
    mock_pp_plan.assert_called_once()

    shutter_call_list = [
        call("Reset", wait=True, timeout=10.0),
        call("Open", wait=True, timeout=10.0),
    ]
    mock_shutter = get_mock_put(shutter.control)
    mock_shutter.assert_has_calls(shutter_call_list)


@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.reset_zebra_when_collection_done_plan"
)
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.DCID")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caput")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caget")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.sup")
def test_tidy_up_at_collection_end_plan_with_eiger(
    fake_sup,
    fake_caget,
    fake_caput,
    fake_dcid,
    mock_reset_zebra_plan,
    RE,
    zebra,
    shutter,
    dummy_params,
):
    RE(tidy_up_at_collection_end_plan(zebra, shutter, dummy_params, fake_dcid))

    mock_reset_zebra_plan.assert_called_once()
    mock_shutter = get_mock_put(shutter.control)
    mock_shutter.assert_has_calls([call("Close", wait=True, timeout=10.0)])

    assert fake_dcid.collection_complete.call_count == 1
    assert fake_dcid.notify_end.call_count == 1
    assert fake_caget.call_count == 1

    call_list = [call(ANY, 0), call(ANY, "Done")]
    fake_caput.assert_has_calls(call_list)

    fake_sup.eiger.assert_called_once_with("return-to-normal")
