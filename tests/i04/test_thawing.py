from collections.abc import AsyncGenerator
from typing import Literal
from unittest.mock import ANY, MagicMock, call, patch

import pytest
from _pytest.python_api import ApproxBase
from bluesky.run_engine import RunEngine
from dodal.beamlines import i04
from dodal.devices.oav.oav_detector import OAV
from dodal.devices.oav.oav_to_redis_forwarder import OAVToRedisForwarder
from dodal.devices.smargon import Smargon
from dodal.devices.thawer import Thawer, ThawerStates
from ophyd.sim import NullStatus, instantiate_fake_device
from ophyd_async.core import (
    DeviceCollector,
    callback_on_mock_put,
    get_mock_put,
    set_mock_value,
)
from ophyd_async.epics.motion import Motor

from mx_bluesky.i04.thawing_plan import thaw, thaw_and_center

DISPLAY_CONFIGURATION = "tests/devices/unit_tests/test_display.configuration"
ZOOM_LEVELS_XML = "tests/devices/unit_tests/test_jCameraManZoomLevels.xml"


class MyException(Exception):
    pass


@pytest.fixture
def oav() -> OAV:
    oav: OAV = instantiate_fake_device(OAV, params=MagicMock())

    oav.zoom_controller.zrst.set("1.0x")

    oav.wait_for_connection()

    return oav


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
async def smargon(RE: RunEngine) -> AsyncGenerator[Smargon, None]:
    smargon = Smargon(name="smargon")
    await smargon.connect(mock=True)

    set_mock_value(smargon.omega.user_readback, 0.0)

    with patch_motor(smargon.omega):
        yield smargon


@pytest.fixture
async def thawer(RE: RunEngine) -> Thawer:
    return i04.thawer(fake_with_ophyd_sim=True)


@pytest.fixture
async def oav_forwarder(RE: RunEngine) -> OAVToRedisForwarder:
    with DeviceCollector(mock=True):
        oav_forwarder = OAVToRedisForwarder(
            "prefix", "host", "password", name="oav_to_redis_forwarder"
        )
    return oav_forwarder


def _do_thaw_and_confirm_cleanup(
    move_mock: MagicMock, smargon: Smargon, thawer: Thawer, do_thaw_func
):
    smargon.omega.set = move_mock
    set_mock_value(smargon.omega.velocity, initial_velocity := 10)
    smargon.omega.set = move_mock
    do_thaw_func()
    last_thawer_call = get_mock_put(thawer.control).call_args_list[-1]
    assert last_thawer_call == call(ThawerStates.OFF, wait=ANY, timeout=ANY)
    last_velocity_call = get_mock_put(smargon.omega.velocity).call_args_list[-1]
    assert last_velocity_call == call(initial_velocity, wait=ANY, timeout=ANY)


def test_given_thaw_succeeds_then_velocity_restored_and_thawer_turned_off(
    smargon: Smargon, thawer: Thawer, RE: RunEngine
):
    def do_thaw_func():
        RE(thaw(10, thawer=thawer, smargon=smargon))

    _do_thaw_and_confirm_cleanup(
        MagicMock(return_value=NullStatus()), smargon, thawer, do_thaw_func
    )


def test_given_moving_smargon_gives_error_then_velocity_restored_and_thawer_turned_off(
    smargon: Smargon, thawer: Thawer, RE: RunEngine
):
    def do_thaw_func():
        with pytest.raises(MyException):
            RE(thaw(10, thawer=thawer, smargon=smargon))

    _do_thaw_and_confirm_cleanup(
        MagicMock(side_effect=MyException()), smargon, thawer, do_thaw_func
    )


@pytest.mark.parametrize(
    "time, rotation, expected_speed",
    [
        (10, 360, 72),
        (3.5, 100, pytest.approx(57.142857)),
        (50, -100, 4),
    ],
)
def test_given_different_rotations_and_times_then_velocity_correct(
    smargon: Smargon,
    thawer: Thawer,
    time: float | Literal[10] | Literal[50],
    rotation: Literal[360] | Literal[100] | Literal[-100],
    expected_speed: ApproxBase | Literal[72] | Literal[4],
    RE: RunEngine,
):
    RE(thaw(time, rotation, thawer=thawer, smargon=smargon))
    first_velocity_call = get_mock_put(smargon.omega.velocity).call_args_list[0]
    assert first_velocity_call == call(expected_speed, wait=ANY, timeout=ANY)


@pytest.mark.parametrize(
    "start_pos, rotation, expected_end",
    [
        (0, 360, 360),
        (78, 100, 178),
        (0, -100, -100),
    ],
)
def test_given_different_rotations_then_motor_moved_relative(
    smargon: Smargon,
    thawer: Thawer,
    start_pos: Literal[0] | Literal[78],
    rotation: Literal[360] | Literal[100] | Literal[-100],
    expected_end: Literal[360] | Literal[178] | Literal[-100],
    RE: RunEngine,
):
    set_mock_value(smargon.omega.user_readback, start_pos)
    RE(thaw(10, rotation, thawer=thawer, smargon=smargon))
    assert get_mock_put(smargon.omega.user_setpoint).call_args_list == [
        call(expected_end, wait=ANY, timeout=ANY),
        call(start_pos, wait=ANY, timeout=ANY),
    ]


@patch("mx_bluesky.i04.thawing_plan.MurkoCallback")
def test_thaw_and_centre_adds_murko_callback_and_produces_expected_messages(
    patch_murko_callback: MagicMock,
    smargon: Smargon,
    thawer: Thawer,
    oav_forwarder: OAVToRedisForwarder,
    oav: OAV,
    RE: RunEngine,
):
    patch_murko_instance = patch_murko_callback.return_value
    RE(
        thaw_and_center(
            10,
            360,
            thawer=thawer,
            smargon=smargon,
            oav=oav,
            robot=MagicMock(),
            oav_to_redis_forwarder=oav_forwarder,
        )
    )

    docs = patch_murko_instance.call_args_list
    start_params = [c.args[1] for c in docs if c.args[0] == "start"]
    event_params = [c.args[1] for c in docs if c.args[0] == "event"]
    assert len(start_params) == 1
    assert len(event_params) == 4
    oav_updates = [
        e for e in event_params if "oav_to_redis_forwarder-uuid" in e["data"].keys()
    ]
    smargon_updates = [e for e in event_params if "smargon-omega" in e["data"].keys()]
    assert len(oav_updates) > 0
    assert len(smargon_updates) > 0


@patch("mx_bluesky.i04.thawing_plan.MurkoCallback.call_murko")
def test_thaw_and_centre_will_produce_events_that_call_murko(
    patch_murko_call: MagicMock,
    smargon: Smargon,
    thawer: Thawer,
    oav_forwarder: OAVToRedisForwarder,
    oav: OAV,
    RE: RunEngine,
):
    RE(
        thaw_and_center(
            10,
            360,
            thawer=thawer,
            smargon=smargon,
            oav=oav,
            robot=MagicMock(),
            oav_to_redis_forwarder=oav_forwarder,
        )
    )
    patch_murko_call.assert_called()
