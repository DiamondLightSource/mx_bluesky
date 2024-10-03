from unittest.mock import MagicMock, call

import pytest
from bluesky import plan_stubs as bps
from dodal.beamlines import i03
from dodal.devices.zebra import (
    AUTO_SHUTTER_GATE,
    AUTO_SHUTTER_INPUT_1,
    IN1_TTL,
    IN3_TTL,
    IN4_TTL,
    PC_GATE,
    PC_PULSE,
    TTL_DETECTOR,
    TTL_PANDA,
    I03Axes,
    Zebra,
)
from dodal.devices.zebra_controlled_shutter import ZebraShutter

from mx_bluesky.hyperion.device_setup_plans.setup_zebra import (
    bluesky_retry,
    setup_zebra_for_gridscan,
    setup_zebra_for_panda_flyscan,
    setup_zebra_for_rotation,
    tidy_up_zebra_after_gridscan,
)


@pytest.fixture
def zebra(RE):
    return i03.zebra(fake_with_ophyd_sim=True)


@pytest.fixture
def zebra_shutter(RE):
    return i03.sample_shutter(fake_with_ophyd_sim=True)


async def _get_shutter_input(zebra: Zebra):
    return (
        await zebra.logic_gates.and_gates[AUTO_SHUTTER_GATE]
        .sources[AUTO_SHUTTER_INPUT_1]
        .get_value()
    )


async def test_zebra_set_up_for_panda_gridscan(
    RE, zebra: Zebra, zebra_shutter: ZebraShutter
):
    RE(setup_zebra_for_panda_flyscan(zebra, zebra_shutter, wait=True))
    assert await zebra.output.out_pvs[TTL_DETECTOR].get_value() == IN1_TTL
    assert await zebra.output.out_pvs[TTL_PANDA].get_value() == IN3_TTL
    assert await _get_shutter_input(zebra) == IN4_TTL


async def test_zebra_set_up_for_gridscan(RE, zebra: Zebra, zebra_shutter: ZebraShutter):
    RE(setup_zebra_for_gridscan(zebra, zebra_shutter, wait=True))
    assert await zebra.output.out_pvs[TTL_DETECTOR].get_value() == IN3_TTL
    assert await _get_shutter_input(zebra) == IN4_TTL


async def test_zebra_set_up_for_rotation(RE, zebra: Zebra, zebra_shutter: ZebraShutter):
    RE(setup_zebra_for_rotation(zebra, zebra_shutter, wait=True))
    assert await zebra.pc.gate_trigger.get_value() == I03Axes.OMEGA.value
    assert await zebra.pc.gate_width.get_value() == pytest.approx(360, 0.01)


async def test_zebra_cleanup(RE, zebra: Zebra, zebra_shutter: ZebraShutter):
    RE(tidy_up_zebra_after_gridscan(zebra, zebra_shutter, wait=True))
    assert await zebra.output.out_pvs[TTL_DETECTOR].get_value() == PC_PULSE
    assert await _get_shutter_input(zebra) == PC_GATE


class MyException(Exception):
    pass


def test_when_first_try_fails_then_bluesky_retry_tries_again(RE, done_status):
    mock_device = MagicMock()

    @bluesky_retry
    def my_plan(value):
        yield from bps.abs_set(mock_device, value)

    mock_device.set.side_effect = [MyException(), done_status]

    RE(my_plan(10))

    assert mock_device.set.mock_calls == [call(10), call(10)]


def test_when_all_tries_fail_then_bluesky_retry_throws_error(RE, done_status):
    mock_device = MagicMock()

    @bluesky_retry
    def my_plan(value):
        yield from bps.abs_set(mock_device, value)

    exception_2 = MyException()
    mock_device.set.side_effect = [MyException(), exception_2]

    with pytest.raises(MyException) as e:
        RE(my_plan(10))

    assert e.value == exception_2
