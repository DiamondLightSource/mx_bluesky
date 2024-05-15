from unittest.mock import ANY, call, patch

import pytest
from dodal.devices.zebra import DISCONNECT, SOFT_IN3

from mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2 import (
    TTL_EIGER,
    TTL_PILATUS,
    enter_hutch,
    initialise_extruder,
    laser_check,
    run_extruder_plan,
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


@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caget")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caput")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.get_detector_type")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.logger")
def test_initialise_extruder(fake_log, fake_det, fake_caput, fake_caget, RE):
    fake_caget.return_value = "/path/to/visit"
    fake_det.return_value = Eiger()
    RE(initialise_extruder())
    assert fake_caput.call_count == 10
    assert fake_caget.call_count == 1


@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caput")
def test_enterhutch(fake_caput, RE):
    RE(enter_hutch())
    assert fake_caput.call_count == 1
    fake_caput.assert_has_calls([call(ANY, 1480)])


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
async def test_laser_check(
    fake_det, laser_mode, expected_in1, expected_out, det_type, zebra, RE
):
    fake_det.return_value = det_type
    RE(laser_check(laser_mode, zebra))

    TTL = TTL_EIGER if isinstance(det_type, Pilatus) else TTL_PILATUS
    assert await zebra.inputs.soft_in_1.get_value() == expected_in1
    assert await zebra.output.out_pvs[TTL].get_value() == expected_out


@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.write_parameter_file",
)
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.shutil")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.sleep")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.DCID")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.call_nexgen")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caput")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caget")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.sup")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.get_detector_type")
@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.setup_zebra_for_quickshot_plan"
)
@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.ExtruderParameters"
)
def test_run_extruder_quickshot_with_eiger(
    mock_params,
    mock_quickshot_plan,
    fake_det,
    fake_sup,
    fake_caget,
    fake_caput,
    fake_nexgen,
    fake_dcid,
    fake_sleep,
    fake_shutil,
    fake_write_params,
    RE,
    zebra,
    dummy_params,
):
    mock_params.from_file.return_value = dummy_params
    fake_det.return_value = Eiger()
    RE(run_extruder_plan(zebra))
    assert fake_nexgen.call_count == 1
    assert fake_dcid.call_count == 1
    # Check temporary piilatus hack is in there
    assert fake_sup.pilatus.call_count == 2
    mock_quickshot_plan.assert_called_once()


@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.write_parameter_file"
)
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.shutil")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.sleep")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.DCID")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caput")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caget")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.sup")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.get_detector_type")
@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.setup_zebra_for_extruder_with_pump_probe_plan"
)
@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.reset_zebra_when_collection_done_plan"
)
@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.ExtruderParameters"
)
def test_run_extruder_pump_probe_with_pilatus(
    mock_params,
    mock_reset_zebra_plan,
    mock_pp_plan,
    fake_det,
    fake_sup,
    fake_caget,
    fake_caput,
    fake_dcid,
    fake_sleep,
    fake_shutil,
    fake_write_params,
    RE,
    zebra,
    dummy_params_pp,
):
    mock_params.from_file.return_value = dummy_params_pp
    # fake_i24.zebra.return_value = MagicMock()
    fake_det.return_value = Pilatus()
    RE(run_extruder_plan(zebra))
    assert fake_dcid.call_count == 1
    mock_pp_plan.assert_called_once()
    mock_reset_zebra_plan.assert_called_once()
