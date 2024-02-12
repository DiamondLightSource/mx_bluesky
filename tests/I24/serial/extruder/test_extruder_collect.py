import argparse
from unittest.mock import ANY, call, mock_open, patch

import pytest
from dodal.devices.zebra import DISCONNECT, IN1_TTL, SOFT_IN1

from mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2 import (
    TTL_EIGER,
    TTL_PILATUS,
    enter_hutch,
    initialise_extruderi24,
    laser_check,
    run_extruderi24,
    scrape_parameter_file,
)
from mx_bluesky.I24.serial.setup_beamline import Eiger, Pilatus

params_file_str = """visit foo
directory bar
filename boh
num_imgs 1
exp_time 0.1
det_dist 100
det_type eiger
pump_probe false
pump_exp 0
pump_delay 0"""


@pytest.fixture
def dummy_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "place",
        type=str,
        choices=["laseron", "laseroff"],
        help="Requested setting.",
    )
    yield parser


@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.open",
    mock_open(read_data=params_file_str),
)
def test_scrape_parameter_file():
    res = scrape_parameter_file()
    assert res[0] == "foo"
    assert len(res) == 10
    # Checking correct types
    assert res[3] == 1 and res[4] == 0.1


@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caget")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caput")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.get_detector_type")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.logger")
def test_initialise_extruder(fake_log, fake_det, fake_caput, fake_caget, RE):
    fake_caget.return_value = "/path/to/visit"
    fake_det.return_value = Eiger()
    RE(initialise_extruderi24())
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
        ("laseron", Eiger(), IN1_TTL, SOFT_IN1),
        ("laseroff", Eiger(), DISCONNECT, DISCONNECT),
        ("laseron", Pilatus(), IN1_TTL, SOFT_IN1),
        ("laseroff", Pilatus(), DISCONNECT, DISCONNECT),
    ],
)
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.get_detector_type")
def test_laser_check(
    fake_det, laser_mode, expected_in1, expected_out, det_type, dummy_parser, zebra, RE
):
    fake_det.return_value = det_type
    fake_args = dummy_parser.parse_args([laser_mode])
    RE(laser_check(fake_args, zebra))

    TTL = TTL_EIGER if isinstance(det_type, Pilatus) else TTL_PILATUS
    assert zebra.inputs.soft_in_1.get() == expected_in1
    assert zebra.output.out_pvs[TTL].get() == expected_out


@patch(
    "mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.open",
    mock_open(read_data=params_file_str),
)
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.sleep")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.DCID")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.call_nexgen")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caput")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.caget")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.sup")
@patch("mx_bluesky.I24.serial.extruder.i24ssx_Extruder_Collect_py3v2.get_detector_type")
def test_run_extruder_with_eiger(
    fake_det,
    fake_sup,
    fake_caget,
    fake_caput,
    fake_nexgen,
    fake_dcid,
    fake_sleep,
    RE,
    zebra,
):
    fake_det.return_value = Eiger()
    RE(run_extruderi24())
    assert fake_nexgen.call_count == 1
    assert fake_dcid.call_count == 1
    # Check temporary piilatus hack is in there
    assert fake_sup.pilatus.call_count == 2
