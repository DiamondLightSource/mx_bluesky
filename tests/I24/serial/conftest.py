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
def aperture() -> Aperture:
    RunEngine()
    aperture = i24.aperture(fake_with_ophyd_sim=True)
    return aperture


@pytest.fixture
def backlight() -> DualBacklight:
    backlight = i24.backlight(fake_with_ophyd_sim=True)
    return backlight


@pytest.fixture
def beamstop() -> Beamstop:
    RunEngine()
    beamstop = i24.beamstop(fake_with_ophyd_sim=True)

    async def mock_set(motor, val):
        await motor._backend.put(val)

    def patch_motor(motor):
        return patch.object(motor, "set", partial(mock_set, motor))

    with patch_motor(beamstop.roty):
        return beamstop
    # return beamstop


@pytest.fixture
def RE():
    return RunEngine()
