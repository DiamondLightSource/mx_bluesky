from functools import partial
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from bluesky.plan_stubs import null
from bluesky.run_engine import RunEngine, RunEngineResult
from dodal.devices.oav.oav_detector import OAV, OAVConfigParams
from dodal.devices.oav.pin_image_recognition import PinTipDetection
from dodal.devices.oav.pin_image_recognition.utils import SampleLocation
from dodal.devices.smargon import Smargon
from ophyd.sim import NullStatus
from ophyd_async.core import get_mock_put, set_mock_value

from mx_bluesky.hyperion.device_setup_plans.smargon import (
    move_smargon_warn_on_out_of_range,
)
from mx_bluesky.hyperion.exceptions import WarningException
from mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan import (
    DEFAULT_STEP_SIZE,
    PinTipCentringComposite,
    move_pin_into_view,
    pin_tip_centre_plan,
    trigger_and_return_pin_tip,
)


def get_fake_pin_values_generator(x, y):
    yield from null()
    return x, y


FAKE_EDGE_ARRAYS = np.ndarray([1, 2, 3]), np.ndarray([3, 4, 5])


@pytest.fixture
def mock_pin_tip(pin_tip: PinTipDetection):
    pin_tip._get_tip_and_edge_data = AsyncMock(return_value=pin_tip.INVALID_POSITION)
    return pin_tip


@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.bps.sleep",
    new=MagicMock(),
)
async def test_given_the_pin_tip_is_already_in_view_when_get_tip_into_view_then_tip_returned_and_smargon_not_moved(
    smargon: Smargon, oav: OAV, RE: RunEngine, mock_pin_tip: PinTipDetection
):
    set_mock_value(smargon.x.user_readback, 0)
    await mock_pin_tip.triggered_tip._backend.put((100, 200))  # type: ignore

    mock_pin_tip.trigger = MagicMock(return_value=NullStatus())

    result = RE(move_pin_into_view(mock_pin_tip, smargon))

    mock_pin_tip.trigger.assert_called_once()
    assert await smargon.x.user_readback.get_value() == 0
    assert isinstance(result, RunEngineResult)
    assert result.plan_result == (100, 200)


@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.bps.sleep",
    new=MagicMock(),
)
async def test_given_no_tip_found_but_will_be_found_when_get_tip_into_view_then_smargon_moved_positive_and_tip_returned(
    smargon: Smargon, oav: OAV, RE: RunEngine, mock_pin_tip: PinTipDetection
):
    set_mock_value(mock_pin_tip.validity_timeout, 0.015)
    set_mock_value(smargon.x.user_readback, 0)

    def set_pin_tip_when_x_moved(f, *args, **kwargs):
        mock_pin_tip._get_tip_and_edge_data.return_value = SampleLocation(  # type: ignore
            100, 200, *FAKE_EDGE_ARRAYS
        )
        return f(*args, **kwargs)

    x_user_setpoint = get_mock_put(smargon.x.user_setpoint)
    x_user_setpoint.side_effect = partial(
        set_pin_tip_when_x_moved, x_user_setpoint.side_effect
    )

    result = RE(move_pin_into_view(mock_pin_tip, smargon))

    assert await smargon.x.user_readback.get_value() == DEFAULT_STEP_SIZE
    assert isinstance(result, RunEngineResult)
    assert result.plan_result == (100, 200)


