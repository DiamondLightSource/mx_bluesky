from unittest.mock import patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.zebra import I24Axes, Zebra

from mx_bluesky.i24.jungfrau_commissioning.plans.zebra_plans import (
    setup_zebra_for_rotation,
)


@pytest.fixture
def RE():
    return RunEngine({})


@pytest.fixture
def zebra():
    return i03.zebra(fake_with_ophyd_sim=True)


@patch("bluesky.plan_stubs.wait")
async def test_zebra_set_up_for_rotation(bps_wait, RE, zebra: Zebra):
    RE(setup_zebra_for_rotation(zebra, wait=True))
    assert await zebra.pc.gate_trigger.get_value() == I24Axes.OMEGA.value
    assert await zebra.pc.gate_width.get_value() == pytest.approx(360, 0.01)
