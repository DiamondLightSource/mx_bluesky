from unittest.mock import AsyncMock

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i24
from dodal.devices.hutch_shutter import HutchShutter, ShutterDemand, ShutterState
from dodal.devices.zebra import Zebra
from ophyd_async.core import callback_on_mock_put, set_mock_value


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
def shutter() -> HutchShutter:
    RunEngine()
    shutter = i24.shutter(fake_with_ophyd_sim=True)
    set_mock_value(shutter.interlock.status, 0)

    def set_status(value: ShutterDemand, *args, **kwargs):
        value_sta = ShutterState.OPEN if value == "Open" else ShutterState.CLOSED
        set_mock_value(shutter.status, value_sta)

    callback_on_mock_put(shutter.control, set_status)
    return shutter


@pytest.fixture
def RE():
    return RunEngine()
