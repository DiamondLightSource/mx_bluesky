from unittest.mock import MagicMock

import pytest
from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining
from dodal.devices.focusing_mirror import (
    FocusingMirrorWithStripes,
    MirrorStripe,
    MirrorVoltages,
)
from dodal.devices.undulator_dcm import UndulatorDCM
from ophyd_async.core import get_mock_put

from mx_bluesky.hyperion.device_setup_plans import dcm_pitch_roll_mirror_adjuster
from mx_bluesky.hyperion.device_setup_plans.dcm_pitch_roll_mirror_adjuster import (
    adjust_dcm_pitch_roll_vfm_from_lut,
    adjust_mirror_stripe,
)


def test_apply_and_wait_for_voltages_to_settle_happy_path(
    RE: RunEngine,
    mirror_voltages: MirrorVoltages,
    vfm: FocusingMirrorWithStripes,
):
    RE(
        dcm_pitch_roll_mirror_adjuster._apply_and_wait_for_voltages_to_settle(
            MirrorStripe.BARE, vfm, mirror_voltages
        )
    )

    for channel, expected_voltage in zip(
        mirror_voltages.vertical_voltages.values(),
        [140, 100, 70, 30, 30, -65, 24, 15],
        strict=False,
    ):
        channel.set.assert_called_once_with(expected_voltage)  # type: ignore


@pytest.mark.parametrize(
    "energy_kev, expected_stripe, first_voltage, last_voltage",
    [
        (6.999, MirrorStripe.BARE, 140, 15),
        (7.001, MirrorStripe.RHODIUM, 124, -46),
    ],
)
def test_adjust_mirror_stripe(
    RE: RunEngine,
    mirror_voltages: MirrorVoltages,
    vfm: FocusingMirrorWithStripes,
    energy_kev,
    expected_stripe,
    first_voltage,
    last_voltage,
):
    parent = MagicMock()
    parent.attach_mock(get_mock_put(vfm.stripe), "stripe_set")
    parent.attach_mock(get_mock_put(vfm.apply_stripe), "apply_stripe")

    RE(adjust_mirror_stripe(energy_kev, vfm, mirror_voltages))

    assert parent.method_calls[0][0] == "stripe_set"
    assert parent.method_calls[0][1] == (expected_stripe,)
    assert parent.method_calls[1][0] == "apply_stripe"
    mirror_voltages.vertical_voltages[0].set.assert_called_once_with(  # type: ignore
        first_voltage
    )
    mirror_voltages.vertical_voltages[7].set.assert_called_once_with(  # type: ignore
        last_voltage
    )


def test_adjust_dcm_pitch_roll_vfm_from_lut(
    undulator_dcm: UndulatorDCM,
    vfm: FocusingMirrorWithStripes,
    mirror_voltages: MirrorVoltages,
    sim_run_engine: RunEngineSimulator,
):
    sim_run_engine.add_handler_for_callback_subscribes()
    sim_run_engine.add_handler(
        "read",
        lambda msg: {"dcm-bragg_in_degrees": {"value": 5.0}},
        "dcm-bragg_in_degrees",
    )

    messages = sim_run_engine.simulate_plan(
        adjust_dcm_pitch_roll_vfm_from_lut(undulator_dcm, vfm, mirror_voltages, 7.5)
    )

    messages = assert_message_and_return_remaining(
        messages,
        lambda msg: msg.command == "set"
        and msg.obj.name == "dcm-pitch_in_mrad"
        and abs(msg.args[0] - -0.75859) < 1e-5
        and msg.kwargs["group"] == "DCM_GROUP",
    )
    messages = assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "dcm-roll_in_mrad"
        and abs(msg.args[0] - 4.0) < 1e-5
        and msg.kwargs["group"] == "DCM_GROUP",
    )
    messages = assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "dcm-offset_in_mm"
        and msg.args == (25.6,)
        and msg.kwargs["group"] == "DCM_GROUP",
    )
    messages = assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "vfm-stripe"
        and msg.args == (MirrorStripe.RHODIUM,),
    )
    messages = assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "wait",
    )
    messages = assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "trigger" and msg.obj.name == "vfm-apply_stripe",
    )
    for channel, expected_voltage in (
        (0, 124),
        (1, 114),
        (2, 34),
        (3, 49),
        (4, 19),
        (5, -116),
        (6, 4),
        (7, -46),
    ):
        messages = assert_message_and_return_remaining(
            messages[1:],
            lambda msg: msg.command == "set"
            and msg.obj.name == f"mirror_voltages-vertical_voltages-{channel}"
            and msg.args == (expected_voltage,),
        )
    messages = assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "wait" and msg.kwargs["group"] == "DCM_GROUP",
    )
    messages = assert_message_and_return_remaining(
        messages[1:],
        lambda msg: msg.command == "set"
        and msg.obj.name == "vfm-x_mm"
        and msg.args == (10.0,),
    )