@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.bps.sleep",
    new=MagicMock(),
)
async def test_given_tip_at_zero_but_will_be_found_when_get_tip_into_view_then_smargon_moved_negative_and_tip_returned(
    smargon: Smargon, oav: OAV, RE: RunEngine, mock_pin_tip: PinTipDetection
):
    mock_pin_tip._get_tip_and_edge_data.return_value = SampleLocation(  # type: ignore
        0, 100, *FAKE_EDGE_ARRAYS
    )
    set_mock_value(mock_pin_tip.validity_timeout, 0.15)

    set_mock_value(smargon.x.user_readback, 0)

    def set_pin_tip_when_x_moved(f, *args, **kwargs):
        mock_pin_tip._get_tip_and_edge_data.return_value = SampleLocation(  # type: ignore
            100, 200, *FAKE_EDGE_ARRAYS
        )
        return f(*args, **kwargs)

    x_user_setpoint = get_mock_put(smargon.x.user_setpoint)
    x_user_setpoint.side_effect = partial(
        set_pin_tip_when_x_moved, x_user_setpoint.side_effect
    )

    result = RE(move_pin_into_view(mock_pin_tip, smargon))

    assert await smargon.x.user_readback.get_value() == -DEFAULT_STEP_SIZE
    assert result.plan_result == (100, 200)  # type: ignore


async def test_trigger_and_return_pin_tip_works_for_AD_pin_tip_detection(
    oav: OAV, RE: RunEngine, mock_pin_tip: PinTipDetection
):
    mock_pin_tip._get_tip_and_edge_data.return_value = SampleLocation(  # type: ignore
        200, 100, *FAKE_EDGE_ARRAYS
    )
    set_mock_value(mock_pin_tip.validity_timeout, 0.15)
    re_result = RE(trigger_and_return_pin_tip(mock_pin_tip))
    assert re_result.plan_result == (200, 100)  # type: ignore


def test_trigger_and_return_pin_tip_works_for_ophyd_pin_tip_detection(
    ophyd_pin_tip_detection: PinTipDetection, RE: RunEngine
):
    mock_trigger_result = SampleLocation(100, 200, np.array([]), np.array([]))
    ophyd_pin_tip_detection._get_tip_and_edge_data = AsyncMock(
        return_value=mock_trigger_result
    )
    re_result = RE(trigger_and_return_pin_tip(ophyd_pin_tip_detection))
    assert re_result.plan_result == (100, 200)  # type: ignore


@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.trigger_and_return_pin_tip"
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.bps.sleep",
    new=MagicMock(),
)
async def test_pin_tip_starting_near_negative_edge_doesnt_exceed_limit(
    mock_trigger_and_return_tip: MagicMock,
    smargon: Smargon,
    oav: OAV,
    RE: RunEngine,
    pin_tip: PinTipDetection,
):
    mock_trigger_and_return_tip.side_effect = [
        get_fake_pin_values_generator(0, 100),
        get_fake_pin_values_generator(0, 100),
    ]

    set_mock_value(smargon.x.user_setpoint, -1.8)
    set_mock_value(smargon.x.user_readback, -1.8)

    with pytest.raises(WarningException):
        RE(move_pin_into_view(pin_tip, smargon, max_steps=1))

    assert await smargon.x.user_readback.get_value() == -2


@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.trigger_and_return_pin_tip"
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.bps.sleep",
    new=MagicMock(),
)
async def test_pin_tip_starting_near_positive_edge_doesnt_exceed_limit(
    mock_trigger_and_return_pin_tip: MagicMock,
    smargon: Smargon,
    oav: OAV,
    RE: RunEngine,
    pin_tip: PinTipDetection,
):
    mock_trigger_and_return_pin_tip.side_effect = [
        get_fake_pin_values_generator(None, None),
        get_fake_pin_values_generator(None, None),
    ]
    set_mock_value(smargon.x.user_setpoint, 1.8)
    set_mock_value(smargon.x.user_readback, 1.8)

    with pytest.raises(WarningException):
        RE(move_pin_into_view(pin_tip, smargon, max_steps=1))

    assert await smargon.x.user_readback.get_value() == 2


