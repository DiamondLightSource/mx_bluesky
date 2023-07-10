from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.attenuator import Attenuator
from dodal.devices.sample_shutter import SampleShutter
from dodal.devices.xspress3_mini.xspress3_mini import Xspress3Mini
from ophyd.status import Status

from artemis.experiment_plans import optimise_attenuation_plan
from artemis.experiment_plans.optimise_attenuation_plan import (
    AttenuationOptimisationFailedException,
    Direction,
    arm_devices,
    calculate_new_direction,
    check_parameters,
    create_devices,
    deadtime_calc_new_transmission,
    deadtime_optimisation,
    is_counts_within_target,
    is_deadtime_optimised,
    total_counts_optimisation,
)
from artemis.log import LOGGER


def fake_create_devices() -> tuple[SampleShutter, Xspress3Mini, Attenuator]:
    sample_shutter = i03.sample_shutter(fake_with_ophyd_sim=True)
    sample_shutter.wait_for_connection()
    xspress3mini = i03.xspress3mini(fake_with_ophyd_sim=True)
    xspress3mini.wait_for_connection()
    attenuator = i03.attenuator(fake_with_ophyd_sim=True)
    attenuator.wait_for_connection()
    return sample_shutter, xspress3mini, attenuator


"""Default params:
default_low_roi = 100
default_high_roi = 2048
increment = 2
lower_lim = 20000
upper_lim = 50000
transmission = 0.1

Produce an array with 1000 values between 0-1 * (1+transmission)
"""
CALCULATED_VALUE = 0


def get_good_status():
    status = Status()
    status.set_finished()
    return status


def test_is_deadtime_optimised_returns_true_once_direction_is_flipped_and_deadtime_goes_back_above_threshold():
    pass


def test_is_deadtime_is_optimised_logs_warning_when_upper_transmission_limit_is_reached():
    LOGGER.warning = MagicMock()
    is_deadtime_optimised(0.5, 0.4, 0.9, 0.9, Direction.POSITIVE)
    LOGGER.warning.assert_called_once()


def test_total_counts_calc_new_transmission_raises_warning_on_high_transmission(
    RE: RunEngine,
):
    sample_shutter, xspress3mini, attenuator = fake_create_devices()
    sample_shutter.set = MagicMock(return_value=get_good_status())
    xspress3mini.do_arm.set = MagicMock(return_value=get_good_status())
    xspress3mini.dt_corrected_latest_mca.sim_put([1, 1, 1, 1, 1, 1])
    LOGGER.warning = MagicMock()
    RE(
        total_counts_optimisation(
            attenuator,
            xspress3mini,
            sample_shutter,
            transmission=0.1,
            low_roi=0,
            high_roi=1,
            lower_count_limit=0,
            upper_count_limit=0.1,
            target_count=1,
            max_cycles=1,
            upper_transmission_limit=0.1,
            lower_transmission_limit=0,
        )
    )
    LOGGER.warning.assert_called_once()


@pytest.mark.parametrize(
    "old_direction, deadtime, deadtime_threshold, new_direction",
    [
        (Direction.POSITIVE, 0.1, 0.9, Direction.POSITIVE),
        (Direction.NEGATIVE, 0.5, 0.4, Direction.NEGATIVE),
    ],
)
def test_calculate_new_direction_gives_correct_value(
    old_direction, deadtime, deadtime_threshold, new_direction
):
    assert (
        calculate_new_direction(old_direction, deadtime, deadtime_threshold)
        == new_direction
    )


@patch(
    "artemis.experiment_plans.optimise_attenuation_plan.do_device_optimise_iteration"
)
def test_deadtime_optimisation_calculates_deadtime_correctly(
    mock_do_device_optimise_iteration, RE: RunEngine
):
    sample_shutter, xspress3mini, attenuator = fake_create_devices()

    xspress3mini.channel_1.total_time.sim_put(100)
    xspress3mini.channel_1.reset_ticks.sim_put(101)
    is_deadtime_optimised.return_value = True

    with patch(
        "artemis.experiment_plans.optimise_attenuation_plan.is_deadtime_optimised"
    ) as mock_is_deadtime_optimised:
        RE(
            deadtime_optimisation(
                attenuator,
                xspress3mini,
                sample_shutter,
                0.5,
                2,
                0.01,
                1,
                0.1,
                1e-6,
            )
        )
        mock_is_deadtime_optimised.assert_called_with(
            0.99, 0.01, 0.5, 0.1, Direction.POSITIVE
        )


