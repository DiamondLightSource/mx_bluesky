from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i24
from dodal.devices.i24.aperture import Aperture
from dodal.devices.i24.beamstop import Beamstop
from dodal.devices.i24.dcm import DCM
from dodal.devices.i24.dual_backlight import DualBacklight
from dodal.devices.i24.pmac import PMAC
from dodal.devices.zebra import Zebra
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
async def RE():
    RE = RunEngine()
    # make sure the event loop is thoroughly up and running before we try to create
    # any ophyd_async devices which might need it
    timeout = time.monotonic() + 1
    while not RE.loop.is_running():
        await asyncio.sleep(0)
        if time.monotonic() > timeout:
            raise TimeoutError("This really shouldn't happen but just in case...")
    yield RE


@pytest.fixture
def zebra(RE) -> Zebra:
    zebra = i24.zebra(fake_with_ophyd_sim=True)

    async def mock_disarm(_):
        await zebra.pc.arm.armed._backend.put(0)  # type: ignore

    async def mock_arm(_):
        await zebra.pc.arm.armed._backend.put(1)  # type: ignore

    zebra.pc.arm.arm_set.set = AsyncMock(side_effect=mock_arm)
    zebra.pc.arm.disarm_set.set = AsyncMock(side_effect=mock_disarm)
    return zebra


@pytest.fixture
def detector_stage(RE):
    detector_motion = i24.detector_motion(fake_with_ophyd_sim=True)

    with patch_motor(detector_motion.y), patch_motor(detector_motion.z):
        yield detector_motion


@pytest.fixture
def aperture(RE):
    aperture: Aperture = i24.aperture(fake_with_ophyd_sim=True)
    with patch_motor(aperture.x), patch_motor(aperture.y):
        yield aperture


@pytest.fixture
def backlight(RE) -> DualBacklight:
    backlight = i24.backlight(fake_with_ophyd_sim=True)
    return backlight


@pytest.fixture
def beamstop(RE):
    beamstop: Beamstop = i24.beamstop(fake_with_ophyd_sim=True)

    with (
        patch_motor(beamstop.x),
        patch_motor(beamstop.y),
        patch_motor(beamstop.z),
        patch_motor(beamstop.y_rotation),
    ):
        yield beamstop


@pytest.fixture
def pmac(RE):
    pmac: PMAC = i24.pmac(fake_with_ophyd_sim=True)
    with (
        patch_motor(pmac.x),
        patch_motor(pmac.y),
        patch_motor(pmac.z),
    ):
        yield pmac


@pytest.fixture
def dcm(RE) -> DCM:
    dcm = i24.dcm(fake_with_ophyd_sim=True)
    return dcm
