from functools import partial
from typing import Generator
from unittest.mock import ANY, MagicMock, call, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i04
from dodal.devices.smargon import Smargon
from dodal.devices.thawer import Thawer, ThawerStates
from ophyd.epics_motor import EpicsMotor
from ophyd.sim import NullStatus
from ophyd.status import Status
from ophyd_async.core import get_mock_put

from mx_bluesky.i04.thawing_plan import thaw


class MyException(Exception):
    pass


def mock_set(motor: EpicsMotor, val):
    motor.user_setpoint.sim_put(val)  # type: ignore
    motor.user_readback.sim_put(val)  # type: ignore
    return Status(done=True, success=True)


def patch_motor(motor: EpicsMotor):
    return patch.object(motor, "set", MagicMock(side_effect=partial(mock_set, motor)))


@pytest.fixture
def smargon() -> Generator[Smargon, None, None]:
    smargon = i04.smargon(fake_with_ophyd_sim=True)
    smargon.omega.user_setpoint._use_limits = False
    smargon.omega.velocity._use_limits = False

    smargon.omega.user_readback.sim_put(0.0)  # type:ignore

    with (
        patch_motor(smargon.omega),
        patch.object(
            smargon.omega.velocity, "set", MagicMock(return_value=NullStatus())
        ),
    ):
        yield smargon


@pytest.fixture
async def thawer() -> Thawer:
    RunEngine()
    return i04.thawer(fake_with_ophyd_sim=True)


def _do_thaw_and_confirm_cleanup(
    move_mock: MagicMock, smargon: Smargon, thawer: Thawer, do_thaw_func
):
    smargon.omega.velocity.sim_put(initial_velocity := 10)  # type: ignore
    with patch.object(smargon.omega, "set", move_mock):
        do_thaw_func()
        last_thawer_call = get_mock_put(thawer.control).call_args_list[-1]
        assert last_thawer_call == call(ThawerStates.OFF, wait=ANY, timeout=ANY)
        last_velocity_call = smargon.omega.velocity.set.call_args_list[-1]
        assert last_velocity_call == call(initial_velocity)


def test_given_thaw_succeeds_then_velocity_restored_and_thawer_turned_off(
    smargon: Smargon, thawer: Thawer
):
    def do_thaw_func():
        RE = RunEngine()
        RE(thaw(10, thawer=thawer, smargon=smargon))

    _do_thaw_and_confirm_cleanup(
        MagicMock(return_value=NullStatus()), smargon, thawer, do_thaw_func
    )


def test_given_moving_smargon_gives_error_then_velocity_restored_and_thawer_turned_off(
    smargon: Smargon, thawer: Thawer
):
    def do_thaw_func():
        RE = RunEngine()
        with pytest.raises(MyException):
            RE(thaw(10, thawer=thawer, smargon=smargon))

    _do_thaw_and_confirm_cleanup(
        MagicMock(side_effect=MyException()), smargon, thawer, do_thaw_func
    )


@pytest.mark.parametrize(
    "time, rotation, expected_speed",
    [
        (10, 360, 36),
        (3.5, 100, pytest.approx(28.5714285)),
        (50, -100, 2),
    ],
)
def test_given_different_rotations_and_times_then_velocity_correct(
    smargon: Smargon, thawer: Thawer, time, rotation, expected_speed
):
    RE = RunEngine()
    RE(thaw(time, rotation, thawer=thawer, smargon=smargon))
    first_velocity_call = smargon.omega.velocity.set.call_args_list[0]
    assert first_velocity_call == call(expected_speed)


@pytest.mark.parametrize(
    "start_pos, rotation, expected_end",
    [
        (0, 360, 360),
        (78, 100, 178),
        (0, -100, -100),
    ],
)
def test_given_different_rotations_then_motor_moved_relative(
    smargon: Smargon, thawer: Thawer, start_pos, rotation, expected_end
):
    smargon.omega.user_readback.sim_put(start_pos)  # type: ignore
    RE = RunEngine()
    RE(thaw(10, rotation, thawer=thawer, smargon=smargon))
    smargon.omega.set.assert_called_once_with(expected_end)
