from unittest.mock import patch

import pytest
from dodal.devices.i24.aperture import Aperture
from dodal.devices.i24.beamstop import Beamstop
from dodal.devices.i24.dual_backlight import DualBacklight
from dodal.devices.i24.I24_detector_motion import DetectorMotion

from mx_bluesky.I24.serial.setup_beamline import setup_beamline


async def test_setup_beamline_for_collection_plan(
    aperture: Aperture, backlight: DualBacklight, beamstop: Beamstop, RE
):
    RE(setup_beamline.setup_beamline_for_collection_plan(aperture, backlight, beamstop))

    assert await aperture.pos.pos_select.get_value() == "In"
    assert await beamstop.pos_select.get_value() == "Data Collection"
    assert await beamstop.roty.user_readback.get_value() == 0

    assert await backlight.pos1.pos_level.get_value() == "Out"


async def test_setup_beamline_for_quickshot_plan(detector_stage: DetectorMotion, RE):
    det_dist = 100
    RE(setup_beamline.setup_beamline_for_quickshot_plan(detector_stage, det_dist))

    assert await detector_stage.z.user_readback.get_value() == det_dist


@patch("mx_bluesky.I24.serial.setup_beamline.setup_beamline.caput")
@patch("mx_bluesky.I24.serial.setup_beamline.setup_beamline.caget")
def test_pilatus_raises_error_if_fastchip_and_no_args_list(fake_caget, fake_caput):
    with pytest.raises(TypeError):
        setup_beamline.pilatus("fastchip")


@patch("mx_bluesky.I24.serial.setup_beamline.setup_beamline.caput")
@patch("mx_bluesky.I24.serial.setup_beamline.setup_beamline.caget")
def test_pilatus_quickshot(fake_caget, fake_caput):
    setup_beamline.pilatus("quickshot", ["", "", 1, 0.1])
    assert fake_caput.call_count == 12
    assert fake_caget.call_count == 2


@patch("mx_bluesky.I24.serial.setup_beamline.setup_beamline.caput")
@patch("mx_bluesky.I24.serial.setup_beamline.setup_beamline.caget")
def test_eiger_raises_error_if_quickshot_and_no_args_list(fake_caget, fake_caput):
    with pytest.raises(TypeError):
        setup_beamline.eiger("quickshot")


@patch("mx_bluesky.I24.serial.setup_beamline.setup_beamline.caput")
@patch("mx_bluesky.I24.serial.setup_beamline.setup_beamline.caget")
def test_eiger_quickshot(fake_caget, fake_caput):
    setup_beamline.eiger("quickshot", ["", "", "1", "0.1"])
    assert fake_caput.call_count == 32
