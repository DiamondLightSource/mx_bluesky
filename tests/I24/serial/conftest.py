from functools import partial
from unittest.mock import AsyncMock, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i24
from dodal.devices.i24.pmac import PMAC
from dodal.devices.zebra import Zebra


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
def pmac() -> PMAC:
    RunEngine()
    pmac = i24.pmac(fake_with_ophyd_sim=True)

    async def mock_set(motor, val):
        await motor._backend.put(val)

    def patch_motor(motor):
        return patch.object(motor, "set", partial(mock_set, motor))

    with (
        patch_motor(pmac.stages.x),
        patch_motor(pmac.stages.y),
        patch_motor(pmac.stages.z),
    ):
        return pmac


@pytest.fixture
def RE():
    return RunEngine()
