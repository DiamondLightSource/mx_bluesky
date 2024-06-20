from functools import partial
from unittest.mock import patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i24
from dodal.devices.i24.I24_detector_motion import DetectorMotion
from ophyd.status import Status

from mx_bluesky.I24.serial.parameters.constants import SSXType
from mx_bluesky.I24.serial.setup_beamline import Eiger, Pilatus
from mx_bluesky.I24.serial.setup_beamline.setup_detector import (
    DetRequest,
    _get_requested_detector,
    get_detector_type,
    setup_detector_stage,
)


@pytest.fixture
def fake_detector_motion() -> DetectorMotion:
    detector_motion = i24.detector_motion(fake_with_ophyd_sim=True)
    detector_motion.y.user_setpoint._use_limits = False
    detector_motion.z.user_setpoint._use_limits = False

    def mock_set(motor, val):
        motor.user_readback.sim_put(val)
        return Status(done=True, success=True)

    def patch_motor(motor):
        return patch.object(motor, "set", partial(mock_set, motor))

    with patch_motor(detector_motion.y), patch_motor(detector_motion.z):
        yield detector_motion


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


@patch("mx_bluesky.I24.serial.setup_beamline.setup_detector.setup_logging")
@patch("mx_bluesky.I24.serial.setup_beamline.setup_detector.caget")
def test_setup_detector_stage(fake_caget, fake_log, fake_detector_motion):
    RE = RunEngine()

    fake_caget.return_value = DetRequest.eiger.value
    RE(setup_detector_stage(SSXType.FIXED, fake_detector_motion))
    assert fake_detector_motion.y.user_readback.get() == Eiger.det_y_target

    fake_caget.return_value = DetRequest.pilatus.value
    RE(setup_detector_stage(SSXType.EXTRUDER, fake_detector_motion))
    assert fake_detector_motion.y.user_readback.get() == Pilatus.det_y_target