@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.bps.sleep",
    new=MagicMock(),
)
async def test_given_no_tip_found_ever_when_get_tip_into_view_then_smargon_moved_positive_and_exception_thrown(
    smargon: Smargon, oav: OAV, RE: RunEngine, pin_tip: PinTipDetection
):
    set_mock_value(pin_tip.triggered_tip, pin_tip.INVALID_POSITION)
    set_mock_value(pin_tip.validity_timeout, 0.01)

    set_mock_value(smargon.x.user_readback, 0)

    with pytest.raises(WarningException):
        RE(move_pin_into_view(pin_tip, smargon))

    assert await smargon.x.user_readback.get_value() == 1


def test_given_moving_out_of_range_when_move_with_warn_called_then_warning_exception(
    RE: RunEngine, smargon: Smargon
):
    set_mock_value(smargon.x.high_limit_travel, 10)

    with pytest.raises(WarningException):
        RE(move_smargon_warn_on_out_of_range(smargon, (100, 0, 0)))


def return_pixel(pixel, *args):
    yield from null()
    return pixel


@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.wait_for_tip_to_be_found",
    new=partial(return_pixel, (200, 200)),
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.get_move_required_so_that_beam_is_at_pixel",
    autospec=True,
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.move_pin_into_view",
    new=partial(return_pixel, (100, 100)),
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.pre_centring_setup_oav",
    autospec=True,
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.bps.sleep",
    autospec=True,
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.move_smargon_warn_on_out_of_range",
    autospec=True,
)
async def test_when_pin_tip_centre_plan_called_then_expected_plans_called(
    move_smargon,
    mock_sleep,
    mock_setup_oav,
    get_move: MagicMock,
    smargon: Smargon,
    test_config_files: dict[str, str],
    RE: RunEngine,
):
    set_mock_value(smargon.omega.user_readback, 0)
    mock_oav: OAV = MagicMock(spec=OAV)
    mock_oav.parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    mock_oav.parameters.micronsPerXPixel = 2.87
    mock_oav.parameters.micronsPerYPixel = 2.87
    composite = PinTipCentringComposite(
        backlight=MagicMock(),
        oav=mock_oav,
        smargon=smargon,
        pin_tip_detection=MagicMock(),
    )
    RE(pin_tip_centre_plan(composite, 50, test_config_files["oav_config_json"]))

    assert mock_setup_oav.call_count == 1

    assert len(get_move.call_args_list) == 2

    args, _ = get_move.call_args_list[0]
    assert args[1] == (117, 100)

    assert await smargon.omega.user_readback.get_value() == 90

    args, _ = get_move.call_args_list[1]
    assert args[1] == (217, 200)


@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.wait_for_tip_to_be_found",
    new=partial(return_pixel, (200, 200)),
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.get_move_required_so_that_beam_is_at_pixel",
    autospec=True,
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.move_pin_into_view",
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.pre_centring_setup_oav",
    autospec=True,
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.bps.sleep",
    autospec=True,
)
@patch(
    "mx_bluesky.hyperion.experiment_plans.pin_tip_centring_plan.move_smargon_warn_on_out_of_range",
    autospec=True,
)
def test_given_pin_tip_detect_using_ophyd_when_pin_tip_centre_plan_called_then_expected_plans_called(
    move_smargon,
    mock_sleep,
    mock_setup_oav,
    mock_move_into_view,
    get_move: MagicMock,
    smargon: Smargon,
    oav: OAV,
    test_config_files: dict[str, str],
    RE: RunEngine,
):
    set_mock_value(smargon.omega.user_readback, 0)
    mock_ophyd_pin_tip_detection = MagicMock()
    composite = PinTipCentringComposite(
        backlight=MagicMock(),
        oav=oav,
        smargon=smargon,
        pin_tip_detection=mock_ophyd_pin_tip_detection,
    )
    mock_move_into_view.side_effect = partial(return_pixel, (100, 100))
    RE(pin_tip_centre_plan(composite, 50, test_config_files["oav_config_json"]))

    mock_move_into_view.assert_called_once_with(mock_ophyd_pin_tip_detection, smargon)

    assert mock_setup_oav.call_count == 1
