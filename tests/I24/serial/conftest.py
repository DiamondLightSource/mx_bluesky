from functools import partial
from unittest.mock import AsyncMock, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i24
from dodal.devices.i24.aperture import Aperture
from dodal.devices.i24.beamstop import Beamstop
from dodal.devices.i24.dual_backlight import DualBacklight
from dodal.devices.i24.I24_detector_motion import DetectorMotion
from dodal.devices.zebra import Zebra
from ophyd.status import Status
from ophyd_async.core import callback_on_mock_put, set_mock_value
from ophyd_async.epics.motion import Motor


def patch_motor(motor: Motor, initial_position: float = 0):
    set_mock_value(motor.user_setpoint, initial_position)
    set_mock_value(motor.user_readback, initial_position)
    set_mock_value(motor.deadband, 0.001)
    set_mock_value(motor.motor_done_move, 1)
    set_mock_value(motor.velocity, 3)
    return callback_on_mock_put(
        motor.user_setpoint,
        lambda pos, *args, **kwargs: set_mock_value(motor.user_readback, pos),
    )


@pytest.fixture
def zebra() -> Zebra:
    RunEngine()
    zebra = i24.zebra(fake_with_ophyd_sim=True)

    async def mock_disarm(_):
        await zebra.pc.arm.armed._backend.put(0)  # type: ignore

    async def mock_arm(_):
        await zebra.pc.arm.armed._backend.put(1)  # type: ignore

    zebra.pc.arm.arm_set.set = AsyncMock(side_effect=mock_arm)
    zebra.pc.arm.disarm_set.set = AsyncMock(side_effect=mock_disarm)
    return zebra


@pytest.fixture
def detector_stage() -> DetectorMotion:
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


@pytest.fixture
def aperture():
    RunEngine()
    aperture: Aperture = i24.aperture(fake_with_ophyd_sim=True)
    with patch_motor(aperture.x), patch_motor(aperture.y):
        yield aperture


@pytest.fixture
def backlight() -> DualBacklight:
    backlight = i24.backlight(fake_with_ophyd_sim=True)
    return backlight


@pytest.fixture
def beamstop():
    RunEngine()
    beamstop: Beamstop = i24.beamstop(fake_with_ophyd_sim=True)

    with (
        patch_motor(beamstop.x),
        patch_motor(beamstop.y),
        patch_motor(beamstop.z),
        patch_motor(beamstop.roty),
    ):
        yield beamstop


@pytest.fixture
def RE():
    return RunEngine()
