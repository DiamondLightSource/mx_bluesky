from unittest.mock import patch

import pytest

from mx_bluesky.I24.serial.parameters.constants import SSXType
from mx_bluesky.I24.serial.setup_beamline import Eiger, Pilatus
from mx_bluesky.I24.serial.setup_beamline.setup_detector import (
    DetRequest,
    _get_requested_detector,
    get_detector_type,
    setup_detector_stage,
)


@patch("mx_bluesky.I24.serial.setup_beamline.setup_detector.caget")
def test_get_detector_type(fake_caget):
    fake_caget.return_value = -22
    assert get_detector_type().name == "eiger"


@patch("mx_bluesky.I24.serial.setup_beamline.setup_detector.caget")
def test_get_detector_type_finds_pilatus(fake_caget):
    fake_caget.return_value = 566
    assert get_detector_type().name == "pilatus"


@patch("mx_bluesky.I24.serial.setup_beamline.setup_detector.caget")
def test_get_requested_detector(fake_caget):
    fake_caget.return_value = "pilatus"
    assert _get_requested_detector("some_pv") == Pilatus.name

    fake_caget.return_value = "0"
    assert _get_requested_detector("some_pv") == Eiger.name


@patch("mx_bluesky.I24.serial.setup_beamline.setup_detector.caget")
def test_get_requested_detector_raises_error_for_invalid_value(fake_caget):
    fake_caget.return_value = "something"
    with pytest.raises(ValueError):
        _get_requested_detector("some_pv")


@patch("mx_bluesky.I24.serial.setup_beamline.setup_detector.caget")
async def test_setup_detector_stage(fake_caget, detector_stage, RE):
    fake_caget.return_value = DetRequest.eiger.value
    RE(setup_detector_stage(detector_stage, SSXType.FIXED))
    assert await detector_stage.y.user_readback.get_value() == Eiger.det_y_target

    fake_caget.return_value = DetRequest.pilatus.value
    RE(setup_detector_stage(detector_stage, SSXType.EXTRUDER))
    assert await detector_stage.y.user_readback.get_value() == Pilatus.det_y_target