@pytest.mark.parametrize(
    "target, upper_limit, lower_limit, default_high_roi, default_low_roi,initial_transmission,upper_transmission,lower_transmission",
    [
        (100, 90, 110, 1, 0, 0.5, 1, 0),
        (50, 100, 20, 10, 20, 0.5, 1, 0),
        (100, 100, 101, 10, 1, 0.5, 1, 0),
        (10, 100, 0, 2, 1, 0.5, 0, 1),
        (10, 100, 0, 2, 1, 0.5, 0.4, 0.1),
    ],
)
def test_check_parameters_fail_on_out_of_range_parameters(
    target,
    upper_limit,
    lower_limit,
    default_high_roi,
    default_low_roi,
    initial_transmission,
    upper_transmission,
    lower_transmission,
):
    with pytest.raises(ValueError):
        check_parameters(
            target,
            upper_limit,
            lower_limit,
            default_high_roi,
            default_low_roi,
            initial_transmission,
            upper_transmission,
            lower_transmission,
        )


def test_check_parameters_runs_on_correct_params():
    assert check_parameters(10, 100, 0, 2, 1, 0.5, 1, 0) is None


@pytest.mark.parametrize(
    "total_count, lower_limit, upper_limit",
    [(100, 99, 100), (100, 100, 100), (50, 25, 1000)],
)
def test_is_counts_within_target_is_true(total_count, lower_limit, upper_limit):
    assert is_counts_within_target(total_count, lower_limit, upper_limit) is True


@pytest.mark.parametrize(
    "total_count, lower_limit, upper_limit",
    [(100, 101, 101), (0, 1, 2), (1000, 2000, 3000)],
)
def test_is_counts_within_target_is_false(total_count, lower_limit, upper_limit):
    assert is_counts_within_target(total_count, lower_limit, upper_limit) is False


def test_total_count_exception_raised_after_max_cycles_reached(RE: RunEngine):
    sample_shutter, xspress3mini, attenuator = fake_create_devices()
    sample_shutter.set = MagicMock(return_value=get_good_status())
    optimise_attenuation_plan.is_counts_within_target = MagicMock(return_value=False)
    xspress3mini.arm = MagicMock(return_value=get_good_status())
    xspress3mini.dt_corrected_latest_mca.sim_put([1, 1, 1, 1, 1, 1])
    with pytest.raises(AttenuationOptimisationFailedException):
        RE(
            total_counts_optimisation(
                attenuator, xspress3mini, sample_shutter, 1, 0, 10, 0, 5, 2, 1, 0, 0
            )
        )


def test_arm_devices_runs_correct_functions(RE: RunEngine):
    sample_shutter, xspress3mini, _ = fake_create_devices()
    xspress3mini.detector_state.sim_put("Acquire")
    xspress3mini.arm = MagicMock(return_value=get_good_status())
    RE(arm_devices(xspress3mini))
    xspress3mini.arm.assert_called_once()


@pytest.mark.parametrize(
    "direction, transmission, increment, upper_limit, lower_limit, new_transmission",
    [
        (Direction.POSITIVE, 0.5, 2, 0.9, 1e-6, 0.9),
        (Direction.POSITIVE, 0.1, 2, 0.9, 1e-6, 0.2),
        (Direction.NEGATIVE, 0.8, 2, 0.9, 1e-6, 0.4),
    ],
)
def test_deadtime_calc_new_transmission_gets_correct_value(
    direction, transmission, increment, upper_limit, lower_limit, new_transmission
):
    assert (
        deadtime_calc_new_transmission(
            direction, transmission, increment, upper_limit, lower_limit
        )
        == new_transmission
    )


def test_deadtime_calc_new_transmission_raises_error_on_low_ransmission():
    with pytest.raises(AttenuationOptimisationFailedException):
        deadtime_calc_new_transmission(Direction.NEGATIVE, 1e-6, 2, 1, 1e-6)


def test_total_count_calc_new_transmission_raises_error_on_low_ransmission(
    RE: RunEngine,
):
    sample_shutter, xspress3mini, attenuator = fake_create_devices()
    xspress3mini.dt_corrected_latest_mca.sim_put([1, 1, 1, 1, 1, 1])
    sample_shutter.set = MagicMock(return_value=get_good_status())
    xspress3mini.do_arm.set = MagicMock(return_value=get_good_status())
    with pytest.raises(AttenuationOptimisationFailedException):
        RE(
            total_counts_optimisation(
                attenuator,
                xspress3mini,
                sample_shutter,
                1e-6,
                0,
                1,
                10,
                20,
                1,
                1,
                0.5,
                0.1,
            )
        )


def test_create_new_devices():
    with patch("artemis.experiment_plans.optimise_attenuation_plan.i03") as i03:
        create_devices()
        i03.sample_shutter.assert_called()
        i03.xspress3mini.assert_called()
        i03.attenuator.assert_called()
